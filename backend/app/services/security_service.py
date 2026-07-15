"""
FalconOps AI - Security Monitoring & Threat Detection Service
Real-time security event processing, threat detection, and user behavior analysis
"""
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Dict, Any, Optional

from ..core.database import db
from . import mitre_mapping_service
from . import threat_intel_service
from .anomaly_detection_engine import anomaly_detection_engine as _anomaly_engine

logger = logging.getLogger(__name__)

# ======================== IN-MEMORY THREAT STATE ========================

_failed_logins = defaultdict(list)  # ip -> [timestamps]
_user_locations = defaultdict(list)  # user -> [(ip, timestamp)]
_user_hosts = defaultdict(list)  # user -> [(host, timestamp)] — lateral-movement tracker
_api_call_counts = defaultdict(list)  # user_or_ip -> [timestamps] — per-minute API call tracker
_ip_failed_users = defaultdict(list)  # ip -> [(user, timestamp)] — credential-stuffing tracker
_signup_attempts = defaultdict(list)  # ip -> [timestamps] — signup-abuse tracker
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW_MINUTES = 10
LATERAL_MOVEMENT_HOST_THRESHOLD = 3
LATERAL_MOVEMENT_WINDOW_MINUTES = 15
CREDENTIAL_STUFFING_USER_THRESHOLD = 8
CREDENTIAL_STUFFING_WINDOW_MINUTES = 10
SIGNUP_ABUSE_THRESHOLD = 5
SIGNUP_ABUSE_WINDOW_MINUTES = 30
ACCOUNT_TAKEOVER_RISK_THRESHOLD = 50
ACCOUNT_TAKEOVER_HISTORY_DAYS = 90

# Known automation/headless-browser/scripting client signatures — a coarse but real
# signal (not a fabricated one): legitimate browsers never send these tokens.
_BOT_UA_PATTERNS = re.compile(
    r"selenium|headlesschrome|phantomjs|puppeteer|playwright|python-requests|"
    r"scrapy|curl/|wget/|go-http-client|okhttp|axios/|bot|crawler|spider",
    re.IGNORECASE,
)


# ======================== THREAT DETECTION ENGINE ========================

