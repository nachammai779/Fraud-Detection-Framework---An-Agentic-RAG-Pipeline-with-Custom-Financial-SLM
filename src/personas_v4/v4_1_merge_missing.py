"""
v4.1 merge step — run AFTER Adaption returns narratives for the 300
missing-typology rows.

Inputs:
  datasets_v4/v4_1/missing_typology_rows.parquet    (built earlier, empty narratives)
  datasets_v4/v4_1/adapted_output.jsonl             (downloaded from Adaption)

Outputs (in place):
  datasets_v4/v4_1/missing_typology_rows.parquet    (narratives filled)
  datasets_v4/{archetype}/adaptive/transactions_adapted.parquet  (300 rows appended across 3 archetypes)
  datasets_v4/exports/transactions_v4_20k.parquet   (bundle rebuilt; will grow to 20,300 rows)
  datasets_v4/exports/transactions_v4_20k.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "datasets_v4"
V41 = V4 / "v4_1"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def _load_narratives(jsonl_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            u = r.get("data_uuid") or ""
            txt = r.get("enhanced_completion") or r.get("completion") or ""
            if isinstance(txt, dict):
                txt = json.dumps(txt, ensure_ascii=False)
            if u and txt:
                out[u] = str(txt)[:2000]
    return out


def main():
    synth_path = V41 / "missing_typology_rows.parquet"
    adapted_path = V41 / "adapted_output.jsonl"
    if not synth_path.exists():
        raise SystemExit(f"missing {synth_path} — run v4_1_add_missing_typologies.py first")
    if not adapted_path.exists():
        raise SystemExit(f"missing {adapted_path} — download the Adaption job output first")

    synth = pd.read_parquet(synth_path)
    narrs = _load_narratives(adapted_path)
    print(f"synth rows={len(synth)}  adapted narratives found={len(narrs)}")

    synth["narrative_text"] = synth["data_uuid"].map(lambda u: narrs.get(u, ""))
    filled = int((synth["narrative_text"].astype(str).str.len() > 0).sum())
    print(f"filled {filled}/{len(synth)} narratives")
    synth.to_parquet(synth_path, index=False, engine="pyarrow")

    # Append per-archetype
    appended_total = 0
    for arch in ARCHETYPES:
        main_path = V4 / arch / "adaptive" / "transactions_adapted.parquet"
        main = pd.read_parquet(main_path)
        add = synth[synth["archetype"] == arch]
        if add.empty:
            continue
        # Align columns
        for c in main.columns:
            if c not in add.columns:
                add[c] = pd.NA
        add = add[main.columns]
        merged = pd.concat([main, add], ignore_index=True)
        merged.to_parquet(main_path, index=False, engine="pyarrow")
        appended_total += len(add)
        print(f"[{arch}] appended {len(add)} rows -> {main_path} (now {len(merged)})")

    # Rebuild bundle
    frames = [pd.read_parquet(V4 / a / "adaptive" / "transactions_adapted.parquet") for a in ARCHETYPES]
    bundle = pd.concat(frames, ignore_index=True)
    bp = V4 / "exports" / "transactions_v4_20k.parquet"
    bc = V4 / "exports" / "transactions_v4_20k.csv"
    if bp.exists():
        existing = pd.read_parquet(bp)
        cols = [c for c in existing.columns if c in bundle.columns] + \
               [c for c in bundle.columns if c not in existing.columns]
        bundle = bundle[cols]
    bundle.to_parquet(bp, index=False, engine="pyarrow")
    bundle.to_csv(bc, index=False)
    print(f"bundle rebuilt: {bp}  ({len(bundle)} rows)")

    # Coverage report
    fr = bundle[bundle["is_fraud"] == 1]
    codes = fr["fraud_vector_typology_ref"].dropna().astype(str)
    codes = codes[codes.str.len() > 0]
    print(f"\nTypology coverage after merge: {codes.nunique()} distinct codes")


if __name__ == "__main__":
    main()