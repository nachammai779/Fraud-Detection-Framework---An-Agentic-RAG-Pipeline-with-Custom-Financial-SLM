"""
Kafka Fraud Detection Consumer
================================
Consumes transaction messages from Kafka, applies feature engineering
(mirroring the EDA pipeline), runs LightGBM inference, and publishes
fraud alerts to a separate topic.

Environment variables:
  KAFKA_BOOTSTRAP_SERVERS  - Kafka broker (default: kafka:9092)
  KAFKA_TOPIC              - Source topic (default: transactions)
  KAFKA_GROUP_ID           - Consumer group (default: fraud-detection-group)
  FRAUD_ALERT_TOPIC        - Topic for flagged fraud (default: fraud-alerts)
  METRICS_TOPIC            - Topic for metrics (default: transaction-metrics)
  MODEL_PATH               - Path to LightGBM model file (default: /model/fraud_model.txt)
  FRAUD_THRESHOLD          - Probability threshold (default: 0.5)
"""

import os
import sys
import json
import time
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
import lightgbm as lgb
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "fraud-detection-group")
FRAUD_ALERT_TOPIC = os.getenv("FRAUD_ALERT_TOPIC", "fraud-alerts")
METRICS_TOPIC = os.getenv("METRICS_TOPIC", "transaction-metrics")
MODEL_PATH = os.getenv("MODEL_PATH", "/model/fraud_model.txt")
FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", "0.5"))


def connect_kafka_consumer(retries: int = 30, delay: int = 5) -> KafkaConsumer:
    """Connect consumer with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            log.info("Consumer connected to Kafka at %s, topic='%s'", KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC)
            return consumer
        except NoBrokersAvailable:
            log.warning("Kafka not ready (attempt %d/%d), retrying in %ds...", attempt, retries, delay)
            time.sleep(delay)
    log.error("Could not connect consumer after %d attempts", retries)
    sys.exit(1)


def connect_kafka_producer(retries: int = 30, delay: int = 5) -> KafkaProducer:
    """Connect producer for alerts/metrics with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            log.info("Alert producer connected to Kafka")
            return producer
        except NoBrokersAvailable:
            log.warning("Alert producer: Kafka not ready (attempt %d/%d)", attempt, retries)
            time.sleep(delay)
    log.error("Could not connect alert producer")
    sys.exit(1)


def load_model(path: str) -> lgb.Booster:
    """Load a trained LightGBM model."""
    log.info("Loading model from %s", path)
    model = lgb.Booster(model_file=path)
    log.info("Model loaded — %d features expected", model.num_feature())
    return model


def load_label_encoders(model_dir: str) -> dict:
    """Load label encoder mappings exported during training."""
    enc_path = os.path.join(model_dir, "label_encoders.json")
    if os.path.exists(enc_path):
        with open(enc_path) as f:
            encoders = json.load(f)
        log.info("Loaded label encoders for %d columns: %s", len(encoders), list(encoders.keys()))
        return encoders
    log.warning("No label_encoders.json found at %s — categorical columns will use NaN", enc_path)
    return {}


