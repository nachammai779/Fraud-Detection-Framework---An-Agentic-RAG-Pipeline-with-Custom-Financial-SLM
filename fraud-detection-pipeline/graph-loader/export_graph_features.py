"""
Export graph features from Neo4j and merge with tabular features.

Extracts per-transaction:
  - communityId, communitySize, communityFraudRate  (Louvain)
  - pageRank                                        (PageRank)
  - cardDegree, addrDegree, emailDegree, deviceDegree  (node degrees)
  - cardFraudRate, addrFraudRate                    (neighborhood fraud rates)
  - numCardsAtAddress, numDevicesOnCard             (structural counts)

Merges with tabular features from train_transaction.csv + train_identity.csv
and saves the final feature matrix to /data/processed/.

Strategy: precompute entity-level stats in Neo4j, then join in pandas.
This avoids expensive multi-hop Cypher queries across 590K transactions.
"""

import os
import logging
import time

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
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/data/processed")


def query_to_df(session, cypher):
    """Run a Cypher query and return results as a DataFrame."""
    result = session.run(cypher)
    return result.to_df()


# =============================================================================
# Step 1: Run GDS algorithms
# =============================================================================

def ensure_graph_projection(session):
    """Create the GDS in-memory graph projection if it doesn't exist."""
    result = session.run("CALL gds.graph.list() YIELD graphName RETURN collect(graphName) AS names")
    existing = result.single()["names"]

    if "fraud-entity-graph" not in existing:
        log.info("Projecting 'fraud-entity-graph'...")
        result = session.run("""
            CALL gds.graph.project(
                'fraud-entity-graph',
                ['Transaction', 'Card', 'Address', 'EmailDomain', 'Device'],
                {
                    USED_CARD:       { orientation: 'UNDIRECTED' },
                    FROM_ADDRESS:    { orientation: 'UNDIRECTED' },
                    SENT_FROM_EMAIL: { orientation: 'UNDIRECTED' },
                    SENT_TO_EMAIL:   { orientation: 'UNDIRECTED' },
                    USED_DEVICE:     { orientation: 'UNDIRECTED' }
                },
                {
                    nodeProperties: {
                        isFraud: { defaultValue: 0 },
                        amount:  { defaultValue: 0.0 }
                    }
                }
            )
            YIELD graphName, nodeCount, relationshipCount
        """)
        rec = result.single()
        log.info(f"  Projected: {rec['nodeCount']:,} nodes, {rec['relationshipCount']:,} rels")
    else:
        log.info("Graph projection 'fraud-entity-graph' already exists.")


def run_louvain(session):
    log.info("Running Louvain community detection...")
    result = session.run("""
        CALL gds.louvain.write(
            'fraud-entity-graph',
            { writeProperty: 'communityId', maxLevels: 10, maxIterations: 10 }
        )
        YIELD communityCount, modularity, nodePropertiesWritten
    """)
    rec = result.single()
    log.info(f"  Communities: {rec['communityCount']:,}, modularity: {rec['modularity']:.4f}")


def run_pagerank(session):
    log.info("Running PageRank...")
    result = session.run("""
        CALL gds.pageRank.write(
            'fraud-entity-graph',
            { writeProperty: 'pageRank', maxIterations: 20, dampingFactor: 0.85 }
        )
        YIELD nodePropertiesWritten, ranIterations, didConverge
    """)
    rec = result.single()
    log.info(f"  Iterations: {rec['ranIterations']}, converged: {rec['didConverge']}")


# =============================================================================
# Step 2: Extract features via fast, separate queries
# =============================================================================

def extract_transaction_base(session):
    """Get transaction-level properties written by GDS (communityId, pageRank)."""
    log.info("Extracting transaction base features (communityId, pageRank)...")
    df = query_to_df(session, """
        MATCH (t:Transaction)
        RETURN t.id          AS TransactionID,
               t.communityId AS communityId,
               t.pageRank    AS pageRank
    """)
    log.info(f"  {len(df):,} transactions")
    return df


def extract_community_stats(session):
    """Compute per-community aggregate statistics."""
    log.info("Extracting community-level statistics...")
    df = query_to_df(session, """
        MATCH (t:Transaction)
        WHERE t.communityId IS NOT NULL
        WITH t.communityId AS communityId,
             count(t) AS communitySize,
             toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS communityFraudRate,
             avg(t.amount) AS communityAvgAmount,
             stDev(t.amount) AS communityStdAmount
        RETURN communityId, communitySize, communityFraudRate,
               communityAvgAmount, communityStdAmount
    """)
    log.info(f"  {len(df):,} communities")
    return df


