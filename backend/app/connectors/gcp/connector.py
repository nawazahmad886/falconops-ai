"""
FalconOps AI - GCP Cloud Monitoring connector.

Real REST calls against Cloud Monitoring's timeSeries.list API. Unlike Azure's
connector (plain OAuth2 POST, no SDK needed), GCP service-account auth requires
signing a JWT with the service account's RSA private key — hand-rolling that is
a meaningful chunk of correctness-sensitive crypto code, so this uses the
already-present `google-auth` dependency (requirements.txt — previously unused
by anything in this codebase) for exactly that narrow purpose: producing a valid
access token. The actual metrics query is still a direct httpx REST call, not
the full google-cloud-monitoring client SDK, same "REST directly, thin auth
helper only" shape as the Azure/Prometheus connectors.

Config fields:
  gcp_project_id
  service_account_json   — the full service account key JSON, as a string (the
                            same file GCP's console gives you when you create a
                            key) — needs "Monitoring Viewer" IAM role.
  metric_type             — e.g. "compute.googleapis.com/instance/cpu/utilization"
                             (comma-separated for more than one)
  resource_filter          — optional extra filter clause ANDed into the query,
                              e.g. resource.labels.instance_id="123456"
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from ..base import (
    AIContextCapable,
    BaseConnector,
    ConfidenceResult,
    ConnectorMetadata,
    HealthResult,
    MetricsCapable,
    MetricPoint,
)
from ..registry import register_connector

logger = logging.getLogger(__name__)

MONITORING_SCOPE = "https://www.googleapis.com/auth/monitoring.read"
MONITORING_BASE = "https://monitoring.googleapis.com/v3"

_google_auth_available = False
try:
    from google.auth.transport.requests import Request as _GoogleAuthRequest
    from google.oauth2 import service_account as _google_service_account
    _google_auth_available = True
except ImportError:
    logger.info("google-auth not available — GCP Cloud Monitoring connector will report unhealthy/no-data")


@register_connector("gcp_cloud_monitoring")
class GCPCloudMonitoringConnector(BaseConnector, MetricsCapable, AIContextCapable):
    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)
        self._client: Optional[httpx.AsyncClient] = None
        self._credentials = None
        self._unavailable_reason: Optional[str] = None

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(
            id="gcp_cloud_monitoring", name="GCP Cloud Monitoring", vendor="Google Cloud",
            version="1.0.0", category="cloud",
        )

    def _metric_types(self) -> List[str]:
        raw = self.config.get("metric_type") or "compute.googleapis.com/instance/cpu/utilization"
        return [m.strip() for m in raw.split(",") if m.strip()]

    async def connect(self) -> None:
        """Never raises on missing/invalid config — records the reason so
        test_connection()/fetch_metrics() report an honest unhealthy/empty
        result instead."""
        if not _google_auth_available:
            self._unavailable_reason = "google-auth not installed"
            return
        if not self.config.get("gcp_project_id"):
            self._unavailable_reason = "gcp_project_id not configured"
            return
        raw_key = self.config.get("service_account_json")
        if not raw_key:
            self._unavailable_reason = "service_account_json not configured"
            return
        try:
            key_info = json.loads(raw_key)
            self._credentials = _google_service_account.Credentials.from_service_account_info(
                key_info, scopes=[MONITORING_SCOPE],
            )
            self._client = httpx.AsyncClient(timeout=15)
        except (json.JSONDecodeError, ValueError) as e:
            self._unavailable_reason = f"invalid service_account_json: {str(e)[:200]}"
        except Exception as e:
            self._unavailable_reason = f"credential init failed: {str(e)[:200]}"

    async def _get_token(self) -> Optional[str]:
        if self._credentials is None:
            return None
        try:
            # google-auth's refresh() is a synchronous, blocking network call —
            # run it off the event loop rather than stalling every other
            # in-flight request while it waits on Google's token endpoint.
            await asyncio.to_thread(self._credentials.refresh, _GoogleAuthRequest())
            return self._credentials.token
        except Exception as e:
            self._unavailable_reason = f"token refresh failed: {str(e)[:200]}"
            return None

    async def test_connection(self) -> HealthResult:
        if self._client is None or self._credentials is None:
            return HealthResult(status="unhealthy", message=self._unavailable_reason or "not connected")
        token = await self._get_token()
        if not token:
            return HealthResult(status="unhealthy", message=self._unavailable_reason or "could not obtain access token")
        try:
            project_id = self.config["gcp_project_id"]
            resp = await self._client.get(
                f"{MONITORING_BASE}/projects/{project_id}/metricDescriptors",
                params={"pageSize": 1},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return HealthResult(status="healthy", message="Cloud Monitoring API reachable")
            return HealthResult(status="unhealthy", message=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])

    async def fetch_metrics(self, since: Optional[str] = None) -> List[MetricPoint]:
        if self._client is None or self._credentials is None:
            return []  # not configured/reachable — never fabricated data
        token = await self._get_token()
        if not token:
            return []

        end = datetime.now(timezone.utc)
        start = self._parse_since(since) or (end - timedelta(minutes=30))
        project_id = self.config["gcp_project_id"]
        resource_filter = self.config.get("resource_filter", "")

        points: List[MetricPoint] = []
        for metric_type in self._metric_types():
            filter_clause = f'metric.type="{metric_type}"'
            if resource_filter:
                filter_clause += f" AND {resource_filter}"
            try:
                resp = await self._client.get(
                    f"{MONITORING_BASE}/projects/{project_id}/timeSeries",
                    params={
                        "filter": filter_clause,
                        "interval.startTime": start.isoformat(),
                        "interval.endTime": end.isoformat(),
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning(f"GCP fetch_metrics {metric_type} failed: HTTP {resp.status_code} {resp.text[:200]}")
                    continue
                body = resp.json()
                for series in body.get("timeSeries", []):
                    resource_labels = series.get("resource", {}).get("labels", {})
                    for point in series.get("points", []):
                        value = self._extract_value(point.get("value", {}))
                        end_time = point.get("interval", {}).get("endTime")
                        if value is None or not end_time:
                            continue
                        points.append(MetricPoint(
                            name=f"gcp.{metric_type}",
                            value=value,
                            timestamp=end_time,
                            tags={k: str(v) for k, v in resource_labels.items()},
                            metric_type="gauge",
                        ))
            except Exception as e:
                logger.warning(f"GCP fetch_metrics {metric_type} error: {e}")
        return points

    @staticmethod
    def _extract_value(value_obj: Dict[str, Any]) -> Optional[float]:
        for key in ("doubleValue", "int64Value", "boolValue"):
            if key in value_obj:
                return float(value_obj[key])
        return None

    @staticmethod
    def _parse_since(since: Optional[str]) -> Optional[datetime]:
        if not since:
            return None
        try:
            return datetime.fromisoformat(since.replace("Z", "+00:00"))
        except Exception:
            return None

    async def get_ai_context(self, minutes: int = 60, **params) -> Dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        points = await self.fetch_metrics(since=since)
        if not points and self._unavailable_reason:
            return {"tool": "connector_gcp_monitoring_context", "count": 0, "data": [],
                    "summary": self._unavailable_reason}
        confidence = ConfidenceResult(score=min(1.0, len(points) / 30), basis=f"{len(points)} data points over {minutes}m")
        return {
            "tool": "connector_gcp_monitoring_context",
            "params": {"minutes": minutes, "metric_types": self._metric_types()},
            "count": len(points),
            "data": [p.to_ingest_dict() for p in points],
            "summary": f"{len(points)} GCP Cloud Monitoring data points over the last {minutes}m",
            "confidence": confidence.to_dict(),
        }
