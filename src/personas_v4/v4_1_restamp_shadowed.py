"""
v4.1 — Re-stamp a subset of v4 fraud rows so shadowed FTA typology codes
appear in the dataset.

Context: the v4 resolver preferred SAR advisories over FTA codes when both
matched a fraud_vector. Result: 4 FTA codes (T4, T6, T9, T11) have 0 rows in
v4 even though rows with matching fraud_vectors exist (stamped with SAR codes
instead). This script re-stamps ~100 rows per shadowed code so all 4 codes
appear in the dataset, without new Adaption credits.

Default rate: 100 rows per shadowed code. Re-stamping picks rows uniformly at
random (seeded) from each code's matching pool; the rest keep their SAR stamp.

Writes back in place to datasets_v4/{archetype}/adaptive/transactions_adapted.parquet
and to datasets_v4/exports/transactions_v4_20k.{parquet,csv}. Prints before/after
code distributions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]
SEED = 42
PER_CODE = 100

# (shadowed FTA code, currently-stamped SAR code, fraud_vectors that map to it)
SHADOWED = [
    ("FTA_IDENTITY_2024_T11", "SAR_ADVISORY_BEC_FRAUD",
     ["bec", "eac", "vendor_email_compromise", "payroll_diversion"]),
    ("FTA_IDENTITY_2024_T6", "SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD",
     ["ato", "account_takeover", "credential_stuffing", "sim_swap"]),
    ("FTA_IDENTITY_2024_T9", "SAR_ADVISORY_CYBER_EVENTS",
     ["phishing", "malware", "data_breach"]),
    ("FTA_IDENTITY_2024_T4", "SAR_ADVISORY_COVID19_IMPOSTER_SCAMS",
     ["money_mule", "third_party_laundering"]),
]


def _load() -> dict[str, pd.DataFrame]:
    return {a: pd.read_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet") for a in ARCHETYPES}


def _save(frames: dict[str, pd.DataFrame]):
    for a, df in frames.items():
        df.to_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet", index=False, engine="pyarrow")
    # Rebuild bundle
    bundle = pd.concat(frames.values(), ignore_index=True)
    bp = V4 / "exports" / "transactions_v4_20k.parquet"
    bc = V4 / "exports" / "transactions_v4_20k.csv"
    if bp.exists():
        # Preserve existing column order if the bundle was previously exported
        existing = pd.read_parquet(bp)
        cols = [c for c in existing.columns if c in bundle.columns] + \
               [c for c in bundle.columns if c not in existing.columns]
        bundle = bundle[cols]
    bundle.to_parquet(bp, index=False, engine="pyarrow")
    bundle.to_csv(bc, index=False)
    print(f"Bundle updated: {bp}")


def main():
    rng = np.random.default_rng(SEED)
    frames = _load()
    df = pd.concat(frames.values(), ignore_index=True)

    print("Before restamp — code counts (fraud rows only):")
    before = df[df["is_fraud"] == 1]["fraud_vector_typology_ref"].value_counts()
    print(before.to_string())
    print()

    # Build a key -> (archetype, original_index) map so we can write back.
    per_arch_index: dict[str, list[int]] = {a: f.index.tolist() for a, f in frames.items()}

    # Work directly on frames dict: mutate fraud_vector_typology_ref on sampled rows.
    restamp_counts = {}
    for fta, sar, vectors in SHADOWED:
        candidate_rows = []  # list of (archetype, row_index)
        for a, f in frames.items():
            mask = (
                (f["is_fraud"] == 1)
                & (f["fraud_vector"].astype(str).isin(vectors))
                & (f["fraud_vector_typology_ref"].astype(str) == sar)
            )
            candidate_rows.extend([(a, i) for i in f.index[mask]])

        # Leave at least half in the SAR stamp so the SAR code stays in the dataset.
        cap_to_preserve_sar = len(candidate_rows) // 2
        k = min(PER_CODE, cap_to_preserve_sar)
        if k == 0:
            print(f"[{fta}] too few candidates ({len(candidate_rows)}, sar={sar}) — skipping")
            continue
        pick_idx = rng.choice(len(candidate_rows), size=k, replace=False)
        picks = [candidate_rows[i] for i in pick_idx]
        for a, i in picks:
            frames[a].at[i, "fraud_vector_typology_ref"] = fta
        restamp_counts[fta] = k
        print(f"[{fta}] re-stamped {k} rows (was {sar})")

    _save(frames)

    df_after = pd.concat(frames.values(), ignore_index=True)
    print("\nAfter restamp — code counts (fraud rows only):")
    after = df_after[df_after["is_fraud"] == 1]["fraud_vector_typology_ref"].value_counts()
    print(after.to_string())

    n_codes_now = int(after.index.nunique())
    print(f"\nDistinct typology codes in fraud rows: {n_codes_now}  (was {before.index.nunique()})")
    print(f"Re-stamp summary: {restamp_counts}")


if __name__ == "__main__":
    main()