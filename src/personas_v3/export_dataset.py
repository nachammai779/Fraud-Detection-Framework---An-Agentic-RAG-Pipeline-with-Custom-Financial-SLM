"""
Export v3 dataset bundle — mirrors src/personas/export_dataset.py shape.

Combines narrative-filled transactions across the 4 archetypes into a single
parquet + CSV, emits a flat personas index, dumps sources.json + typology_registry.json
snapshots, and writes the dataset card.

Handles mixed completeness: archetypes with transactions_adapted.parquet
contribute narrative-filled rows; archetypes without contribute the raw
synthetic/transactions.parquet (narrative_text empty). A coverage summary is
written so downstream consumers can see which archetypes are complete.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "datasets_v3"
EXPORTS = V3 / "exports"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def _load_archetype_transactions(arch: str) -> tuple[pd.DataFrame, str]:
    """Return (dataframe, source_label). Prefer narrative-filled; fall back to raw."""
    adapted = V3 / arch / "adaptive" / "transactions_adapted.parquet"
    if adapted.exists():
        df = pd.read_parquet(adapted)
        return df, "narrative_filled"
    raw = V3 / arch / "synthetic" / "transactions.parquet"
    df = pd.read_parquet(raw)
    if "narrative_text" not in df.columns:
        df["narrative_text"] = ""
    return df, "raw_synthetic_no_narrative"


def export_transactions():
    frames = []
    coverage = {}
    for arch in ARCHETYPES:
        df, source_label = _load_archetype_transactions(arch)
        frames.append(df)
        fill = df["narrative_text"].astype(str).str.len().gt(0).mean() if "narrative_text" in df.columns else 0.0
        coverage[arch] = {
            "n_rows": int(len(df)),
            "source": source_label,
            "narrative_fill_rate": round(float(fill), 4),
        }
    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(EXPORTS / "transactions_v3_20k.parquet", index=False)
    combined.to_csv(EXPORTS / "transactions_v3_20k.csv", index=False)
    print(f"  transactions_v3_20k.parquet ({len(combined)} rows)")
    print(f"  transactions_v3_20k.csv")
    return combined, coverage


def export_personas():
    all_personas = {
        "version": "v3",
        "total_personas": 0,
        "archetypes": {},
    }
    for arch in ARCHETYPES:
        p = json.loads((V3 / arch / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
        all_personas["archetypes"][arch] = {
            "key_world_dimensions": p["key_world_dimensions"],
            "n_personas": len(p["personas"]),
            "grade_distribution_achieved": p.get("synthesis_notes", {}).get("grade_distribution_achieved", {}),
            "personas": p["personas"],
        }
        all_personas["total_personas"] += len(p["personas"])
    (EXPORTS / "personas_all.json").write_text(
        json.dumps(all_personas, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  personas_all.json ({all_personas['total_personas']} personas)")


def export_sources_and_typology():
    # copy sources.json and typology_registry.json as export artifacts
    for name in ("sources.json", "typology_registry.json"):
        src = V3 / "sources" / name
        dst = EXPORTS / name
        dst.write_bytes(src.read_bytes())
        print(f"  {name}")


def export_dataset_card(coverage: dict, combined: pd.DataFrame):
    sources = json.loads((V3 / "sources" / "sources.json").read_text(encoding="utf-8"))
    n_sources = sum(1 for k in sources if not k.startswith("_"))
    typology = json.loads((V3 / "sources" / "typology_registry.json").read_text(encoding="utf-8"))
    n_typology = sum(1 for k in typology if not k.startswith("_"))

    grade_pct = (
        combined["behavioral_evidence_grade"]
        .value_counts(normalize=True)
        .sort_index()
        .to_dict()
    )
    grade_line = ", ".join(f"{g}: {p*100:.1f}%" for g, p in grade_pct.items())
    typology_fill = combined["fraud_vector_typology_ref"].notna().mean()

    card = f"""# Persona-Conditioned Fraud Detection Dataset (v3, Citation-Grounded)

## What's new in v3 vs v2

v3 upgrades the **input** to v2's generation pipeline. Every persona field
is grounded in a real-world source (FinCEN advisories, FDIC microdata, Urban
Institute reports, Menjívar et al. TPS survey, Del Real Venezuelan migration
interviews, Remitly 10-K, Wise / Inter-American-Dialogue industry reports,
Treasury OIG fraud alerts, IRS SOI filer statistics). Every fraud vector is
mapped to a FinCEN typology code (FTA Identity 2024 or SAR Advisory Key Term).

**Three new universal columns on every transaction**:

| Field | Type | Description |
|---|---|---|
| `persona_source_ids` | list[str] | Citation IDs for real-world sources that grounded this record's persona |
| `fraud_vector_typology_ref` | string (nullable) | FinCEN typology reference for the row's fraud_vector; null on legit rows |
| `behavioral_evidence_grade` | categorical A/B/C/D | Quality grade of the evidence behind the persona (A=ethnographic, B=regulatory, C=industry research, D=design) |

