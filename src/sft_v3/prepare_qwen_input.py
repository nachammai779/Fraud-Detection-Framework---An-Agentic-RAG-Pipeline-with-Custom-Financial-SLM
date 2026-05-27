"""Dataset B — narrative pool for Qwen-72B distillation pass.

Sources (deduped by data_uuid, also deduped against v4 CoT to avoid Dataset A overlap):
  - datasets/hf_reasoning/{archetype}/train_0.jsonl   (3,751 rows)
  - datasets_v3/{archetype}/adaptive/transactions_adapted.parquet  (~20k rows, ~1,963 fraud)
  - datasets_v4/{archetype}/adaptive/transactions_adapted.parquet  (~20k rows)

Stratified sample (default 14,000) balanced across:
  - archetype (4)  x  is_fraud (binary)

Output: data/sft_v3/dataset_b_qwen_input.parquet

Per-row schema:
  data_uuid, archetype, narrative_text, fraud_vector_hint, instrument, language,
  transaction_amount_usd, fee_amount_usd, hour_of_day, day_of_week_name,
  days_since_last_txn, account_age_days, txn_count_30d, device_type,
  device_stability, sender_age, persona_id, _source, _gt_is_fraud

The ground-truth label is stored ONLY as `_gt_is_fraud`. Qwen prompt builder
must not include this column. It is preserved for the post-filter step
(Qwen-verdict vs ground-truth agreement).

Run: python -m src.sft_v3.prepare_qwen_input --target 14000
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

import pandas as pd

HF_REASONING_DIR = Path("datasets/hf_reasoning")
V3_ADAPTIVE_TMPL = "datasets_v3/{archetype}/adaptive/transactions_adapted.parquet"
V4_ADAPTIVE_TMPL = "datasets_v4/{archetype}/adaptive/transactions_adapted.parquet"
V4_COT = Path("datasets_v4/reasoning/cot_dataset.parquet")
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]

DEFAULT_OUT = Path("data/sft_v3/dataset_b_qwen_input.parquet")
DEFAULT_TARGET = 14_000
DEFAULT_SEED = 42

NORMALIZED_COLS = [
    "data_uuid", "archetype", "narrative_text", "fraud_vector_hint",
    "instrument", "language",
    "transaction_amount_usd", "fee_amount_usd",
    "hour_of_day", "day_of_week_name",
    "days_since_last_txn", "account_age_days", "txn_count_30d",
    "device_type", "device_stability",
    "sender_age", "persona_id",
]


def _norm_hf_row(r: dict, archetype: str) -> dict:
    """HF jsonl rows have a lean schema; project them onto the normalized schema."""
    return {
        "data_uuid": r["data_uuid"],
        "archetype": archetype,
        "narrative_text": r.get("enhanced_completion") or r.get("prompt"),
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
        "device_type": None,
        "device_stability": None,
        "sender_age": None,
        "persona_id": None,
        "_source": "hf_reasoning",
        "_gt_is_fraud": int(r.get("is_fraud", 0)),
    }


def _norm_adaptive_row(r: dict, source_tag: str) -> dict:
    out = {c: r.get(c) for c in NORMALIZED_COLS}
    out["_source"] = source_tag
    out["_gt_is_fraud"] = int(r.get("is_fraud", 0))
    return out


def load_hf_pool() -> pd.DataFrame:
    rows = []
    for a in ARCHETYPES:
        path = HF_REASONING_DIR / a / "train_0.jsonl"
        if not path.exists():
            print(f"[hf] missing: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                rows.append(_norm_hf_row(json.loads(line), a))
        print(f"[hf] {a}: {sum(1 for r in rows if r['archetype']==a)}")
    return pd.DataFrame(rows)


def load_adaptive_pool(tmpl: str, source_tag: str) -> pd.DataFrame:
    frames = []
    for a in ARCHETYPES:
        path = Path(tmpl.format(archetype=a))
        if not path.exists():
            print(f"[{source_tag}] missing: {path}")
            continue
        df = pd.read_parquet(path)
        frames.append(df)
        print(f"[{source_tag}] {a}: {len(df)}")
    if not frames:
        return pd.DataFrame()
    big = pd.concat(frames, ignore_index=True)
    rows = [_norm_adaptive_row(r, source_tag) for r in big.to_dict(orient="records")]
    return pd.DataFrame(rows)


def stratified_sample(pool: pd.DataFrame, target: int, seed: int) -> pd.DataFrame:
    """Even split across archetype x is_fraud cells. Falls back to whatever is available
    per cell if a cell is undersupplied."""
    cells = [(a, f) for a in ARCHETYPES for f in (0, 1)]
    per_cell = math.ceil(target / len(cells))
    print(f"[sample] target={target}  per-cell quota={per_cell}  cells={len(cells)}")
    out = []
    rng_state = seed
    for a, f in cells:
        sub = pool[(pool["archetype"] == a) & (pool["_gt_is_fraud"] == f)]
        take = min(per_cell, len(sub))
        if take < per_cell:
            print(f"  WARN cell ({a}, fraud={f}): wanted {per_cell}, have {len(sub)}")
        sampled = sub.sample(n=take, random_state=rng_state)
        out.append(sampled)
        rng_state += 1
    df = pd.concat(out, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    if len(df) > target:
        df = df.iloc[:target].reset_index(drop=True)
    return df


def main(target: int, out_path: Path, seed: int) -> None:
    # Load v4 CoT uuids — we exclude these so Dataset B doesn't overlap with Dataset A
    v4_cot_uuids = set(pd.read_parquet(V4_COT)["data_uuid"].astype(str))
    print(f"[exclude] v4 CoT uuids to skip: {len(v4_cot_uuids)}")

    hf = load_hf_pool()
    v3 = load_adaptive_pool(V3_ADAPTIVE_TMPL, "v3_adaptive")
    v4 = load_adaptive_pool(V4_ADAPTIVE_TMPL, "v4_adaptive")
    print(f"[pool] hf={len(hf)}  v3_adaptive={len(v3)}  v4_adaptive={len(v4)}")

    pool = pd.concat([hf, v3, v4], ignore_index=True)
    before = len(pool)
    pool = pool[~pool["data_uuid"].astype(str).isin(v4_cot_uuids)]
    pool = pool.drop_duplicates(subset=["data_uuid"])
    # Drop rows with no narrative
    pool = pool[pool["narrative_text"].notna() & (pool["narrative_text"].astype(str).str.len() > 50)]
    print(f"[dedup] {before} -> {len(pool)} after excluding v4-CoT uuids + dup uuids + empty narratives")

    print("[dist] archetype x is_fraud counts in pool:")
    print(pool.groupby(["archetype", "_gt_is_fraud"]).size())

    sampled = stratified_sample(pool, target=target, seed=seed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_parquet(out_path, index=False)

    print(f"\n[write] {out_path}: {len(sampled)} rows")
    print(f"[stats] archetype: {sampled['archetype'].value_counts().to_dict()}")
    print(f"[stats] _gt_is_fraud: {sampled['_gt_is_fraud'].value_counts().to_dict()}")
    print(f"[stats] _source: {sampled['_source'].value_counts().to_dict()}")
    print(f"[stats] avg narrative chars: {sampled['narrative_text'].str.len().mean():.0f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--target", type=int, default=DEFAULT_TARGET)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = p.parse_args()
    main(args.target, args.output, args.seed)