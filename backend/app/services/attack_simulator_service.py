"""
FalconOps AI - Attack Simulation Service
Controlled red-team simulation engine for testing security detection capabilities
"""
import uuid
import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from ..core.database import db
from .security_service import threat_engine

logger = logging.getLogger(__name__)


SCENARIOS = {
    "brute_force": {
        "name": "Brute Force Attack",
        "description": "Simulate multiple failed login attempts from a single IP",
        "severity": "critical",
        "mitre": "T1110",
        "default_config": {"attempts": 15, "target_user": "admin", "source_ip": "185.220.101.1", "delay_ms": 500},
    },
    "credential_stuffing": {
        "name": "Credential Stuffing",
        "description": "Simulate login attempts with multiple username/password combinations",
        "severity": "critical",
        "mitre": "T1110.004",
        "default_config": {"attempts": 20, "source_ip": "91.121.87.18", "delay_ms": 300},
    },
    "impossible_travel": {
        "name": "Impossible Travel",
        "description": "Simulate login from two geographically distant locations in a short time",
        "severity": "high",
        "mitre": "T1078",
        "default_config": {"user": "ops_engineer", "locations": ["Riyadh, SA", "London, UK"], "delay_ms": 1000},
    },
    "privilege_escalation": {
        "name": "Privilege Escalation",
        "description": "Simulate unauthorized privilege escalation attempts",
        "severity": "high",
        "mitre": "T1548",
        "default_config": {"user": "dev_user", "escalation_count": 5, "delay_ms": 800},
    },
    "data_exfiltration": {
        "name": "Data Exfiltration",
        "description": "Simulate suspicious data export and bulk download activity",
        "severity": "critical",
        "mitre": "T1041",
        "default_config": {"user": "service_account", "export_count": 8, "delay_ms": 600},
    },
    "port_scan": {
        "name": "Port Scan",
        "description": "Simulate network port scanning activity from an external IP",
        "severity": "high",
        "mitre": "T1046",
        "default_config": {"source_ip": "45.33.32.156", "ports": 50, "delay_ms": 100},
    },
    "insider_threat": {
        "name": "Insider Threat",
        "description": "Simulate off-hours access, unusual data access, and suspicious behavior",
        "severity": "critical",
        "mitre": "T1078",
        "default_config": {"user": "security_analyst", "events": 12, "delay_ms": 700},
    },
}


