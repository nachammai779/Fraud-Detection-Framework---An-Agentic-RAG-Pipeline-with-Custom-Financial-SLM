"""
Export open-source dataset: join all 4 archetypes into single files per iteration.

Outputs:
  datasets_v2/exports/personas_all.json                    40 personas, all archetypes
  datasets_v2/exports/round1_coherence.parquet             800 rows (200/arch, v1 fallback)
  datasets_v2/exports/round2_coherence.parquet             200 rows (50/arch, tightened)
  datasets_v2/exports/round3_coherence.parquet             200 rows (50/arch, joint sampling)
  datasets_v2/exports/transactions_v2_20k.parquet          20,000 rows (5k/arch, final gen)
  datasets_v2/exports/transactions_v2_20k.csv              CSV version
  datasets_v2/exports/conditioning_schemas_all.parquet     40 rows (expanded world schemas)
  datasets_v2/exports/dataset_card.md                      Dataset documentation

Usage:
  python src/personas/export_dataset.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets_v2"
EXPORTS = DATA / "exports"
ARCHETYPES = ["remittance", "gig_worker", "unbanked", "itin"]


def export_personas():
    all_personas = {
        "version": "v2",
        "total_personas": 0,
        "archetypes": {},
    }
    for arch in ARCHETYPES:
        p = json.loads((DATA / arch / "personas" / "persona_profiles.json").read_text(encoding="utf-8"))
        all_personas["archetypes"][arch] = {
            "key_world_dimensions": p["key_world_dimensions"],
            "personas": p["personas"],
        }
        all_personas["total_personas"] += len(p["personas"])
    out = EXPORTS / "personas_all.json"
    out.write_text(json.dumps(all_personas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  personas_all.json ({all_personas['total_personas']} personas)")


def export_transactions():
    frames = []
    for arch in ARCHETYPES:
        df = pd.read_parquet(DATA / arch / "synthetic" / "transactions.parquet")
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(EXPORTS / "transactions_v2_20k.parquet", index=False)
    combined.to_csv(EXPORTS / "transactions_v2_20k.csv", index=False)
    print(f"  transactions_v2_20k.parquet ({len(combined)} rows)")


def export_conditioning_schemas():
    frames = []
    for arch in ARCHETYPES:
        df = pd.read_parquet(DATA / arch / "expanded_world" / "conditioning_schema.parquet")
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(EXPORTS / "conditioning_schemas_all.parquet", index=False)
    print(f"  conditioning_schemas_all.parquet ({len(combined)} rows)")


def export_coherence_rounds():
    # Export latest coherence report (Round 3 / final iteration) joined across archetypes
    frames = []
    for arch in ARCHETYPES:
        report_path = DATA / arch / "persona_verification" / "coherence_report.parquet"
        if report_path.exists():
            df = pd.read_parquet(report_path)
            frames.append(df)
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined.to_parquet(EXPORTS / "coherence_report_latest.parquet", index=False)
        print(f"  coherence_report_latest.parquet ({len(combined)} rows, Round 3 final)")

    # Export progression summary with historical means from all 4 rounds
    summary_rows = []
    rounds = [
        ("v1", "Random persona assignment (baseline)", {
            "remittance": 0.090, "gig_worker": 0.168, "unbanked": 0.145, "itin": 0.097}),
        ("v2_r1", "Persona-anchored generation", {
            "remittance": 0.426, "gig_worker": 0.370, "unbanked": 0.543, "itin": 0.720}),
        ("v2_r2", "Cadence/fee/amount tightened", {
            "remittance": 0.589, "gig_worker": 0.402, "unbanked": 0.540, "itin": 0.718}),
        ("v2_r3", "Joint platform+hour sampling", {
            "remittance": 0.516, "gig_worker": 0.399, "unbanked": 0.609, "itin": 0.798}),
    ]
    pass_rates = [
        {"remittance": 0, "gig_worker": 0, "unbanked": 0, "itin": 0},
        {"remittance": 24, "gig_worker": 20, "unbanked": 46, "itin": 74},
        {"remittance": 56, "gig_worker": 20, "unbanked": 46, "itin": 80},
        {"remittance": 44, "gig_worker": 24, "unbanked": 58, "itin": 90},
    ]
    for i, (rnd, label, means) in enumerate(rounds):
        for arch, mean in means.items():
            summary_rows.append({
                "round": rnd,
                "round_label": label,
                "archetype": arch,
                "mean_coherence": mean,
                "pass_rate_pct": pass_rates[i][arch],
            })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(EXPORTS / "coherence_progression.csv", index=False)
    print(f"  coherence_progression.csv ({len(summary_df)} rows, 4 rounds x 4 archetypes)")


def export_dataset_card():
    card = """# Persona-Conditioned Fraud Detection Dataset (v2)

