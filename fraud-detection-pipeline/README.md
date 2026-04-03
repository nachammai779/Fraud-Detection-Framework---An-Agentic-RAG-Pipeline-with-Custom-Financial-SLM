# Fraud Detection Pipeline

Dockerized real-time fraud detection with Kafka streaming, Neo4j graph analytics, ChromaDB RAG, and LightGBM inference.

## Services

### Kafka Infrastructure
- **zookeeper** — Cluster coordination (port 2181)
- **kafka** — Message broker (ports 9092/29092)
- **kafka-init** — Creates topics: `transactions`, `fraud-alerts`, `fraud-alerts-enriched`, `transaction-metrics`
- **kafka-ui** — Web dashboard at `http://localhost:8080`

### Neo4j Graph Database
- **neo4j** — Graph DB with GDS plugin (browser: `http://localhost:7474`, bolt: `localhost:7687`)
  - Credentials: `neo4j` / `fraud_detection`
- **graph-loader** — Loads transaction/identity CSVs into Neo4j property graph (590K nodes, 1.9M relationships)
- **feature-exporter** — Runs PageRank + Louvain, exports 22 graph features to parquet

### ChromaDB Vector Database
- **chromadb** — Persistent vector store at `http://localhost:8000`
- **chroma-indexer** — Indexes 4 collections:
  - `fraud_cases` (~20K docs) — historical fraud profiles for similarity search
  - `community_profiles` (~39 docs) — Louvain community risk profiles
  - `entity_risk_profiles` (~14K docs) — card and address risk profiles
  - `fraud_patterns` (~40 docs) — aggregated fraud rules

### Application Services
- **producer** — Streams transactions from CSV to Kafka at configurable TPS
- **consumer** — LightGBM inference per transaction, publishes to `fraud-alerts`
- **rag-enricher** — Queries ChromaDB for context, publishes to `fraud-alerts-enriched`

## Graph Model

```
(:Transaction)-[:USED_CARD]->(:Card)
(:Transaction)-[:FROM_ADDRESS]->(:Address)
(:Transaction)-[:SENT_FROM_EMAIL]->(:EmailDomain)
(:Transaction)-[:SENT_TO_EMAIL]->(:EmailDomain)
(:Transaction)-[:USED_DEVICE]->(:Device)
(:Card)-[:LINKED_TO_ADDRESS]->(:Address)
```

## Graph Features (22)

Extracted via `graph-loader/export_graph_features.py`:

| Feature | Source | Description |
|---------|--------|-------------|
| `communityId` | Louvain | Community assignment |
| `pageRank` | PageRank | Node centrality score |
| `communitySize` | Louvain | Transactions in community |
| `communityFraudRate` | Louvain | Fraud rate within community |
| `communityAvgAmount` | Louvain | Avg transaction amount in community |
| `communityStdAmount` | Louvain | Std dev of amounts in community |
| `cardDegree` | Card node | Transaction count per card |
| `cardFraudRate` | Card node | Fraud rate per card |
| `numDevicesOnCard` | Card-Device | Distinct devices used with card |
| `addressesPerCard` | Card-Address | Distinct addresses per card |
| `fraudOnSameCard` | Card node | Count of fraudulent txns on card |
| `neighborCardFraudRate` | 2-hop | Avg fraud rate of cards at same address |
| `neighborCardCount` | 2-hop | Distinct neighbor cards via address |
| `addrDegree` | Address node | Transaction count per address |
| `addrFraudRate` | Address node | Fraud rate per address |
| `numCardsAtAddress` | Address-Card | Distinct cards at address |
| `emailDegree` | Email node | Transaction count per email domain |
| `emailFraudRate` | Email node | Fraud rate per email domain |
| `cardsPerEmail` | Email-Card | Distinct cards per email domain |
| `deviceDegree` | Device node | Transaction count per device |
| `deviceFraudRate` | Device node | Fraud rate per device |
| `maxEntityFraudRate` | All entities | Max fraud rate across card/addr/email/device |

## RAG Enrichment

Each fraud alert is enriched with:
- **Top 5 similar historical frauds** (embedding search in `fraud_cases`)
- **Community profile** (metadata lookup in `community_profiles`)
- **Card and address risk** (ID lookup in `entity_risk_profiles`)
- **Top 3 matching fraud patterns** (embedding search in `fraud_patterns`)

Enriched alerts are published to `fraud-alerts-enriched` with a `rag_context` field.

## Configuration

Environment variables in `docker-compose.yml` and `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSACTIONS_PER_SECOND` | 10 | Producer streaming rate |
| `FRAUD_THRESHOLD` | 0.5 | Consumer alert threshold |
| `NEO4J_AUTH` | neo4j/fraud_detection | Neo4j credentials |
| `BATCH_SIZE` | 5000 | Graph loader batch size |
| `CHUNK_SIZE` | 50000 | Graph loader CSV chunk size |

## Directory Structure

```
fraud-detection-pipeline/
|-- docker-compose.yml          # Full orchestration
|-- .env                        # Runtime config
|-- producer/                   # Kafka transaction producer
|   |-- producer.py
|   |-- Dockerfile
|   `-- requirements.txt
|-- consumer/                   # LightGBM fraud detector
|   |-- consumer.py
|   |-- Dockerfile
|   `-- requirements.txt
|-- graph-loader/               # Neo4j graph loading + feature export
|   |-- load_graph.py           # Load CSVs into Neo4j
|   |-- export_graph_features.py # GDS algorithms + feature extraction
|   |-- cypher_queries.py       # Reference Cypher query library
|   |-- Dockerfile
|   `-- requirements.txt
|-- chroma-indexer/              # ChromaDB batch indexer
|   |-- indexer.py              # Index 4 collections
|   |-- Dockerfile
|   `-- requirements.txt
|-- rag-enricher/                # RAG alert enrichment
|   |-- enricher.py             # Kafka consumer + ChromaDB query
|   |-- Dockerfile
|   `-- requirements.txt
|-- model/                       # Trained model artifacts
|   |-- fraud_model.txt         # LightGBM model (AUC: 0.9486)
|   |-- feature_names.json      # 446 feature names
|   `-- label_encoders.json     # Categorical encodings
`-- scripts/
    `-- train_and_export_model.py # Model training script
```
