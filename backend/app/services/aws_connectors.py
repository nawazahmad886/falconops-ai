"""
FalconOps AI - AWS CloudTrail & VPC Flow Logs Connector
Polls AWS CloudTrail events and parses VPC Flow Logs for security event ingestion
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from ..core.database import db

logger = logging.getLogger(__name__)

_boto3_available = False
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    _boto3_available = True
except ImportError:
    logger.info("boto3 not available - AWS connectors will use simulation mode")


# ======================== CLOUDTRAIL CONNECTOR ========================

class CloudTrailConnector:
    """Fetch and normalize AWS CloudTrail events"""

    SECURITY_EVENTS = {
        "ConsoleLogin": ("authentication", "login_success"),
        "ConsoleLoginFailure": ("authentication", "login_failed"),
        "DeleteUser": ("authorization", "privilege_escalation"),
        "CreateUser": ("authorization", "config_change"),
        "AttachUserPolicy": ("authorization", "privilege_escalation"),
        "DetachUserPolicy": ("authorization", "config_change"),
        "CreateAccessKey": ("authorization", "config_change"),
        "DeleteAccessKey": ("authorization", "config_change"),
        "PutBucketPolicy": ("configuration", "config_change"),
        "AuthorizeSecurityGroupIngress": ("network", "config_change"),
        "RevokeSecurityGroupIngress": ("network", "config_change"),
        "StopInstances": ("compute", "config_change"),
        "TerminateInstances": ("compute", "config_change"),
    }

    def __init__(self, config: Dict):
        self.config = config
        self.client = None
        if _boto3_available and config.get("aws_access_key"):
            try:
                self.client = boto3.client(
                    "cloudtrail",
                    aws_access_key_id=config["aws_access_key"],
                    aws_secret_access_key=config.get("aws_secret_key", ""),
                    region_name=config.get("aws_region", "us-east-1"),
                )
            except Exception as e:
                logger.error(f"CloudTrail client init failed: {e}")

    async def fetch_events(self, max_results: int = 50) -> List[Dict]:
        """Fetch recent CloudTrail events and normalize them"""
        if not self.client:
            return self._simulate_events(max_results)

        try:
            response = self.client.lookup_events(MaxResults=min(max_results, 50))
            events = []
            for event in response.get("Events", []):
                normalized = self._normalize_event(event)
                if normalized:
                    events.append(normalized)
            return events
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"CloudTrail fetch failed: {e}")
            return []

    def _normalize_event(self, raw: Dict) -> Optional[Dict]:
        event_name = raw.get("EventName", "")
        mapping = self.SECURITY_EVENTS.get(event_name)
        category = mapping[0] if mapping else "aws_api"
        action = mapping[1] if mapping else "api_call"
        severity = "high" if event_name in ("DeleteUser", "AttachUserPolicy", "TerminateInstances") else "info"

        return {
            "timestamp": raw.get("EventTime", datetime.now(timezone.utc)).isoformat() if isinstance(raw.get("EventTime"), datetime) else datetime.now(timezone.utc).isoformat(),
            "event_type": "security",
            "category": category,
            "action": action,
            "user": raw.get("Username", "unknown"),
            "source_ip": raw.get("SourceIPAddress", ""),
            "severity": severity,
            "message": f"AWS CloudTrail: {event_name} by {raw.get('Username', 'unknown')}",
            "host": "aws",
            "service": "cloudtrail",
            "source": "aws_cloudtrail",
            "raw": event_name,
        }

    def _simulate_events(self, count: int) -> List[Dict]:
        """Generate simulated CloudTrail events when AWS isn't configured"""
        import random
        events = []
        actions = list(self.SECURITY_EVENTS.keys())
        users = ["admin-user", "deploy-role", "lambda-exec", "ci-cd-pipeline"]
        now = datetime.now(timezone.utc)

        for i in range(min(count, 20)):
            event_name = random.choice(actions)
            mapping = self.SECURITY_EVENTS[event_name]
            events.append({
                "timestamp": (now - timedelta(minutes=i * 3)).isoformat(),
                "event_type": "security",
                "category": mapping[0],
                "action": mapping[1],
                "user": random.choice(users),
                "source_ip": f"52.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
                "severity": "high" if event_name in ("DeleteUser", "AttachUserPolicy") else "info",
                "message": f"[Simulated] AWS CloudTrail: {event_name}",
                "host": "aws",
                "service": "cloudtrail",
                "source": "aws_cloudtrail_sim",
            })
        return events