## Overview

Synthetic fraud detection dataset for 4 underserved financial archetypes, generated using
persona-conditioned sampling. Each transaction is anchored to a named persona with structured
world dimensions, enabling behavioral coherence verification.

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | 20,000 (5,000 per archetype) |
| Total personas | 40 (11 remittance, 11 gig worker, 9 unbanked, 9 ITIN) |
| Fraud rate | ~10% per archetype |
| Conditioning schemas | 40 (expanded from personas via Adaption Labs) |
| Verification rounds | 3 iterative rounds with coherence scoring |
| Best coherence pass rate | 90% (ITIN archetype, Round 3) |
| Adaption quality grade | E (5.0) → A (9.4-10.0) |

## Archetypes

| Archetype | Personas | Key Dimensions | Best Coherence |
|-----------|----------|----------------|----------------|
| Remittance | 11 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | 0.516 mean |
| Gig Worker | 11 | platform_mix, daily_cashout_pattern, device_stability, sim_history | 0.399 mean |
| Unbanked | 9 | kiosk_location, prepaid_card_stack, income_source, documentation_status | 0.609 mean |
| ITIN | 9 | business_type, tax_filing_history, credit_file_age, accountant_relationship | 0.798 mean |

## Files

| File | Description |
|------|-------------|
| `personas_all.json` | 40 structured persona profiles across 4 archetypes |
| `transactions_v2_20k.parquet` | 20,000 synthetic transactions with persona_id |
| `transactions_v2_20k.csv` | CSV version |
| `conditioning_schemas_all.parquet` | Expanded world schemas (40 personas) |
| `round3_coherence.parquet` | Latest coherence report with scores and violations |
| `coherence_progression.csv` | Mean coherence across all 4 verification rounds |

## Schema (per transaction)

| Field | Type | Description |
|-------|------|-------------|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) |
| archetype | string | remittance, gig_worker, unbanked, itin |
| dataset_version | string | "v2" |
| transaction_amount_usd | float | Amount in USD |
| fee_amount_usd | float | Fee in USD |
| sender_age | int | Persona-derived age with jitter |
| hour_of_day | int | Transaction hour (persona-window constrained) |
| day_of_week | int | 0=Monday through 6=Sunday |
| days_since_last_txn | int | Cadence-derived interval |
| account_age_days | int | Tenure-derived account age |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method (persona-specific) |
| language | string | Language code from persona's language_mix |
| fraud_vector | string | Fraud type or instrument label |
| is_fraud | int | 0 = legitimate, 1 = fraudulent |
| device_type | string | Persona's device |
| device_stability | float | Device churn score |

## Generation Pipeline

```
persona_profiles.json → Adaption Labs Expand World → conditioning_schema.parquet
    → TabDDPM v2 generator (persona-conditioned) → transactions.parquet
    → Adaption Labs coherence scoring → coherence_report.parquet
```

## Coherence Verification Progression

| Round | Method | Remittance | Gig Worker | Unbanked | ITIN |
|-------|--------|-----------|------------|----------|------|
| 1 | Random persona assignment | 0.090 | 0.168 | 0.145 | 0.097 |
| 2 | Persona-anchored | 0.426 | 0.370 | 0.543 | 0.720 |
| 3 | Cadence/fee/amount tightened | 0.589 | 0.402 | 0.540 | 0.718 |
| 4 | Joint platform+hour sampling | 0.516 | 0.399 | 0.609 | 0.798 |

## License

This dataset is released for research and educational purposes.

## Credits

- [Adaption Labs](https://www.adaptionlabs.ai/) — Expand World and coherence scoring
- [Tab-DDPM](https://github.com/rotot0/tab-ddpm) — Gaussian diffusion for tabular data
"""
    (EXPORTS / "dataset_card.md").write_text(card, encoding="utf-8")
    print("  dataset_card.md")


def main():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    print("Exporting open-source dataset...")
    export_personas()
    export_transactions()
    export_conditioning_schemas()
    export_coherence_rounds()
    export_dataset_card()
    print(f"\nAll exports in {EXPORTS}/")


if __name__ == "__main__":
    main()