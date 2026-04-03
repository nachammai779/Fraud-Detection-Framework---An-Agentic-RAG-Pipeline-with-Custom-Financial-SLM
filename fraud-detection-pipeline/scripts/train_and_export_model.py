"""
Model Training & Export Script (v2 — with graph features)
============================================================
Loads the merged feature matrix (tabular + graph), engineers derived
graph features, trains LightGBM, and exports model artifacts.

Usage:
  python fraud-detection-pipeline/scripts/train_and_export_model.py

Prerequisites:
  - data/processed/feature_matrix.parquet must exist
    (run: python scripts/merge_features.py)

Output:
  model/fraud_model.txt        — serialized LightGBM model
  model/feature_names.json     — ordered list of feature names
  model/label_encoders.json    — label encoder mappings for categorical cols
"""

import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ROOT_DIR = os.path.dirname(PROJECT_DIR)
FEATURE_MATRIX_PATH = os.path.join(ROOT_DIR, "data", "processed", "feature_matrix.parquet")
MODEL_DIR = os.path.join(PROJECT_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)


def engineer_derived_features(df):
    """No-op — graph features are used as-is from the feature matrix."""
    return df


def main():
    print("=" * 60)
    print("FRAUD DETECTION — Model Training & Export (v2)")
    print("=" * 60)

    # ── 1. Load Feature Matrix ──────────────────────────────────────────
    print("\n[1/6] Loading feature matrix...")
    if not os.path.exists(FEATURE_MATRIX_PATH):
        print(f"  ERROR: {FEATURE_MATRIX_PATH} not found.")
        print("  Run: python scripts/merge_features.py")
        return

    train = pd.read_parquet(FEATURE_MATRIX_PATH)
    print(f"  Shape: {train.shape}")
    print(f"  Fraud rate: {train['isFraud'].mean():.2%}")

    # ── 2. Engineer Derived Graph Features ──────────────────────────────
    print("\n[2/6] Engineering derived graph features...")
    train = engineer_derived_features(train)
    derived = []
    existing = [c for c in derived if c in train.columns]
    print(f"  Added: {existing}")
    print(f"  Shape: {train.shape}")

    # ── 3. Drop High-Missing & Encode Categoricals ──────────────────────
    print("\n[3/6] Preprocessing...")
    missing_pct = train.isnull().mean()
    cols_to_drop = missing_pct[missing_pct > 0.9].index.tolist()
    cols_to_drop = [c for c in cols_to_drop if c not in ("isFraud", "TransactionID")]
    train.drop(columns=cols_to_drop, inplace=True)
    print(f"  Dropped {len(cols_to_drop)} high-missing columns -> {train.shape[1]} remaining")

    cat_cols = train.select_dtypes(include=["object"]).columns.tolist()
    label_encoder_mappings = {}
    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        label_encoder_mappings[col] = {
            label: int(idx) for idx, label in enumerate(le.classes_)
        }
    print(f"  Encoded {len(cat_cols)} categorical columns")

    # ── 4. Prepare Features ─────────────────────────────────────────────
    print("\n[4/6] Preparing features...")
    target = "isFraud"
    drop_cols = ["TransactionID", "isFraud", "TransactionDT"]
    features = [c for c in train.columns if c not in drop_cols]

    X = train[features]
    y = train[target]

    # Time-based 80/20 split
    split_idx = int(len(train) * 0.8)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"  Total features: {len(features)}")
    print(f"  Train: {len(X_train):,} | Val: {len(X_val):,}")

    # ── 5. Train LightGBM ──────────────────────────────────────────────
    print("\n[5/6] Training LightGBM...")
    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "learning_rate": 0.05,
        "num_leaves": 256,
        "max_depth": -1,
        "min_child_samples": 50,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "n_jobs": -1,
        "verbose": -1,
        "is_unbalance": True,
        "random_state": 42,
    }

    lgb_train = lgb.Dataset(X_train, y_train)
    lgb_val = lgb.Dataset(X_val, y_val, reference=lgb_train)

    model = lgb.train(
        params,
        lgb_train,
        num_boost_round=1000,
        valid_sets=[lgb_train, lgb_val],
        valid_names=["train", "valid"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=100),
        ],
    )

    y_val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    val_auc = roc_auc_score(y_val, y_val_pred)

    print(f"\n  Best iteration:   {model.best_iteration}")
    print(f"  Validation AUC:   {val_auc:.6f}")
    print(f"\n  Baseline (tabular only):       0.914258")
    print(f"  Previous (tabular + graph):    0.942460")
    print(f"  Current  (+ derived features): {val_auc:.6f}")

    # Top feature importances
    importances = sorted(
        zip(model.feature_name(), model.feature_importance(importance_type="gain")),
        key=lambda x: -x[1],
    )
    print("\n  Top 20 features (gain):")
    for feat, imp in importances[:20]:
        marker = " *" if feat in derived else ""
        print(f"    {feat:30s} {imp:>12.1f}{marker}")

    # ── 6. Export Model ─────────────────────────────────────────────────
    print("\n[6/6] Exporting model artifacts...")

    model_path = os.path.join(MODEL_DIR, "fraud_model.txt")
    model.save_model(model_path)

    # Fix line endings for Linux compatibility
    with open(model_path, "r") as f:
        content = f.read()
    with open(model_path, "w", newline="\n") as f:
        f.write(content)
    print(f"  Model saved (LF):      {model_path}")

    features_path = os.path.join(MODEL_DIR, "feature_names.json")
    with open(features_path, "w") as f:
        json.dump(features, f, indent=2)
    print(f"  Feature names saved:   {features_path}")

    encoders_path = os.path.join(MODEL_DIR, "label_encoders.json")
    with open(encoders_path, "w") as f:
        json.dump(label_encoder_mappings, f, indent=2)
    print(f"  Label encoders saved:  {encoders_path}")

    print("\n" + "=" * 60)
    print(f"Training complete. AUC: {val_auc:.6f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
