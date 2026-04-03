"""
RAG Enricher — Consumes fraud alerts and enriches them with context from ChromaDB.

Subscribes to: fraud-alerts (Kafka topic)
Publishes to:  fraud-alerts-enriched (Kafka topic)

For each fraud alert:
  1. Queries fraud_cases for top-K similar historical frauds
  2. Queries community_profiles for the alert's community context
  3. Queries entity_risk_profiles for card and address risk
  4. Queries fraud_patterns for relevant pattern matches
  5. Assembles enriched alert with rag_context and publishes
"""

import os
import sys
import json
import time
import logging

import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RAG-ENRICHER] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
INPUT_TOPIC = os.environ.get("INPUT_TOPIC", "fraud-alerts")
OUTPUT_TOPIC = os.environ.get("OUTPUT_TOPIC", "fraud-alerts-enriched")
KAFKA_GROUP_ID = os.environ.get("KAFKA_GROUP_ID", "rag-enricher-group")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
TOP_K_CASES = int(os.environ.get("TOP_K_CASES", "5"))
TOP_K_PATTERNS = int(os.environ.get("TOP_K_PATTERNS", "3"))


def connect_kafka_consumer(retries=30, delay=5):
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                INPUT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            log.info("Consumer connected to '%s'", INPUT_TOPIC)
            return consumer
        except NoBrokersAvailable:
            log.warning("Kafka not ready (attempt %d/%d)", attempt, retries)
            time.sleep(delay)
    log.error("Could not connect consumer after %d attempts", retries)
    sys.exit(1)


def connect_kafka_producer(retries=30, delay=5):
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            log.info("Producer connected for '%s'", OUTPUT_TOPIC)
            return producer
        except NoBrokersAvailable:
            log.warning("Producer: Kafka not ready (attempt %d/%d)", attempt, retries)
            time.sleep(delay)
    log.error("Could not connect producer")
    sys.exit(1)


def build_query_text(alert):
    """Build a natural language query from alert fields for embedding search."""
    parts = [
        f"Transaction ${alert.get('TransactionAmt', 0):.2f}",
        f"via {alert.get('ProductCD', 'unknown')} product",
    ]
    if alert.get("card4"):
        parts.append(f"card: {alert['card4']} {alert.get('card6', '')}")
    if alert.get("P_emaildomain"):
        parts.append(f"email: {alert['P_emaildomain']}")
    if alert.get("DeviceType"):
        parts.append(f"device: {alert['DeviceType']}")
    return ", ".join(parts)


def query_similar_cases(collection, model, alert, top_k):
    """Find top-K similar historical fraud cases."""
    query_text = build_query_text(alert)
    query_embedding = model.encode([query_text]).tolist()

    # Optional metadata filter: same product code
    where_filter = None
    if alert.get("ProductCD"):
        where_filter = {"product_cd": str(alert["ProductCD"])}

    try:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # Fall back without filter if it fails (e.g., no matching product)
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

    cases = []
    if results and results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            cases.append({
                "transaction_id": meta.get("transaction_id"),
                "similarity": round(1.0 - dist, 4) if dist <= 1.0 else round(1.0 / (1.0 + dist), 4),
                "summary": doc[:200],
            })
    return cases


def query_community_profile(collection, alert):
    """Get the community profile for this alert's community."""
    card1 = alert.get("card1")
    # We don't have communityId in the alert directly, so search by text
    query_text = f"Community with card {card1}" if card1 else "High risk community"

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=1,
            include=["documents", "metadatas"],
        )
    except Exception:
        return None

    if results and results["documents"] and results["documents"][0]:
        meta = results["metadatas"][0][0]
        return {
            "community_id": meta.get("community_id"),
            "size": meta.get("community_size"),
            "fraud_rate": meta.get("fraud_rate"),
            "risk_level": meta.get("risk_level"),
            "summary": results["documents"][0][0],
        }
    return None