async def run_simulation(scenario_id: str, config: Dict = None) -> Dict:
    """Run an attack simulation scenario"""
    if scenario_id not in SCENARIOS:
        return {"error": f"Unknown scenario: {scenario_id}"}

    scenario = SCENARIOS[scenario_id]
    cfg = {**scenario["default_config"], **(config or {})}

    sim_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc)

    events = []
    threats_detected = 0

    if scenario_id == "brute_force":
        events, threats_detected = await _sim_brute_force(sim_id, cfg, now)
    elif scenario_id == "credential_stuffing":
        events, threats_detected = await _sim_credential_stuffing(sim_id, cfg, now)
    elif scenario_id == "impossible_travel":
        events, threats_detected = await _sim_impossible_travel(sim_id, cfg, now)
    elif scenario_id == "privilege_escalation":
        events, threats_detected = await _sim_privilege_escalation(sim_id, cfg, now)
    elif scenario_id == "data_exfiltration":
        events, threats_detected = await _sim_data_exfiltration(sim_id, cfg, now)
    elif scenario_id == "port_scan":
        events, threats_detected = await _sim_port_scan(sim_id, cfg, now)
    elif scenario_id == "insider_threat":
        events, threats_detected = await _sim_insider_threat(sim_id, cfg, now)

    # Store simulation record
    sim_record = {
        "id": sim_id,
        "scenario": scenario_id,
        "scenario_name": scenario["name"],
        "config": cfg,
        "events_generated": len(events),
        "threats_detected": threats_detected,
        "status": "completed",
        "started_at": now.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.attack_simulations.insert_one(sim_record)

    # Remove MongoDB _id before returning (not JSON serializable)
    sim_record.pop("_id", None)
    return sim_record


async def _sim_brute_force(sim_id, cfg, now):
    events = []
    threats = 0
    ip = cfg["source_ip"]
    user = cfg["target_user"]
    for i in range(cfg["attempts"]):
        ts = now - timedelta(seconds=(cfg["attempts"] - i) * 2)
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "authentication", "action": "login_failed", "user": user,
            "source_ip": ip, "severity": "warning", "host": "prod-web-01",
            "service": "sshd", "message": f"[SIM-{sim_id}] Failed SSH login for {user} from {ip}",
            "geo_location": "Unknown", "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_credential_stuffing(sim_id, cfg, now):
    events = []
    threats = 0
    ip = cfg["source_ip"]
    users = ["admin", "root", "operator", "service", "deploy", "backup", "test", "dev", "staging", "monitor"]
    for i in range(cfg["attempts"]):
        ts = now - timedelta(seconds=(cfg["attempts"] - i) * 1)
        user = users[i % len(users)]
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "authentication", "action": "login_failed", "user": user,
            "source_ip": ip, "severity": "warning", "host": "prod-web-01",
            "service": "api-gateway", "message": f"[SIM-{sim_id}] Credential stuffing: {user} from {ip}",
            "geo_location": "Unknown", "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_impossible_travel(sim_id, cfg, now):
    events = []
    threats = 0
    user = cfg["user"]
    locs = cfg["locations"]
    ips = ["10.0.0.50", "203.0.113.42"]
    for i, loc in enumerate(locs):
        ts = now - timedelta(minutes=30 - i * 25)
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "authentication", "action": "login_success", "user": user,
            "source_ip": ips[i % len(ips)], "severity": "info", "host": "prod-web-01",
            "service": "admin-portal", "message": f"[SIM-{sim_id}] Login from {loc}",
            "geo_location": loc, "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_privilege_escalation(sim_id, cfg, now):
    events = []
    threats = 0
    user = cfg["user"]
    actions = ["sudo_command", "privilege_escalation", "role_change"]
    for i in range(cfg["escalation_count"]):
        ts = now - timedelta(seconds=(cfg["escalation_count"] - i) * 10)
        action = actions[i % len(actions)]
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "authorization", "action": action, "user": user,
            "source_ip": "10.0.0.50", "severity": "critical" if action == "privilege_escalation" else "high",
            "host": "prod-db-01", "service": "database",
            "message": f"[SIM-{sim_id}] {action} by {user}",
            "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_data_exfiltration(sim_id, cfg, now):
    events = []
    threats = 0
    user = cfg["user"]
    data_actions = ["data_export", "bulk_download", "data_export", "mass_delete"]
    for i in range(cfg["export_count"]):
        ts = now - timedelta(seconds=(cfg["export_count"] - i) * 15)
        action = data_actions[i % len(data_actions)]
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "data_access", "action": action, "user": user,
            "source_ip": "172.16.0.10", "severity": "high",
            "host": "prod-db-01", "service": "database",
            "message": f"[SIM-{sim_id}] {action} initiated by {user}",
            "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_port_scan(sim_id, cfg, now):
    events = []
    threats = 0
    ip = cfg["source_ip"]
    for i in range(cfg["ports"]):
        ts = now - timedelta(seconds=(cfg["ports"] - i))
        port = random.choice([22, 80, 443, 3306, 5432, 6379, 8080, 8443, 9200, 27017])
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": "network", "action": "port_scan", "user": "unknown",
            "source_ip": ip, "severity": "high",
            "host": "firewall-01", "service": "firewall",
            "target": f"prod-web-01:{port}",
            "message": f"[SIM-{sim_id}] Port scan from {ip} targeting port {port}",
            "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


async def _sim_insider_threat(sim_id, cfg, now):
    events = []
    threats = 0
    user = cfg["user"]
    insider_actions = [
        ("login_success", "authentication", "info", "Off-hours login"),
        ("data_export", "data_access", "high", "Large data export"),
        ("config_change", "configuration", "warning", "Security config modified"),
        ("privilege_escalation", "authorization", "critical", "Self-elevated privileges"),
        ("data_export", "data_access", "high", "Database dump"),
        ("bulk_download", "data_access", "high", "Bulk file download"),
    ]
    for i in range(cfg["events"]):
        ts = now - timedelta(minutes=(cfg["events"] - i) * 5)
        action, cat, sev, desc = insider_actions[i % len(insider_actions)]
        ev = {
            "id": str(uuid.uuid4()), "timestamp": ts.isoformat(), "event_type": "security",
            "category": cat, "action": action, "user": user,
            "source_ip": "192.168.1.100", "severity": sev,
            "host": "prod-db-01", "service": "admin-portal",
            "message": f"[SIM-{sim_id}] {desc} by {user}",
            "source": "attack_simulation", "created_at": now.isoformat(),
        }
        events.append(ev)
        result = await threat_engine.process_event(ev)
        if result:
            threats += len(result)
    if events:
        await db.security_events.insert_many(events)
    return events, threats


def get_available_scenarios() -> List[Dict]:
    """Get list of available attack scenarios"""
    return [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "severity": v["severity"],
            "mitre": v["mitre"],
            "default_config": v["default_config"],
        }
        for k, v in SCENARIOS.items()
    ]


async def get_simulation_history(limit: int = 20) -> List[Dict]:
    """Get recent simulation history"""
    return await db.attack_simulations.find(
        {}, {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
