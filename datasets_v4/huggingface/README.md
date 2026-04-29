---
license: cc-by-4.0
task_categories:
  - tabular-classification
  - text-generation
language:
  - en
  - es
  - vi
  - wo
  - yo
  - hi
  - fr
  - ko
  - zh
  - ru
  - tw
  - am
  - ar
  - ta
  - ja
  - te
  - fil
  - mr
  - ceb
  - gu
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
  - chain-of-thought
pretty_name: Persona-Conditioned Fraud Detection (v4 + v4.1, Full Typology Coverage)
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
  - config_name: cot_reasoning
    data_files:
      - split: train
        path: data/cot_reasoning/train.parquet
---

# Persona-Conditioned Fraud Detection Dataset (v4 + v4.1, Full Typology Coverage)

A 20,300-row citation-grounded synthetic fraud-narrative dataset for four
underserved US financial-system archetypes — **remittance**, **gig_worker**,
**unbanked**, **ITIN** — with **all 25 FinCEN typology codes exercised**.

## What's new vs v3

V3 covered 10 of 25 FinCEN typology codes. **v4 closed the gap to 18/25**
through three targeted changes:

1. **16 persona edits** documenting fraud events (SIM-swap, BEC, hawala/IVTS,
   hurricane scams, money-mule, synthetic-ID, unauthorized-ACH, lax-KYC,
   false-chargeback, COVID-imposter). 8 grade upgrades D→B.
2. **SAR-preference resolver** picks the more-specific SAR Advisory code
   when both an FTA Identity code and a SAR Advisory match a fraud_vector.
3. **Combined 20k Adaption narrative fill** — single job, 20 native scripts,
   per-row persona/transaction context.

**v4.1 closed the remaining gap to 25/25** through:

1. **Strip prompt-tag leakage** from 1,235 narratives (Adaption was echoing
   the upload metadata block into completions for ~6% of rows).
2. **Re-stamp 4 shadowed FTA codes** (T4, T6, T9, T11) on a half-cap subset
   so both the FTA and SAR equivalents carry rows. No Adaption credits.
3. **Add 3 truly-missing codes** (T7 Abuse of Access, T8 Refusal to Cooperate,
   SAR_HUMAN_TRAFFICKING) via persona-event additions on `unb_001`,
   `gig_001`, `itin_010` + 300 synthetic transactions narrated by Adaption.
4. **Refill 51/52 empty narratives** by resubmitting the original prompts.

## Quick start

```python
from datasets import load_dataset

repo = "Nachammai41/underserved-persona_conditioned-fraud-v4"  # TBD

ds       = load_dataset(repo, name="all")["train"]                  # 20,300 rows
remit    = load_dataset(repo, name="remittance")["train"]           #  5,000 rows
gig      = load_dataset(repo, name="gig_worker")["train"]           #  5,100 rows
unbanked = load_dataset(repo, name="unbanked")["train"]             #  5,100 rows
itin     = load_dataset(repo, name="itin")["train"]                 #  5,100 rows
personas = load_dataset(repo, name="personas")["train"]             #     46 rows
sources  = load_dataset(repo, name="sources")["train"]              #     13 rows
typology = load_dataset(repo, name="typology_registry")["train"]    #     25 rows
cot      = load_dataset(repo, name="cot_reasoning")["train"]        #  3,926 rows (SFT companion)
```

## Dataset Statistics

| Metric | Value |
|---|---|
| Total transactions | **20,300** |
| Per-archetype rows | remittance 5,000 / gig_worker 5,100 / unbanked 5,100 / itin 5,100 |
| Total personas | 46 (12/12/10/12) |
| Sources in registry | 13 (7 PDFs + 1 data bundle + 5 links) |
| FinCEN typology codes | 25 registered, **all 25 exercised** |
| Languages | 20 tagged, 29 detected, 92.8% tag↔detect match |
| Fraud rate | ~11.1% (2,263 of 20,300 rows) |
| Overall persona grade | A 6.3% / **B 58.3%** / C 22.9% / **D 12.5%** |
| Narrative fill rate | 99.81% (39 empty rows of 20,300) |
| Prompt-tag leakage | 0 (post-strip) |

