"""
Model Training & Export Script
================================
Trains the LightGBM model using the same pipeline as the EDA notebook
and exports it as a .txt file for the Kafka consumer to load at runtime.

Usage:
  cd fraud-detection-pipeline/
  python scripts/train_and_export_model.py

Output:
  model/fraud_model.txt        — serialized LightGBM model
  model/feature_names.json     — ordered list of feature names
  model/label_encoders.json    — label encoder mappings for categorical cols
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "Kaggle-IEEE-dataset")
MODEL_DIR = os.path.join(PROJECT_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)


def main():
    print("=" * 60)
    print("FRAUD DETECTION — Model Training & Export")
    print("=" * 60)

    # ── 1. Load Data ─────────────────────────────────────────────────────
    print("\n[1/6] Loading data...")
    train_txn = pd.read_csv(os.path.join(DATA_DIR, "train_transaction.csv"))
    train_id = pd.read_csv(os.path.join(DATA_DIR, "train_identity.csv"))

    train = train_txn.merge(train_id, on="TransactionID", how="left")
    del train_txn, train_id

    print(f"  Train shape: {train.shape}")
    print(f"  Fraud rate:  {train['isFraud'].mean():.2%}")

    # ── 2. Drop High-Missing Columns ────────────────────────────────────
    print("\n[2/6] Dropping columns with >90% missing...")
    missing_pct = train.isnull().mean()
    cols_to_drop = missing_pct[missing_pct > 0.9].index.tolist()
    cols_to_drop = [c for c in cols_to_drop if c != "isFraud"]
    train.drop(columns=cols_to_drop, inplace=True)
    print(f"  Dropped {len(cols_to_drop)} columns → {train.shape[1]} remaining")

    # ── 3. Feature Engineering ───────────────────────────────────────────
    print("\n[3/6] Engineering features...")
    train["TransactionHour"] = (train["TransactionDT"] // 3600) % 24
    train["TransactionDayOfWeek"] = (train["TransactionDT"] // (3600 * 24)) % 7
    train["TransactionAmt_Log"] = np.log1p(train["TransactionAmt"])
    train["TransactionAmt_Decimal"] = (
        (train["TransactionAmt"] - train["TransactionAmt"].astype(int)) * 1000
    ).astype(int)
    train["TransactionAmt_IsRound"] = (
        train["TransactionAmt"] == train["TransactionAmt"].astype(int)
    ).astype(int)
    print("  Created: TransactionHour, TransactionDayOfWeek, TransactionAmt_Log, "
          "TransactionAmt_Decimal, TransactionAmt_IsRound")

    # ── 4. Encode Categoricals ───────────────────────────────────────────
    print("\n[4/6] Label encoding categoricals...")
    cat_cols = train.select_dtypes(include=["object"]).columns.tolist()
    label_encoder_mappings = {}

    for col in cat_cols:
        le = LabelEncoder()
        train[col] = le.fit_transform(train[col].astype(str))
        label_encoder_mappings[col] = {
            label: int(idx) for idx, label in enumerate(le.classes_)
        }

    print(f"  Encoded {len(cat_cols)} columns: {cat_cols}")

    # ── 5. Train LightGBM ───────────────────────────────────────────────
    print("\n[5/6] Training LightGBM...")
    target = "isFraud"
    drop_cols = ["TransactionID", "isFraud", "TransactionDT"]
    features = [c for c in train.columns if c not in drop_cols]

    X = train[features]
    y = train[target]

    # Time-based 80/20 split
    split_idx = int(len(train) * 0.8)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"  Features:    {len(features)}")
    print(f"  Train split: {len(X_train):,} | Val split: {len(X_val):,}")

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

    # Validation score
    y_val_pred = model.predict(X_val, num_iteration=model.best_iteration)
    val_auc = roc_auc_score(y_val, y_val_pred)
    print(f"\n  Best iteration:   {model.best_iteration}")
    print(f"  Validation AUC:   {val_auc:.6f}")

    # ── 6. Export Model ──────────────────────────────────────────────────
    print("\n[6/6] Exporting model artifacts...")

    model_path = os.path.join(MODEL_DIR, "fraud_model.txt")
    model.save_model(model_path)
    print(f"  Model saved:           {model_path}")

    features_path = os.path.join(MODEL_DIR, "feature_names.json")
    with open(features_path, "w") as f:
        json.dump(features, f, indent=2)
    print(f"  Feature names saved:   {features_path}")

    encoders_path = os.path.join(MODEL_DIR, "label_encoders.json")
    with open(encoders_path, "w") as f:
        json.dump(label_encoder_mappings, f, indent=2)
    print(f"  Label encoders saved:  {encoders_path}")

    print("\n" + "=" * 60)
    print("Model export complete. Ready for Docker deployment.")
    print("=" * 60)


if __name__ == "__main__":
    main()