class ThreatDetectionEngine:
    """Real-time threat detection engine"""

    async def process_event(self, event: Dict) -> Optional[Dict]:
        """Process a single security event and detect threats"""
        threats = []

        if event.get("action") in ("login_failed", "auth_failure"):
            t = await self._check_brute_force(event)
            if t:
                threats.append(t)
            t = await self._check_credential_stuffing(event)
            if t:
                threats.append(t)

        if event.get("action") in ("signup", "signup_failed"):
            t = await self._check_signup_abuse(event)
            if t:
                threats.append(t)

        t = await self._check_malicious_ip(event)
        if t:
            threats.append(t)

        if event.get("action") in ("login_success", "login_failed"):
            t = await self._check_impossible_travel(event)
            if t:
                threats.append(t)

        if event.get("action") in ("privilege_escalation", "sudo_command", "role_change"):
            threats.append(await self._flag_privilege_escalation(event))

        if event.get("action") in ("data_export", "bulk_download", "mass_delete"):
            threats.append(await self._flag_data_exfiltration(event))

        if event.get("action") == "login_success":
            t = await self._check_lateral_movement(event)
            if t:
                threats.append(t)
            t = await self._check_account_takeover_risk(event)
            if t:
                threats.append(t)

        if event.get("category") == "application" or event.get("action") == "api_access":
            t = await self._check_api_abuse(event)
            if t:
                threats.append(t)

        if event.get("action") in ("login_success", "login_failed", "signup", "signup_failed"):
            t = await self._check_bot_traffic(event)
            if t:
                threats.append(t)

        # Store any generated threats
        for threat in threats:
            if threat:
                await self._store_threat(threat)

        return threats if threats else None

    async def _check_brute_force(self, event: Dict) -> Optional[Dict]:
        ip = event.get("source_ip", "unknown")
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=BRUTE_FORCE_WINDOW_MINUTES)

        _failed_logins[ip] = [t for t in _failed_logins[ip] if t > cutoff]
        _failed_logins[ip].append(now)

        if len(_failed_logins[ip]) >= BRUTE_FORCE_THRESHOLD:
            mitre = mitre_mapping_service.classify_mitre_primary("brute force repeated login failed logins") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "brute_force",
                "severity": "critical",
                "source_ip": ip,
                "target_user": event.get("user", "unknown"),
                "message": f"Brute force attack detected: {len(_failed_logins[ip])} failed logins from {ip} in {BRUTE_FORCE_WINDOW_MINUTES}min",
                "attempt_count": len(_failed_logins[ip]),
                "timestamp": now.isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Credential Access"),
                "mitre_technique": mitre.get("mitre_technique", "T1110 - Brute Force"),
            }
        return None

    async def _check_credential_stuffing(self, event: Dict) -> Optional[Dict]:
        """Distinguishes credential stuffing from brute force: brute force is many failed
        attempts against ONE username from an IP; credential stuffing is failed attempts
        against MANY DISTINCT usernames from one IP — the signature of testing a leaked
        username/password list. Needs no password data (which we deliberately never log),
        just the username + IP already captured on every failed login."""
        ip = event.get("source_ip", "unknown")
        user = event.get("user", "unknown")
        if not ip or ip == "unknown" or not user or user == "unknown":
            return None
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=CREDENTIAL_STUFFING_WINDOW_MINUTES)

        _ip_failed_users[ip] = [(u, t) for u, t in _ip_failed_users[ip] if t > cutoff]
        _ip_failed_users[ip].append((user, now))

        distinct_users = {u for u, _ in _ip_failed_users[ip]}
        if len(distinct_users) >= CREDENTIAL_STUFFING_USER_THRESHOLD:
            mitre = mitre_mapping_service.classify_mitre_primary("credential stuffing repeated login failed logins") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "credential_stuffing",
                "severity": "critical",
                "source_ip": ip,
                "message": f"Possible credential stuffing: failed logins against {len(distinct_users)} distinct "
                           f"usernames from {ip} in {CREDENTIAL_STUFFING_WINDOW_MINUTES}min",
                "distinct_usernames": len(distinct_users),
                "timestamp": now.isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Credential Access"),
                "mitre_technique": mitre.get("mitre_technique", "T1110 - Brute Force"),
            }
        return None

    async def _check_signup_abuse(self, event: Dict) -> Optional[Dict]:
        """Mass-registration / signup-abuse proxy: many registration attempts from one IP
        in a short window (fake accounts, bot registrations, enumeration of existing
        emails via the 'already registered' response)."""
        ip = event.get("source_ip", "unknown")
        if not ip or ip == "unknown":
            return None
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=SIGNUP_ABUSE_WINDOW_MINUTES)

        _signup_attempts[ip] = [t for t in _signup_attempts[ip] if t > cutoff]
        _signup_attempts[ip].append(now)

        if len(_signup_attempts[ip]) >= SIGNUP_ABUSE_THRESHOLD:
            mitre = mitre_mapping_service.classify_mitre_primary("account discovery user enumeration") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "signup_abuse",
                "severity": "medium",
                "source_ip": ip,
                "message": f"Possible signup abuse: {len(_signup_attempts[ip])} registration attempt(s) "
                           f"from {ip} in {SIGNUP_ABUSE_WINDOW_MINUTES}min",
                "attempt_count": len(_signup_attempts[ip]),
                "timestamp": now.isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Reconnaissance"),
                "mitre_technique": mitre.get("mitre_technique", "T1589 - Gather Victim Identity Information"),
            }
        return None

    async def _check_account_takeover_risk(self, event: Dict) -> Optional[Dict]:
        """Composite account-takeover risk score on a successful login: is this IP,
        geo, and/or device genuinely new for this user, based on their real login
        history (not a fabricated score). A user's first-ever login has nothing to
        compare against and is never flagged."""
        user = event.get("user", "unknown")
        if not user or user == "unknown":
            return None
        ip = event.get("source_ip", "")
        geo = event.get("geo_location", "")
        device = event.get("user_agent", "")

        cutoff = (datetime.now(timezone.utc) - timedelta(days=ACCOUNT_TAKEOVER_HISTORY_DAYS)).isoformat()
        history = await db.security_events.find({
            "user": user, "action": "login_success",
            "timestamp": {"$gte": cutoff, "$lt": event.get("timestamp", datetime.now(timezone.utc).isoformat())},
        }, {"_id": 0, "source_ip": 1, "geo_location": 1, "user_agent": 1}).sort("timestamp", -1).limit(50).to_list(50)

        if not history:
            return None  # no prior logins to compare against — not suspicious, just new

        known_ips = {h.get("source_ip") for h in history if h.get("source_ip")}
        known_geos = {h.get("geo_location") for h in history if h.get("geo_location")}
        known_devices = {h.get("user_agent") for h in history if h.get("user_agent")}

        risk = 0
        reasons = []
        if ip and known_ips and ip not in known_ips:
            risk += 30
            reasons.append("new IP address")
        if geo and known_geos and geo not in known_geos:
            risk += 35
            reasons.append("new geographic location")
        if device and known_devices and device not in known_devices:
            risk += 25
            reasons.append("new device/browser")

        if risk < ACCOUNT_TAKEOVER_RISK_THRESHOLD:
            return None

        mitre = mitre_mapping_service.classify_mitre_primary("valid account compromise") or {}
        return {
            "id": str(uuid.uuid4()),
            "type": "account_takeover_risk",
            "severity": "critical" if risk >= 80 else "high",
            "user": user,
            "source_ip": ip,
            "message": f"Elevated account-takeover risk for {user}: {', '.join(reasons)} (risk {risk}/100)",
            "risk_score": risk,
            "risk_factors": reasons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "mitre_tactic": mitre.get("mitre_tactic", "Initial Access"),
            "mitre_technique": mitre.get("mitre_technique", "T1078 - Valid Accounts"),
        }

    async def _check_bot_traffic(self, event: Dict) -> Optional[Dict]:
        """Flags known automation/headless-browser/scripting client signatures on
        auth-related requests — a real (if coarse) signal since legitimate human
        browsers never send these User-Agent tokens."""
        ua = event.get("user_agent") or ""
        if not ua or not _BOT_UA_PATTERNS.search(ua):
            return None
        mitre = mitre_mapping_service.classify_mitre_primary("api abuse abnormal api") or {}
        return {
            "id": str(uuid.uuid4()),
            "type": "bot_traffic",
            "severity": "medium",
            "user": event.get("user", "unknown"),
            "source_ip": event.get("source_ip", "unknown"),
            "message": f"Automated/bot-like client detected on {event.get('action')}: "
                       f"user-agent matched known automation signature",
            "user_agent": ua[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "mitre_tactic": mitre.get("mitre_tactic", "Execution"),
            "mitre_technique": mitre.get("mitre_technique", "T1106 - Native API"),
        }

    async def _check_malicious_ip(self, event: Dict) -> Optional[Dict]:
        ip = event.get("source_ip", "")
        if not ip or ip == "unknown":
            return None
        match = await threat_intel_service.is_malicious_ip(ip)
        if match:
            mitre = mitre_mapping_service.classify_mitre_primary("malicious ip known bad ip blocklisted ip") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "malicious_ip",
                "severity": "critical",
                "source_ip": ip,
                "message": f"Connection from known malicious IP: {ip} (source: {match.get('source')}, "
                           f"{match.get('malware_family') or 'threat intel match'})",
                "ioc_source": match.get("source"),
                "malware_family": match.get("malware_family"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Initial Access"),
                "mitre_technique": mitre.get("mitre_technique", "T1190 - Exploit Public-Facing Application"),
            }
        return None

    async def _check_lateral_movement(self, event: Dict) -> Optional[Dict]:
        """Flag a user authenticating to many distinct hosts in a short window —
        a real signal of lateral movement, not just noisy legitimate access patterns."""
        user = event.get("user", "unknown")
        host = event.get("host", "")
        if not host or user == "unknown":
            return None
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=LATERAL_MOVEMENT_WINDOW_MINUTES)

        _user_hosts[user] = [(h, t) for h, t in _user_hosts[user] if t > cutoff]
        _user_hosts[user].append((host, now))

        distinct_hosts = {h for h, _ in _user_hosts[user]}
        if len(distinct_hosts) >= LATERAL_MOVEMENT_HOST_THRESHOLD:
            mitre = mitre_mapping_service.classify_mitre_primary("lateral movement remote service multiple hosts") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "lateral_movement",
                "severity": "high",
                "user": user,
                "source_ip": event.get("source_ip", "unknown"),
                "message": f"Possible lateral movement: {user} authenticated to {len(distinct_hosts)} distinct hosts "
                           f"in {LATERAL_MOVEMENT_WINDOW_MINUTES}min ({', '.join(sorted(distinct_hosts)[:5])})",
                "hosts": sorted(distinct_hosts),
                "timestamp": now.isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Lateral Movement"),
                "mitre_technique": mitre.get("mitre_technique", "T1021 - Remote Services"),
            }
        return None

    async def _check_api_abuse(self, event: Dict) -> Optional[Dict]:
        """Reuses the real IsolationForest+ensemble anomaly_detection_engine on a
        per-minute API-call-count series, rather than a bespoke threshold — a genuine
        ML-based detector, not a second hardcoded rule."""
        key = event.get("user") if event.get("user") and event.get("user") != "unknown" else event.get("source_ip", "unknown")
        if not key or key == "unknown":
            return None
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=6)
        _api_call_counts[key] = [t for t in _api_call_counts[key] if t > cutoff]
        _api_call_counts[key].append(now)

        # Write the rolling per-minute REQUEST COUNT (not a constant 1 per event) — the
        # anomaly engine detects spikes in this value over time, so it must actually vary
        # with call volume, or a burst would look identical to steady-state traffic.
        rolling_count = sum(1 for t in _api_call_counts[key] if t > now - timedelta(minutes=1))
        try:
            await db.metrics_timeseries.insert_one({
                "name": "api_requests_per_min",
                "value": rolling_count,
                "unit": "count",
                "tags": {"host": key},
                "timestamp": now.isoformat(),
            })
        except Exception as e:
            logger.debug(f"api_requests_per_min metric write skipped: {e}")

        # Only worth running the detector once we have a minimally meaningful baseline.
        if len(_api_call_counts[key]) < 10:
            return None

        try:
            result = await _anomaly_engine.analyze_metric("api_requests_per_min", host=key, lookback_hours=6)
        except Exception as e:
            logger.debug(f"api abuse anomaly check skipped: {e}")
            return None

        anomaly = result.get("anomaly") or {}
        if result.get("status") == "success" and anomaly.get("is_anomaly"):
            mitre = mitre_mapping_service.classify_mitre_primary("api abuse abnormal api rate anomaly") or {}
            return {
                "id": str(uuid.uuid4()),
                "type": "api_abuse",
                "severity": "high" if anomaly.get("severity") in ("high", "critical") else "medium",
                "user": event.get("user", "unknown"),
                "source_ip": event.get("source_ip", "unknown"),
                "message": f"Abnormal API request rate detected for {key}: ensemble anomaly score "
                           f"{anomaly.get('ensemble_score')} ({anomaly.get('detector_votes')}/{anomaly.get('total_detectors')} detectors agree)",
                "ensemble_score": anomaly.get("ensemble_score"),
                "timestamp": now.isoformat(),
                "status": "active",
                "mitre_tactic": mitre.get("mitre_tactic", "Execution"),
                "mitre_technique": mitre.get("mitre_technique", "T1106 - Native API"),
            }
        return None

    async def _check_impossible_travel(self, event: Dict) -> Optional[Dict]:
        user = event.get("user", "unknown")
        ip = event.get("source_ip", "unknown")
        geo = event.get("geo_location", "")
        now = datetime.now(timezone.utc)

        _user_locations[user].append({"ip": ip, "geo": geo, "ts": now})
        # Keep last 20 entries
        _user_locations[user] = _user_locations[user][-20:]

        locations = _user_locations[user]
        if len(locations) >= 2:
            prev = locations[-2]
            curr = locations[-1]
            if prev["geo"] and curr["geo"] and prev["geo"] != curr["geo"]:
                delta = (curr["ts"] - prev["ts"]).total_seconds()
                if delta < 3600:  # < 1 hour between different geos
                    mitre = mitre_mapping_service.classify_mitre_primary("impossible travel valid account") or {}
                    return {
                        "id": str(uuid.uuid4()),
                        "type": "impossible_travel",
                        "severity": "high",
                        "user": user,
                        "source_ip": ip,
                        "message": f"Impossible travel: {user} logged in from {prev['geo']} and {curr['geo']} within {int(delta/60)}min",
                        "from_location": prev["geo"],
                        "to_location": curr["geo"],
                        "time_delta_seconds": delta,
                        "timestamp": now.isoformat(),
                        "status": "active",
                        "mitre_tactic": mitre.get("mitre_tactic", "Initial Access"),
                        "mitre_technique": mitre.get("mitre_technique", "T1078 - Valid Accounts"),
                    }
        return None

    async def _flag_privilege_escalation(self, event: Dict) -> Dict:
        mitre = mitre_mapping_service.classify_mitre_primary("privilege escalation sudo command role change") or {}
        return {
            "id": str(uuid.uuid4()),
            "type": "privilege_escalation",
            "severity": "high",
            "user": event.get("user", "unknown"),
            "source_ip": event.get("source_ip", "unknown"),
            "message": f"Privilege escalation detected: {event.get('user', 'unknown')} performed {event.get('action', '')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "mitre_tactic": mitre.get("mitre_tactic", "Privilege Escalation"),
            "mitre_technique": mitre.get("mitre_technique", "T1548 - Abuse Elevation Control"),
        }

    async def _flag_data_exfiltration(self, event: Dict) -> Dict:
        mitre = mitre_mapping_service.classify_mitre_primary("exfiltration data export bulk download") or {}
        return {
            "id": str(uuid.uuid4()),
            "type": "data_exfiltration",
            "severity": "critical",
            "user": event.get("user", "unknown"),
            "source_ip": event.get("source_ip", "unknown"),
            "message": f"Potential data exfiltration: {event.get('user', 'unknown')} initiated {event.get('action', '')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "mitre_tactic": mitre.get("mitre_tactic", "Exfiltration"),
            "mitre_technique": mitre.get("mitre_technique", "T1041 - Exfiltration Over C2 Channel"),
        }

    async def _store_threat(self, threat: Dict):
        try:
            await db.security_threats.insert_one(threat)
            # Dispatch to configured integrations
            try:
                from .connector_dispatcher import dispatch_threat
                from .remediation_service import auto_remediate_threat
                await dispatch_threat(threat)
                await auto_remediate_threat(threat)
            except Exception as e:
                logger.warning(f"Threat dispatch/remediation skipped: {e}")
            # Publish to the real event bus (Kafka if connected, MongoDB fallback
            # otherwise) — kafka_consumers.py's handler fans this out to the SOC
            # live feed and a durable event_log record.
            try:
                from .kafka_pipeline import producer
                await producer.send("threats", {k: v for k, v in threat.items() if k != "_id"})
            except Exception as e:
                logger.warning(f"Threat event publish skipped: {e}")
            # 'AI anomaly trigger' workflows — best-effort, never allowed to affect
            # threat storage itself.
            try:
                from . import workflow_trigger_service
                asyncio.create_task(workflow_trigger_service.evaluate_anomaly_triggers(threat))
            except Exception as e:
                logger.warning(f"Anomaly trigger evaluation skipped: {e}")
        except Exception as e:
            logger.error(f"Failed to store threat: {e}")


