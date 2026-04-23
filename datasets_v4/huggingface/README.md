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
  - fincen-typology
  - underserved-communities
  - remittance
  - gig-economy
  - unbanked
  - itin
pretty_name: Persona-Conditioned Fraud Detection (v4, Expanded Typology Coverage)
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

# Persona-Conditioned Fraud Detection Dataset (v4, Expanded Typology Coverage)

## What's new in v4 vs v3

v3 shipped a citation-grounded dataset with 10 of 25 FinCEN typology codes
exercised. **v4 closes the gap to 18 of 25 (+80%)** through three targeted
changes — none of which required new Adaption credits:

1. **16 persona edits**: added documented fraud events (SIM-swap, BEC,
   hawala/IVTS, hurricane relief scams, money-mule recruitment, synthetic-ID,
   unauthorized ACH, lax-KYC observation, false chargeback, COVID-imposter)
   across gig / remittance / unbanked personas. 4 personas graded D→B.
2. **SAR-preference typology resolver**: when a fraud vector maps to both an
   FTA Identity code and a more-specific SAR Advisory code, the resolver now
   picks the SAR advisory (citeable to a FIN-YYYY-A### advisory). Surfaces 4
   previously-shadowed SAR codes.
3. **Narrative overlay from v3** by persona_id: zero-credit reuse of v3's
   Adaption-filled narratives. Persona voice preserved; row-level amount /
   day / language drift accepted.

The generation pipeline is otherwise identical to v3 (persona-conditioned
Tab-DDPM-style sampling, joint platform+hour for gig workers, five v2
tightening rules).

### Same three universal v3 columns, updated v4 values

| Field | Type | V4 note |
|---|---|---|
| `persona_source_ids` | list[string] | Persona-level; includes new FinCEN advisory IDs for the 16 edited personas |
| `fraud_vector_typology_ref` | string (nullable) | Re-resolved per SAR-preference rule; 18 distinct codes exercised |
| `behavioral_evidence_grade` | string A/B/C/D | 4 promotions D→B |

## Quick start

```python
from datasets import load_dataset

repo = "Nachammai41/underserved-persona_conditioned-fraud-v4"  # TBD

ds = load_dataset(repo, name="all")["train"]                    # 20,000 rows
remit = load_dataset(repo, name="remittance")["train"]          # 5,000 rows
personas = load_dataset(repo, name="personas")["train"]         # 46 rows
sources = load_dataset(repo, name="sources")["train"]           # 13 rows
typology = load_dataset(repo, name="typology_registry")["train"] # 25 rows
```

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total transactions | 20,000 (5,000 per archetype) |
| Total personas | 46 (12 remittance, 12 gig_worker, 10 unbanked, 12 ITIN) |
| Fraud rate | ~10% per archetype |
| Sources in registry | 13 (7 PDFs + 1 data bundle + 5 links) |
| FinCEN typology codes | 25 registered, **18 exercised** in generated output |
| Languages | 17+ native scripts (Latin, Devanagari, CJK, Arabic, Cyrillic, Ge'ez, etc.) |
| Overall grade distribution | A 6.3% / **B 58.3%** / C 22.9% / **D 12.5%** |
| Narrative fill rate | 100% (v3-overlaid) |

## Narrative-overlay tradeoff

v4 reuses v3's narratives by `persona_id` without new credit spend. This
preserves **persona-level grounding** (corridor, platform, biographical
details) but introduces **row-level drift** in:

| Signal | v3 | v4 | Note |
|---|---:|---:|---|
| Corridor keyword in narrative | 71.4% | 71.1% | stable |
| Platform name in narrative | 42.7% | 43.2% | stable |
| Amount in narrative (rounded) | 35.9% | 7.8% | drift |
| Amount in narrative (exact) | 28.5% | 1.6% | drift |
| Day of week mentioned | 47.4% | 24.5% | drift |
| Language tag↔detected match | 92.1% | 59.3% | drift |

Downstream consumers using the **structured columns** (amount, instrument,
day_of_week, language, etc.) are unaffected — those are accurate. Models
trying to recover transaction features from `narrative_text` will see
degraded signal compared to v3; prefer the structured columns for that.

If your use case requires row-accurate narratives, use
[`Nachammai41/underserved-persona_conditioned-fraud-v3`](https://huggingface.co/datasets/Nachammai41/underserved-persona_conditioned-fraud-v3)
— same schema, higher row-level narrative fidelity, 10-of-25 typology coverage.

## Archetypes

| Archetype | Personas | Key Dimensions | Primary Sources |
|---|---|---|---|
| Remittance | 12 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | Remitly 10-K, Menjívar 2022, Del Real 2022, Wise 2023, IAD 2026, FinCEN SAR Key Terms |
| Gig Worker | 12 | platform_mix, daily_cashout_pattern, device_stability, sim_history | Vallas & Schor 2020, FinCEN FTA 2024, Fed synthetic-ID, SAR ATO/BEC advisories |
| Unbanked | 10 | kiosk_location, prepaid_card_stack, income_source, documentation_status | FDIC 2023 HH Survey microdata, SAR_3PP / FTA T5 (v4 additions) |
| ITIN | 12 | business_type, tax_filing_history, credit_file_age, accountant_relationship | Menjívar 2022, Treasury OIG, IRS SOI, FinCEN SAR |

## Available Configs

**Transaction data:**
- `all` — 20,000 rows across all 4 archetypes
- `remittance` / `gig_worker` / `unbanked` / `itin` — 5,000 rows each

**Reference / attribution:**
- `personas` — 46 persona profiles with evidence grade, source IDs, family_crisis_history (v4 edits included)
- `sources` — 13-entry citation registry (with v4 unbanked archetype extension noted)
- `typology_registry` — 25 FinCEN typology codes with applies_to_fraud_vectors mapping

## Schema

Same 25 columns as v3. See v3 dataset card for field-by-field descriptions.
V4-specific columns (`persona_source_ids`, `fraud_vector_typology_ref`,
`behavioral_evidence_grade`) carry v4 values, recomputed from the edited
persona profiles.

## V4 Typology Coverage Table

| Code | Count | Notes |
|---|---:|---|
| SAR_ADVISORY_ELDER_FINANCIAL_EXPLOITATION | 326 | carries from v3 |
| SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD | 271 | **v4-new** via SAR-pref + ATO events |
| FTA_IDENTITY_2024_T1 (General Fraud) | 259 | |
| FTA_IDENTITY_2024_T10 (Scam) | 207 | shifted, portion redirected to SAR-specifics |
| SAR_ADVISORY_TAX_REFUND_FRAUD | 205 | |
| FTA_IDENTITY_2024_T13 (Synthetic Identity) | 197 | |
| FTA_IDENTITY_2024_T2 (False Records) | 101 | |
| FTA_IDENTITY_2024_T3 (Identity Theft) | 95 | |
| SAR_ADVISORY_BEC_FRAUD | 88 | **v4-new** via BEC events on gig_004/gig_006 |
| FTA_IDENTITY_2024_T14 (Kiting) | 86 | |
| SAR_ADVISORY_IVTS | 29 | **v4-new** via rem_004 hawala + rem_009 Bronx-merchant events |
| SAR_ADVISORY_COVID19_IMPOSTER_SCAMS | 25 | **v4-new** via rem_007 COVID + rem_010 money-mule events |
| SAR_ADVISORY_CYBER_EVENTS | 15 | **v4-new** via gig_012 phishing event |
| SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS | 15 | **v4-new** via unb_003 unauthorized-ACH event |
| FTA_IDENTITY_2024_T12 (False Claims) | 13 | **v4-new** via gig_008 false-chargeback event |
| SAR_ADVISORY_DISASTER_RELATED_FRAUD | 13 | **v4-new** via rem_002 + rem_011 hurricane events |
| SAR_ADVISORY_FUNNEL_ACCOUNT | 11 | **v4-new** via rem_012 funnel-account event |
| FTA_IDENTITY_2024_T5 (Circumventing Standards) | 7 | **v4-new** via unb_009 lax-KYC event |

Unexercised (7/25): FTA T4 (recoverable), FTA T6/T9/T11 (SAR shadow-dedupes),
FTA T7 Abuse of Access (insider concept), FTA T8 Refusal to Cooperate
(regulatory), SAR_HUMAN_TRAFFICKING (deliberately skipped as sensitive).

## License

Released under CC-BY-4.0 for research and educational purposes. Persona names
are fictional; biographical details are composed from published aggregate
source evidence. Any resemblance to real individuals is coincidental.

## Credits

- Adaption Labs — narrative fill (v3 narratives overlaid into v4)
- FinCEN — Financial Trend Analysis 2024 (Identity), SAR Advisory Key Terms
- FDIC — 2023 National Survey of Unbanked and Underbanked Households
- Menjívar, Agadjanian & Oh — "The Contradictions of Liminal Legality" (Soc Probl 2022)
- Del Real — "Seemingly inclusive liminal legality" (J Ethn Migr Stud 2022)
- Vallas & Schor — "What Do Platforms Do?" (Annu Rev Sociol 2020)
- Remitly, Wise, Inter-American Dialogue, Oxfam America, IRS SOI, Treasury
  OIG, Federal Reserve FedPayments Improvement — industry & regulatory sources
- Tab-DDPM — Gaussian multinomial diffusion for tabular data
