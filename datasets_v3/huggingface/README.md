---
license: cc-by-4.0
task_categories:
  - tabular-classification
language:
  - en
  - es
  - vi
  - ht
  - hi
  - mr
  - ta
  - te
  - yo
  - fr
  - am
  - tw
  - ru
  - zh
  - tl
  - ko
  - ar
tags:
  - fraud-detection
  - synthetic-data
  - persona-conditioned
  - citation-grounded
  - underserved-communities
  - remittance
  - gig-economy
  - unbanked
  - itin
  - fincen
pretty_name: Persona-Conditioned Fraud Detection (v3, Citation-Grounded)
size_categories:
  - 10K<n<100K
configs:
  - config_name: all
    data_files:
      - split: train
        path: data/all/train.parquet
  - config_name: remittance
    data_files:
      - split: train
        path: data/remittance/train.parquet
  - config_name: gig_worker
    data_files:
      - split: train
        path: data/gig_worker/train.parquet
  - config_name: unbanked
    data_files:
      - split: train
        path: data/unbanked/train.parquet
  - config_name: itin
    data_files:
      - split: train
        path: data/itin/train.parquet
  - config_name: personas
    data_files:
      - split: train
        path: data/personas/train.parquet
  - config_name: sources
    data_files:
      - split: train
        path: data/sources/train.parquet
  - config_name: typology_registry
    data_files:
      - split: train
        path: data/typology_registry/train.parquet
---

# Persona-Conditioned Fraud Detection Dataset (v3, Citation-Grounded)

## What's new in v3 vs v2

v2 generated personas from design assumptions. v3 grounds every load-bearing
persona field in a real-world source (FinCEN advisories, FDIC microdata,
Urban Institute reports, Menjívar et al. TPS survey, Del Real Venezuelan
migration interviews, Remitly 10-K, Wise / Inter-American-Dialogue industry
reports, Treasury OIG fraud alerts, IRS SOI filer statistics). Every fraud
vector is mapped to a FinCEN typology code.

The generation machinery (TabDDPM-style persona-conditioned sampling with
joint platform→hour→amount for gig workers, five v2 tightening rules,
Adaption Labs narrative fill) is **unchanged** from v2 R4. Only the
conditioning input — the persona profiles — is upgraded.

### Three new universal columns on every transaction

| Field | Type | Description |
|---|---|---|
| `persona_source_ids` | list[string] | Citation IDs for real-world sources that grounded this record's persona |
| `fraud_vector_typology_ref` | string (nullable) | FinCEN SAR Advisory / FTA Identity typology code for the row's fraud_vector; null on legit rows |
| `behavioral_evidence_grade` | string A/B/C/D | Evidence quality: A=ethnographic field interview; B=regulatory typology; C=industry research; D=synthetic design assumption |

## Quick start

```python
from datasets import load_dataset

# Full 20,000-row combined dataset
ds = load_dataset("Nachammai41/underserved-persona_conditioned-fraud-v3", name="all")["train"]

# One archetype
remit = load_dataset("Nachammai41/underserved-persona_conditioned-fraud-v3", name="remittance")["train"]

# Citation registry — look up a persona_source_id
sources = load_dataset("Nachammai41/underserved-persona_conditioned-fraud-v3", name="sources")["train"]

# FinCEN typology lookup — resolve fraud_vector_typology_ref
typology = load_dataset("Nachammai41/underserved-persona_conditioned-fraud-v3", name="typology_registry")["train"]
```

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | 20,000 (5,000 per archetype) |
| Total personas | 46 (12 remittance, 12 gig_worker, 10 unbanked, 12 ITIN) |
| Fraud rate | ~10% per archetype |
| Sources in registry | 13 (7 PDFs + 1 data bundle + 5 links) |
| FinCEN typology codes | 25 (14 FTA Identity 2024 + 11 SAR Advisory Key Terms) |
| Languages represented in narratives | 17+ (en, es, vi, ht, hi, mr, ta, te, yo, fr, am, tw, ru, zh, tl, ko, ar) |
| Overall grade distribution | A 6.3% / B 50.0% / C 22.9% / D 20.8% |

## Archetypes

