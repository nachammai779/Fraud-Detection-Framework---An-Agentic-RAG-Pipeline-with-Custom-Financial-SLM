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
  - yo
  - fr
  - zh
  - tl
  - pt
tags:
  - fraud-detection
  - synthetic-data
  - persona-conditioned
  - underserved-communities
  - remittance
  - gig-economy
  - unbanked
  - itin
pretty_name: Persona-Conditioned Fraud Detection (v2)
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
  - config_name: conditioning_schemas
    data_files:
      - split: train
        path: data/conditioning_schemas/train.parquet
  - config_name: coherence_round1
    data_files:
      - split: train
        path: data/coherence_round1/train.parquet
  - config_name: coherence_round2
    data_files:
      - split: train
        path: data/coherence_round2/train.parquet
  - config_name: coherence_round3
    data_files:
      - split: train
        path: data/coherence_round3/train.parquet
  - config_name: coherence_round4
    data_files:
      - split: train
        path: data/coherence_round4/train.parquet
  - config_name: coherence_latest
    data_files:
      - split: train
        path: data/coherence_latest/train.parquet
  - config_name: coherence_progression
    data_files:
      - split: train
        path: data/coherence_progression/train.parquet
---

# Persona-Conditioned Fraud Detection Dataset (v2)

## Overview

Synthetic fraud detection dataset for 4 underserved financial archetypes, generated using
persona-conditioned sampling. Each transaction is anchored to a named persona with structured
world dimensions (corridor, service loyalty, cadence, fraud-vector history, language mix),
enabling behavioral coherence verification against the persona that produced it.

## Quick Start

```python
from datasets import load_dataset

# The full 20k-row dataset
ds = load_dataset("<user>/<repo>", name="all")["train"]

# One archetype only
remit = load_dataset("<user>/<repo>", name="remittance")["train"]

# Look up the persona behind persona_id="rem_004"
personas = load_dataset("<user>/<repo>", name="personas")["train"]
profile  = personas.filter(lambda r: r["persona_id"] == "rem_004")[0]
```

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | 20,000 (5,000 per archetype) |
| Total personas | 40 (11 remittance, 11 gig worker, 9 unbanked, 9 ITIN) |
| Fraud rate | ~10% per archetype |
| Conditioning schemas | 40 (expanded from personas via Adaption Labs) |
| Verification rounds | 4 iterative rounds with coherence scoring |
| Best coherence pass rate | 90% (ITIN archetype, Round 4) |
| Languages represented | 10 (en, es, vi, ht, hi, yo, fr, zh, tl, pt) |

## Archetypes

| Archetype | Personas | Key World Dimensions | Best Coherence |
|-----------|----------|----------------------|----------------|
| Remittance | 11 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | 0.589 mean (R3) |
| Gig Worker | 11 | platform_mix, daily_cashout_pattern, device_stability, sim_history | 0.402 mean (R3) |
| Unbanked | 9 | kiosk_location, prepaid_card_stack, income_source, documentation_status | 0.609 mean (R4) |
| ITIN | 9 | business_type, tax_filing_history, credit_file_age, accountant_relationship | 0.798 mean (R4) |

## Available Configs

Transaction data:
- **`all`** — 20,000 rows across 4 archetypes (main dataset)
- **`remittance`** / **`gig_worker`** / **`unbanked`** / **`itin`** — 5,000 rows each

Supplementary:
- **`personas`** — 40 persona profiles (flat, one row per persona)
- **`conditioning_schemas`** — 40 expanded-world schemas (input to the generator)

Coherence verification progression:
- **`coherence_round1`** — v1 baseline (random persona assignment), 800 rows
- **`coherence_round2`** — v2 R1 (persona-anchored), 200 rows
- **`coherence_round3`** — v2 R2 (cadence/fee/amount tightened), 200 rows
- **`coherence_round4`** — v2 R3 (joint platform+hour sampling), 200 rows
- **`coherence_latest`** — alias pointing to the final round
- **`coherence_progression`** — 16-row summary (4 rounds × 4 archetypes)

## Schema (per transaction row)

| Field | Type | Description |
|-------|------|-------------|
| data_uuid | string | Unique identifier |
| persona_id | string | Source persona (e.g., rem_004, gig_001) — join to `personas` config |
| archetype | string | remittance, gig_worker, unbanked, itin |
| dataset_version | string | "v2" |
| transaction_amount_usd | float | Amount in USD |
| fee_amount_usd | float | Fee in USD |
| sender_age | int | Persona-derived age with jitter |
| hour_of_day | int | Transaction hour (persona-window constrained) |
| day_of_week | int | 0=Monday through 6=Sunday |
| day_of_week_name | string | Human-readable day |
| days_since_last_txn | int | Cadence-derived interval |
| account_age_days | int | Tenure-derived account age |
| txn_count_30d | int | Cadence-derived monthly count |
| instrument | string | Payment method (persona-specific) |
| language | string | Language code from persona's language_mix |
| fraud_vector | string | Fraud type or instrument label |
| is_fraud | int | 0 = legitimate, 1 = fraudulent |
| device_type | string | Persona's device |
| device_stability | float | Device churn score |
| narrative_text | string | Adaption-generated narrative description |
| detected_language_hints | string | Languages detected in the narrative |
| fraud_vector_hint | string | Fraud pattern hint |
| record_timestamp | string | ISO timestamp |
| source | string | Provenance tag |
| id | string | Legacy id field |

## Generation Pipeline

```
persona_profiles.json
    └── Adaption Labs "Expand the World"
        └── conditioning_schemas/train.parquet  (40 personas × 5 world schemas)
            └── TabDDPM v2 generator (persona-conditioned sampling)
                └── transactions (5k per archetype)
                    └── Adaption Labs coherence scoring
                        └── coherence_round{1..4}/train.parquet
```

## Coherence Verification Progression

| Round | Method | Remittance | Gig Worker | Unbanked | ITIN |
|-------|--------|------------|------------|----------|------|
| R1 | v1 baseline (random persona) | 0.090 | 0.168 | 0.145 | 0.097 |
| R2 | v2 persona-anchored | 0.426 | 0.370 | 0.543 | 0.720 |
| R3 | cadence/fee/amount tightened | 0.589 | 0.402 | 0.540 | 0.718 |
| R4 | joint platform+hour sampling | 0.516 | 0.399 | 0.609 | 0.798 |

At R4, Remittance dipped in pass rate — the deterministic tightening approach hits a ceiling
on event-driven archetypes where fraud vectors (phone scams, courier theft, fake-ICE calls)
are discrete events rather than schedule features. Resolving this requires an agentic or
small-language-model generation layer and is the target of v2_r4 / future v3 work.

## License

Released under CC-BY-4.0 for research and educational purposes. Persona names are fictional;
any resemblance to real individuals is coincidental.

## Credits

- [Adaption Labs](https://www.adaptionlabs.ai/) — Expand World and coherence scoring
- [Tab-DDPM](https://github.com/rotot0/tab-ddpm) — Gaussian diffusion for tabular data