def engineer_features(txn: dict) -> dict:
    """
    Apply the same feature engineering as the EDA notebook:
    - TransactionHour, TransactionDayOfWeek
    - TransactionAmt_Log, TransactionAmt_Decimal, TransactionAmt_IsRound
    """
    dt = txn.get("TransactionDT")
    amt = txn.get("TransactionAmt")

    if dt is not None:
        txn["TransactionHour"] = (int(dt) // 3600) % 24
        txn["TransactionDayOfWeek"] = (int(dt) // (3600 * 24)) % 7

    if amt is not None:
        txn["TransactionAmt_Log"] = float(np.log1p(amt))
        txn["TransactionAmt_Decimal"] = int((amt - int(amt)) * 1000)
        txn["TransactionAmt_IsRound"] = 1 if amt == int(amt) else 0

    return txn


def predict_fraud(model: lgb.Booster, txn: dict, label_encoders: dict) -> float:
    """Run inference on a single transaction. Returns fraud probability."""
    feature_names = model.feature_name()

    # Build a single-row DataFrame with the expected features
    row = {}
    for feat in feature_names:
        val = txn.get(feat)
        if val is None:
            row[feat] = np.nan
        elif feat in label_encoders:
            # Apply label encoding — map string to int, unseen values to NaN
            str_val = str(val) if val is not None else "NaN"
            row[feat] = label_encoders[feat].get(str_val, np.nan)
        else:
            row[feat] = val

    df = pd.DataFrame([row], columns=feature_names)
    prob = model.predict(df, num_iteration=model.best_iteration)[0]
    return float(prob)


def main():
    # Load model and label encoders
    model = load_model(MODEL_PATH)
    label_encoders = load_label_encoders(os.path.dirname(MODEL_PATH))

    # Connect to Kafka
    consumer = connect_kafka_consumer()
    alert_producer = connect_kafka_producer()

    # Metrics tracking
    stats = defaultdict(int)
    stats["start_time"] = time.time()

    log.info("Listening for transactions on '%s' (threshold=%.2f)...", KAFKA_TOPIC, FRAUD_THRESHOLD)
    log.info("=" * 60)

    for message in consumer:
        txn = message.value
        txn_id = txn.get("TransactionID", "unknown")
        actual_fraud = txn.get("isFraud")

        # Feature engineering
        txn = engineer_features(txn)

        # Predict
        fraud_prob = predict_fraud(model, txn, label_encoders)
        is_fraud_pred = fraud_prob >= FRAUD_THRESHOLD

        stats["total"] += 1

        if is_fraud_pred:
            stats["flagged_fraud"] += 1

            alert = {
                "TransactionID": txn_id,
                "fraud_probability": round(fraud_prob, 6),
                "TransactionAmt": txn.get("TransactionAmt"),
                "ProductCD": txn.get("ProductCD"),
                "card4": txn.get("card4"),
                "card6": txn.get("card6"),
                "P_emaildomain": txn.get("P_emaildomain"),
                "DeviceType": txn.get("DeviceType"),
                "actual_fraud": actual_fraud,
                "timestamp": time.time(),
            }

            alert_producer.send(FRAUD_ALERT_TOPIC, value=alert)
            log.warning(
                "FRAUD ALERT | TxnID=%s | Prob=%.4f | Amt=$%.2f | Actual=%s",
                txn_id, fraud_prob, txn.get("TransactionAmt", 0), actual_fraud,
            )
        else:
            stats["legit"] += 1

        # Track accuracy if ground truth is available
        if actual_fraud is not None:
            if is_fraud_pred and actual_fraud == 1:
                stats["true_positive"] += 1
            elif is_fraud_pred and actual_fraud == 0:
                stats["false_positive"] += 1
            elif not is_fraud_pred and actual_fraud == 1:
                stats["false_negative"] += 1
            else:
                stats["true_negative"] += 1

        # Periodic metrics every 500 messages
        if stats["total"] % 500 == 0:
            elapsed = time.time() - stats["start_time"]
            tp = stats["true_positive"]
            fp = stats["false_positive"]
            fn = stats["false_negative"]
            tn = stats["true_negative"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0

            metrics = {
                "total_processed": stats["total"],
                "flagged_fraud": stats["flagged_fraud"],
                "legit": stats["legit"],
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "throughput_tps": round(stats["total"] / elapsed, 1),
                "elapsed_seconds": round(elapsed, 1),
            }

            alert_producer.send(METRICS_TOPIC, value=metrics)
            log.info(
                "METRICS | Processed: %d | Fraud: %d | Precision: %.3f | Recall: %.3f | TPS: %.1f",
                stats["total"], stats["flagged_fraud"], precision, recall,
                stats["total"] / elapsed,
            )


if __name__ == "__main__":
    main()