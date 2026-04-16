# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout — Two Distinct Projects

This repo contains two largely independent projects, separated by branch but coexisting on disk:

1. **Uncharted Data Challenge pipeline** (branch `unchartered_data_challenge`, currently checked out): Synthetic fraud-narrative dataset generation for 4 underserved archetypes (`remittance`, `gig_worker`, `unbanked`, `itin`). Lives in `src/`, `notebooks/generation/`, `datasets/`, `lib/tab-ddpm/`.
2. **Original Fraud Detection Framework** (branch `main`): Real-time fraud detection on the Kaggle IEEE-CIS dataset using LightGBM + Neo4j graph features + ChromaDB RAG, plus an NGBoost-stacked ensemble. Lives in `fraud-detection-pipeline/`, `scripts/`, `data/processed/`, `Kaggle-IEEE-dataset/`, and the root notebook/script `Fraud_Detection_Kaggle_IEEE_Dataset.{ipynb,py}`.

When making changes, identify which project the task touches — they share no code and have separate dependencies.

## Project 1: Uncharted Data Challenge (current branch)

### Pipeline architecture
The pipeline is a 6-stage flow where each stage's output feeds the next; each stage has its own CLI script under `src/`:

```
scrapers (Reddit/CFPB/BBB)  ─►  merge_sources.py  ─►  seed_narratives.jsonl
                                                              │
profile_configs.py + schema.py (31 canonical fields) ─────────┤
                                                              ▼
                                        tabddpm_generator.py (Gaussian diffusion
                                        for numeric cols; profile-weighted sampling
                                        for categoricals — avoids multinomial mode collapse)
                                                              │
                                                              ▼  transactions.parquet (no narratives)
                                        adaptive_submit → adaptive_check → adaptive_download
                                        (Adaption Labs API fills narrative_text per row,
                                        prompt context = fraud_vector + language + instrument + amount)
                                                              │
                                                              ▼  transactions_adapted.parquet
                                        adaptive_reasoning.py (optional: 100 CoT traces / archetype)
```

Per-archetype outputs are written under `datasets/{archetype}/{synthetic,adaptive,reasoning}/`. Job state for the async Adaption Labs API is tracked in `datasets/adaption_jobs.json` and `datasets/adaption_reasoning_jobs.json` — `adaptive_submit.py` is fire-and-forget and writes job IDs there; `adaptive_check.py` and `adaptive_download.py` read them back.

### Key invariants when editing
- `src/scrapers/schema.py` defines the canonical 31-field schema (8 universal + 23 source-extension fields). All scraper output and synthetic generator output must validate against it.
- `src/scrapers/profile_configs.py` defines per-archetype behavioral distributions (fraud-vector weights, language mix, instruments, demographics). Tab-DDPM uses these for categorical sampling — changes here affect the realism of generated rows.
- Tab-DDPM core is vendored under `lib/tab-ddpm/` (modified). Don't treat it as upstream.

### Common commands
```bash
# Full scrape (no API keys required)
python src/scrapers/run_all_scrapers.py
python src/scrapers/merge_sources.py

# Tab-DDPM generation — local CPU is slow; use notebooks/generation/tabddpm_colab.ipynb on A100
python src/generators/tabddpm_generator.py --epochs 700 --samples_per_archetype 5000

# Adaption Labs narrative fill (requires ADAPTION_API_KEY)
python src/generators/adaptive_data.py --all --estimate
python src/generators/adaptive_submit.py
python src/generators/adaptive_check.py
python src/generators/adaptive_download.py

# Reasoning traces
python src/generators/adaptive_reasoning.py --{estimate,submit,check,download}

# QA
python src/generators/verify_language.py --all
python src/generators/export_csv.py
```

### Dependencies
```bash
pip install torch scikit-learn pandas pyarrow requests beautifulsoup4 adaption langdetect
```

## Project 2: Fraud Detection Framework (main branch)

### Architecture
Dockerized streaming inference — see `fraud-detection-pipeline/README.md` for full service catalog. Big picture: a Kafka producer streams Kaggle IEEE transactions; a LightGBM consumer scores them; a RAG enricher annotates alerts with ChromaDB context (similar historical frauds, community profiles, entity risk, fraud patterns); Neo4j holds a property graph used to compute 22 graph features (PageRank + Louvain via GDS) that are merged into the training feature matrix.

Topics: `transactions` → `fraud-alerts` → `fraud-alerts-enriched`. Kafka UI at `:8080`, Neo4j browser at `:7474` (creds `neo4j` / `fraud_detection`), ChromaDB at `:8000`.

### Training flow
1. `Fraud_Detection_Kaggle_IEEE_Dataset.{ipynb,py}` (repo root) — main feature engineering + LightGBM training. Reads `Kaggle-IEEE-dataset/`, writes `data/processed/feature_matrix.parquet`.
2. `fraud-detection-pipeline/graph-loader/` — loads CSVs into Neo4j, runs PageRank/Louvain, exports 22 graph features.
3. `scripts/merge_features.py` — joins graph features into the base feature matrix.
4. `scripts/ensemble_train.py` — 5-fold OOF NGBoost (uncertainty estimates) → stacked into LightGBM. Compares LightGBM-only vs. ensemble AUC. Subsample/estimator constants at top of file (`NGB_SUBSAMPLE`, `NGB_ESTIMATORS`, `NGB_EARLY_STOP`).
5. `fraud-detection-pipeline/scripts/train_and_export_model.py` — exports the production model artifacts to `fraud-detection-pipeline/model/` (`fraud_model.txt`, `feature_names.json`, `label_encoders.json`).

### Common commands
```bash
# Bring up the pipeline
docker compose -f fraud-detection-pipeline/docker-compose.yml up -d

# Train ensemble (requires data/processed/feature_matrix.parquet)
python scripts/ensemble_train.py
```

## Cross-cutting notes

- The two projects share the directory but **not** dependencies; install per-project.
- `submission.csv` at repo root is a Kaggle submission artifact for project 2.
- `notebooks/{benchmarks,finetuning,scraping}/` directories are currently empty placeholders.