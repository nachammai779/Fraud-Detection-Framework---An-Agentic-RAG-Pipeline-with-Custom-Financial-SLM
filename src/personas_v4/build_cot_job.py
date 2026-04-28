"""
Build a CoT reasoning job for Adaption: all v4 fraud rows + matched non-fraud
rows at ~1:1. Matching is on (archetype, instrument, amount band).

Output:
  datasets_v4/reasoning/for_reasoning.jsonl   Adaption-ready rows
  datasets_v4/reasoning/cot_selection.parquet selected v4 rows with match flags

Submit with adaptive_reasoning.py's --submit flow after repointing TRACKER_PATH
and upload path, or via the Adaption CLI directly.
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
OUT_DIR = V4 / "reasoning"
SEED = 42

# Log-spaced amount bands covering the bulk of v4 amounts.
AMOUNT_BINS = [0, 50, 200, 1000, 5000, 1e9]
AMOUNT_LABELS = ["xs", "s", "m", "l", "xl"]


def _load_v4() -> pd.DataFrame:
    frames = []
    for a in ARCHETYPES:
        df = pd.read_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet")
        if "archetype" not in df.columns:
            df["archetype"] = a
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["amount_band"] = pd.cut(
        df["transaction_amount_usd"], bins=AMOUNT_BINS, labels=AMOUNT_LABELS,
        include_lowest=True
    )
    return df


def _match_negatives(frauds: pd.DataFrame, negs: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """For each fraud row, pick one non-fraud row matched on
    (archetype, instrument, amount_band). Fall back to (archetype, amount_band)
    if the triple yields no candidates. Draw without replacement where possible.
    """
    # Index negatives by strict and relaxed keys
    strict_idx: dict[tuple, list[int]] = {}
    relaxed_idx: dict[tuple, list[int]] = {}
    for pos, (_, r) in enumerate(negs.iterrows()):
        strict_idx.setdefault((r["archetype"], r["instrument"], r["amount_band"]), []).append(pos)
        relaxed_idx.setdefault((r["archetype"], r["amount_band"]), []).append(pos)

    used = set()
    picks: list[int] = []
    misses = 0

    for _, f in frauds.iterrows():
        key_s = (f["archetype"], f["instrument"], f["amount_band"])
        key_r = (f["archetype"], f["amount_band"])

        def pick_from(pool):
            avail = [p for p in pool if p not in used]
            if not avail:
                return None
            return int(rng.choice(avail))

        chosen = pick_from(strict_idx.get(key_s, []))
        if chosen is None:
            chosen = pick_from(relaxed_idx.get(key_r, []))
        if chosen is None:
            # Last-resort: any unused neg in same archetype
            arch_pool = negs.index[negs["archetype"] == f["archetype"]].tolist()
            arch_positions = [negs.index.get_loc(i) for i in arch_pool]
            chosen = pick_from(arch_positions)
            misses += 1
        if chosen is None:
            continue
        used.add(chosen)
        picks.append(chosen)

    print(f"  matched_negatives: {len(picks)} / {len(frauds)} fraud rows  (fallback used {misses})")
    return negs.iloc[picks].reset_index(drop=True)


def _format_for_adaption(df: pd.DataFrame) -> list[dict]:
    """Match adaptive_reasoning.py's schema: prompt + empty completion +
    context fields that Adaption ingests for reasoning traces."""
    out = []
    for _, r in df.iterrows():
        is_fraud = int(r["is_fraud"])
        label = "fraudulent" if is_fraud else "legitimate"
        amt = float(r["transaction_amount_usd"])
        narrative = str(r.get("narrative_text") or "")

        prompt = (
            f"Transaction context:\n"
            f"- archetype: {r['archetype']}\n"
            f"- instrument: {r['instrument']}\n"
            f"- amount: ${amt:.2f}\n"
            f"- fraud_vector: {r['fraud_vector']}\n"
            f"- language: {r['language']}\n"
            f"- narrative: {narrative[:400]}\n\n"
            f"Walk through how an analyst would evaluate this transaction "
            f"step by step — what signals they would check, what the red "
            f"flags or confirming-legitimacy signals are, and the conclusion "
            f"they would reach. End with a one-sentence verdict."
        )
        out.append({
            "prompt": prompt,
            "completion": "",
            "data_uuid": r["data_uuid"],
            "archetype": r["archetype"],
            "persona_id": r["persona_id"],
            "fraud_vector": str(r["fraud_vector"]),
            "fraud_vector_typology_ref": str(r.get("fraud_vector_typology_ref") or ""),
            "instrument": str(r["instrument"]),
            "amount_usd": amt,
            "is_fraud": is_fraud,
            "language": str(r["language"]),
        })
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    df = _load_v4()
    print(f"Loaded {len(df)} v4 rows; fraud={int((df['is_fraud']==1).sum())}")

    frauds = df[df["is_fraud"] == 1].copy()
    negs = df[df["is_fraud"] == 0].copy()

    matched_negs = _match_negatives(frauds, negs, rng)
    selection = pd.concat([frauds, matched_negs], ignore_index=True)
    selection = selection.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    sel_path = OUT_DIR / "cot_selection.parquet"
    selection.to_parquet(sel_path, index=False)
    print(f"Selection saved: {sel_path}  ({len(selection)} rows, "
          f"fraud={int((selection['is_fraud']==1).sum())}, "
          f"legit={int((selection['is_fraud']==0).sum())})")

    rows = _format_for_adaption(selection)
    jsonl_path = OUT_DIR / "for_reasoning.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Adaption JSONL: {jsonl_path}  ({len(rows)} rows)")

    # Pair-quality summary
    print("\nMatched-pair summary (fraud vs matched neg):")
    print(f"  archetype breakdown:")
    for a in ARCHETYPES:
        f_n = int(((selection["archetype"] == a) & (selection["is_fraud"] == 1)).sum())
        l_n = int(((selection["archetype"] == a) & (selection["is_fraud"] == 0)).sum())
        print(f"    {a:12s} fraud={f_n:4d}  legit={l_n:4d}")


if __name__ == "__main__":
    main()