# Fraud Detection Framework

A machine learning framework for fraud detection using the Kaggle IEEE dataset, featuring a real-time streaming pipeline with Kafka and Neo4j graph analytics.

## Project Structure

- `Fraud_Detection_Kaggle_IEEE_Dataset.ipynb` — Jupyter notebook for EDA and model development
- `Fraud_Detection_Kaggle_IEEE_Dataset.py` — Python script version
- `Kaggle-IEEE-dataset/` — Dataset directory
- `fraud-detection-pipeline/` — Real-time fraud detection pipeline (Kafka, Docker)
  - `graph-loader/` — Neo4j graph loader and Cypher queries for community detection & PageRank