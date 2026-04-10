# Uncharted Data Challenge — Fraud Detection for Underserved Communities

Synthetic fraud detection dataset targeting **4 underserved archetypes** that are underrepresented in existing financial crime datasets. Built for the [Adaption Labs Uncharted Data Challenge](https://www.adaptionlabs.ai/blog/the-uncharted-data-challenge).

## The Problem

Fraud detection models are trained almost exclusively on mainstream banking data. Communities that rely on informal remittances, gig economy payments, prepaid cards, or ITIN-based transactions are left unprotected. This project fills that gap.

## 4 Archetypes

| Archetype | Description | Fraud Vectors | Languages |
|-----------|-------------|---------------|-----------|
| **Remittance** | Cross-border money transfer fraud targeting immigrant communities | Wire transfer, exchange rate, emergency, interception, estafa | en, es, vi, yo, hi, ht |
| **Gig Worker** | Account takeover and payment fraud targeting gig economy workers | ATO, SIM swap, OTP, stolen, hacked, fake support | en, hi, vi, es, yo |
| **Unbanked** | Prepaid card, payday loan, and kiosk fraud targeting unbanked populations | Predatory, prepaid, kiosk, advance fee, fake loan, hawala | en, vi, yo, es, hi |
| **ITIN** | Identity theft, tax fraud, and synthetic identity targeting ITIN holders | ITIN, EIN, identity theft, synthetic identity, tax return | en, vi, ta, es |

## Pipeline

```
Scrapers (Reddit + CFPB + BBB)          Profile Configs
    |   1,040 seed narratives               |   Behavioral distributions
    v                                       v
Schema (31 fields)                   Tab-DDPM (Gaussian diffusion)
    |                                       |   5,000 synthetic transactions
    v                                       v   per archetype (20,000 total)
Merge Sources                        Adaption Labs API
    |                                       |   15,076 AI-generated narratives
    v                                       |   + 390 reasoning traces
Seed Narratives                      Final Adapted Dataset
    (JSONL per archetype)                (parquet + CSV per archetype)
```

## Dataset Summary

| Metric | Value |
|--------|-------|
| Total synthetic records | 20,000 (5,000 per archetype) |
| Narratives generated | 15,076 by Adaption Labs + 4,924 reused from pool |
| Reasoning traces | 390 (100 sampled per archetype) |
| Seed narratives scraped | 1,040 from Reddit, CFPB, BBB |
| Languages covered | 8 (en, es, hi, ta, ta-en, ht, yo, vi) |
| Fraud rate | ~10% across all archetypes |
| Schema fields | 31 (8 universal + 23 source extensions) |
| Adaption quality score | E (5.0) -> A (9.2-9.4), 82-88% improvement |

## Project Structure

```
Fraud Detection Framework/
|-- datasets/
|   |-- {archetype}/
|   |   |-- adaptive/
|   |   |   |-- transactions_adapted.parquet      # Final dataset (narratives filled)
|   |   |   |-- transactions_adapted_{arch}.csv   # CSV for viewing
|   |   |   |-- adapted_output.jsonl              # Raw Adaption response
|   |   |   |-- prompt_reference.csv              # Prompt/enhanced_prompt reference
|   |   |   `-- for_adaption.jsonl                # Uploaded to Adaption
|   |   |-- reasoning/
|   |   |   |-- reasoning_{arch}.csv              # Reasoning traces (100 samples)
|   |   |   `-- reasoning_output.jsonl            # Raw reasoning response
|   |   `-- synthetic/
|   |       |-- transactions.parquet              # Tab-DDPM output (pre-adaptation)
|   |       |-- transactions_{arch}.csv           # CSV version
|   |       `-- generation_summary.json           # Generation stats
|   |-- adaption_jobs.json                        # Job tracker (narrative generation)
|   `-- adaption_reasoning_jobs.json              # Job tracker (reasoning traces)
|
|-- src/
|   |-- scrapers/
|   |   |-- web_scraper.py             # Pullpush.io (Reddit archive) scraper
|   |   |-- cfpb_scraper.py            # CFPB complaint database scraper
|   |   |-- bbb_scraper.py             # BBB Scam Tracker scraper
|   |   |-- merge_sources.py           # Merge all scraped JSONL per archetype
|   |   |-- run_all_scrapers.py        # Master scraper runner
|   |   |-- schema.py                  # 31-field canonical schema + validation
|   |   |-- profile_configs.py         # Behavioral profiles per archetype
|   |   |-- README.md                  # Scraper documentation
|   |   `-- datasets/                  # Scraped seed narratives (1,040 records)
|   |
|   `-- generators/
|       |-- tabddpm_generator.py       # Hybrid Tab-DDPM generator
|       |-- adaptive_data.py           # Adaption Labs integration (main)
|       |-- adaptive_submit.py         # Fire-and-forget job submission
|       |-- adaptive_check.py          # Job status checker
|       |-- adaptive_download.py       # Download + merge adapted results
|       |-- adaptive_reasoning.py      # Reasoning traces pipeline
|       |-- verify_language.py         # Language verification via langdetect
|       `-- export_csv.py              # Parquet to CSV exporter
|
|-- notebooks/
|   `-- generation/
|       |-- tabddpm_colab.ipynb        # Colab Pro notebook (A100 GPU)
|       `-- tabddpm_output/            # Colab generation output (4 parquets)
|
`-- lib/
    `-- tab-ddpm/                      # Tab-DDPM library (Gaussian diffusion core)
```

## How It Works

### 1. Scraping (no API keys needed)

Three public sources, zero authentication:

| Source | What | Records |
|--------|------|---------|
| Pullpush.io | Reddit archive — fraud/scam posts from 40+ subreddits | 717 |
| CFPB | Consumer Financial Protection Bureau complaints | 187 |
| BBB Scam Tracker | Better Business Bureau scam reports | 136 |

```bash
python src/scrapers/run_all_scrapers.py
python src/scrapers/merge_sources.py
```

### 2. Schema & Profiles

**Schema** (`schema.py`): 31 fields — 8 universal (data_uuid, id, archetype, source, narrative_text, detected_language_hints, fraud_vector_hint, record_timestamp) + source-specific extensions.

**Profiles** (`profile_configs.py`): Behavioral distributions per archetype derived from scraped data — fraud vector weights, language mix, transaction patterns, instruments, demographics.

### 3. Synthetic Generation (Tab-DDPM Hybrid)

Gaussian diffusion for numerical columns + profile-weighted sampling for categoricals. This avoids multinomial diffusion mode-collapse.

```bash
# Local (CPU)
python src/generators/tabddpm_generator.py --epochs 700 --samples_per_archetype 5000

# Colab Pro (A100 GPU — recommended)
# Upload notebooks/generation/tabddpm_colab.ipynb
```

Output: 5,000 synthetic transactions per archetype with realistic amounts, fees, ages, hours — but empty `narrative_text`.

### 4. Narrative Generation (Adaption Labs)

Fills `narrative_text` using Adaption Labs API. Each row's fraud vector, language, instrument, and amount become prompt context.

```bash
export ADAPTION_API_KEY=sk-...

# Estimate credits
python src/generators/adaptive_data.py --all --estimate

# Submit all 4 archetypes
python src/generators/adaptive_submit.py

# Check status
python src/generators/adaptive_check.py

# Download and merge
python src/generators/adaptive_download.py
```

### 5. Reasoning Traces (optional)

Adds chain-of-thought reasoning to 100 sampled rows per archetype.

```bash
python src/generators/adaptive_reasoning.py --estimate
python src/generators/adaptive_reasoning.py --submit
python src/generators/adaptive_reasoning.py --check
python src/generators/adaptive_reasoning.py --download
```

### 6. Verification

```bash
python src/generators/verify_language.py --all
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Synthetic tabular data | Tab-DDPM (Gaussian diffusion) |
| Narrative generation | Adaption Labs API |
| Seed scraping | Pullpush.io, CFPB API, BBB Scam Tracker |
| Language detection | langdetect |
| Data formats | Parquet, JSONL, CSV |
| GPU training | Google Colab Pro (A100) |
| Languages | Python 3.9+ |

## Dependencies

```bash
pip install torch scikit-learn pandas pyarrow requests beautifulsoup4 adaption langdetect
```

## Credits

- [Adaption Labs](https://www.adaptionlabs.ai/) — Adaptive Data platform for narrative generation
- [Tab-DDPM](https://github.com/rotot0/tab-ddpm) — Denoising diffusion for tabular data
- [CFPB](https://www.consumerfinance.gov/) — Consumer complaint database
- [BBB Scam Tracker](https://www.bbb.org/scamtracker) — Public scam reports
- [Pullpush.io](https://pullpush.io/) — Reddit archive API

## Branch Info

This branch (`unchartered_data_challenge`) contains the full Uncharted Data Challenge pipeline. The `main` branch contains the original Fraud Detection Framework (LightGBM + Neo4j + ChromaDB + NGBoost on Kaggle IEEE dataset).
