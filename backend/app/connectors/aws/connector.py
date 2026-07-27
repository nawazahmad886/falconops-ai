"""
FalconOps AI - AWS CloudTrail & VPC Flow Logs connectors (reference connector
#2 for the SDK). Migrated from the legacy app/services/aws_connectors.py,
which is now a thin backward-compatible adapter re-exporting these classes.

The previous _simulate_events()/_simulate_logs() fake-data fallback (returned
fabricated events whenever no real boto3 client was available) has been
deliberately removed — fetch_events()/fetch_logs() now honestly return []
when not configured/reachable, and test_connection() reports why.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base import BaseConnector, ConnectorMetadata, EventsCapable, HealthResult
from ..registry import register_connector

logger = logging.getLogger(__name__)

_boto3_available = False
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    _boto3_available = True
except ImportError:
    logger.info("boto3 not available — AWS connectors will report unhealthy/no-data rather than simulating")


# ======================== CLOUDTRAIL CONNECTOR ========================

@register_connector("aws_cloudtrail")
class CloudTrailConnector(BaseConnector, EventsCapable):
    """Fetch and normalize AWS CloudTrail events."""

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

    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)
        self.client = None
        self._unavailable_reason: Optional[str] = None
        self._try_build_client()

    def _try_build_client(self) -> None:
        if not _boto3_available:
            self._unavailable_reason = "boto3 not available"
            return
        if not self.config.get("aws_access_key"):
            self._unavailable_reason = "aws_access_key not configured"
            return
        try:
            self.client = boto3.client(
                "cloudtrail",
                aws_access_key_id=self.config["aws_access_key"],
                aws_secret_access_key=self.config.get("aws_secret_key", ""),
                region_name=self.config.get("aws_region", "us-east-1"),
            )
        except Exception as e:
            logger.error(f"CloudTrail client init failed: {e}")
            self._unavailable_reason = f"client init failed: {e}"

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(id="aws_cloudtrail", name="AWS CloudTrail", vendor="AWS",
                                  version="1.0.0", category="cloud")

    async def connect(self) -> None:
        # Client is already (idempotently) built in __init__ to preserve the
        # legacy "construct-and-immediately-use" behavior for callers that
        # never call connect() (aws_connector_routes.py's GET routes).
        if self.client is None:
            self._try_build_client()

    async def test_connection(self) -> HealthResult:
        if not self.client:
            return HealthResult(status="unhealthy",
                                 message=self._unavailable_reason or "boto3 not available or credentials not configured")
        try:
            self.client.lookup_events(MaxResults=1)
            return HealthResult(status="healthy", message="CloudTrail reachable")
        except (ClientError, NoCredentialsError) as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])

    async def fetch_events(self, max_results: int = 50) -> List[Dict[str, Any]]:
        if not self.client:
            return []  # not configured/reachable — never fabricated data

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
            "timestamp": raw.get("EventTime", datetime.now(timezone.utc)).isoformat()
            if isinstance(raw.get("EventTime"), datetime) else datetime.now(timezone.utc).isoformat(),
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


# ======================== VPC FLOW LOG CONNECTOR ========================

@register_connector("aws_vpc_flowlogs")
class VPCFlowLogConnector(BaseConnector, EventsCapable):
    """Parse and normalize AWS VPC Flow Logs."""

    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)
        self.client = None
        self._unavailable_reason: Optional[str] = None
        self._try_build_client()

    def _try_build_client(self) -> None:
        if not _boto3_available:
            self._unavailable_reason = "boto3 not available"
            return
        if not self.config.get("aws_access_key"):
            self._unavailable_reason = "aws_access_key not configured"
            return
        try:
            self.client = boto3.client(
                "logs",
                aws_access_key_id=self.config["aws_access_key"],
                aws_secret_access_key=self.config.get("aws_secret_key", ""),
                region_name=self.config.get("aws_region", "us-east-1"),
            )
        except Exception as e:
            logger.error(f"VPC Flow Log client init failed: {e}")
            self._unavailable_reason = f"client init failed: {e}"

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(id="aws_vpc_flowlogs", name="AWS VPC Flow Logs", vendor="AWS",
                                  version="1.0.0", category="cloud")

    async def connect(self) -> None:
        if self.client is None:
            self._try_build_client()

    async def test_connection(self) -> HealthResult:
        if not self.client:
            return HealthResult(status="unhealthy",
                                 message=self._unavailable_reason or "boto3 not available or credentials not configured")
        try:
            log_group = self.config.get("log_group", "vpc-flow-logs")
            self.client.filter_log_events(logGroupName=log_group, limit=1, interleaved=True)
            return HealthResult(status="healthy", message="VPC Flow Logs reachable")
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])

    async def fetch_events(self, max_results: int = 50) -> List[Dict[str, Any]]:
        return await self.fetch_logs(max_results)

    async def fetch_logs(self, max_results: int = 50) -> List[Dict[str, Any]]:
        if not self.client:
            return []  # not configured/reachable — never fabricated data

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
        """version account-id interface-id srcaddr dstaddr srcport dstport
        protocol packets bytes start end action log-status"""
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
