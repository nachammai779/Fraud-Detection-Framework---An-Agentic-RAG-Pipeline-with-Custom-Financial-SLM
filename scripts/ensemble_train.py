"""
NGBoost + LightGBM Stacked Ensemble
=====================================
1. Train NGBoost via 5-fold CV → generate OOF predictions + uncertainty
2. Augment feature matrix with NGBoost outputs (ngb_prob, ngb_variance, ngb_log_odds)
3. Train LightGBM on augmented features
4. Compare: LightGBM-only vs Ensemble AUC

Usage:
  python scripts/ensemble_train.py
"""

import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import KFold
from ngboost import NGBClassifier
from ngboost.distns import Bernoulli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURE_MATRIX_PATH = os.path.join(ROOT, "data", "processed", "feature_matrix.parquet")
MODEL_DIR = os.path.join(ROOT, "fraud-detection-pipeline", "model")

# NGBoost subsample per fold (for speed)
NGB_SUBSAMPLE = 120_000
NGB_ESTIMATORS = 500
NGB_EARLY_STOP = 50
N_FOLDS = 5


def main():
    print("=" * 60)
    print("ENSEMBLE: NGBoost + LightGBM Stacked Training")
    print("=" * 60)

    # ── 1. Load & Preprocess ────────────────────────────────────────────
    print("\n[1/4] Loading feature matrix...")
    df = pd.read_parquet(FEATURE_MATRIX_PATH)
    print(f"  Shape: {df.shape}")

    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    label_encoder_mappings = {}
    for col in cat_cols:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str))
        label_encoder_mappings[col] = {
            label: int(idx) for idx, label in enumerate(le.classes_)
        }

    target = "isFraud"
    drop_cols = ["TransactionID", "isFraud", "TransactionDT"]
    features = [c for c in df.columns if c not in drop_cols]

    # Time-based 80/20 split
    split_idx = int(len(df) * 0.8)
    X_all = df[features].values
    y_all = df[target].values
    X_train, X_val = X_all[:split_idx], X_all[split_idx:]
    y_train, y_val = y_all[:split_idx], y_all[split_idx:]

    # Fill NaN for NGBoost
    X_train_filled = np.nan_to_num(X_train, nan=-999)
    X_val_filled = np.nan_to_num(X_val, nan=-999)

    print(f"  Features: {len(features)}")
    print(f"  Train: {len(X_train):,} | Val: {len(X_val):,}")

    # ── 2. NGBoost 5-Fold OOF Predictions ───────────────────────────────
    print(f"\n[2/4] Training NGBoost ({N_FOLDS}-fold CV, {NGB_SUBSAMPLE:,} subsample/fold)...")

    oof_prob = np.zeros(len(X_train))
    oof_var = np.zeros(len(X_train))
    val_probs = np.zeros((N_FOLDS, len(X_val)))
    val_vars = np.zeros((N_FOLDS, len(X_val)))

    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

    for fold, (train_idx, oof_idx) in enumerate(kf.split(X_train_filled)):
        print(f"\n  Fold {fold + 1}/{N_FOLDS}:")
        X_fold_train = X_train_filled[train_idx]
        y_fold_train = y_train[train_idx]
        X_fold_oof = X_train_filled[oof_idx]

        # Subsample for speed
        if len(X_fold_train) > NGB_SUBSAMPLE:
            np.random.seed(42 + fold)
            sub_idx = np.random.choice(len(X_fold_train), size=NGB_SUBSAMPLE, replace=False)
            X_fold_train = X_fold_train[sub_idx]
            y_fold_train = y_fold_train[sub_idx]

        print(f"    Train: {len(X_fold_train):,} | OOF: {len(X_fold_oof):,}")

        ngb = NGBClassifier(
            Dist=Bernoulli,
            Base=DecisionTreeRegressor(max_depth=6, max_features=0.7, min_samples_leaf=50),
            n_estimators=NGB_ESTIMATORS,
            learning_rate=0.05,
            natural_gradient=True,
            verbose=False,
            random_state=42,
        )
        ngb.fit(
            X_fold_train, y_fold_train,
            X_val=X_fold_oof, Y_val=y_train[oof_idx],
            early_stopping_rounds=NGB_EARLY_STOP,
        )

        # OOF predictions
        oof_dist = ngb.pred_dist(X_fold_oof)
        oof_prob[oof_idx] = oof_dist.probs.flatten()
        oof_var[oof_idx] = oof_dist.probs.flatten() * (1 - oof_dist.probs.flatten())

        # Val predictions (average across folds)
        val_dist = ngb.pred_dist(X_val_filled)
        val_probs[fold] = val_dist.probs.flatten()
        val_vars[fold] = val_dist.probs.flatten() * (1 - val_dist.probs.flatten())

        fold_auc = roc_auc_score(y_train[oof_idx], oof_prob[oof_idx])
        print(f"    OOF AUC: {fold_auc:.6f}")

    # Average val predictions across folds
    val_prob_avg = val_probs.mean(axis=0)
    val_var_avg = val_vars.mean(axis=0)

    ngb_oof_auc = roc_auc_score(y_train, oof_prob)
    ngb_val_auc = roc_auc_score(y_val, val_prob_avg)
    print(f"\n  NGBoost OOF AUC: {ngb_oof_auc:.6f}")
    print(f"  NGBoost Val AUC: {ngb_val_auc:.6f}")

    # ── 3. Augment Features ─────────────────────────────────────────────
    print("\n[3/4] Augmenting features with NGBoost outputs...")

    # Compute log-odds (clip to avoid inf)
    eps = 1e-7
    oof_log_odds = np.log((oof_prob + eps) / (1 - oof_prob + eps))
    val_log_odds = np.log((val_prob_avg + eps) / (1 - val_prob_avg + eps))

    # Augmented train
    X_train_aug = np.column_stack([X_train, oof_prob, oof_var, oof_log_odds])
    X_val_aug = np.column_stack([X_val, val_prob_avg, val_var_avg, val_log_odds])

    features_aug = features + ["ngb_prob", "ngb_variance", "ngb_log_odds"]
    print(f"  Augmented features: {len(features_aug)} (was {len(features)})")

    # ── 4. Train LightGBM ──────────────────────────────────────────────
    print("\n[4/4] Training LightGBM...")

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

    # --- LightGBM only (baseline) ---
    print("\n  Training LightGBM (baseline, no NGBoost features)...")
    lgb_train_base = lgb.Dataset(X_train, y_train, feature_name=features)
    lgb_val_base = lgb.Dataset(X_val, y_val, reference=lgb_train_base, feature_name=features)
    model_base = lgb.train(
        params, lgb_train_base, num_boost_round=1000,
        valid_sets=[lgb_val_base], valid_names=["valid"],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    pred_base = model_base.predict(X_val, num_iteration=model_base.best_iteration)
    auc_base = roc_auc_score(y_val, pred_base)
    print(f"  LightGBM-only AUC: {auc_base:.6f} (iter {model_base.best_iteration})")

    # --- LightGBM + NGBoost features (ensemble) ---
    print("\n  Training LightGBM (ensemble, + NGBoost features)...")
    lgb_train_ens = lgb.Dataset(X_train_aug, y_train, feature_name=features_aug)
    lgb_val_ens = lgb.Dataset(X_val_aug, y_val, reference=lgb_train_ens, feature_name=features_aug)
    model_ens = lgb.train(
        params, lgb_train_ens, num_boost_round=1000,
        valid_sets=[lgb_val_ens], valid_names=["valid"],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    pred_ens = model_ens.predict(X_val_aug, num_iteration=model_ens.best_iteration)
    auc_ens = roc_auc_score(y_val, pred_ens)
    print(f"  Ensemble AUC:      {auc_ens:.6f} (iter {model_ens.best_iteration})")

    # ── Results ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  NGBoost alone:          {ngb_val_auc:.6f}")
    print(f"  LightGBM alone:         {auc_base:.6f}")
    print(f"  Ensemble (LGB + NGB):   {auc_ens:.6f}")
    print(f"  Improvement:            {auc_ens - auc_base:+.6f} ({(auc_ens - auc_base) / auc_base * 100:+.2f}%)")
    print("=" * 60)

    # NGBoost feature importances in ensemble model
    importances = dict(zip(
        model_ens.feature_name(),
        model_ens.feature_importance(importance_type="gain"),
    ))
    ngb_feats = ["ngb_prob", "ngb_variance", "ngb_log_odds"]
    print("\nNGBoost feature importances in ensemble:")
    for f in ngb_feats:
        print(f"  {f:20s} {importances.get(f, 0):>12.1f}")

    # Top 20 overall
    sorted_imp = sorted(importances.items(), key=lambda x: -x[1])
    print("\nTop 20 features (ensemble):")
    for feat, imp in sorted_imp[:20]:
        marker = " *" if feat in ngb_feats else ""
        print(f"  {feat:30s} {imp:>12.1f}{marker}")

    # Export if improved
    if auc_ens > auc_base:
        print("\nExporting ensemble model...")
        os.makedirs(MODEL_DIR, exist_ok=True)

        model_path = os.path.join(MODEL_DIR, "fraud_model.txt")
        model_ens.save_model(model_path)
        with open(model_path, "r") as f:
            content = f.read()
        with open(model_path, "w", newline="\n") as f:
            f.write(content)

        features_path = os.path.join(MODEL_DIR, "feature_names.json")
        with open(features_path, "w") as f:
            json.dump(features_aug, f, indent=2)

        encoders_path = os.path.join(MODEL_DIR, "label_encoders.json")
        with open(encoders_path, "w") as f:
            json.dump(label_encoder_mappings, f, indent=2)

        print(f"  Saved to {MODEL_DIR}")
    else:
        print("\nNo improvement — keeping original model.")


if __name__ == "__main__":
    main()
