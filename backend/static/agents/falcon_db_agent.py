#!/usr/bin/env python3
"""
FalconOps AI - Database Monitoring Agent v1.0.0
Lightweight external agent that collects database metrics and pushes them to the FalconOps API.
Supports: PostgreSQL, MySQL, Oracle, SQL Server (simulated mode for demo)

Usage:
    python3 falcon_db_agent.py --config /etc/falconops/db_agent.yaml
    python3 falcon_db_agent.py --config /etc/falconops/db_agent.yaml --dry-run --once
"""
import os
import sys
import time
import json
import argparse
import logging
import random
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("falcon-db-agent")

VERSION = "1.0.0"


def load_config(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        with open(path) as f:
            return json.load(f)


def collect_simulated(cfg):
    """Simulated metrics for demo/testing"""
    return {
        "metrics": {
            "active_sessions": random.randint(5, 120),
            "total_connections": random.randint(20, 300),
            "cpu_usage": round(random.uniform(10, 85), 1),
            "memory_usage": round(random.uniform(30, 90), 1),
            "tps": random.randint(50, 2000),
            "cache_hit_ratio": round(random.uniform(85, 99.9), 2),
            "io_read_ms": round(random.uniform(0.5, 15), 2),
            "io_write_ms": round(random.uniform(0.5, 10), 2),
            "db_size_bytes": random.randint(100000000, 50000000000),
            "replication_lag_ms": round(random.uniform(0, 500), 1),
            "agent_version": VERSION,
        },
        "slow_queries": [
            {
                "query": "SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at",
                "duration_ms": round(random.uniform(500, 5000), 1),
                "calls": random.randint(10, 500),
                "user": "app_user",
                "fingerprint": "SELECT * FROM orders WHERE status = ?",
            }
        ] if random.random() > 0.5 else [],
        "locks": [],
    }


def push_metrics(api_url, api_key, instance_id, data):
    url = f"{api_url}/api/db-monitoring/metrics/ingest"
    payload = {
        "instance_id": instance_id,
        "metrics": data["metrics"],
        "slow_queries": data.get("slow_queries", []),
        "locks": data.get("locks", []),
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="FalconOps DB Monitoring Agent")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_cfg = cfg.get("database", {})
    api_cfg = cfg.get("api", {})
    interval = cfg.get("collection_interval", 60)

    logger.info(f"FalconOps DB Agent v{VERSION} starting (interval={interval}s)")

    while True:
        try:
            data = collect_simulated(db_cfg)
            if args.dry_run:
                logger.info(f"[DRY RUN] {json.dumps(data, indent=2)}")
            else:
                result = push_metrics(api_cfg.get("endpoint", ""), api_cfg.get("key", ""), api_cfg.get("instance_id", ""), data)
                logger.info(f"Pushed: {result}")
        except Exception as e:
            logger.error(f"Failed: {e}")

        if args.once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
