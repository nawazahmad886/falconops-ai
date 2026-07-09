FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir httpx pyyaml requests
COPY check_node.py .
ENV API_URL=""
ENV NODE_NAME="check-node"
ENV NODE_REGION="us-east"
ENV CHECK_INTERVAL="60"
CMD ["python3", "check_node.py"]
