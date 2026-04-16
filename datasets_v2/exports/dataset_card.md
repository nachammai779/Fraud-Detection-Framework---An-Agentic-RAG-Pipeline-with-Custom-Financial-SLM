
# Persona-Conditioned Fraud Detection Dataset (v2)

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
| Verification rounds | 4 iterative rounds with coherence scoring |
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
| `coherence_round1.parquet` | Round 1 coherence report — v1 baseline, random persona assignment (800 rows) |
| `coherence_round2.parquet` | Round 2 coherence report — v2 R1, persona-anchored (200 rows) |
| `coherence_round3.parquet` | Round 3 coherence report — v2 R2, cadence/fee/amount tightened (200 rows) |
| `coherence_latest.parquet` | Round 4 coherence report — v2 R3, joint platform+hour sampling (200 rows) |
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

This dataset is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Credits

- [Adaption Labs](https://www.adaptionlabs.ai/) — Expand World and coherence scoring
- [Tab-DDPM](https://github.com/rotot0/tab-ddpm) — Gaussian diffusion for tabular data
