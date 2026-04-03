"""
Load Kaggle IEEE Fraud Detection data into Neo4j as a property graph.

Graph Model:
  (:Transaction {id, amount, dt, isFraud, productCD, ...})
  (:Card {card1})
  (:Address {addr1})
  (:EmailDomain {domain})
  (:Device {deviceType, deviceInfo})

Relationships:
  (Transaction)-[:USED_CARD]->(Card)
  (Transaction)-[:FROM_ADDRESS]->(Address)
  (Transaction)-[:SENT_FROM_EMAIL]->(EmailDomain)   -- purchaser
  (Transaction)-[:SENT_TO_EMAIL]->(EmailDomain)      -- recipient
  (Transaction)-[:USED_DEVICE]->(Device)
  (Card)-[:LINKED_TO_ADDRESS]->(Address)              -- derived link

Memory-optimized: reads CSVs in chunks, only loads needed columns.
"""

import os
import logging
import time
import gc

import numpy as np
import pandas as pd
from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "fraud_detection")
TRANSACTION_PATH = os.environ.get("TRANSACTION_PATH", "/data/train_transaction.csv")
IDENTITY_PATH = os.environ.get("IDENTITY_PATH", "/data/train_identity.csv")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5000"))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "50000"))

# Only load columns we need for the graph — not all 394
TX_COLUMNS = [
    "TransactionID", "isFraud", "TransactionDT", "TransactionAmt",
    "ProductCD", "card1", "card2", "card4", "card6",
    "addr1", "addr2", "dist1",
    "P_emaildomain", "R_emaildomain",
    "C1", "C2", "C13", "C14",
]

ID_COLUMNS = [
    "TransactionID", "DeviceType", "DeviceInfo",
    "id_01", "id_02", "id_05", "id_06", "id_30", "id_31",
]


def clean_value(v):
    """Convert numpy/pandas types to native Python; replace NaN with None."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def create_constraints(session):
    """Create uniqueness constraints and indexes for fast lookups."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaction) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Card) REQUIRE c.card1 IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Address) REQUIRE a.addr1 IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:EmailDomain) REQUIRE e.domain IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE",
    ]
    for cypher in constraints:
        session.run(cypher)
    log.info("Constraints created.")


def chunk_to_records(chunk):
    """Convert a DataFrame chunk to a list of dicts with clean values."""
    records = []
    for _, row in chunk.iterrows():
        rec = {col: clean_value(row.get(col)) for col in chunk.columns}
        # Ensure TransactionID is int
        rec["TransactionID"] = int(row["TransactionID"])
        if "isFraud" in rec and rec["isFraud"] is not None:
            rec["isFraud"] = int(rec["isFraud"])
        records.append(rec)
    return records


