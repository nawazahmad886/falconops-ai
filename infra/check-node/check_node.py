#!/usr/bin/env python3
"""
FalconOps AI - Distributed Check Node
Runs in any region, self-registers, pulls monitor configs, executes checks, pushes results.
Deploy via Docker: docker run -e API_URL=https://... -e NODE_REGION=eu-west falconops-check-node
"""
import os
import sys
import time
import json
import socket
import logging
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("check-node")

VERSION = "1.0.0"


def get_public_ip():
    try:
        with httpx.Client(timeout=5) as c:
            return c.get("https://api.ipify.org").text.strip()
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def register(api_url, name, region, ip):
    resp = httpx.post(f"{api_url}/api/check-nodes/register", json={
        "name": name, "region": region, "ip": ip, "version": VERSION,
        "capabilities": ["http", "https", "tcp"],
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Registered as {data.get('id')} in {region}")
    return data["id"]


def heartbeat(api_url, node_id):
    try:
        httpx.post(f"{api_url}/api/check-nodes/{node_id}/heartbeat", json={"metrics": {}}, timeout=5)
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")


def fetch_monitors(api_url, node_id):
    try:
        resp = httpx.get(f"{api_url}/api/check-nodes/{node_id}/monitors", timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"Fetch monitors failed: {e}")
        return []


def check_url(url, method="GET", timeout=10, expected=200):
    try:
        start = time.time()
        with httpx.Client(timeout=timeout, follow_redirects=True) as c:
            if method == "HEAD":
                resp = c.head(url)
            elif method == "POST":
                resp = c.post(url)
            else:
                resp = c.get(url)
            duration = (time.time() - start) * 1000
            return {
                "status_code": resp.status_code,
                "response_time_ms": round(duration, 1),
                "success": resp.status_code == expected,
                "error": None,
            }
    except httpx.TimeoutException:
        return {"status_code": 0, "response_time_ms": timeout * 1000, "success": False, "error": "Timeout"}
    except Exception as e:
        return {"status_code": 0, "response_time_ms": 0, "success": False, "error": str(e)[:200]}


def submit_result(api_url, node_id, monitor, result, region):
    try:
        httpx.post(f"{api_url}/api/check-nodes/{node_id}/results", json={
            "monitor_id": monitor["id"],
            "url": monitor["url"],
            "region": region,
            **result,
        }, timeout=10)
    except Exception as e:
        logger.error(f"Submit result failed: {e}")


def main():
    api_url = os.environ.get("API_URL", "").rstrip("/")
    node_name = os.environ.get("NODE_NAME", f"node-{socket.gethostname()}")
    region = os.environ.get("NODE_REGION", "us-east")
    interval = int(os.environ.get("CHECK_INTERVAL", "60"))

    if not api_url:
        logger.error("API_URL env var required")
        sys.exit(1)

    ip = get_public_ip()
    logger.info(f"FalconOps Check Node v{VERSION} | Region: {region} | IP: {ip}")

    node_id = register(api_url, node_name, region, ip)
    last_hb = 0

    while True:
        now = time.time()
        if now - last_hb >= 30:
            heartbeat(api_url, node_id)
            last_hb = now

        monitors = fetch_monitors(api_url, node_id)
        for mon in monitors:
            result = check_url(
                mon["url"],
                mon.get("method", "GET"),
                mon.get("timeout", 10),
                mon.get("expected_status", 200),
            )
            submit_result(api_url, node_id, mon, result, region)
            logger.info(f"Checked {mon['name']}: {result['status_code']} in {result['response_time_ms']}ms")

        time.sleep(interval)


if __name__ == "__main__":
    main()
