FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY load_graph.py .
COPY cypher_queries.py .
COPY export_graph_features.py .

CMD ["python", "-u", "load_graph.py"]