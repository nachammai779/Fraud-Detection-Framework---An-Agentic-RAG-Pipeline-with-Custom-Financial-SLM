"""
ChromaDB Indexer — Batch index fraud intelligence into vector collections.

Collections created:
  1. fraud_cases          — One doc per fraudulent transaction (~20K)
  2. community_profiles   — One doc per Louvain community (~36)
  3. entity_risk_profiles — One doc per card + address (~14K)
  4. fraud_patterns       — Aggregated pattern rules (~30-50)

Reads from:
  - data/processed/feature_matrix.parquet  (tabular + graph features)
  - Neo4j (community and entity stats)
"""

import os
import logging
import time

import numpy as np
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [INDEXER] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "fraud_detection")
FEATURE_MATRIX_PATH = os.environ.get("FEATURE_MATRIX_PATH", "/data/feature_matrix.parquet")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "500"))


def safe(val, default="unknown"):
    """Return val if not null/NaN, else default."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return val


def safe_float(val, default=0.0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


def safe_int(val, default=0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return int(val)


# =============================================================================
# Collection 1: Fraud Cases
# =============================================================================

def index_fraud_cases(client, model, df):
    """Index one document per fraudulent transaction."""
    log.info("Indexing fraud_cases collection...")

    collection = client.get_or_create_collection(
        name="fraud_cases",
        metadata={"description": "Historical fraud transaction profiles for similarity search"},
    )

    fraud_df = df[df["isFraud"] == 1].copy()
    log.info(f"  {len(fraud_df):,} fraud transactions to index")

    documents = []
    metadatas = []
    ids = []

    for _, row in fraud_df.iterrows():
        txn_id = int(row["TransactionID"])
        doc = (
            f"Fraud transaction {txn_id}: ${safe_float(row.get('TransactionAmt')):.2f} "
            f"via {safe(row.get('ProductCD'))} product. "
            f"Card type: {safe(row.get('card4'))} {safe(row.get('card6'))}. "
            f"Email domain: {safe(row.get('P_emaildomain'))}. "
            f"Transaction hour: {safe_int(row.get('TransactionHour'))}, "
            f"day of week: {safe_int(row.get('TransactionDayOfWeek'))}. "
            f"Community {safe_int(row.get('communityId'))} "
            f"(size: {safe_int(row.get('communitySize'))}, "
            f"fraud rate: {safe_float(row.get('communityFraudRate')) * 100:.1f}%). "
            f"PageRank: {safe_float(row.get('pageRank')):.4f}. "
            f"Card degree: {safe_int(row.get('cardDegree'))}, "
            f"card fraud rate: {safe_float(row.get('cardFraudRate')) * 100:.1f}%. "
            f"Address degree: {safe_int(row.get('addrDegree'))}, "
            f"address fraud rate: {safe_float(row.get('addrFraudRate')) * 100:.1f}%."
        )

        meta = {
            "transaction_id": txn_id,
            "product_cd": str(safe(row.get("ProductCD"))),
            "card4": str(safe(row.get("card4"))),
            "card6": str(safe(row.get("card6"))),
            "transaction_amt": safe_float(row.get("TransactionAmt")),
            "community_id": safe_int(row.get("communityId")),
            "community_fraud_rate": safe_float(row.get("communityFraudRate")),
            "page_rank": safe_float(row.get("pageRank")),
            "transaction_hour": safe_int(row.get("TransactionHour")),
        }

        documents.append(doc)
        metadatas.append(meta)
        ids.append(f"fraud_{txn_id}")

    # Index in batches
    total = len(documents)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch_docs = documents[start:end]
        batch_embeddings = model.encode(batch_docs).tolist()

        collection.add(
            ids=ids[start:end],
            documents=batch_docs,
            metadatas=metadatas[start:end],
            embeddings=batch_embeddings,
        )

        log.info(f"  Indexed {end:,}/{total:,} fraud cases")

    log.info(f"  fraud_cases collection: {collection.count()} documents")


# =============================================================================
# Collection 2: Community Profiles
# =============================================================================

def index_community_profiles(client, model, neo4j_driver):
    """Index one document per community from Neo4j stats."""
    log.info("Indexing community_profiles collection...")

    collection = client.get_or_create_collection(
        name="community_profiles",
        metadata={"description": "Louvain community risk profiles"},
    )

    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (t:Transaction)
            WHERE t.communityId IS NOT NULL
            WITH t.communityId AS communityId,
                 count(t) AS communitySize,
                 toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS fraudRate,
                 avg(t.amount) AS avgAmount,
                 stDev(t.amount) AS stdAmount
            RETURN communityId, communitySize, fraudRate, avgAmount, stdAmount
            ORDER BY fraudRate DESC
        """)

        documents = []
        metadatas = []
        ids = []

        for rec in result:
            cid = rec["communityId"]
            fraud_rate = rec["fraudRate"]
            risk = "HIGH RISK" if fraud_rate > 0.10 else "MODERATE RISK" if fraud_rate > 0.035 else "LOW RISK"

            doc = (
                f"Community {cid}: {rec['communitySize']:,} transactions, "
                f"{fraud_rate * 100:.1f}% fraud rate. "
                f"Average transaction amount: ${rec['avgAmount']:.2f} "
                f"(std: ${rec['stdAmount']:.2f}). "
                f"Classification: {risk}."
            )

            meta = {
                "community_id": int(cid),
                "community_size": int(rec["communitySize"]),
                "fraud_rate": float(fraud_rate),
                "risk_level": risk.split()[0].lower(),
                "avg_amount": float(rec["avgAmount"]),
            }

            documents.append(doc)
            metadatas.append(meta)
            ids.append(f"community_{cid}")

    embeddings = model.encode(documents).tolist()
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
    log.info(f"  community_profiles collection: {collection.count()} documents")