def query_entity_profiles(collection, alert):
    """Get card and address risk profiles."""
    profiles = {}

    # Card profile — exact match by entity_id
    card1 = alert.get("card1")
    if card1 is not None:
        try:
            results = collection.get(
                ids=[f"card_{int(card1)}"],
                include=["documents", "metadatas"],
            )
            if results and results["documents"]:
                profiles["card_profile"] = {
                    "summary": results["documents"][0],
                    **results["metadatas"][0],
                }
        except Exception:
            pass

    # Address profile — exact match by entity_id
    addr1 = alert.get("addr1")
    if addr1 is not None:
        try:
            results = collection.get(
                ids=[f"addr_{int(addr1)}"],
                include=["documents", "metadatas"],
            )
            if results and results["documents"]:
                profiles["address_profile"] = {
                    "summary": results["documents"][0],
                    **results["metadatas"][0],
                }
        except Exception:
            pass

    return profiles


def query_matching_patterns(collection, model, alert, top_k):
    """Find the most relevant fraud patterns for this alert."""
    query_text = build_query_text(alert)
    query_embedding = model.encode([query_text]).tolist()

    try:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas"],
        )
    except Exception:
        return []

    patterns = []
    if results and results["documents"] and results["documents"][0]:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            patterns.append({
                "pattern": doc,
                "type": meta.get("pattern_type"),
                "fraud_rate": meta.get("fraud_rate"),
            })
    return patterns


def enrich_alert(alert, collections, model):
    """Query all ChromaDB collections and build rag_context."""
    try:
        similar_cases = query_similar_cases(
            collections["fraud_cases"], model, alert, TOP_K_CASES
        )
        community = query_community_profile(
            collections["community_profiles"], alert
        )
        entity_risk = query_entity_profiles(
            collections["entity_risk_profiles"], alert
        )
        patterns = query_matching_patterns(
            collections["fraud_patterns"], model, alert, TOP_K_PATTERNS
        )

        return {
            "similar_fraud_cases": similar_cases,
            "community_profile": community,
            "entity_risk": entity_risk,
            "matching_patterns": patterns,
        }
    except Exception as e:
        log.error("ChromaDB query failed: %s", e)
        return None


def main():
    log.info("=" * 60)
    log.info("RAG ENRICHER — Fraud Alert Context Service")
    log.info("=" * 60)

    # Load embedding model
    log.info("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    log.info("  Model loaded")

    # Connect to ChromaDB
    log.info(f"Connecting to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}...")
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    chroma_client.heartbeat()
    log.info("  ChromaDB connected")

    # Get collections
    collections = {
        "fraud_cases": chroma_client.get_collection("fraud_cases"),
        "community_profiles": chroma_client.get_collection("community_profiles"),
        "entity_risk_profiles": chroma_client.get_collection("entity_risk_profiles"),
        "fraud_patterns": chroma_client.get_collection("fraud_patterns"),
    }

    for name, col in collections.items():
        log.info(f"  {name}: {col.count()} documents")

    # Connect to Kafka
    consumer = connect_kafka_consumer()
    producer = connect_kafka_producer()

    log.info("Listening for fraud alerts on '%s'...", INPUT_TOPIC)
    log.info("=" * 60)

    count = 0
    for message in consumer:
        alert = message.value
        txn_id = alert.get("TransactionID", "unknown")

        # Enrich with RAG context
        rag_context = enrich_alert(alert, collections, model)

        # Build enriched alert
        enriched = {**alert, "rag_context": rag_context}

        # Publish
        producer.send(OUTPUT_TOPIC, value=enriched)
        count += 1

        if rag_context and rag_context.get("similar_fraud_cases"):
            top_sim = rag_context["similar_fraud_cases"][0].get("similarity", 0)
            log.info(
                "ENRICHED | TxnID=%s | Prob=%.4f | TopSimilarity=%.4f | Patterns=%d",
                txn_id, alert.get("fraud_probability", 0), top_sim,
                len(rag_context.get("matching_patterns", [])),
            )
        else:
            log.info("ENRICHED | TxnID=%s | No RAG context available", txn_id)

        if count % 100 == 0:
            log.info("Total alerts enriched: %d", count)


if __name__ == "__main__":
    main()