def extract_card_stats(session):
    """Compute per-card: degree (tx count), fraud rate."""
    log.info("Extracting card-level stats...")
    df = query_to_df(session, """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)
        WITH c.card1 AS card1,
             count(t) AS cardDegree,
             toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS cardFraudRate
        RETURN card1, cardDegree, cardFraudRate
    """)
    log.info(f"  {len(df):,} cards")
    return df


def extract_addr_stats(session):
    """Compute per-address: degree, fraud rate, number of distinct cards."""
    log.info("Extracting address-level stats...")
    df = query_to_df(session, """
        MATCH (a:Address)<-[:FROM_ADDRESS]-(t:Transaction)
        OPTIONAL MATCH (t)-[:USED_CARD]->(c:Card)
        WITH a.addr1 AS addr1,
             count(DISTINCT t) AS addrDegree,
             toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(DISTINCT t) AS addrFraudRate,
             count(DISTINCT c) AS numCardsAtAddress
        RETURN addr1, addrDegree, addrFraudRate, numCardsAtAddress
    """)
    log.info(f"  {len(df):,} addresses")
    return df


def extract_email_stats(session):
    """Compute per-email-domain: degree, fraud rate, distinct cards."""
    log.info("Extracting email-level stats...")
    df = query_to_df(session, """
        MATCH (e:EmailDomain)<-[:SENT_FROM_EMAIL]-(t:Transaction)
        OPTIONAL MATCH (t)-[:USED_CARD]->(c:Card)
        WITH e.domain AS domain,
             count(DISTINCT t) AS emailDegree,
             toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(DISTINCT t) AS emailFraudRate,
             count(DISTINCT c) AS cardsPerEmail
        RETURN domain, emailDegree, emailFraudRate, cardsPerEmail
    """)
    log.info(f"  {len(df):,} email domains")
    return df


def extract_device_stats(session):
    """Compute per-device: degree, fraud rate."""
    log.info("Extracting device-level stats...")
    df = query_to_df(session, """
        MATCH (d:Device)<-[:USED_DEVICE]-(t:Transaction)
        WITH d.fingerprint AS fingerprint,
             count(t) AS deviceDegree,
             toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS deviceFraudRate
        RETURN fingerprint, deviceDegree, deviceFraudRate
    """)
    log.info(f"  {len(df):,} devices")
    return df


def extract_card_device_count(session):
    """Compute per-card: number of distinct devices used."""
    log.info("Extracting card-device counts...")
    df = query_to_df(session, """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)-[:USED_DEVICE]->(d:Device)
        WITH c.card1 AS card1,
             count(DISTINCT d) AS numDevicesOnCard
        RETURN card1, numDevicesOnCard
    """)
    log.info(f"  {len(df):,} cards with device info")
    return df


def extract_card_address_count(session):
    """Compute per-card: number of distinct addresses (addressesPerCard)."""
    log.info("Extracting card-address counts...")
    df = query_to_df(session, """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)-[:FROM_ADDRESS]->(a:Address)
        WITH c.card1 AS card1,
             count(DISTINCT a) AS addressesPerCard
        RETURN card1, addressesPerCard
    """)
    log.info(f"  {len(df):,} cards with address info")
    return df


def extract_fraud_on_same_card(session):
    """Count of fraudulent transactions on each card (excluding self)."""
    log.info("Extracting fraud-on-same-card counts...")
    df = query_to_df(session, """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)
        WITH c.card1 AS card1,
             sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END) AS fraudOnSameCard
        RETURN card1, fraudOnSameCard
    """)
    log.info(f"  {len(df):,} cards")
    return df


def extract_card_to_addr_mapping(session):
    """Get card-to-address mapping for computing neighbor features in pandas."""
    log.info("Extracting card-to-address mapping...")
    df = query_to_df(session, """
        MATCH (c:Card)<-[:USED_CARD]-(t:Transaction)-[:FROM_ADDRESS]->(a:Address)
        WITH c.card1 AS card1, a.addr1 AS addr1
        RETURN DISTINCT card1, addr1
    """)
    log.info(f"  {len(df):,} card-address pairs")
    return df