def load_transactions_chunked(session, csv_path):
    """Load Transaction nodes from CSV in chunks to minimize memory usage."""
    log.info(f"Loading transactions from {csv_path} in chunks of {CHUNK_SIZE}...")

    total_loaded = 0
    for chunk in pd.read_csv(csv_path, usecols=TX_COLUMNS, chunksize=CHUNK_SIZE):
        chunk_len = len(chunk)

        # Process in smaller batches for Neo4j
        for start in range(0, chunk_len, BATCH_SIZE):
            batch = chunk.iloc[start : start + BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                records.append({
                    "id": int(row["TransactionID"]),
                    "amount": clean_value(row.get("TransactionAmt")),
                    "dt": clean_value(row.get("TransactionDT")),
                    "isFraud": int(row["isFraud"]) if pd.notna(row.get("isFraud")) else None,
                    "productCD": clean_value(row.get("ProductCD")),
                    "card1": clean_value(row.get("card1")),
                    "card2": clean_value(row.get("card2")),
                    "card4": clean_value(row.get("card4")),
                    "card6": clean_value(row.get("card6")),
                    "addr1": clean_value(row.get("addr1")),
                    "addr2": clean_value(row.get("addr2")),
                    "dist1": clean_value(row.get("dist1")),
                    "P_emaildomain": clean_value(row.get("P_emaildomain")),
                    "R_emaildomain": clean_value(row.get("R_emaildomain")),
                    "C1": clean_value(row.get("C1")),
                    "C2": clean_value(row.get("C2")),
                    "C13": clean_value(row.get("C13")),
                    "C14": clean_value(row.get("C14")),
                })

            session.run(
                """
                UNWIND $rows AS r

                MERGE (t:Transaction {id: r.id})
                SET t.amount    = r.amount,
                    t.dt        = r.dt,
                    t.isFraud   = r.isFraud,
                    t.productCD = r.productCD,
                    t.card4     = r.card4,
                    t.card6     = r.card6,
                    t.addr2     = r.addr2,
                    t.dist1     = r.dist1,
                    t.C1        = r.C1,
                    t.C2        = r.C2,
                    t.C13       = r.C13,
                    t.C14       = r.C14

                FOREACH (_ IN CASE WHEN r.card1 IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (c:Card {card1: r.card1})
                    SET c.card2 = r.card2, c.card4 = r.card4, c.card6 = r.card6
                    MERGE (t)-[:USED_CARD]->(c)
                )

                FOREACH (_ IN CASE WHEN r.addr1 IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (a:Address {addr1: r.addr1})
                    SET a.addr2 = r.addr2
                    MERGE (t)-[:FROM_ADDRESS]->(a)
                )

                FOREACH (_ IN CASE WHEN r.P_emaildomain IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (e:EmailDomain {domain: r.P_emaildomain})
                    MERGE (t)-[:SENT_FROM_EMAIL]->(e)
                )

                FOREACH (_ IN CASE WHEN r.R_emaildomain IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (e:EmailDomain {domain: r.R_emaildomain})
                    MERGE (t)-[:SENT_TO_EMAIL]->(e)
                )
                """,
                rows=records,
            )

        total_loaded += chunk_len
        log.info(f"  {total_loaded:,} transactions loaded")
        gc.collect()

    log.info(f"Transaction loading complete: {total_loaded:,} total")


def load_identity_chunked(session, csv_path):
    """Enrich Transaction nodes with identity info and create Device nodes."""
    log.info(f"Loading identity records from {csv_path} in chunks of {CHUNK_SIZE}...")

    total_loaded = 0
    for chunk in pd.read_csv(csv_path, usecols=ID_COLUMNS, chunksize=CHUNK_SIZE):
        chunk_len = len(chunk)

        for start in range(0, chunk_len, BATCH_SIZE):
            batch = chunk.iloc[start : start + BATCH_SIZE]
            records = []
            for _, row in batch.iterrows():
                device_type = clean_value(row.get("DeviceType"))
                device_info = clean_value(row.get("DeviceInfo"))
                fingerprint = f"{device_type}|{device_info}" if device_type or device_info else None

                records.append({
                    "id": int(row["TransactionID"]),
                    "deviceType": device_type,
                    "deviceInfo": device_info,
                    "fingerprint": fingerprint,
                    "id_01": clean_value(row.get("id_01")),
                    "id_02": clean_value(row.get("id_02")),
                    "id_05": clean_value(row.get("id_05")),
                    "id_06": clean_value(row.get("id_06")),
                    "id_30": clean_value(row.get("id_30")),
                    "id_31": clean_value(row.get("id_31")),
                })

            session.run(
                """
                UNWIND $rows AS r

                MATCH (t:Transaction {id: r.id})
                SET t.id_01 = r.id_01,
                    t.id_02 = r.id_02,
                    t.id_05 = r.id_05,
                    t.id_06 = r.id_06

                FOREACH (_ IN CASE WHEN r.fingerprint IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (d:Device {fingerprint: r.fingerprint})
                    SET d.deviceType = r.deviceType,
                        d.deviceInfo = r.deviceInfo,
                        d.os         = r.id_30,
                        d.browser    = r.id_31
                    MERGE (t)-[:USED_DEVICE]->(d)
                )
                """,
                rows=records,
            )

        total_loaded += chunk_len
        log.info(f"  {total_loaded:,} identity records loaded")
        gc.collect()

    log.info(f"Identity loading complete: {total_loaded:,} total")


def create_derived_links(session):
    """Create Card-Address links inferred from shared transactions."""
    log.info("Creating derived Card-Address links...")
    session.run(
        """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)-[:FROM_ADDRESS]->(a:Address)
        WITH c, a, count(t) AS txCount
        WHERE txCount >= 2
        MERGE (c)-[r:LINKED_TO_ADDRESS]->(a)
        SET r.sharedTransactions = txCount
        """
    )
    log.info("Derived links created.")


def print_summary(session):
    """Print graph statistics."""
    result = session.run(
        """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
        """
    )
    log.info("--- Graph Summary ---")
    for record in result:
        log.info(f"  :{record['label']}  {record['count']:,} nodes")

    result = session.run(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(r) AS count
        ORDER BY count DESC
        """
    )
    for record in result:
        log.info(f"  -[:{record['type']}]->  {record['count']:,} relationships")

    result = session.run(
        "MATCH (t:Transaction) WHERE t.isFraud = 1 RETURN count(t) AS fraudCount"
    )
    fraud_count = result.single()["fraudCount"]
    log.info(f"  Fraudulent transactions: {fraud_count:,}")


def main():
    log.info("Starting Neo4j graph loader...")
    log.info(f"  Neo4j URI:        {NEO4J_URI}")
    log.info(f"  Transaction file: {TRANSACTION_PATH}")
    log.info(f"  Identity file:    {IDENTITY_PATH}")
    log.info(f"  Batch size:       {BATCH_SIZE}")
    log.info(f"  Chunk size:       {CHUNK_SIZE}")

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected to Neo4j.")

    start_time = time.time()

    with driver.session() as session:
        create_constraints(session)
        load_transactions_chunked(session, TRANSACTION_PATH)
        load_identity_chunked(session, IDENTITY_PATH)
        create_derived_links(session)
        print_summary(session)

    elapsed = time.time() - start_time
    log.info(f"Graph loading complete in {elapsed:.1f}s")

    driver.close()


if __name__ == "__main__":
    main()