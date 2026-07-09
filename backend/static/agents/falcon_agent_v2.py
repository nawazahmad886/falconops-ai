#!/usr/bin/env python3
"""
FalconOps Monitoring Agent v2
Standalone system metrics collector for FalconOps AI Platform

Usage:
    python falcon_agent_v2.py --api-url https://your-falconops.com --token YOUR_TOKEN

Collects: CPU, Memory, Disk, Network, Load Average, Process Count, Uptime
Pushes to: /api/servers/metrics/ingest and /api/metrics/ingest
"""
import os
import sys
import time
import json
import uuid
import socket
import platform
import argparse
import logging
from datetime import datetime, timezone

try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

try:
    import requests
    REQUESTS = True
except ImportError:
    REQUESTS = False

if not REQUESTS:
    try:
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        import ssl
    except ImportError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FalconOps Agent] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("falcon-agent")

# ======================== CONFIG ========================

DEFAULT_INTERVAL = 30
DEFAULT_API_URL = os.environ.get("FALCON_API_URL", "")
DEFAULT_TOKEN = os.environ.get("FALCON_TOKEN", "")
DEFAULT_AGENT_TOKEN = os.environ.get("FALCON_AGENT_TOKEN", "")

# ======================== METRICS COLLECTION ========================

def collect_metrics():
    """Collect system metrics using psutil or /proc fallback."""
    metrics = {
        "hostname": socket.gethostname(),
        "ip_address": _get_ip(),
        "os_type": platform.system().lower(),
        "os_version": platform.platform(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if PSUTIL:
        metrics.update(_collect_psutil())
    else:
        metrics.update(_collect_proc())

    return metrics


def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _collect_psutil():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)
    boot = psutil.boot_time()
    uptime = int(time.time() - boot)

    return {
        "cpu_percent": round(cpu, 2),
        "memory_percent": round(mem.percent, 2),
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "disk_percent": round(disk.percent, 2),
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "network_in_mbps": round(net.bytes_recv / (1024**2), 2),
        "network_out_mbps": round(net.bytes_sent / (1024**2), 2),
        "load_average_1m": round(load[0], 2),
        "load_average_5m": round(load[1], 2),
        "load_average_15m": round(load[2], 2),
        "process_count": len(psutil.pids()),
        "uptime_seconds": uptime,
    }


def _collect_proc():
    """Fallback: read from /proc on Linux."""
    m = {}
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            m["load_average_1m"] = float(parts[0])
            m["load_average_5m"] = float(parts[1])
            m["load_average_15m"] = float(parts[2])
    except Exception:
        m["load_average_1m"] = 0

    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.strip().split()[0])
            total = info.get("MemTotal", 1)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            used = total - avail
            m["memory_percent"] = round(used / total * 100, 2)
            m["memory_used_gb"] = round(used / (1024**2), 2)
            m["memory_total_gb"] = round(total / (1024**2), 2)
    except Exception:
        m["memory_percent"] = 0

    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        m["disk_percent"] = round(used / total * 100, 2) if total else 0
        m["disk_used_gb"] = round(used / (1024**3), 2)
        m["disk_total_gb"] = round(total / (1024**3), 2)
    except Exception:
        m["disk_percent"] = 0

    try:
        with open("/proc/stat") as f:
            line = f.readline()
            parts = line.split()
            total_time = sum(int(p) for p in parts[1:])
            idle_time = int(parts[4])
            m["cpu_percent"] = round((1 - idle_time / total_time) * 100, 2) if total_time else 0
    except Exception:
        m["cpu_percent"] = 0

    m.setdefault("network_in_mbps", 0)
    m.setdefault("network_out_mbps", 0)
    m.setdefault("process_count", 0)
    m.setdefault("uptime_seconds", 0)
    return m


# ======================== API CLIENT ========================

def http_post(url, data, headers=None):
    """Send POST request (uses requests if available, else urllib)."""
    body = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)

    if REQUESTS:
        resp = requests.post(url, json=data, headers=hdrs, timeout=10)
        return resp.status_code, resp.text
    else:
        req = Request(url, data=body, headers=hdrs, method="POST")
        try:
            ctx = ssl.create_default_context()
            resp = urlopen(req, timeout=10, context=ctx)
            return resp.status, resp.read().decode()
        except HTTPError as e:
            return e.code, e.read().decode()
        except URLError as e:
            return 0, str(e)