# =============================================================================
# Collection 3: Entity Risk Profiles
# =============================================================================

def index_entity_risk_profiles(client, model, neo4j_driver):
    """Index per-card and per-address risk profiles."""
    log.info("Indexing entity_risk_profiles collection...")

    collection = client.get_or_create_collection(
        name="entity_risk_profiles",
        metadata={"description": "Card and address risk profiles"},
    )

    documents = []
    metadatas = []
    ids = []

    with neo4j_driver.session() as session:
        # Card profiles
        result = session.run("""
            MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)
            WITH c.card1 AS card1, c.card4 AS card4, c.card6 AS card6,
                 count(t) AS degree,
                 toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS fraudRate
            OPTIONAL MATCH (c2:Card {card1: card1})<-[:USED_CARD]-(:Transaction)-[:USED_DEVICE]->(d:Device)
            WITH card1, card4, card6, degree, fraudRate, count(DISTINCT d) AS numDevices
            RETURN card1, card4, card6, degree, fraudRate, numDevices
        """)

        for rec in result:
            fraud_rate = rec["fraudRate"]
            risk = "HIGH" if fraud_rate > 0.15 else "MODERATE" if fraud_rate > 0.05 else "LOW"

            doc = (
                f"Card {rec['card1']}: {rec['degree']} transactions, "
                f"{fraud_rate * 100:.1f}% fraud rate. "
                f"Brand: {safe(rec.get('card4'))}, type: {safe(rec.get('card6'))}. "
                f"{rec['numDevices']} distinct devices used. Risk: {risk}."
            )

            meta = {
                "entity_type": "card",
                "entity_id": str(int(rec["card1"])) if rec["card1"] is not None else "unknown",
                "degree": int(rec["degree"]),
                "fraud_rate": float(fraud_rate),
                "risk_level": risk.lower(),
            }

            documents.append(doc)
            metadatas.append(meta)
            ids.append(f"card_{rec['card1']}")

        log.info(f"  {len(documents):,} card profiles prepared")

        # Address profiles
        addr_start = len(documents)
        result = session.run("""
            MATCH (a:Address)<-[:FROM_ADDRESS]-(t:Transaction)
            OPTIONAL MATCH (t)-[:USED_CARD]->(c:Card)
            WITH a.addr1 AS addr1,
                 count(DISTINCT t) AS degree,
                 toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(DISTINCT t) AS fraudRate,
                 count(DISTINCT c) AS numCards
            RETURN addr1, degree, fraudRate, numCards
        """)

        for rec in result:
            fraud_rate = rec["fraudRate"]
            risk = "HIGH" if fraud_rate > 0.15 else "MODERATE" if fraud_rate > 0.05 else "LOW"

            doc = (
                f"Address {rec['addr1']}: {rec['degree']} transactions, "
                f"{fraud_rate * 100:.1f}% fraud rate. "
                f"{rec['numCards']} cards at this address. Risk: {risk}."
            )

            meta = {
                "entity_type": "address",
                "entity_id": str(int(rec["addr1"])) if rec["addr1"] is not None else "unknown",
                "degree": int(rec["degree"]),
                "fraud_rate": float(fraud_rate),
                "risk_level": risk.lower(),
            }

            documents.append(doc)
            metadatas.append(meta)
            ids.append(f"addr_{rec['addr1']}")

        log.info(f"  {len(documents) - addr_start:,} address profiles prepared")

    # Index in batches
    total = len(documents)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch_docs = documents[start:end]
        batch_embeddings = model.encode(batch_docs).tolist()

        collection.add(
            ids=ids[start:end],
            documents=batch_docs,
            metadatas=metadatas[start:end],
            embeddings=batch_embeddings,
        )

        log.info(f"  Indexed {end:,}/{total:,} entity profiles")

    log.info(f"  entity_risk_profiles collection: {collection.count()} documents")


