"""
Cypher queries for graph-based fraud detection using Neo4j Graph Data Science (GDS).

Prerequisites:
  - Neo4j with GDS plugin installed
  - Graph loaded via load_graph.py

Usage:
  Run these queries in Neo4j Browser (http://localhost:7474)
  or execute programmatically via the Neo4j Python driver.
"""

# =============================================================================
# 1. GRAPH PROJECTION — Create an in-memory graph for GDS algorithms
# =============================================================================

# Project the card-transaction bipartite graph (undirected for community detection)
PROJECT_CARD_TRANSACTION_GRAPH = """
CALL gds.graph.project(
    'fraud-card-graph',
    ['Transaction', 'Card'],
    {
        USED_CARD: { orientation: 'UNDIRECTED' }
    },
    {
        nodeProperties: {
            isFraud: { defaultValue: 0 },
            amount:  { defaultValue: 0.0 }
        }
    }
)
YIELD graphName, nodeCount, relationshipCount
"""

# Full entity graph — transactions linked through cards, addresses, emails, devices
PROJECT_FULL_ENTITY_GRAPH = """
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
"""


# =============================================================================
# 2. COMMUNITY DETECTION — Louvain algorithm
# =============================================================================

# Detect communities in the full entity graph and write back to nodes
LOUVAIN_COMMUNITY_DETECTION = """
CALL gds.louvain.write(
    'fraud-entity-graph',
    {
        writeProperty: 'communityId',
        maxLevels: 10,
        maxIterations: 10
    }
)
YIELD communityCount, modularity, ranLevels, nodePropertiesWritten
"""

# Stream Louvain results (preview without writing)
LOUVAIN_STREAM = """
CALL gds.louvain.stream('fraud-entity-graph')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS node, communityId
WHERE 'Transaction' IN labels(node)
RETURN communityId,
       count(node)                              AS txCount,
       sum(CASE WHEN node.isFraud = 1 THEN 1 ELSE 0 END) AS fraudCount,
       toFloat(sum(CASE WHEN node.isFraud = 1 THEN 1 ELSE 0 END)) /
           count(node)                          AS fraudRate,
       avg(node.amount)                         AS avgAmount
ORDER BY fraudRate DESC, txCount DESC
LIMIT 25
"""

# Find high-risk communities — clusters with elevated fraud rates
HIGH_RISK_COMMUNITIES = """
MATCH (t:Transaction)
WHERE t.communityId IS NOT NULL
WITH t.communityId AS community,
     count(t)      AS txCount,
     sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END) AS fraudCount
WHERE txCount >= 10
WITH community, txCount, fraudCount,
     toFloat(fraudCount) / txCount AS fraudRate
WHERE fraudRate > 0.10
RETURN community, txCount, fraudCount,
       round(fraudRate * 100, 2) AS fraudRatePct
ORDER BY fraudRate DESC
LIMIT 20
"""

# Inspect a specific community — see all entity types within it
INSPECT_COMMUNITY = """
// Replace $communityId with the target community ID
MATCH (n {communityId: $communityId})
RETURN labels(n)[0] AS nodeType,
       count(n)      AS count
ORDER BY count DESC
"""

# Visualize a community subgraph (limit for browser performance)
VISUALIZE_COMMUNITY = """
MATCH (t:Transaction {communityId: $communityId})-[r]-(neighbor)
WITH t, r, neighbor
LIMIT 200
RETURN t, r, neighbor
"""


# =============================================================================
# 3. PAGERANK — Identify influential nodes in the fraud network
# =============================================================================

# Run PageRank on the full entity graph and write scores back
PAGERANK_WRITE = """
CALL gds.pageRank.write(
    'fraud-entity-graph',
    {
        writeProperty: 'pageRank',
        maxIterations: 20,
        dampingFactor: 0.85
    }
)
YIELD nodePropertiesWritten, ranIterations,
      didConverge, centralityDistribution
"""

# Stream PageRank — top cards by influence (high-degree hub cards)
PAGERANK_TOP_CARDS = """
CALL gds.pageRank.stream('fraud-entity-graph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE 'Card' IN labels(node)
RETURN node.card1 AS card,
       node.card4 AS brand,
       node.card6 AS type,
       round(score, 6) AS pageRank
ORDER BY score DESC
LIMIT 20
"""

