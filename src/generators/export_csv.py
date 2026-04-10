"""
export_csv.py
=============
Exports all synthetic parquet files to CSV for viewing.

Usage:
    python export_csv.py
"""

import os
import pandas as pd

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
BASE_DIR = "datasets"


def export_all():
    for arch in ARCHETYPES:
        parquet_path = os.path.join(BASE_DIR, arch, "synthetic", "transactions.parquet")
        if not os.path.exists(parquet_path):
            print(f"  SKIP -- {parquet_path} not found")
            continue

        df = pd.read_parquet(parquet_path)
        csv_path = os.path.join(BASE_DIR, arch, "synthetic", f"transactions_{arch}.csv")
        df.to_csv(csv_path, index=False)
        print(f"  {arch}: {len(df)} records -> {csv_path}")


if __name__ == "__main__":
    print("Exporting parquet to CSV...")
    export_all()
    print("Done.")