# =============================================================================
# Collection 4: Fraud Patterns
# =============================================================================

def index_fraud_patterns(client, model, df):
    """Generate and index aggregated fraud pattern rules."""
    log.info("Indexing fraud_patterns collection...")

    collection = client.get_or_create_collection(
        name="fraud_patterns",
        metadata={"description": "Aggregated fraud pattern rules derived from data analysis"},
    )

    documents = []
    metadatas = []
    ids = []
    pattern_id = 0

    def add_pattern(doc, ptype, fraud_rate, sample_size):
        nonlocal pattern_id
        documents.append(doc)
        metadatas.append({
            "pattern_type": ptype,
            "fraud_rate": float(fraud_rate),
            "sample_size": int(sample_size),
        })
        ids.append(f"pattern_{pattern_id}")
        pattern_id += 1

    overall_fraud_rate = df["isFraud"].mean()

    # Product-based patterns
    if "ProductCD" in df.columns:
        for product, grp in df.groupby("ProductCD"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if count >= 100:
                add_pattern(
                    f"Product code {product} has a {rate * 100:.1f}% fraud rate across "
                    f"{count:,} transactions ({rate / overall_fraud_rate:.1f}x the overall average).",
                    "product", rate, count,
                )

    # Temporal patterns (hour)
    if "TransactionHour" in df.columns:
        for hour, grp in df.groupby("TransactionHour"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if rate > overall_fraud_rate * 1.5 and count >= 500:
                add_pattern(
                    f"Transactions at hour {int(hour)}:00 have a {rate * 100:.1f}% fraud rate "
                    f"({rate / overall_fraud_rate:.1f}x average) across {count:,} transactions.",
                    "temporal", rate, count,
                )

    # Temporal patterns (day of week)
    if "TransactionDayOfWeek" in df.columns:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for dow, grp in df.groupby("TransactionDayOfWeek"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            day_name = days[int(dow)] if int(dow) < 7 else f"Day {int(dow)}"
            if rate > overall_fraud_rate * 1.3 and count >= 1000:
                add_pattern(
                    f"Transactions on {day_name} have a {rate * 100:.1f}% fraud rate "
                    f"({rate / overall_fraud_rate:.1f}x average) across {count:,} transactions.",
                    "temporal", rate, count,
                )

    # Card brand patterns
    if "card4" in df.columns:
        for brand, grp in df.groupby("card4"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if count >= 100:
                add_pattern(
                    f"Card brand {brand} has a {rate * 100:.1f}% fraud rate across {count:,} transactions.",
                    "card", rate, count,
                )

    # Card type patterns
    if "card6" in df.columns:
        for ctype, grp in df.groupby("card6"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if count >= 100:
                add_pattern(
                    f"Card type {ctype} has a {rate * 100:.1f}% fraud rate across {count:,} transactions.",
                    "card", rate, count,
                )

    # Amount bucket patterns
    if "TransactionAmt" in df.columns:
        bins = [0, 50, 100, 200, 500, 1000, float("inf")]
        labels = ["$0-50", "$50-100", "$100-200", "$200-500", "$500-1000", "$1000+"]
        df["_amt_bucket"] = pd.cut(df["TransactionAmt"], bins=bins, labels=labels)
        for bucket, grp in df.groupby("_amt_bucket", observed=True):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if count >= 100:
                add_pattern(
                    f"Transactions in the {bucket} range have a {rate * 100:.1f}% fraud rate "
                    f"across {count:,} transactions.",
                    "amount", rate, count,
                )
        df.drop(columns=["_amt_bucket"], inplace=True)

    # Community-based patterns
    if "communityFraudRate" in df.columns:
        high_risk = df[df["communityFraudRate"] > 0.10]
        if len(high_risk) > 0:
            rate = high_risk["isFraud"].mean()
            add_pattern(
                f"Transactions in high-risk communities (fraud rate >10%) have a "
                f"{rate * 100:.1f}% actual fraud rate across {len(high_risk):,} transactions.",
                "community", rate, len(high_risk),
            )

        low_risk = df[df["communityFraudRate"] <= 0.035]
        if len(low_risk) > 0:
            rate = low_risk["isFraud"].mean()
            add_pattern(
                f"Transactions in low-risk communities (fraud rate <=3.5%) have a "
                f"{rate * 100:.1f}% actual fraud rate across {len(low_risk):,} transactions.",
                "community", rate, len(low_risk),
            )

    # Device diversity patterns
    if "numDevicesOnCard" in df.columns:
        multi_dev = df[df["numDevicesOnCard"] >= 3].dropna(subset=["numDevicesOnCard"])
        if len(multi_dev) > 0:
            rate = multi_dev["isFraud"].mean()
            add_pattern(
                f"Cards used from 3 or more devices have a {rate * 100:.1f}% fraud rate "
                f"across {len(multi_dev):,} transactions.",
                "device", rate, len(multi_dev),
            )

    # Cards at address patterns
    if "numCardsAtAddress" in df.columns:
        multi_card = df[df["numCardsAtAddress"] >= 3].dropna(subset=["numCardsAtAddress"])
        if len(multi_card) > 0:
            rate = multi_card["isFraud"].mean()
            add_pattern(
                f"Addresses with 3 or more cards have a {rate * 100:.1f}% fraud rate "
                f"across {len(multi_card):,} transactions.",
                "address", rate, len(multi_card),
            )

    # Email domain patterns
    if "P_emaildomain" in df.columns:
        for domain, grp in df.groupby("P_emaildomain"):
            rate = grp["isFraud"].mean()
            count = len(grp)
            if count >= 500 and rate > overall_fraud_rate * 1.5:
                add_pattern(
                    f"Email domain {domain} has a {rate * 100:.1f}% fraud rate across "
                    f"{count:,} transactions ({rate / overall_fraud_rate:.1f}x the overall average).",
                    "email", rate, count,
                )

    # PageRank patterns
    if "pageRank" in df.columns:
        high_pr = df[df["pageRank"] > df["pageRank"].quantile(0.95)]
        if len(high_pr) > 0:
            rate = high_pr["isFraud"].mean()
            add_pattern(
                f"Transactions with top 5% PageRank scores have a {rate * 100:.1f}% fraud rate "
                f"across {len(high_pr):,} transactions.",
                "graph", rate, len(high_pr),
            )

    # Index all patterns
    if documents:
        embeddings = model.encode(documents).tolist()
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    log.info(f"  fraud_patterns collection: {collection.count()} documents")


# =============================================================================
# Main
# =============================================================================

def main():
    log.info("=" * 60)
    log.info("CHROMADB INDEXER — Fraud Intelligence Vectorization")
    log.info("=" * 60)

    start_time = time.time()

    # Load embedding model
    log.info("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    log.info("  Model loaded")

    # Connect to ChromaDB
    log.info(f"Connecting to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}...")
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    chroma_client.heartbeat()
    log.info("  ChromaDB connected")

    # Connect to Neo4j
    log.info(f"Connecting to Neo4j at {NEO4J_URI}...")
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    neo4j_driver.verify_connectivity()
    log.info("  Neo4j connected")

    import gc

    # Columns needed for fraud_cases
    fraud_case_cols = [
        "TransactionID", "isFraud", "TransactionAmt", "ProductCD",
        "card4", "card6", "P_emaildomain", "TransactionHour", "TransactionDayOfWeek",
        "communityId", "communitySize", "communityFraudRate", "pageRank",
        "cardDegree", "cardFraudRate", "addrDegree", "addrFraudRate",
    ]

    # Index fraud cases — load only needed columns
    log.info(f"Loading fraud case columns from {FEATURE_MATRIX_PATH}...")
    df_fraud = pd.read_parquet(FEATURE_MATRIX_PATH, columns=fraud_case_cols)
    log.info(f"  Shape: {df_fraud.shape}")
    index_fraud_cases(chroma_client, model, df_fraud)
    del df_fraud
    gc.collect()

    # Index community and entity profiles from Neo4j (no parquet needed)
    index_community_profiles(chroma_client, model, neo4j_driver)
    index_entity_risk_profiles(chroma_client, model, neo4j_driver)
    neo4j_driver.close()

    # Index fraud patterns — load only needed columns
    pattern_cols = [
        "isFraud", "ProductCD", "TransactionHour", "TransactionDayOfWeek",
        "card4", "card6", "TransactionAmt", "P_emaildomain", "pageRank",
        "communityFraudRate", "numDevicesOnCard", "numCardsAtAddress",
    ]
    log.info(f"Loading pattern columns from {FEATURE_MATRIX_PATH}...")
    df_patterns = pd.read_parquet(FEATURE_MATRIX_PATH, columns=pattern_cols)
    log.info(f"  Shape: {df_patterns.shape}")
    index_fraud_patterns(chroma_client, model, df_patterns)
    del df_patterns
    gc.collect()

    elapsed = time.time() - start_time
    log.info(f"\nIndexing complete in {elapsed:.1f}s")

    # Summary
    for name in ["fraud_cases", "community_profiles", "entity_risk_profiles", "fraud_patterns"]:
        col = chroma_client.get_collection(name)
        log.info(f"  {name}: {col.count()} documents")

    log.info("Done.")


if __name__ == "__main__":
    main()
