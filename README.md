# Fraud Detection Framework — An Agentic RAG Pipeline with Custom Financial SLM

An end-to-end fraud detection system combining **LightGBM**, **Neo4j graph analytics**, **ChromaDB RAG**, and **NGBoost uncertainty estimation** on the Kaggle IEEE-CIS Fraud Detection dataset.

## Architecture

```
Kaggle IEEE Dataset (590K transactions)
        |
        v
+------------------+     +-------------------+     +-------------------+
|  Kafka Producer  | --> |   Kafka Broker    | --> |  Kafka Consumer   |
|  (streaming)     |     |  (transactions)   |     |  (LightGBM)       |
+------------------+     +-------------------+     +--------+----------+
                                                            |
                                                   fraud-alerts topic
                                                            |
                                                            v
+------------------+     +-------------------+     +-------------------+
|  Neo4j + GDS     | --> | Graph Features    | --> |  RAG Enricher     |
|  (PageRank,      |     | (22 features)     |     |  (ChromaDB query) |
|   Louvain)       |     +-------------------+     +--------+----------+
+------------------+                                        |
                                                            v
+------------------+     +-------------------+     fraud-alerts-enriched
|  ChromaDB        | <-- | Chroma Indexer    |          topic
|  (4 collections) |     | (batch vectorize) |
+------------------+     +-------------------+
```

## Model Performance

| Model | AUC-ROC | Features |
|-------|---------|----------|
| LightGBM (tabular only) | 0.9143 | 424 |
| + 14 Neo4j graph features | 0.9425 | 438 |
| **+ 22 graph features (with 2-hop)** | **0.9486** | **446** |
| NGBoost standalone (120K subsample) | 0.9292 | 446 |
| NGBoost + LightGBM ensemble | 0.9424 | 449 |

## Project Structure

