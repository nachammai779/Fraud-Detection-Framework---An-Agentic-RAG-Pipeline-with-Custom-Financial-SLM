"""
Merge graph features with tabular features locally (outside Docker).

Reads:
  - Kaggle-IEEE-dataset/train_transaction.csv
  - Kaggle-IEEE-dataset/train_identity.csv
  - data/processed/graph_features.parquet

Outputs:
  - data/processed/feature_matrix.parquet
"""

import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "Kaggle-IEEE-dataset")
PROCESSED_DIR = os.path.join(ROOT, "data", "processed")


def main():
    print("Loading graph features...")
    graph_df = pd.read_parquet(os.path.join(PROCESSED_DIR, "graph_features.parquet"))
    print(f"  Graph features: {graph_df.shape}")

    print("Loading transaction CSV...")
    tx_df = pd.read_csv(os.path.join(DATA_DIR, "train_transaction.csv"))
    print(f"  Transactions: {tx_df.shape}")

    print("Loading identity CSV...")
    id_df = pd.read_csv(os.path.join(DATA_DIR, "train_identity.csv"))
    print(f"  Identity: {id_df.shape}")

    print("Merging transaction + identity...")
    df = tx_df.merge(id_df, on="TransactionID", how="left")
    del tx_df, id_df
    print(f"  Merged: {df.shape}")

    # Drop high-missing columns (>90%)
    missing_pct = df.isnull().mean()
    cols_to_drop = missing_pct[missing_pct > 0.9].index.tolist()
    cols_to_drop = [c for c in cols_to_drop if c not in ("isFraud", "TransactionID")]
    df.drop(columns=cols_to_drop, inplace=True)
    print(f"  Dropped {len(cols_to_drop)} high-missing cols -> {df.shape[1]} remaining")

    # Feature engineering (same as training pipeline)
    df["TransactionHour"] = (df["TransactionDT"] // 3600) % 24
    df["TransactionDayOfWeek"] = (df["TransactionDT"] // (3600 * 24)) % 7
    df["TransactionAmt_Log"] = np.log1p(df["TransactionAmt"])
    df["TransactionAmt_Decimal"] = (
        (df["TransactionAmt"] - df["TransactionAmt"].astype(int)) * 1000
    ).astype(int)
    df["TransactionAmt_IsRound"] = (
        df["TransactionAmt"] == df["TransactionAmt"].astype(int)
    ).astype(int)
    print(f"  Engineered features -> {df.shape}")

    # Merge graph features
    print("Merging graph features...")
    final_df = df.merge(graph_df, on="TransactionID", how="left")
    del df, graph_df
    print(f"  Merged shape: {final_df.shape}")

    print(f"  Final feature matrix: {final_df.shape}")

    # Summary of graph columns
    graph_cols = [c for c in final_df.columns if c in [
        "communityId", "pageRank",
        "communitySize", "communityFraudRate", "communityAvgAmount", "communityStdAmount",
        "cardDegree", "cardFraudRate", "numDevicesOnCard", "addressesPerCard",
        "neighborCardFraudRate", "neighborCardCount", "fraudOnSameCard",
        "addrDegree", "addrFraudRate", "numCardsAtAddress",
        "emailDegree", "emailFraudRate", "cardsPerEmail",
        "deviceDegree", "deviceFraudRate",
        "maxEntityFraudRate",
    ]]
    print(f"\nGraph features ({len(graph_cols)}):")
    for col in graph_cols:
        non_null = final_df[col].notna().sum()
        print(f"  {col:25s}  non-null: {non_null:>8,} / {len(final_df):,}")

    # Save
    out_path = os.path.join(PROCESSED_DIR, "feature_matrix.parquet")
    final_df.to_parquet(out_path, index=False)
    print(f"\nSaved: {out_path}")
    print(f"Size: {os.path.getsize(out_path) / 1e6:.1f} MB")
    print("Done.")


if __name__ == "__main__":
    main()