# ======================== VPC FLOW LOG CONNECTOR ========================

class VPCFlowLogConnector:
    """Parse and normalize AWS VPC Flow Logs"""

    def __init__(self, config: Dict):
        self.config = config
        self.client = None
        if _boto3_available and config.get("aws_access_key"):
            try:
                self.client = boto3.client(
                    "logs",
                    aws_access_key_id=config["aws_access_key"],
                    aws_secret_access_key=config.get("aws_secret_key", ""),
                    region_name=config.get("aws_region", "us-east-1"),
                )
            except Exception as e:
                logger.error(f"VPC Flow Log client init failed: {e}")

    async def fetch_logs(self, max_results: int = 50) -> List[Dict]:
        if not self.client:
            return self._simulate_logs(max_results)

        try:
            log_group = self.config.get("log_group", "vpc-flow-logs")
            response = self.client.filter_log_events(
                logGroupName=log_group,
                limit=min(max_results, 50),
                interleaved=True,
            )
            events = []
            for event in response.get("events", []):
                normalized = self._parse_flow_log(event.get("message", ""))
                if normalized:
                    events.append(normalized)
            return events
        except Exception as e:
            logger.error(f"VPC Flow Log fetch failed: {e}")
            return []

    def _parse_flow_log(self, line: str) -> Optional[Dict]:
        """Parse a VPC Flow Log line: version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status"""
        parts = line.strip().split()
        if len(parts) < 14:
            return None
        try:
            action = parts[12]  # ACCEPT or REJECT
            severity = "warning" if action == "REJECT" else "info"
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "security",
                "category": "network",
                "action": "network_traffic",
                "user": "vpc",
                "source_ip": parts[3],
                "target": f"{parts[4]}:{parts[6]}",
                "severity": severity,
                "message": f"VPC Flow: {parts[3]}:{parts[5]} -> {parts[4]}:{parts[6]} {action}",
                "host": parts[2],
                "service": "vpc_flow",
                "source": "aws_vpc_flowlogs",
                "status": action.lower(),
            }
        except (IndexError, ValueError):
            return None

    def _simulate_logs(self, count: int) -> List[Dict]:
        import random
        events = []
        now = datetime.now(timezone.utc)
        src_ips = ["10.0.1.50", "10.0.2.100", "172.16.0.10", "185.220.101.1", "203.0.113.42"]
        dst_ips = ["10.0.1.10", "10.0.1.20", "10.0.2.10"]
        ports = [22, 80, 443, 3306, 5432, 8080]

        for i in range(min(count, 20)):
            action = random.choice(["ACCEPT", "ACCEPT", "ACCEPT", "REJECT"])
            src = random.choice(src_ips)
            dst = random.choice(dst_ips)
            port = random.choice(ports)
            events.append({
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "event_type": "security",
                "category": "network",
                "action": "network_traffic",
                "user": "vpc",
                "source_ip": src,
                "target": f"{dst}:{port}",
                "severity": "warning" if action == "REJECT" else "info",
                "message": f"[Simulated] VPC Flow: {src} -> {dst}:{port} {action}",
                "host": "eni-sim",
                "service": "vpc_flow",
                "source": "aws_vpc_sim",
                "status": action.lower(),
            })
        return events


# ======================== CONNECTOR ORCHESTRATOR ========================

async def fetch_aws_events() -> Dict:
    """Fetch events from all configured AWS connectors and ingest them"""
    from .security_service import ingest_security_event

    results = {"cloudtrail": 0, "vpc_flow": 0, "errors": []}

    # CloudTrail
    ct_config = await db.integrations.find_one({"integration_id": "aws_cloudtrail", "enabled": True}, {"_id": 0})
    if ct_config:
        connector = CloudTrailConnector(ct_config.get("config", {}))
        events = await connector.fetch_events(50)
        for ev in events:
            await ingest_security_event(ev)
        results["cloudtrail"] = len(events)

    # VPC Flow Logs
    vpc_config = await db.integrations.find_one({"integration_id": "aws_vpc_flowlogs", "enabled": True}, {"_id": 0})
    if vpc_config:
        connector = VPCFlowLogConnector(vpc_config.get("config", {}))
        logs = await connector.fetch_logs(50)
        for ev in logs:
            await ingest_security_event(ev)
        results["vpc_flow"] = len(logs)

    return results