```
Fraud Detection Framework/
|-- Fraud_Detection_Kaggle_IEEE_Dataset.ipynb   # EDA & model development notebook
|-- Fraud_Detection_Kaggle_IEEE_Dataset.py      # Python script version
|-- Kaggle-IEEE-dataset/                        # IEEE-CIS dataset (590K transactions)
|-- data/processed/                             # Generated feature matrices
|   |-- feature_matrix.parquet                  # Tabular + graph features (446 cols)
|   |-- graph_features.parquet                  # Graph-only features (22 cols)
|   |-- graph_features.csv                      # CSV for inspection
|   |-- explore.py                              # Streamlit viewer
|   `-- view_parquet.py                         # CLI parquet viewer
|-- scripts/
|   |-- merge_features.py                       # Merge graph + tabular features locally
|   `-- ensemble_train.py                       # NGBoost + LightGBM stacked ensemble
`-- fraud-detection-pipeline/                   # Dockerized pipeline (see below)
```

## Key Components

### 1. Neo4j Graph Analytics

The transaction and identity data is loaded into Neo4j as a property graph with 5 node types and 6 relationship types:

**Graph Model:**
- `:Transaction` -- `:Card` -- `:Address` -- `:EmailDomain` -- `:Device`
- Relationships: `USED_CARD`, `FROM_ADDRESS`, `SENT_FROM_EMAIL`, `SENT_TO_EMAIL`, `USED_DEVICE`, `LINKED_TO_ADDRESS`

**GDS Algorithms:**
- **PageRank** — Identifies hub-connected transactions. Top 20% PageRank transactions have 2.1x the average fraud rate (7.38% vs 3.50%).
- **Louvain Community Detection** — Groups transactions into ~39 communities by shared entities. High-risk communities (>10% fraud rate) are strong fraud signals.

**22 Graph Features Extracted:**

| Category | Features | Description |
|----------|----------|-------------|
| GDS | `communityId`, `pageRank` | Louvain community + PageRank score |
| Community | `communitySize`, `communityFraudRate`, `communityAvgAmount`, `communityStdAmount` | Per-community aggregates |
| Card | `cardDegree`, `cardFraudRate`, `numDevicesOnCard`, `addressesPerCard`, `fraudOnSameCard` | Card-level stats |
| 2-hop | `neighborCardFraudRate`, `neighborCardCount` | Fraud rate of cards sharing same address |
| Address | `addrDegree`, `addrFraudRate`, `numCardsAtAddress` | Address-level stats |
| Email | `emailDegree`, `emailFraudRate`, `cardsPerEmail` | Email domain stats |
| Device | `deviceDegree`, `deviceFraudRate` | Device fingerprint stats |
| Cross-entity | `maxEntityFraudRate` | Max fraud rate across all connected entities |

**Top graph features by importance (LightGBM gain):**
1. `cardFraudRate` — 3,293,442
2. `maxEntityFraudRate` — 449,753
3. `fraudOnSameCard` — 216,162
4. `pageRank` — 157,572
5. `deviceFraudRate` — 129,445

### 2. ChromaDB RAG Pipeline

ChromaDB provides semantic search over fraud intelligence, enabling the RAG enricher to add context to every fraud alert.

**4 Collections:**

| Collection | Documents | Content |
|------------|-----------|---------|
| `fraud_cases` | ~20,663 | One doc per historical fraud — amount, card, email, community stats, PageRank |
| `community_profiles` | ~39 | Louvain community risk profiles with fraud rates and classifications |
| `entity_risk_profiles` | ~13,885 | Per-card and per-address risk profiles with degree, fraud rate, risk level |
| `fraud_patterns` | ~30-50 | Aggregated pattern rules (e.g., "Transactions 2am-5am have 6.1% fraud rate") |

**Embedding Model:** `all-MiniLM-L6-v2` (384-dim, runs locally — no API keys needed)

**RAG Enricher Flow:**
1. Consumes from `fraud-alerts` Kafka topic
2. Queries ChromaDB for top-5 similar historical frauds, community context, entity risk profiles, and matching patterns
3. Publishes enriched alert with `rag_context` to `fraud-alerts-enriched` topic

### 3. NGBoost Uncertainty Estimation

NGBoost provides calibrated probabilistic predictions — not just a fraud score, but a confidence estimate.

- **Standalone AUC:** 0.9292 (on 120K subsample — competitive given data limitation)
- **Stacked Ensemble:** NGBoost OOF predictions used as features for LightGBM
- **Key Value:** Uncertainty estimates (`ngb_variance`) for analyst triage — high-confidence alerts can be auto-actioned, low-confidence ones need human review

**Ensemble Script:** `scripts/ensemble_train.py` — 5-fold CV NGBoost + LightGBM stacking

### 4. Real-Time Kafka Pipeline

- **Producer** streams transactions at configurable TPS (default: 10)
- **Consumer** runs LightGBM inference per transaction, publishes fraud alerts
- **RAG Enricher** adds ChromaDB context to each alert
- **Kafka UI** at `localhost:8080` for monitoring all topics

## Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `zookeeper` | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka coordination |
| `kafka` | confluentinc/cp-kafka:7.5.0 | 9092, 29092 | Message broker |
| `kafka-ui` | provectuslabs/kafka-ui | 8080 | Monitoring dashboard |
| `neo4j` | neo4j:5.26-community | 7474, 7687 | Graph database + GDS |
| `chromadb` | chromadb/chroma:0.5.23 | 8000 | Vector database |
| `graph-loader` | custom | — | Loads CSV data into Neo4j |
| `feature-exporter` | custom | — | Runs GDS algorithms, exports graph features |
| `chroma-indexer` | custom | — | Indexes fraud intelligence into ChromaDB |
| `rag-enricher` | custom | — | Enriches fraud alerts with RAG context |
| `producer` | custom | — | Streams transactions to Kafka |
| `consumer` | custom | — | LightGBM inference + fraud alerting |

## Quick Start

```bash
cd fraud-detection-pipeline/

# 1. Start infrastructure
docker compose up zookeeper kafka neo4j chromadb kafka-ui -d

# 2. Load graph and extract features
docker compose up graph-loader
docker compose run --rm feature-exporter

# 3. Merge features and train model (local)
cd ..
python scripts/merge_features.py
python fraud-detection-pipeline/scripts/train_and_export_model.py

# 4. Index fraud intelligence into ChromaDB
cd fraud-detection-pipeline/
docker compose up chroma-indexer --build

# 5. Run the full pipeline
docker compose up producer consumer rag-enricher --build
```

## Dataset

[Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/c/ieee-fraud-detection)
- 590,540 transactions, 394 features
- 144,233 identity records (24.4% coverage)
- Binary target: `isFraud` (3.50% fraud rate)

## Tech Stack

- **ML:** LightGBM, NGBoost, scikit-learn
- **Graph:** Neo4j, Graph Data Science (GDS) library
- **Vector DB:** ChromaDB, sentence-transformers
- **Streaming:** Apache Kafka
- **Containerization:** Docker Compose
- **Data:** pandas, PyArrow, NumPy