# Top devices by PageRank — potential fraud device hubs
PAGERANK_TOP_DEVICES = """
CALL gds.pageRank.stream('fraud-entity-graph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE 'Device' IN labels(node)
RETURN node.deviceType AS deviceType,
       node.deviceInfo AS deviceInfo,
       round(score, 6) AS pageRank
ORDER BY score DESC
LIMIT 20
"""

# Transactions with highest PageRank — likely connected to fraud hubs
PAGERANK_TOP_TRANSACTIONS = """
MATCH (t:Transaction)
WHERE t.pageRank IS NOT NULL
RETURN t.id       AS transactionId,
       t.isFraud  AS isFraud,
       t.amount   AS amount,
       t.productCD AS productCD,
       round(t.pageRank, 6) AS pageRank
ORDER BY t.pageRank DESC
LIMIT 25
"""

# Correlate PageRank with fraud — do high-PageRank transactions have more fraud?
PAGERANK_FRAUD_CORRELATION = """
MATCH (t:Transaction)
WHERE t.pageRank IS NOT NULL
WITH CASE
       WHEN t.pageRank < 0.5  THEN 'low'
       WHEN t.pageRank < 2.0  THEN 'medium'
       ELSE 'high'
     END AS prBucket,
     t.isFraud AS isFraud
RETURN prBucket,
       count(*)                                      AS txCount,
       sum(isFraud)                                  AS fraudCount,
       round(toFloat(sum(isFraud)) / count(*) * 100, 2) AS fraudRatePct
ORDER BY CASE prBucket
           WHEN 'low'    THEN 1
           WHEN 'medium' THEN 2
           WHEN 'high'   THEN 3
         END
"""


# =============================================================================
# 4. COMBINED ANALYSIS — Community + PageRank fraud risk scoring
# =============================================================================

# Risk score: combine community fraud rate with node PageRank
COMBINED_RISK_SCORE = """
MATCH (t:Transaction)
WHERE t.communityId IS NOT NULL AND t.pageRank IS NOT NULL
WITH t.communityId AS community,
     count(t) AS txCount,
     toFloat(sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END)) / count(t) AS communityFraudRate
WHERE txCount >= 10
WITH community, txCount, communityFraudRate
MATCH (t:Transaction {communityId: community})
RETURN t.id                         AS transactionId,
       t.isFraud                    AS actualFraud,
       t.amount                     AS amount,
       community                    AS communityId,
       round(communityFraudRate * 100, 2) AS communityFraudRatePct,
       round(t.pageRank, 6)        AS pageRank,
       round(communityFraudRate * 0.6 + t.pageRank * 0.4, 4) AS riskScore
ORDER BY riskScore DESC
LIMIT 50
"""

# Fraud ring detection — cards sharing addresses with high fraud rates
FRAUD_RING_DETECTION = """
MATCH (c1:Card)-[:LINKED_TO_ADDRESS]->(a:Address)<-[:LINKED_TO_ADDRESS]-(c2:Card)
WHERE c1 <> c2
WITH a, collect(DISTINCT c1) + collect(DISTINCT c2) AS cards
WHERE size(cards) >= 3
UNWIND cards AS card
MATCH (card)<-[:USED_CARD]-(t:Transaction)
WITH a.addr1 AS address,
     size(cards) AS cardCount,
     count(t) AS txCount,
     sum(CASE WHEN t.isFraud = 1 THEN 1 ELSE 0 END) AS fraudCount
WHERE txCount >= 5
RETURN address, cardCount, txCount, fraudCount,
       round(toFloat(fraudCount) / txCount * 100, 2) AS fraudRatePct
ORDER BY fraudRatePct DESC, cardCount DESC
LIMIT 20
"""


# =============================================================================
# 5. UTILITY QUERIES
# =============================================================================

# Graph summary statistics
GRAPH_STATS = """
CALL gds.graph.list()
YIELD graphName, nodeCount, relationshipCount, memoryUsage
RETURN graphName, nodeCount, relationshipCount, memoryUsage
"""

# Drop a projected graph when done
DROP_GRAPH = """
CALL gds.graph.drop('fraud-entity-graph')
"""

DROP_CARD_GRAPH = """
CALL gds.graph.drop('fraud-card-graph')
"""