def register_server(api_url, token, hostname, ip_address, os_type, os_version):
    """Register the server and get an agent_token."""
    url = f"{api_url}/api/servers/register"
    data = {
        "hostname": hostname,
        "ip_address": ip_address,
        "os_type": os_type,
        "os_version": os_version,
        "agent_version": "2.0.0",
        "tags": {"collector": "falcon-agent-v2"}
    }
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    status, body = http_post(url, data, headers)
    if status in (200, 201):
        result = json.loads(body)
        return result.get("agent_token") or result.get("server_id")
    log.error(f"Registration failed: {status} {body}")
    return None


def push_server_metrics(api_url, agent_token, metrics):
    """Push metrics to /api/servers/metrics/ingest."""
    url = f"{api_url}/api/servers/metrics/ingest"
    data = {
        "agent_token": agent_token,
        "cpu_percent": metrics.get("cpu_percent", 0),
        "memory_percent": metrics.get("memory_percent", 0),
        "memory_used_gb": metrics.get("memory_used_gb"),
        "memory_total_gb": metrics.get("memory_total_gb"),
        "disk_percent": metrics.get("disk_percent", 0),
        "disk_used_gb": metrics.get("disk_used_gb"),
        "disk_total_gb": metrics.get("disk_total_gb"),
        "network_in_mbps": metrics.get("network_in_mbps"),
        "network_out_mbps": metrics.get("network_out_mbps"),
        "load_average_1m": metrics.get("load_average_1m"),
        "load_average_5m": metrics.get("load_average_5m"),
        "load_average_15m": metrics.get("load_average_15m"),
        "process_count": metrics.get("process_count"),
        "uptime_seconds": metrics.get("uptime_seconds"),
        "timestamp": metrics.get("timestamp"),
    }
    status, body = http_post(url, data)
    return status in (200, 201)


def push_timeseries_metrics(api_url, token, metrics):
    """Push metrics to /api/metrics/v2/ingest for the time-series pipeline."""
    url = f"{api_url}/api/metrics/v2/ingest"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    hostname = metrics.get("hostname", "unknown")

    metric_batch = []
    for metric_name in ["cpu_percent", "memory_percent", "disk_percent", "load_average_1m"]:
        value = metrics.get(metric_name)
        if value is not None:
            clean_name = metric_name.replace("_percent", "_usage")
            metric_batch.append({
                "name": clean_name,
                "value": value,
                "timestamp": metrics.get("timestamp"),
                "tags": {
                    "host": hostname,
                    "service": "system",
                    "collector": "falcon-agent-v2",
                    "environment": "production"
                }
            })

    for m in metric_batch:
        status, _ = http_post(url, m, headers)
        if status not in (200, 201):
            log.warning(f"Failed to push {m['name']}: status={status}")


# ======================== MAIN LOOP ========================

def main():
    parser = argparse.ArgumentParser(description="FalconOps Monitoring Agent v2")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="FalconOps API URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="JWT auth token")
    parser.add_argument("--agent-token", default=DEFAULT_AGENT_TOKEN, help="Pre-registered agent token")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Collection interval (seconds)")
    parser.add_argument("--once", action="store_true", help="Collect once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print metrics without sending")
    args = parser.parse_args()

    if not args.api_url and not args.dry_run:
        log.error("--api-url is required. Set FALCON_API_URL env var or pass --api-url")
        sys.exit(1)

    log.info(f"FalconOps Agent v2 starting")
    log.info(f"  API URL:  {args.api_url}")
    log.info(f"  Interval: {args.interval}s")
    log.info(f"  psutil:   {'yes' if PSUTIL else 'no (using /proc fallback)'}")
    log.info(f"  requests: {'yes' if REQUESTS else 'no (using urllib)'}")

    agent_token = args.agent_token

    while True:
        try:
            metrics = collect_metrics()

            if args.dry_run:
                print(json.dumps(metrics, indent=2))
                if args.once:
                    break
                time.sleep(args.interval)
                continue

            # Auto-register if no agent token
            if not agent_token:
                agent_token = register_server(
                    args.api_url, args.token,
                    metrics["hostname"], metrics["ip_address"],
                    metrics["os_type"], metrics.get("os_version", "")
                )
                if agent_token:
                    log.info(f"Registered with agent token: {agent_token[:20]}...")
                else:
                    log.warning("Registration failed, retrying next cycle")

            # Push server metrics
            if agent_token:
                ok = push_server_metrics(args.api_url, agent_token, metrics)
                if ok:
                    log.info(f"CPU={metrics['cpu_percent']}% MEM={metrics['memory_percent']}% DISK={metrics['disk_percent']}%")
                else:
                    log.warning("Server metrics push failed")

            # Also push to time-series pipeline
            if args.token:
                push_timeseries_metrics(args.api_url, args.token, metrics)

        except KeyboardInterrupt:
            log.info("Agent stopped by user")
            break
        except Exception as e:
            log.error(f"Collection error: {e}")

        if args.once:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