## Narrative quality

Combined 20k Adaption fresh fill recovers row-level signals that an overlay
approach would have lost:

| Signal | v3 | v4 | Note |
|---|---:|---:|---|
| Corridor keyword | 71.4% | 68.4% | persona-level, stable |
| Platform name | 42.7% | 41.6% | persona-level, stable |
| Day of week | 47.4% | 43.6% | row-level, recovered |
| Instrument | 37.7% | 37.6% | row-level, recovered |
| Amount (rounded) | 35.9% | 27.4% | row-level |
| Amount (exact) | 28.5% | 19.1% | row-level |
| Hour class | 35.9% | 38.4% | row-level, recovered |
| Language tag↔detect | 92.1% | 92.8% | row-level, recovered |

## Archetypes

| Archetype | Personas | Key Dimensions | Primary Sources |
|---|---|---|---|
| Remittance | 12 | corridor_country, transfer_service_loyalty, family_crisis_history, sender_tenure | Remitly 10-K, Menjívar 2022, Del Real 2022, Wise 2023, IAD 2026, FinCEN SAR Key Terms |
| Gig Worker | 12 | platform_mix, daily_cashout_pattern, device_stability, sim_history | Vallas & Schor 2020, FinCEN FTA 2024, Fed synthetic-ID, SAR ATO/BEC advisories |
| Unbanked | 10 | kiosk_location, prepaid_card_stack, income_source, documentation_status | FDIC 2023 HH Survey microdata, SAR_3PP / FTA T5 (v4 additions) |
| ITIN | 12 | business_type, tax_filing_history, credit_file_age, accountant_relationship | Menjívar 2022, Treasury OIG, IRS SOI, FinCEN SAR |

## Available Configs

**Transaction data:**
- `all` — 20,300 rows across all 4 archetypes
- `remittance` (5,000) / `gig_worker` (5,100) / `unbanked` (5,100) / `itin` (5,100)

**Reference / attribution:**
- `personas` — 46 persona profiles with grade, source IDs, family_crisis_history
- `sources` — 13-entry citation registry
- `typology_registry` — 25 FinCEN typology codes with applies_to_fraud_vectors

**SFT companion:**
- `cot_reasoning` — 3,926 rows (1,963 fraud + 1,963 matched non-fraud) with chain-of-thought reasoning traces; A-graded by Adaption (E → A, +92%), 100% trace fill

## Schema

Same 25 columns as v3, plus three universal grounding columns
(`persona_source_ids`, `fraud_vector_typology_ref`,
`behavioral_evidence_grade`). See `dataset_card.md` for field-by-field
descriptions.

## V4 + v4.1 Typology Coverage Table (all 25 codes)

| Code | Count | Source |
|---|---:|---|
| SAR_ADVISORY_ELDER_FINANCIAL_EXPLOITATION | 326 | inherited from v3 |
| FTA_IDENTITY_2024_T1 (General Fraud) | 259 | broad coverage |
| FTA_IDENTITY_2024_T10 (Scam) | 207 | redirected to SAR-specifics |
| SAR_ADVISORY_TAX_REFUND_FRAUD | 205 | inherited |
| FTA_IDENTITY_2024_T13 (Synthetic Identity) | 197 | inherited |
| SAR_ADVISORY_ACCOUNT_TAKEOVER_FRAUD | 171 | SAR-pref + gig_001/gig_011 |
| FTA_IDENTITY_2024_T2 (False Records) | 101 | inherited |
| FTA_IDENTITY_2024_T6 (Account Takeover) | 100 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_HUMAN_TRAFFICKING | 100 | **v4.1** itin_010 wage_confiscation event |
| FTA_IDENTITY_2024_T8 (Refusal to Cooperate) | 100 | **v4.1** gig_001 platform_refusal event |
| FTA_IDENTITY_2024_T7 (Abuse of Access) | 100 | **v4.1** unb_001 POA_abuse event |
| FTA_IDENTITY_2024_T3 (Identity Theft) | 95 | inherited |
| FTA_IDENTITY_2024_T14 (Kiting) | 86 | inherited |
| FTA_IDENTITY_2024_T11 (BEC) | 44 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_BEC_FRAUD | 44 | gig_004/gig_006 BEC events |
| SAR_ADVISORY_IVTS | 29 | rem_004 + rem_009 IVTS/hawala |
| SAR_ADVISORY_COVID19_IMPOSTER_SCAMS | 17 | rem_007 + rem_010 |
| SAR_ADVISORY_THIRD_PARTY_PAYMENT_PROCESSORS | 15 | unb_003 unauthorized-ACH |
| FTA_IDENTITY_2024_T12 (False Claims) | 13 | gig_008 false-chargeback |
| SAR_ADVISORY_DISASTER_RELATED_FRAUD | 13 | rem_002 + rem_011 hurricane |
| SAR_ADVISORY_FUNNEL_ACCOUNT | 11 | rem_012 |
| FTA_IDENTITY_2024_T4 (Third-Party ML) | 8 | **v4.1** half-cap re-stamp |
| SAR_ADVISORY_CYBER_EVENTS | 8 | gig_012 phishing |
| FTA_IDENTITY_2024_T9 (Cyber Incident) | 7 | **v4.1** half-cap re-stamp |
| FTA_IDENTITY_2024_T5 (Circumventing Standards) | 7 | unb_009 lax-KYC |