| Archetype | Personas | Key Dimensions | Primary Source |
|---|---|---|---|
| Remittance | 12 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | Remitly 10-K, Menjívar 2022, Del Real 2022, Wise 2023, IAD 2026 |
| Gig Worker | 12 | platform_mix, daily_cashout_pattern, device_stability, sim_history | Vallas & Schor 2020, FinCEN FTA 2024, Fed synthetic-ID |
| Unbanked | 10 | kiosk_location, prepaid_card_stack, income_source, documentation_status | FDIC 2023 HH Survey microdata (empirical distributions) |
| ITIN | 12 | business_type, tax_filing_history, credit_file_age, accountant_relationship | Menjívar 2022 (former-TPS lapse), Treasury OIG, IRS SOI, FinCEN SAR |

## Available Configs

Transaction data:
- **`all`** — 20,000 rows across 4 archetypes
- **`remittance`** / **`gig_worker`** / **`unbanked`** / **`itin`** — 5,000 rows each

Reference / attribution:
- **`personas`** — 46 persona profiles with evidence grade, source IDs, per-field grounding
- **`sources`** — 13-entry citation registry
- **`typology_registry`** — 25 FinCEN typology codes with applies_to_fraud_vectors mapping

## Schema (per transaction row)

| Field | Type | Description |
|---|---|---|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) — join to `personas` |
| archetype | string | remittance, gig_worker, unbanked, itin |
| dataset_version | string | "v3" |
| transaction_amount_usd | float | USD amount |
| fee_amount_usd | float | USD fee |
| sender_age | int | Persona-derived age with jitter |
| hour_of_day | int | Persona-window constrained hour |
| day_of_week | int / string | Day index / name |
| days_since_last_txn | int | Cadence-derived interval |
| account_age_days | int | Tenure-derived account age |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method / platform |
| language | string | From persona's language_mix |
| fraud_vector | string | Fraud type or instrument label |
| narrative_text | string | Adaption-generated first-person narrative |
| is_fraud | int | 0 = legit, 1 = fraud |
| device_type | string | Persona's device |
| device_stability | float | Device churn proxy |
| record_timestamp | string | ISO timestamp |
| **persona_source_ids** | list[string] | **v3**: citation IDs that grounded this record's persona |
| **fraud_vector_typology_ref** | string (nullable) | **v3**: FinCEN typology code for the fraud_vector |
| **behavioral_evidence_grade** | string A/B/C/D | **v3**: evidence quality grade |

## Grade Distribution

| Archetype | A (ethnographic) | B (regulatory) | C (industry) | D (design) |
|---|---:|---:|---:|---:|
| Remittance | 16.7% | 25.0% | 41.7% | 16.7% |
| Gig Worker | 0% | 25.0% | 41.7% | 33.3% |
| Unbanked | 0% | 100% | 0% | 0% |
| ITIN | 8.3% | 50.0% | 8.3% | 33.3% |

## Generation Pipeline

```
13 curated sources (PDFs + links)
    └── Structured extraction (persona_dimensions per source)
        └── 46 grounded persona profiles with per-field attribution
            └── TabDDPM v3 generator (joint platform+hour sampling,
                five v2 tightening rules, per-persona fraud-vector weighting,
                FinCEN typology resolution)
                └── 20,000-row transaction dataset (22 columns)
                    └── Adaption Labs narrative fill (persona-anchored prompts)
                        └── Final dataset with narrative_text (25 columns)
```

## Citing the dataset

The `sources` config is the authoritative citation list. Each persona's
`persona_source_ids` identifies which sources grounded it. Each fraud row's
`fraud_vector_typology_ref` identifies the FinCEN typology code — look up its
FIN-YYYY-A### advisory via the `typology_registry` config.

## License

Released under CC-BY-4.0 for research and educational purposes. Persona names
are fictional; biographical details are composed from published aggregate
source evidence. Any resemblance to real individuals is coincidental.

## Credits

- Adaption Labs — narrative fill via Enhanced Completion recipe
- FinCEN — Financial Trend Analysis 2024 (Identity), SAR Advisory Key Terms
- FDIC — 2023 National Survey of Unbanked and Underbanked Households
- Menjívar, Agadjanian & Oh — "The Contradictions of Liminal Legality" (Soc Probl 2022)
- Del Real — "Seemingly inclusive liminal legality" (J Ethn Migr Stud 2022)
- Vallas & Schor — "What Do Platforms Do?" (Annu Rev Sociol 2020)
- Remitly, Wise, Inter-American Dialogue, Oxfam America, IRS SOI, Treasury
  OIG, Federal Reserve (FedPayments Improvement) — industry & regulatory
  sources
- Tab-DDPM — Gaussian multinomial diffusion for tabular data (Kotelnikov et al.)
