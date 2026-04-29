# datasets_v4

Citation-grounded synthetic fraud-narrative dataset for four underserved
US financial-system archetypes: **remittance**, **gig_worker**, **unbanked**,
**itin**. Builds on `datasets_v3/`; the v4.1 patch layer (in `v4_1/`)
closes typology coverage to 25/25.

## Headline numbers (post-v4.1)

| Metric | Value |
|---|---|
| Rows | 20,300 |
| Personas | 46 (3 patched in v4.1 with new fraud-event grounding) |
| Languages | 20 tagged, 29 detected, 92.8% tag↔detect match (see list below) |
| Typology coverage | **25 / 25** FinCEN codes (was 18 / 25 at v4 close) |
| Fraud / legit | 2,263 fraud / 18,037 legit |
| Empty narratives | 39 (~0.19%) |
| Prompt-tag leakage | 0 (stripped from 1,235 narratives) |

A separate **CoT reasoning dataset** (3,926 rows: all fraud + matched legit)
lives at `reasoning/cot_dataset.parquet` for SFT use; A-graded by Adaption.

## Languages (20 tagged)

| Code | Language | Rows |
|---|---|---:|
| en | English | 12,164 |
| es | Spanish | 3,693 |
| vi | Vietnamese | 683 |
| wo | Wolof | 390 |
| yo | Yoruba | 388 |
| hi | Hindi | 296 |
| fr | French | 256 |
| ko | Korean | 228 |
| zh | Chinese | 218 |
| ru | Russian | 215 |
| tw | Twi | 207 |
| am | Amharic | 206 |
| ar | Arabic | 205 |
| ta | Tamil | 202 |
| ja | Japanese | 189 |
| te | Telugu | 188 |
| fil | Filipino | 149 |
| mr | Marathi | 145 |
| ceb | Cebuano | 142 |
| gu | Gujarati | 136 |

`detected_language_hints` column captures runtime-detected languages (29
distinct, including Somali, Swahili, Indonesian, and others picked up by
langdetect on phrase fragments).

## Where things live

```
datasets_v4/
├── README.md                       this file
├── ARCHITECTURE.md                 full pipeline walkthrough (v3 → v4)
├── DISTRIBUTION_METRICS.md         sampling, grades, typology, propagation
├── exports/
│   ├── transactions_v4_20k.parquet  ← canonical 20,300-row bundle
│   ├── transactions_v4_20k.csv
│   ├── personas_all.json            46 personas, nested by archetype
│   ├── sources.json / typology_registry.json
│   ├── coverage.json / analysis_report.json
│   └── dataset_card.md              HF-style card
├── sources/                         13-entry citation registry (inherits v3)
├── {archetype}/
│   ├── personas/persona_profiles.json   archetype's personas
│   ├── synthetic/transactions.parquet   TabDDPM v4 generator output
│   └── adaptive/transactions_adapted.parquet   final fresh-narrative artifact
├── adaptive_combined/               20k Adaption combined-job inputs/outputs
├── reasoning/                       CoT dataset (3,926 rows) for SFT
├── v4_1/                            v4.1 patch layer (see v4_1/README.md)
└── huggingface/                     8 HF dataset configs + card
```

## Quick start

```python
import pandas as pd
df = pd.read_parquet("datasets_v4/exports/transactions_v4_20k.parquet")

print(df.shape)                       # (20300, ~25)
print(df["archetype"].value_counts())
print(df[df.is_fraud == 1]["fraud_vector_typology_ref"].value_counts())
```

For the CoT subset:

```python
cot = pd.read_parquet("datasets_v4/reasoning/cot_dataset.parquet")
# Columns include: cot_completion, cot_reasoning_trace + the v4 row metadata
```

## How v4 was built

Start from v3 personas + sources. Apply 16 persona edits to expand fraud-event
coverage (8 grade upgrades D→B). Run TabDDPM v4 generator with the
SAR-advisory-preferred resolver and 9 new fraud-event regex patterns. Submit
all 20,000 prompts as a single combined Adaption narrative-fill job. Strip
the prompt-tag leakage that ~6% of rows came back with. Apply the v4.1
patch layer to close typology coverage from 18/25 to 25/25 (re-stamp
shadowed FTA codes + add 3 truly-missing codes via persona events + 300 new
synthetic rows). Refill empty narratives. Build the CoT subset.

Detailed walkthrough: `ARCHITECTURE.md`. Distribution and coverage tables:
`DISTRIBUTION_METRICS.md`. v4.1 patch layer: `v4_1/ARCHITECTURE.md`.

## Reproducing

Tracked in git: scripts under `src/personas_v4/`, persona JSONs, sources,
typology registry, exports JSON, run-metadata files, small prompt JSONLs.

Not tracked (regeneratable from `dataset_id` via the wrappers in
`src/personas_v4/*adaption_job.py` if your Adaption account still holds them):
- `adaptive_combined/{adapted_output,for_adaption}.jsonl`
- `reasoning/{adapted_output,for_reasoning}.jsonl`
- `v4_1/{adapted_output,combined_upload}.jsonl`
- All `*.parquet` and `*.csv` (covered by global gitignore rules)

The bundle is rebuilt deterministically by
`python src/personas_v4/export_dataset.py` from the per-archetype
`adaptive/transactions_adapted.parquet` files.