Total fraud rows: 2,263. **All 25 codes carry rows.**

## Companion: CoT reasoning dataset (`cot_reasoning` config)

A **3,926-row chain-of-thought dataset** (1,963 fraud + 1,963 matched
non-fraud) generated for SFT / judge training. Each row pairs a v4
transaction with a reasoning trace produced by Adaption's
`reasoning_traces` recipe. Adaption quality grade: **E → A (+92%)**,
100% trace fill.

```python
cot = load_dataset(repo, name="cot_reasoning")["train"]
cot[0]["cot_reasoning_trace"]    # step-by-step reasoning
cot[0]["cot_completion"]         # final verdict + supporting analysis
cot[0]["narrative_text"]         # the v4 narrative under review
cot[0]["is_fraud"]               # the ground-truth label the trace reasons toward
```

### Schema (additional columns vs the transaction configs)

| Field | Type | Description |
|---|---|---|
| `cot_completion` | string | Final verdict + analysis emitted by the reasoning recipe |
| `cot_reasoning_trace` | string | Step-by-step reasoning produced by Adaption |
| `enhanced_prompt` | string | Adaption's rephrased prompt (audit trail) |
| `amount_band` | category | Band used for fraud/non-fraud matching (xs/s/m/l/xl) |

All other columns are inherited from the parent v4 transaction row, so
you can join `cot_reasoning` to `all` on `data_uuid` if you need
additional context.

### Suggested uses

- **SFT for fraud-analyst LLMs**: train a model to emit reasoning traces
  given (transaction metadata + narrative) → verdict.
- **LLM-as-judge fine-tuning**: distill the reasoning style into a
  smaller model used for evaluation pipelines.
- **CoT data augmentation**: combine with the 20,300-row bundle for
  mixed reasoning + narrative-only training.

The CoT subset is independent of the 20,300-row bundle — selecting
`cot_reasoning` does not duplicate rows from `all`.

## License

Released under CC-BY-4.0 for research and educational purposes. Persona
names are fictional; biographical details are composed from published
aggregate source evidence. Any resemblance to real individuals is
coincidental.

## Credits

- **Adaption Labs** — narrative fill (combined 20k v4 job + v4.1 patch + CoT job)
- **FinCEN** — Financial Trend Analysis 2024 (Identity), SAR Advisory Key Terms
- **FDIC** — 2023 National Survey of Unbanked and Underbanked Households
- **Menjívar, Agadjanian & Oh** — "The Contradictions of Liminal Legality" (Soc Probl 2022)
- **Del Real** — "Seemingly inclusive liminal legality" (J Ethn Migr Stud 2022)
- **Vallas & Schor** — "What Do Platforms Do?" (Annu Rev Sociol 2020)
- **Remitly, Wise, Inter-American Dialogue, Oxfam America, IRS SOI, Treasury OIG, Federal Reserve FedPayments Improvement** — industry & regulatory sources
- **Tab-DDPM** — Gaussian multinomial diffusion for tabular data