def extract_transaction_links(session):
    """Get per-transaction: which card1, addr1, email domain, device fingerprint."""
    log.info("Extracting transaction entity links...")
    df = query_to_df(session, """
        MATCH (t:Transaction)
        OPTIONAL MATCH (t)-[:USED_CARD]->(c:Card)
        OPTIONAL MATCH (t)-[:FROM_ADDRESS]->(a:Address)
        OPTIONAL MATCH (t)-[:SENT_FROM_EMAIL]->(e:EmailDomain)
        OPTIONAL MATCH (t)-[:USED_DEVICE]->(d:Device)
        RETURN t.id        AS TransactionID,
               c.card1     AS card1,
               a.addr1     AS addr1,
               e.domain    AS P_emaildomain,
               d.fingerprint AS deviceFingerprint
    """)
    log.info(f"  {len(df):,} transaction links")
    return df


# =============================================================================
# Step 3: Build tabular features (same pipeline as train_and_export_model.py)
# =============================================================================

def build_tabular_features(tx_path, id_path):
    """Load and engineer tabular features matching the training pipeline."""
    log.info("Loading tabular data...")
    tx_df = pd.read_csv(tx_path)
    id_df = pd.read_csv(id_path)
    log.info(f"  Transactions: {tx_df.shape}, Identity: {id_df.shape}")

    df = tx_df.merge(id_df, on="TransactionID", how="left")
    del tx_df, id_df
    log.info(f"  Merged shape: {df.shape}")

    # Drop high-missing columns (>90%)
    missing_pct = df.isnull().mean()
    cols_to_drop = missing_pct[missing_pct > 0.9].index.tolist()
    cols_to_drop = [c for c in cols_to_drop if c not in ("isFraud", "TransactionID")]
    df.drop(columns=cols_to_drop, inplace=True)
    log.info(f"  Dropped {len(cols_to_drop)} high-missing cols -> {df.shape[1]} remaining")

    df["TransactionHour"] = (df["TransactionDT"] // 3600) % 24
    df["TransactionDayOfWeek"] = (df["TransactionDT"] // (3600 * 24)) % 7
    df["TransactionAmt_Log"] = np.log1p(df["TransactionAmt"])
    df["TransactionAmt_Decimal"] = (
        (df["TransactionAmt"] - df["TransactionAmt"].astype(int)) * 1000
    ).astype(int)
    df["TransactionAmt_IsRound"] = (
        df["TransactionAmt"] == df["TransactionAmt"].astype(int)
    ).astype(int)

    log.info(f"  Final tabular shape: {df.shape}")
    return df


# =============================================================================
# Step 4: Assemble graph features in pandas and merge
# =============================================================================

def main():
    log.info("=" * 60)
    log.info("GRAPH FEATURE EXPORT & MERGE")
    log.info("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected to Neo4j.")

    start_time = time.time()

    with driver.session() as session:
        # Run GDS algorithms
        ensure_graph_projection(session)
        run_louvain(session)
        run_pagerank(session)

        # Extract features via fast separate queries
        tx_base_df = extract_transaction_base(session)
        community_df = extract_community_stats(session)
        card_df = extract_card_stats(session)
        addr_df = extract_addr_stats(session)
        email_df = extract_email_stats(session)
        device_df = extract_device_stats(session)
        card_device_df = extract_card_device_count(session)
        card_addr_count_df = extract_card_address_count(session)
        fraud_same_card_df = extract_fraud_on_same_card(session)
        card_addr_map_df = extract_card_to_addr_mapping(session)
        links_df = extract_transaction_links(session)

    driver.close()
    log.info(f"Neo4j queries complete in {time.time() - start_time:.1f}s")

    # --- Assemble graph features in pandas ---
    log.info("Assembling graph features...")

    # Start with transaction base (communityId, pageRank)
    graph_df = tx_base_df

    # Add community stats
    graph_df = graph_df.merge(community_df, on="communityId", how="left")

    # Add entity links to join entity stats
    graph_df = graph_df.merge(links_df, on="TransactionID", how="left")

    # Add card stats (merge all card-level features first)
    card_df = card_df.merge(card_device_df, on="card1", how="left")
    card_df = card_df.merge(card_addr_count_df, on="card1", how="left")
    card_df = card_df.merge(fraud_same_card_df, on="card1", how="left")
    graph_df = graph_df.merge(card_df, on="card1", how="left")

    # Compute neighborCardFraudRate in pandas (2-hop: cards sharing same address)
    # Join card→addr mapping with card fraud rates, then aggregate per card
    log.info("Computing neighbor card fraud rate (2-hop via address, in pandas)...")
    if len(card_addr_map_df) > 0:
        # For each address, get avg fraud rate of all cards at that address
        addr_card_fraud = card_addr_map_df.merge(
            card_df[["card1", "cardFraudRate"]].rename(columns={"card1": "neighbor_card1"}),
            left_on="card1", right_on="neighbor_card1", how="left"
        )
        # Per address: avg fraud rate across all cards
        addr_avg_fraud = addr_card_fraud.groupby("addr1")["cardFraudRate"].mean().reset_index()
        addr_avg_fraud.columns = ["addr1", "addrAvgCardFraudRate"]

        # Per card: avg of address-level avg card fraud rates (excluding self is approximated)
        card_neighbor = card_addr_map_df.merge(addr_avg_fraud, on="addr1", how="left")
        card_neighbor_agg = card_neighbor.groupby("card1")["addrAvgCardFraudRate"].mean().reset_index()
        card_neighbor_agg.columns = ["card1", "neighborCardFraudRate"]

        # Count distinct neighbor cards per address
        neighbor_counts = card_addr_map_df.groupby("card1")["addr1"].count().reset_index()
        neighbor_counts.columns = ["card1", "neighborCardCount"]

        graph_df = graph_df.merge(card_neighbor_agg, on="card1", how="left")
        graph_df = graph_df.merge(neighbor_counts, on="card1", how="left")
        log.info("  Neighbor card fraud rate computed")

    # Add address stats
    graph_df = graph_df.merge(addr_df, on="addr1", how="left")

    # Add email degree
    graph_df = graph_df.merge(email_df, left_on="P_emaildomain", right_on="domain", how="left")
    graph_df.drop(columns=["domain"], inplace=True, errors="ignore")

    # Add device degree
    graph_df = graph_df.merge(device_df, left_on="deviceFingerprint", right_on="fingerprint", how="left")
    graph_df.drop(columns=["fingerprint", "deviceFingerprint", "P_emaildomain", "card1", "addr1"],
                  inplace=True, errors="ignore")

    # Compute maxEntityFraudRate — max fraud rate across all connected entities
    fraud_rate_cols = ["cardFraudRate", "addrFraudRate", "emailFraudRate", "deviceFraudRate"]
    existing_fr_cols = [c for c in fraud_rate_cols if c in graph_df.columns]
    if existing_fr_cols:
        graph_df["maxEntityFraudRate"] = graph_df[existing_fr_cols].max(axis=1)

    log.info(f"  Graph features shape: {graph_df.shape}")

    # Save graph-only features
    graph_only_path = os.path.join(OUTPUT_DIR, "graph_features.parquet")
    graph_df.to_parquet(graph_only_path, index=False)
    log.info(f"Saved graph features: {graph_only_path}")

    graph_csv_path = os.path.join(OUTPUT_DIR, "graph_features.csv")
    graph_df.to_csv(graph_csv_path, index=False)
    log.info(f"Saved graph features CSV: {graph_csv_path}")

    # --- Build tabular features and merge ---
    tabular_df = build_tabular_features(TRANSACTION_PATH, IDENTITY_PATH)

    final_df = tabular_df.merge(graph_df, on="TransactionID", how="left")

    # --- Summary ---
    graph_columns = [
        "communityId", "pageRank",
        "communitySize", "communityFraudRate", "communityAvgAmount", "communityStdAmount",
        "cardDegree", "cardFraudRate", "numDevicesOnCard", "addressesPerCard",
        "neighborCardFraudRate", "neighborCardCount", "fraudOnSameCard",
        "addrDegree", "addrFraudRate", "numCardsAtAddress",
        "emailDegree", "emailFraudRate", "cardsPerEmail",
        "deviceDegree", "deviceFraudRate",
        "maxEntityFraudRate",
    ]
    log.info(f"\nGraph features added ({len(graph_columns)}):")
    for col in graph_columns:
        if col in final_df.columns:
            non_null = final_df[col].notna().sum()
            log.info(f"  {col:25s}  non-null: {non_null:>8,} / {len(final_df):,}")

    log.info(f"\nFinal feature matrix: {final_df.shape}")

    features_path = os.path.join(OUTPUT_DIR, "feature_matrix.parquet")
    final_df.to_parquet(features_path, index=False)
    log.info(f"Saved feature matrix: {features_path}")

    elapsed = time.time() - start_time
    log.info(f"\nTotal pipeline time: {elapsed:.1f}s")
    log.info("Done.")


if __name__ == "__main__":
    main()