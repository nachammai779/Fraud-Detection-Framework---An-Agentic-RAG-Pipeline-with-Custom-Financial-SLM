"""Compare v4 fresh Adaption narratives vs v3 reference narratives, per persona,
across all 4 archetypes. v3 and v4 data_uuids differ (TabDDPM was re-run for v4),
so the join is by persona_id: for each v4 persona we pick one v3 narrative from
the same persona to sit alongside one v4 narrative.
"""
import sys

import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
V4 = ROOT / "datasets_v4"

ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def compare(arch: str, max_personas: int = 6):
    v4_path = V4 / arch / "adaptive" / "transactions_adapted.parquet"
    v3_path = V3 / arch / "adaptive" / "transactions_adapted.parquet"
    if not v4_path.exists():
        print(f"[{arch}] v4 transactions_adapted.parquet missing — skipping\n")
        return

    v4 = pd.read_parquet(v4_path)

    v3_by_persona: dict[str, str] = {}
    if v3_path.exists():
        v3 = pd.read_parquet(v3_path)
        v3 = v3[v3["narrative_text"].astype(str).str.len() > 0]
        v3_by_persona = v3.groupby("persona_id")["narrative_text"].first().to_dict()

    n_personas = v4["persona_id"].nunique()
    print(f"=== {arch} === (v4 {len(v4)} rows, {n_personas} personas; v3 refs for "
          f"{sum(pid in v3_by_persona for pid in v4['persona_id'].unique())}/{n_personas})\n")

    for pid in sorted(v4["persona_id"].unique())[:max_personas]:
        r = v4[v4["persona_id"] == pid].head(1).iloc[0]
        amt = float(r["transaction_amount_usd"])
        print(f"-- {pid}  amt=${amt:.0f}  lang={r['language']}  "
              f"{r['day_of_week_name']}@{r['hour_of_day']}  fraud={r['is_fraud']}  "
              f"vec={r['fraud_vector']}")
        print(f"   typology={r['fraud_vector_typology_ref']}   "
              f"grade={r['behavioral_evidence_grade']}")
        v3_ref = v3_by_persona.get(pid)
        print(f"   V3-REF: {str(v3_ref)[:240] if v3_ref else '(no v3 narrative for this persona)'}")
        print(f"   V4:     {str(r['narrative_text'])[:240]}")
        print()


def main():
    for arch in ARCHETYPES:
        compare(arch)


if __name__ == "__main__":
    main()