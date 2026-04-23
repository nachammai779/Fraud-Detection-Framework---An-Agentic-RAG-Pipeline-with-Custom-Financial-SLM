"""
Overlay v3 narratives onto v4 transactions.

For each v4 row, pick a v3 narrative from the same persona_id (random, seeded)
and copy narrative_text. v4 metadata columns (persona_source_ids,
behavioral_evidence_grade, fraud_vector_typology_ref) stay as generated —
those are the refreshed-from-v4-personas values.

The fraud_vector on a v4 row may not match the fraud_vector that produced the
v3 narrative — this is accepted per user decision ("keep old narratives,
update only metadata"). Downstream consumers should expect narrative-to-row
drift for a subset of rows.

Output: datasets_v4/{archetype}/adaptive/transactions_adapted.parquet
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
V4 = ROOT / "datasets_v4"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def overlay(arch: str, rng: np.random.Generator) -> dict:
    v3_path = V3 / arch / "adaptive" / "transactions_adapted.parquet"
    v4_path = V4 / arch / "synthetic" / "transactions.parquet"
    out_dir = V4 / arch / "adaptive"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "transactions_adapted.parquet"

    v3 = pd.read_parquet(v3_path)
    v4 = pd.read_parquet(v4_path)

    # Index v3 narratives by persona_id
    v3_by_persona: dict[str, list[str]] = {}
    for _, row in v3[["persona_id", "narrative_text"]].dropna().iterrows():
        nt = str(row["narrative_text"])
        if nt.strip():
            v3_by_persona.setdefault(row["persona_id"], []).append(nt)

    narratives = []
    missing = 0
    for _, row in v4.iterrows():
        pool = v3_by_persona.get(row["persona_id"], [])
        if not pool:
            narratives.append("")
            missing += 1
            continue
        narratives.append(str(rng.choice(pool)))
    v4["narrative_text"] = narratives

    v4.to_parquet(out_path, index=False)
    fill = (v4["narrative_text"].astype(str).str.len() > 0).mean()
    return {
        "archetype": arch,
        "n_v4_rows": int(len(v4)),
        "v3_narratives_available_for_personas": {k: len(v) for k, v in v3_by_persona.items()},
        "narrative_fill_rate": round(float(fill), 4),
        "missing_narratives": int(missing),
        "out_path": str(out_path),
    }


def main():
    rng = np.random.default_rng(42)
    print("Overlaying v3 narratives onto v4 transactions (per persona_id match)...")
    for arch in ARCHETYPES:
        info = overlay(arch, rng)
        print(f"  {arch}: fill={info['narrative_fill_rate']:.3f} "
              f"({info['n_v4_rows']} rows, {info['missing_narratives']} missing)")


if __name__ == "__main__":
    main()
