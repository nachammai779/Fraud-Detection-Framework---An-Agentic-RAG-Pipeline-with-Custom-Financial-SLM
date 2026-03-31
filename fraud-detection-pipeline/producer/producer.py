"""
Kafka Transaction Producer
===========================
Reads the IEEE-CIS train_transaction.csv and streams each row as a JSON
message to the 'transactions' Kafka topic, simulating real-time payment flow.

Environment variables:
  KAFKA_BOOTSTRAP_SERVERS  - Kafka broker address (default: kafka:9092)
  KAFKA_TOPIC              - Target topic (default: transactions)
  TRANSACTIONS_PER_SECOND  - Throughput throttle (default: 10)
  DATA_PATH                - Path to train_transaction.csv
"""

import os
import sys
import json
import time
import logging

import numpy as np
import pandas as pd
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
TPS = int(os.getenv("TRANSACTIONS_PER_SECOND", "10"))
DATA_PATH = os.getenv("DATA_PATH", "/data/train_transaction.csv")

# Features to stream — mirrors the columns the consumer/model expects.
# We send all columns so the consumer can do its own feature engineering.
# Heavy V-columns are included because the model uses them.
SELECTED_FEATURES = None  # None = send all columns


def connect_kafka(retries: int = 30, delay: int = 5) -> KafkaProducer:
    """Connect to Kafka with retry logic for container startup ordering."""
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8") if k else None,
                acks="all",
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            log.info("Connected to Kafka at %s", KAFKA_BOOTSTRAP_SERVERS)
            return producer
        except NoBrokersAvailable:
            log.warning("Kafka not ready (attempt %d/%d), retrying in %ds...", attempt, retries, delay)
            time.sleep(delay)
    log.error("Could not connect to Kafka after %d attempts", retries)
    sys.exit(1)


def iter_transactions(path: str, chunksize: int = 5000):
    """Yield transaction rows from the CSV in chunks to limit memory usage."""
    log.info("Streaming transactions from %s (chunksize=%d) ...", path, chunksize)
    total_rows = 0
    num_cols = None
    for chunk in pd.read_csv(path, chunksize=chunksize):
        if num_cols is None:
            num_cols = len(chunk.columns)
            log.info("CSV has %d columns", num_cols)
        total_rows += len(chunk)
        yield chunk
    log.info("Finished reading %d total transactions", total_rows)


def row_to_message(row: pd.Series) -> dict:
    """Convert a DataFrame row to a JSON-serializable dict, handling NaN."""
    msg = {}
    for col, val in row.items():
        if pd.isna(val):
            msg[col] = None
        elif isinstance(val, (np.integer,)):
            msg[col] = int(val)
        elif isinstance(val, (np.floating,)):
            msg[col] = float(val)
        else:
            msg[col] = val
    return msg


def main():
    producer = connect_kafka()

    delay = 1.0 / TPS if TPS > 0 else 0
    sent = 0
    fraud_count = 0

    log.info("Streaming transactions at ~%d TPS to topic '%s'", TPS, KAFKA_TOPIC)
    log.info("=" * 60)

    start_time = time.time()

    for chunk in iter_transactions(DATA_PATH):
        if SELECTED_FEATURES:
            cols = [c for c in SELECTED_FEATURES if c in chunk.columns]
            for must_have in ["TransactionID", "isFraud"]:
                if must_have in chunk.columns and must_have not in cols:
                    cols.insert(0, must_have)
            chunk = chunk[cols]

        for idx, row in chunk.iterrows():
            message = row_to_message(row)
            txn_id = str(message.get("TransactionID", idx))
            is_fraud = message.get("isFraud", 0)

            producer.send(
                KAFKA_TOPIC,
                key=txn_id,
                value=message,
            )

            sent += 1
            if is_fraud:
                fraud_count += 1

            # Progress logging every 1000 messages
            if sent % 1000 == 0:
                elapsed = time.time() - start_time
                actual_tps = sent / elapsed if elapsed > 0 else 0
                log.info(
                    "Sent %d | Fraud: %d | Actual TPS: %.1f",
                    sent, fraud_count, actual_tps,
                )

            time.sleep(delay)

    producer.flush()
    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info(
        "DONE — Sent %d transactions in %.1fs (%.1f TPS) | Fraud: %d (%.2f%%)",
        sent, elapsed, sent / elapsed if elapsed > 0 else 0,
        fraud_count, 100 * fraud_count / sent if sent > 0 else 0,
    )
    producer.close()


if __name__ == "__main__":
    main()