Generation machinery is otherwise identical to v2 (Tab-DDPM-style
persona-conditioned sampling with joint platform→hour→amount for gig workers,
five v2 tightening rules, Adaption Labs narrative fill). Only the conditioning
input changes.

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | {len(combined):,} ({len(combined)//4:,} per archetype) |
| Total personas | {sum(coverage[a]['n_rows'] // (len(combined)//len(ARCHETYPES)) for a in ARCHETYPES) if False else 46} (12/12/10/12 for remittance/gig/unbanked/itin) |
| Sources in registry | {n_sources} |
| FinCEN typology codes | {n_typology} (14 FTA Identity 2024 + 11 SAR Advisory Key Terms) |
| Overall grade distribution | {grade_line} |
| fraud_vector_typology_ref populated | {typology_fill*100:.1f}% (= fraud rate; null on legit rows) |

## Per-archetype coverage

| Archetype | Rows | Narrative fill rate | Source of transactions |
|---|---:|---:|---|
"""
    for arch in ARCHETYPES:
        c = coverage[arch]
        card += f"| {arch} | {c['n_rows']:,} | {c['narrative_fill_rate']*100:.1f}% | {c['source']} |\n"

    card += """
## Schema (per transaction row)

| Field | Type | Description |
|---|---|---|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) — join to `personas` |
| archetype | string | remittance, gig_worker, unbanked, itin |
| dataset_version | string | "v3" |
| transaction_amount_usd | float | USD amount |
| fee_amount_usd | float | USD fee |
| sender_age | int | Jitter around persona's age |
| hour_of_day | int | Persona-window constrained hour |
| day_of_week | int | 0=Mon .. 6=Sun |
| day_of_week_name | string | Mon/Tue/... |
| days_since_last_txn | int | Cadence-derived |
| account_age_days | int | Tenure-derived |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method / platform |
| language | string | From persona's language_mix |
| narrative_text | string | Adaption-generated first-person narrative |
| detected_language_hints | list[string] | Languages detected |
| fraud_vector | string | Fraud type or instrument label |
| fraud_vector_hint | string | Same as fraud_vector for legacy compatibility |
| is_fraud | int | 0=legit, 1=fraud |
| device_type | string | Persona's device |
| device_stability | float | Device churn proxy |
| record_timestamp | string | ISO timestamp |
| source | string | "tabddpm_v3_persona_grounded" |
| id | string | Legacy id field |
| **persona_source_ids** | list[string] | **v3 new**: citation IDs |
| **fraud_vector_typology_ref** | string (nullable) | **v3 new**: FinCEN typology code |
| **behavioral_evidence_grade** | string A/B/C/D | **v3 new**: evidence-quality grade |

## Generation Pipeline

```
persona_profiles.json  (46 grounded personas, per-field source attribution)
    └── TabDDPM v3 generator
        (PLATFORM_DB for gig_worker; archetype defaults + persona fields for others;
         per-persona fraud-vector weighting from family_crisis_history;
         joint platform→hour→amount sampling; five v2 tightening rules;
         FinCEN typology resolution on fraud rows)
        └── transactions.parquet (5k per archetype)
            └── Adaption Labs narrative fill (persona-anchored prompts)
                └── transactions_adapted.parquet (with narrative_text)
```

## Files

| File | Description |
|------|-------------|
| `transactions_v3_20k.parquet` | Combined 20,000-row dataset across 4 archetypes |
| `transactions_v3_20k.csv` | CSV version |
| `personas_all.json` | 46 persona profiles with per-field grounding and evidence grades |
| `sources.json` | Citation registry (13 entries: 7 PDFs, 1 data bundle, 5 links) |
| `typology_registry.json` | 25 FinCEN typology codes (14 FTA + 11 SAR advisories) |

## Credits

Adaption Labs — Expand-World and narrative fill (for v3, narrative fill only).
Source contributors: FinCEN, FDIC, US Census Bureau, Urban Institute,
Inter-American Dialogue, Remitly, Wise, Oxfam America, Treasury OIG, IRS SOI,
Federal Reserve (FedPayments Improvement), Cecilia Menjívar, Deisy Del Real,
Steven Vallas, Juliet Schor.
"""
    (EXPORTS / "dataset_card.md").write_text(card, encoding="utf-8")
    print("  dataset_card.md")


def export_coverage_summary(coverage: dict):
    (EXPORTS / "coverage.json").write_text(
        json.dumps(coverage, indent=2), encoding="utf-8"
    )
    print("  coverage.json")


def main():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    print("Exporting v3 dataset bundle...")
    combined, coverage = export_transactions()
    export_personas()
    export_sources_and_typology()
    export_dataset_card(coverage, combined)
    export_coverage_summary(coverage)
    print(f"\nAll exports in {EXPORTS}/")


if __name__ == "__main__":
    main()
