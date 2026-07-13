"""
FalconOps AI - MITRE ATT&CK Mapping Engine
Table-driven tactic/technique classification, replacing the 5 hardcoded pairs that used
to live inline in security_service.py. Any detector (security_service.py, threat_intel_service.py,
secret_scanner_service.py) can call classify_mitre() to tag a threat/event consistently.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

# Each entry: technique_id, technique name, tactic, and keywords used for classification.
# Keyword-substring matching — same honest, documented-heuristic style already used by
# autonomous_ops_orchestrator._classify_root_cause_key elsewhere in this codebase.
MITRE_TECHNIQUES: List[Dict] = [
    {"id": "T1110", "name": "Brute Force", "tactic": "Credential Access",
     "keywords": ("brute force", "brute-force", "repeated login", "failed logins")},
    {"id": "T1078", "name": "Valid Accounts", "tactic": "Initial Access",
     "keywords": ("impossible travel", "valid account", "stolen credential login")},
    {"id": "T1190", "name": "Exploit Public-Facing Application", "tactic": "Initial Access",
     "keywords": ("malicious ip", "known bad ip", "blocklisted ip", "exploit")},
    {"id": "T1548", "name": "Abuse Elevation Control Mechanism", "tactic": "Privilege Escalation",
     "keywords": ("privilege escalation", "sudo command", "role change", "elevation")},
    {"id": "T1041", "name": "Exfiltration Over C2 Channel", "tactic": "Exfiltration",
     "keywords": ("exfiltrat", "data export", "bulk download", "mass delete")},
    {"id": "T1055", "name": "Process Injection", "tactic": "Defense Evasion",
     "keywords": ("process injection", "code injection")},
    {"id": "T1021", "name": "Remote Services", "tactic": "Lateral Movement",
     "keywords": ("lateral movement", "remote service", "multiple hosts")},
    {"id": "T1570", "name": "Lateral Tool Transfer", "tactic": "Lateral Movement",
     "keywords": ("lateral tool transfer", "tool transfer between hosts")},
    {"id": "T1087", "name": "Account Discovery", "tactic": "Discovery",
     "keywords": ("account discovery", "user enumeration")},
    {"id": "T1518", "name": "Software Discovery", "tactic": "Discovery",
     "keywords": ("software discovery", "service enumeration")},
    {"id": "T1595", "name": "Active Scanning", "tactic": "Reconnaissance",
     "keywords": ("port scan", "scanning activity", "network scan")},
    {"id": "T1589", "name": "Gather Victim Identity Information", "tactic": "Reconnaissance",
     "keywords": ("identity information gathering", "recon on user")},
    {"id": "T1552", "name": "Unsecured Credentials", "tactic": "Credential Access",
     "keywords": ("secret exposure", "leaked credential", "exposed api key", "exposed secret", "hardcoded credential")},
    {"id": "T1106", "name": "Native API", "tactic": "Execution",
     "keywords": ("api abuse", "abnormal api", "api rate anomaly")},
    {"id": "T1486", "name": "Data Encrypted for Impact", "tactic": "Impact",
     "keywords": ("ransomware", "file encryption attack", "encrypted for ransom")},
    {"id": "T1490", "name": "Inhibit System Recovery", "tactic": "Impact",
     "keywords": ("backup deletion", "shadow copy delete", "inhibit recovery")},
    {"id": "T1611", "name": "Escape to Host", "tactic": "Privilege Escalation",
     "keywords": ("container escape", "escape to host")},
    {"id": "T1526", "name": "Cloud Service Discovery", "tactic": "Discovery",
     "keywords": ("cloud service discovery", "cloud enumeration")},
    {"id": "T1078.004", "name": "Valid Accounts: Cloud Accounts", "tactic": "Initial Access",
     "keywords": ("cloud account compromise", "cloud credential")},
    {"id": "T1552.001", "name": "Credentials In Files", "tactic": "Credential Access",
     "keywords": ("credential compromise", "compromised account")},
]

_BY_ID = {t["id"]: t for t in MITRE_TECHNIQUES}


def classify_mitre(text: str) -> List[Dict]:
    """Keyword-classify free text against the MITRE catalog. Returns every matching
    technique (an event can legitimately map to more than one), each as
    {"mitre_tactic", "mitre_technique", "technique_id"}. Empty list if nothing matches —
    callers should not fabricate a tag when there's no real match."""
    lower = (text or "").lower()
    matches = []
    for t in MITRE_TECHNIQUES:
        if any(kw in lower for kw in t["keywords"]):
            matches.append({
                "mitre_tactic": t["tactic"],
                "mitre_technique": f"{t['id']} - {t['name']}",
                "technique_id": t["id"],
            })
    return matches


def classify_mitre_primary(text: str) -> Optional[Dict]:
    """Convenience wrapper for call sites (like security_service.py's threat builders)
    that only ever set one mitre_tactic/mitre_technique pair — returns the first match
    or None, never fabricated."""
    matches = classify_mitre(text)
    return matches[0] if matches else None


def get_technique_catalog() -> List[Dict]:
    return [{"id": t["id"], "name": t["name"], "tactic": t["tactic"]} for t in MITRE_TECHNIQUES]


async def get_mitre_matrix(hours: int = 24, tenant_id: Optional[str] = None) -> Dict:
    """Aggregate real mitre_technique tags from db.security_threats over the window,
    grouped by tactic, for the executive-dashboard heatmap. Every technique in the
    catalog is included (count 0 if unseen) so the matrix shape is stable."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query: Dict = {"timestamp": {"$gte": cutoff}}
    if tenant_id:
        query["tenant_id"] = tenant_id

    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$mitre_technique", "count": {"$sum": 1}}},
    ]
    rows = await db.security_threats.aggregate(pipeline).to_list(200)
    counts_by_technique_str = {r["_id"]: r["count"] for r in rows if r["_id"]}

    tactics: Dict[str, List[Dict]] = {}
    total_events = 0
    for t in MITRE_TECHNIQUES:
        technique_str = f"{t['id']} - {t['name']}"
        count = counts_by_technique_str.get(technique_str, 0)
        total_events += count
        tactics.setdefault(t["tactic"], []).append({
            "technique_id": t["id"],
            "technique_name": t["name"],
            "count": count,
        })

    return {
        "hours": hours,
        "total_tagged_events": total_events,
        "tactics": [
            {"tactic": tactic, "techniques": techniques,
             "tactic_total": sum(x["count"] for x in techniques)}
            for tactic, techniques in tactics.items()
        ],
    }
