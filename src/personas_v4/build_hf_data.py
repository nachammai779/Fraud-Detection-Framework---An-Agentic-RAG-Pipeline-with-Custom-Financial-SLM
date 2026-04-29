"""
Rebuild datasets_v4/huggingface/data/{config}/train.parquet from the
canonical post-v4.1 bundle + reference JSONs.

Configs produced:
  all                  — full bundle, 20,300 rows
  remittance / gig_worker / unbanked / itin — archetype slices
  personas             — flattened personas_all.json (46 rows)
  sources              — flattened sources.json (13 rows)
  typology_registry    — flattened typology_registry.json (25 rows)

Run after the bundle parquet is up to date.
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
EXPORTS = V4 / "exports"
HF = V4 / "huggingface" / "data"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def _write(df: pd.DataFrame, name: str):
    out_dir = HF / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "train.parquet"
    df.to_parquet(out, index=False, engine="pyarrow")
    print(f"  {name:20s} {len(df):6d} rows  -> {out}")


def build_transactions():
    bundle = pd.read_parquet(EXPORTS / "transactions_v4_20k.parquet")
    print(f"loaded bundle: {len(bundle)} rows, {len(bundle.columns)} cols")
    _write(bundle, "all")
    for a in ARCHETYPES:
        _write(bundle[bundle["archetype"] == a].reset_index(drop=True), a)


def build_personas():
    data = json.loads((EXPORTS / "personas_all.json").read_text(encoding="utf-8"))
    rows = []
    archetypes = data.get("archetypes", {})
    for arch, group in archetypes.items():
        personas = group.get("personas", []) if isinstance(group, dict) else group
        for p in personas:
            rows.append({
                "persona_id": p.get("persona_id", ""),
                "archetype": arch,
                "name": p.get("name", ""),
                "age": int(p.get("age", 0) or 0),
                "summary": p.get("summary", ""),
                "behavioral_evidence_grade": p.get("behavioral_evidence_grade", ""),
                "persona_source_ids": p.get("persona_source_ids", []) or [],
                "family_crisis_history": p.get("family_crisis_history", []) or [],
                "profile_json": json.dumps(p, ensure_ascii=False),
            })
    _write(pd.DataFrame(rows), "personas")


def build_sources():
    data = json.loads((V4 / "sources" / "sources.json").read_text(encoding="utf-8"))
    rows = []
    for sid, entry in data.items():
        if sid.startswith("_"):
            continue
        rows.append({
            "source_id": sid,
            "kind": entry.get("kind", ""),
            "title": entry.get("title", ""),
            "authors": entry.get("authors", entry.get("author", "")),
            "year": entry.get("year", ""),
            "publisher": entry.get("publisher", ""),
            "url": entry.get("url", ""),
            "archetypes": entry.get("archetypes", []) or [],
            "notes": entry.get("notes", ""),
        })
    _write(pd.DataFrame(rows), "sources")


def build_cot_reasoning():
    src = V4 / "reasoning" / "cot_dataset.parquet"
    if not src.exists():
        print(f"  cot_reasoning       SKIPPED — {src} missing (run cot_adaption_job.py --download first)")
        return
    df = pd.read_parquet(src)
    _write(df, "cot_reasoning")


def build_typology():
    data = json.loads((V4 / "sources" / "typology_registry.json").read_text(encoding="utf-8"))
    rows = []
    for code, entry in data.items():
        if code.startswith("_"):
            continue
        rows.append({
            "code": code,
            "name": entry.get("name", ""),
            "definition": entry.get("definition", ""),
            "primary_exploitation": entry.get("primary_exploitation", ""),
            "source_id": entry.get("source_id", ""),
            "applies_to_fraud_vectors": entry.get("applies_to_fraud_vectors", []) or [],
            "fincen_advisory_codes": entry.get("fincen_advisory_codes", []) or [],
        })
    _write(pd.DataFrame(rows), "typology_registry")


def main():
    HF.mkdir(parents=True, exist_ok=True)
    print("--- transactions ---")
    build_transactions()
    print("--- references ---")
    build_personas()
    build_sources()
    build_typology()
    print("--- cot_reasoning ---")
    build_cot_reasoning()
    print("\ndone.")


if __name__ == "__main__":
    main()