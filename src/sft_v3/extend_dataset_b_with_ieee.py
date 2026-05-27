"""Merge IEEE-Adapted narratives into Dataset B for the Qwen distillation pool.

Reads:
  - data/sft_v3/dataset_b_qwen_input.parquet            (base pool)
  - datasets/ieee_for_adaption/{archetype}/transactions_ieee_adapted.parquet
    (Adaption Labs Pass-1 outputs from adaption_download_ieee.py)

Writes:
  - data/sft_v3/dataset_b_qwen_input_extended.parquet   (combined pool)

After this, point qwen_distill at the extended file:
    python -m src.sft_v3.qwen_distill \
        --input data/sft_v3/dataset_b_qwen_input_extended.parquet \
        --output data/sft_v3/qwen_distilled_extended.parquet

The qwen_raw_completions.jsonl log is keyed on (data_uuid, sample_idx),
so previously-processed rows are skipped — only the new IEEE rows are called.
"""
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

BASE_DATASET_B = Path("data/sft_v3/dataset_b_qwen_input.parquet")
IEEE_DIR = Path("datasets/ieee_for_adaption")
DEFAULT_OUT = Path("data/sft_v3/dataset_b_qwen_input_extended.parquet")
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

# Dataset B's normalized schema (from prepare_qwen_input.py)
NORMALIZED_COLS = [
    "data_uuid", "archetype", "narrative_text", "fraud_vector_hint",
    "instrument", "language",
    "transaction_amount_usd", "fee_amount_usd",
    "hour_of_day", "day_of_week_name",
    "days_since_last_txn", "account_age_days", "txn_count_30d",
    "device_type", "device_stability",
    "sender_age", "persona_id",
    "_source", "_gt_is_fraud",
]


def normalize_ieee_row(r: dict) -> dict:
    """Map an IEEE-adapted row onto Dataset B's normalized schema.

    IEEE-adapted source columns:
      data_uuid, archetype, fraud_vector, language, instrument, amount_usd,
      is_fraud, prompt, enhanced_prompt, narrative_text
    Sidecar-joined columns (from datasets/ieee_for_adaption/spec.parquet):
      sender_age, _ieee_transaction_id, _ieee_product_cd, _ieee_p_emaildomain,
      _ieee_card6
    """
    return {
        "data_uuid": r["data_uuid"],
        "archetype": r["archetype"],
        "narrative_text": r.get("narrative_text") or r.get("enhanced_prompt"),
        "fraud_vector_hint": r.get("fraud_vector"),
        "instrument": r.get("instrument"),
        "language": r.get("language"),
        "transaction_amount_usd": r.get("amount_usd"),
        "fee_amount_usd": None,
        "hour_of_day": None,
        "day_of_week_name": None,
        "days_since_last_txn": None,
        "account_age_days": None,
        "txn_count_30d": None,
        "device_type": r.get("_ieee_card6"),       # debit / credit / etc.
        "device_stability": None,
        "sender_age": r.get("sender_age"),
        "persona_id": None,
        "_source": "ieee_adapted",
        "_gt_is_fraud": int(r.get("is_fraud", 0)),
    }


def load_ieee_pool() -> pd.DataFrame:
    frames = []
    for a in ARCHETYPES:
        path = IEEE_DIR / a / "transactions_ieee_adapted.parquet"
        if not path.exists():
            print(f"[ieee] missing: {path}  (run adaption_download_ieee.py first)")
            continue
        df = pd.read_parquet(path)
        print(f"[ieee] {a:11s}  {len(df):5d}  fraud={int((df['is_fraud']==1).sum())}")
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    big = pd.concat(frames, ignore_index=True)
    rows = [normalize_ieee_row(r) for r in big.to_dict(orient="records")]
    return pd.DataFrame(rows)


def main(base_path: Path, out_path: Path) -> None:
    if not base_path.exists():
        raise FileNotFoundError(f"base Dataset B not found: {base_path}")

    base = pd.read_parquet(base_path)
    print(f"[base] {base_path}: {len(base)} rows")

    ieee = load_ieee_pool()
    if ieee.empty:
        print("[ieee] no IEEE-adapted parquets found — nothing to merge")
        return

    # Drop empty/short narratives
    ieee = ieee[ieee["narrative_text"].notna() & (ieee["narrative_text"].astype(str).str.len() > 50)]
    print(f"[ieee] {len(ieee)} rows after narrative filter")

    # Dedupe vs base (should be disjoint since IEEE uses fresh uuids)
    base_uuids = set(base["data_uuid"].astype(str))
    overlap = ieee[ieee["data_uuid"].astype(str).isin(base_uuids)]
    if len(overlap):
        print(f"[warn] {len(overlap)} IEEE rows already in base — skipping")
        ieee = ieee[~ieee["data_uuid"].astype(str).isin(base_uuids)]

    # Align columns
    for c in NORMALIZED_COLS:
        if c not in ieee.columns:
            ieee[c] = None
        if c not in base.columns:
            base[c] = None
    ieee = ieee[NORMALIZED_COLS]
    base_aligned = base[NORMALIZED_COLS]

    combined = pd.concat([base_aligned, ieee], ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)

    print(f"\n[write] {out_path}: {len(combined)} rows  (base {len(base)} + ieee {len(ieee)})")
    print(f"[stats] _source:        {combined['_source'].value_counts().to_dict()}")
    print(f"[stats] archetype:      {combined['archetype'].value_counts().to_dict()}")
    print(f"[stats] _gt_is_fraud:   {combined['_gt_is_fraud'].value_counts().to_dict()}")
    print(f"[stats] avg narr chars: {combined['narrative_text'].astype(str).str.len().mean():.0f}")
    print("\n[next] python -m src.sft_v3.qwen_distill "
          f"--input {out_path} --output data/sft_v3/qwen_distilled_extended.parquet")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, default=BASE_DATASET_B)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    main(args.base, args.output)