# Singleton
threat_engine = ThreatDetectionEngine()


# ======================== SECURITY EVENT INGESTION ========================

async def ingest_security_event(event: Dict, tenant_id: str = None) -> Dict:
    """Ingest and process a security event"""
    doc = {
        "id": str(uuid.uuid4()),
        "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "event_type": "security",
        "category": event.get("category", "authentication"),
        "action": event.get("action", "unknown"),
        "user": event.get("user", "unknown"),
        "source_ip": event.get("source_ip", "unknown"),
        "target": event.get("target", ""),
        "status": event.get("status", "unknown"),
        "severity": event.get("severity", "info"),
        "message": event.get("message", ""),
        "host": event.get("host", ""),
        "service": event.get("service", ""),
        "geo_location": event.get("geo_location", ""),
        "user_agent": event.get("user_agent", ""),
        "source": event.get("source", "api"),
        "raw": event.get("raw", ""),
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.security_events.insert_one(doc)

    # Run threat detection
    detected = await threat_engine.process_event(doc)

    return {
        "id": doc["id"],
        "threats_detected": len(detected) if detected else 0,
        "threats": detected or [],
    }


# ======================== DASHBOARD & QUERIES ========================

async def get_security_dashboard(hours: int = 24) -> Dict:
    """Get security dashboard overview"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    total_events = await db.security_events.count_documents({"timestamp": {"$gte": cutoff}})
    active_threats = await db.security_threats.count_documents({"status": "active"})
    critical_threats = await db.security_threats.count_documents({"status": "active", "severity": "critical"})
    high_threats = await db.security_threats.count_documents({"status": "active", "severity": "high"})

    # Severity breakdown
    severity_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
    ]
    severity_data = await db.security_events.aggregate(severity_pipeline).to_list(10)
    severity_map = {s["_id"]: s["count"] for s in severity_data}

    # Top threat types
    threat_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_threats = await db.security_threats.aggregate(threat_pipeline).to_list(5)

    # Top source IPs
    ip_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}, "action": {"$in": ["login_failed", "auth_failure"]}}},
        {"$group": {"_id": "$source_ip", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_ips = await db.security_events.aggregate(ip_pipeline).to_list(10)

    # Event category breakdown
    cat_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    categories = await db.security_events.aggregate(cat_pipeline).to_list(20)

    # Timeline (hourly buckets for last 24h)
    timeline = []
    for i in range(min(hours, 24)):
        bucket_start = datetime.now(timezone.utc) - timedelta(hours=i + 1)
        bucket_end = datetime.now(timezone.utc) - timedelta(hours=i)
        count = await db.security_events.count_documents({
            "timestamp": {"$gte": bucket_start.isoformat(), "$lt": bucket_end.isoformat()}
        })
        threat_count = await db.security_threats.count_documents({
            "timestamp": {"$gte": bucket_start.isoformat(), "$lt": bucket_end.isoformat()}
        })
        timeline.append({
            "hour": bucket_end.strftime("%H:%M"),
            "events": count,
            "threats": threat_count,
        })
    timeline.reverse()

    return {
        "total_events": total_events,
        "active_threats": active_threats,
        "critical_threats": critical_threats,
        "high_threats": high_threats,
        "severity_breakdown": severity_map,
        "top_threat_types": [{"type": t["_id"], "count": t["count"]} for t in top_threats],
        "top_source_ips": [{"ip": ip["_id"], "count": ip["count"]} for ip in top_ips],
        "event_categories": [{"category": c["_id"], "count": c["count"]} for c in categories],
        "timeline": timeline,
    }


async def get_auth_security_dashboard(hours: int = 24) -> Dict:
    """Authentication-specific security dashboard: success/failure counts, signups,
    top attacking IPs, failures by country, and counts of the auth-specific threat
    types (credential stuffing, signup abuse, account-takeover risk, bot traffic)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    base_query = {"timestamp": {"$gte": cutoff}, "category": "authentication"}

    login_success = await db.security_events.count_documents({**base_query, "action": "login_success"})
    login_failed = await db.security_events.count_documents({**base_query, "action": "login_failed"})
    signups = await db.security_events.count_documents({**base_query, "action": "signup"})
    signup_failed = await db.security_events.count_documents({**base_query, "action": "signup_failed"})

    top_ip_pipeline = [
        {"$match": {**base_query, "action": "login_failed"}},
        {"$group": {"_id": "$source_ip", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_ips = await db.security_events.aggregate(top_ip_pipeline).to_list(10)

    country_pipeline = [
        {"$match": {**base_query, "action": "login_failed", "geo_location": {"$ne": ""}}},
        {"$group": {"_id": "$geo_location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    by_country = await db.security_events.aggregate(country_pipeline).to_list(10)

    threat_query = {"timestamp": {"$gte": cutoff}, "status": "active"}
    auth_threat_counts = {}
    for t in ("credential_stuffing", "signup_abuse", "account_takeover_risk", "bot_traffic", "brute_force", "impossible_travel"):
        auth_threat_counts[t] = await db.security_threats.count_documents({**threat_query, "type": t})

    return {
        "login_success": login_success,
        "login_failed": login_failed,
        "signups": signups,
        "signup_failed": signup_failed,
        "success_rate": round(100 * login_success / max(login_success + login_failed, 1), 1),
        "top_attacking_ips": [{"ip": r["_id"], "count": r["count"]} for r in top_ips],
        "failures_by_country": [{"country": r["_id"], "count": r["count"]} for r in by_country],
        "threat_counts": auth_threat_counts,
        "hours": hours,
    }


async def get_threats(status: str = "active", severity: str = None, limit: int = 50) -> List[Dict]:
    """Get threats with filters"""
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    threats = await db.security_threats.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return threats


async def get_user_activity(hours: int = 24, limit: int = 50) -> Dict:
    """Get user activity summary for security analysis"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Users with most failed logins
    failed_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}, "action": {"$in": ["login_failed", "auth_failure"]}}},
        {"$group": {
            "_id": "$user",
            "failed_count": {"$sum": 1},
            "ips": {"$addToSet": "$source_ip"},
            "last_attempt": {"$max": "$timestamp"},
        }},
        {"$sort": {"failed_count": -1}},
        {"$limit": limit},
    ]
    failed_users = await db.security_events.aggregate(failed_pipeline).to_list(limit)

    # Users with successful logins from multiple IPs
    multi_ip_pipeline = [
        {"$match": {"timestamp": {"$gte": cutoff}, "action": "login_success"}},
        {"$group": {
            "_id": "$user",
            "ips": {"$addToSet": "$source_ip"},
            "login_count": {"$sum": 1},
            "last_login": {"$max": "$timestamp"},
        }},
        {"$match": {"$expr": {"$gt": [{"$size": "$ips"}, 1]}}},
        {"$sort": {"login_count": -1}},
        {"$limit": limit},
    ]
    multi_ip_users = await db.security_events.aggregate(multi_ip_pipeline).to_list(limit)

    # Recent privileged actions
    priv_events = await db.security_events.find(
        {"timestamp": {"$gte": cutoff}, "action": {"$in": ["privilege_escalation", "sudo_command", "role_change", "data_export"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)

    return {
        "suspicious_users": [
            {"user": u["_id"], "failed_logins": u["failed_count"], "unique_ips": len(u["ips"]), "ips": u["ips"][:5], "last_attempt": u["last_attempt"]}
            for u in failed_users
        ],
        "multi_ip_users": [
            {"user": u["_id"], "ip_count": len(u["ips"]), "ips": u["ips"][:5], "login_count": u["login_count"], "last_login": u["last_login"]}
            for u in multi_ip_users
        ],
        "privileged_actions": priv_events,
    }


async def get_security_events(
    hours: int = 24, category: str = None, severity: str = None,
    action: str = None, search: str = None, limit: int = 100, offset: int = 0
) -> Dict:
    """Get security events with filters"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query = {"timestamp": {"$gte": cutoff}}

    if category:
        query["category"] = category
    if severity:
        query["severity"] = severity
    if action:
        query["action"] = action
    if search:
        escaped = re.escape(search)
        query["$or"] = [
            {"message": {"$regex": escaped, "$options": "i"}},
            {"user": {"$regex": escaped, "$options": "i"}},
            {"source_ip": {"$regex": escaped, "$options": "i"}},
        ]

    events = await db.security_events.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit).to_list(limit)
    total = await db.security_events.count_documents(query)

    return {"events": events, "total": total, "limit": limit, "offset": offset}


async def update_threat_status(threat_id: str, status: str, resolved_by: str = None) -> Dict:
    """Update threat status (resolve, dismiss, etc.)"""
    update = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if resolved_by:
        update["resolved_by"] = resolved_by

    result = await db.security_threats.update_one({"id": threat_id}, {"$set": update})
    if result.modified_count == 0:
        return {"error": "Threat not found"}
    return {"message": f"Threat {threat_id} updated to {status}"}


async def correlate_security_ops() -> List[Dict]:
    """Correlate security events with operational incidents"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    # Get active security threats
    sec_threats = await db.security_threats.find(
        {"status": "active", "timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).to_list(50)

    # Get active health violations / performance issues
    perf_issues = await db["db.health_violations"].find(
        {"state": {"$in": ["active", "critical", "warning"]}, "timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).to_list(50)

    correlations = []
    for threat in sec_threats:
        t_ip = threat.get("source_ip", "")
        t_host = threat.get("host", "")
        for perf in perf_issues:
            p_host = perf.get("source_name", "")
            if t_ip and (t_ip == p_host or t_host == p_host):
                correlations.append({
                    "id": str(uuid.uuid4()),
                    "type": "security_ops_correlation",
                    "severity": "critical",
                    "message": f"Security threat ({threat['type']}) and performance issue ({perf.get('rule_name', '')}) detected on same host: {p_host}",
                    "security_threat": {"id": threat["id"], "type": threat["type"], "severity": threat["severity"]},
                    "ops_issue": {"rule_name": perf.get("rule_name", ""), "severity": perf.get("severity", ""), "metric": perf.get("metric", "")},
                    "host": p_host,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    return correlations


# ======================== DEMO DATA GENERATOR ========================

async def generate_security_demo_data(count: int = 200) -> Dict:
    """Generate realistic security events for demo"""
    import random

    actions = [
        ("login_success", "authentication", "info"),
        ("login_failed", "authentication", "warning"),
        ("login_failed", "authentication", "warning"),
        ("auth_failure", "authentication", "warning"),
        ("sudo_command", "authorization", "high"),
        ("privilege_escalation", "authorization", "critical"),
        ("firewall_block", "network", "warning"),
        ("port_scan", "network", "high"),
        ("data_export", "data_access", "high"),
        ("api_access", "application", "info"),
        ("config_change", "configuration", "warning"),
        ("vpn_connect", "network", "info"),
        ("vpn_disconnect", "network", "info"),
        ("mfa_bypass_attempt", "authentication", "critical"),
    ]

    users = ["admin", "ops_engineer", "dev_user", "service_account", "security_analyst", "unknown", "root"]
    ips = [
        "192.168.1.100", "192.168.1.101", "10.0.0.50", "10.0.0.51",
        "172.16.0.10", "203.0.113.42", "198.51.100.77", "45.33.32.156",
        "185.220.101.1", "91.121.87.18",
    ]
    hosts = ["prod-web-01", "prod-web-02", "prod-db-01", "staging-api-01", "firewall-01", "vpn-gw-01"]
    services = ["sshd", "nginx", "api-gateway", "admin-portal", "database", "vpn", "firewall"]
    geos = ["Riyadh, SA", "Jeddah, SA", "Dubai, AE", "London, UK", "Berlin, DE", "Shanghai, CN", ""]

    events = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        action, category, severity = random.choice(actions)
        ts = now - timedelta(minutes=random.randint(0, 1440))
        user = random.choice(users)
        ip = random.choice(ips)

        msg_map = {
            "login_success": f"Successful login for {user} from {ip}",
            "login_failed": f"Failed login attempt for {user} from {ip}",
            "auth_failure": f"Authentication failure for {user}",
            "sudo_command": f"Sudo command executed by {user}",
            "privilege_escalation": f"Privilege escalation by {user}",
            "firewall_block": f"Firewall blocked connection from {ip}",
            "port_scan": f"Port scan detected from {ip}",
            "data_export": f"Data export initiated by {user}",
            "api_access": f"API access by {user}",
            "config_change": f"Configuration changed by {user}",
            "vpn_connect": f"VPN connection from {user} at {ip}",
            "vpn_disconnect": f"VPN disconnected for {user}",
            "mfa_bypass_attempt": f"MFA bypass attempt for {user} from {ip}",
        }

        events.append({
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat(),
            "event_type": "security",
            "category": category,
            "action": action,
            "user": user,
            "source_ip": ip,
            "target": random.choice(hosts),
            "status": "failed" if "fail" in action else "success",
            "severity": severity,
            "message": msg_map.get(action, f"{action} by {user}"),
            "host": random.choice(hosts),
            "service": random.choice(services),
            "geo_location": random.choice(geos),
            "user_agent": "",
            "source": "demo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if events:
        await db.security_events.insert_many(events)

    # Process some events through threat engine for demo threats
    threat_count = 0
    for ev in events[:50]:
        result = await threat_engine.process_event(ev)
        if result:
            threat_count += len(result)

    return {
        "events_created": len(events),
        "threats_detected": threat_count,
    }
