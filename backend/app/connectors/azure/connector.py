"""
FalconOps AI - Azure Monitor connector.

Real REST calls against Azure Monitor's Metrics API — no Azure SDK dependency
needed (unlike GCP's connector, which needs google-auth for JWT/service-account
signing; Azure AD's client-credentials flow is a single plain OAuth2 POST, so
httpx alone is enough, same reasoning the Prometheus connector already used for
avoiding a heavy client library).

Auth: Azure AD app registration (client_id/client_secret/azure_tenant_id) via the
OAuth2 client-credentials grant against https://login.microsoftonline.com — the
standard way a backend service authenticates to Azure Resource Manager. The app
registration's service principal needs "Monitoring Reader" role (or broader) on
the target resource(s).

Config fields (see metadata()/CONFIG_FIELDS-equivalent in integration_management_service):
  azure_tenant_id, client_id, client_secret, subscription_id
  resource_uris     — comma-separated full ARM resource IDs to pull metrics for
                       (e.g. "/subscriptions/xxx/resourceGroups/rg1/providers/
                       Microsoft.Compute/virtualMachines/vm1") — Azure Monitor's
                       Metrics API is per-resource, there is no "all metrics for
                       the whole subscription" cheap call without Azure Resource
                       Graph, so this connector is explicit about what it polls,
                       same pattern Prometheus's default_queries config uses.
  metric_names      — comma-separated metric names (e.g. "Percentage CPU,Network In")
"""
import logging
import time
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

AAD_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
ARM_SCOPE = "https://management.azure.com/.default"
ARM_BASE = "https://management.azure.com"


@register_connector("azure_monitor")
class AzureMonitorConnector(BaseConnector, MetricsCapable, AIContextCapable):
    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)
        self._client: Optional[httpx.AsyncClient] = None
        self._unavailable_reason: Optional[str] = None
        # Cached AAD token — client-credentials tokens are valid ~1h, no reason
        # to fetch a fresh one on every single metrics call.
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(
            id="azure_monitor", name="Azure Monitor", vendor="Microsoft Azure",
            version="1.0.0", category="cloud",
        )

    def _resource_uris(self) -> List[str]:
        raw = self.config.get("resource_uris") or ""
        return [r.strip() for r in raw.split(",") if r.strip()]

    def _metric_names(self) -> List[str]:
        raw = self.config.get("metric_names") or "Percentage CPU"
        return [m.strip() for m in raw.split(",") if m.strip()]

    async def connect(self) -> None:
        """Never raises on missing config — records the reason so
        test_connection()/fetch_metrics() report an honest unhealthy/empty
        result instead."""
        required = ("azure_tenant_id", "client_id", "client_secret", "subscription_id")
        missing = [f for f in required if not self.config.get(f)]
        if missing:
            self._unavailable_reason = f"missing config: {', '.join(missing)}"
            return
        self._client = httpx.AsyncClient(timeout=15)

    async def _get_token(self) -> Optional[str]:
        if self._client is None:
            return None
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        try:
            url = AAD_TOKEN_URL.format(tenant=self.config["azure_tenant_id"])
            resp = await self._client.post(url, data={
                "grant_type": "client_credentials",
                "client_id": self.config["client_id"],
                "client_secret": self.config["client_secret"],
                "scope": ARM_SCOPE,
            })
            if resp.status_code != 200:
                self._unavailable_reason = f"AAD token request failed: HTTP {resp.status_code} {resp.text[:200]}"
                return None
            body = resp.json()
            self._token = body["access_token"]
            # Refresh 60s early rather than exactly at expiry.
            self._token_expires_at = time.monotonic() + int(body.get("expires_in", 3600)) - 60
            return self._token
        except Exception as e:
            self._unavailable_reason = f"AAD token request error: {str(e)[:200]}"
            return None

    async def test_connection(self) -> HealthResult:
        if self._client is None:
            return HealthResult(status="unhealthy", message=self._unavailable_reason or "not connected")
        token = await self._get_token()
        if not token:
            return HealthResult(status="unhealthy", message=self._unavailable_reason or "could not obtain AAD token")
        resource_uris = self._resource_uris()
        if not resource_uris:
            return HealthResult(status="degraded",
                                 message="AAD auth OK, but no resource_uris configured — nothing to poll")
        try:
            resp = await self._client.get(
                f"{ARM_BASE}{resource_uris[0]}/providers/Microsoft.Insights/metrics",
                params={"api-version": "2021-05-01", "metricnames": self._metric_names()[0]},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return HealthResult(status="healthy", message="Azure Monitor Metrics API reachable")
            return HealthResult(status="unhealthy", message=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])

    async def fetch_metrics(self, since: Optional[str] = None) -> List[MetricPoint]:
        if self._client is None:
            return []  # not configured/reachable — never fabricated data
        token = await self._get_token()
        if not token:
            return []
        resource_uris = self._resource_uris()
        if not resource_uris:
            return []

        timespan = self._timespan(since)
        metric_names = ",".join(self._metric_names())
        points: List[MetricPoint] = []
        for resource_uri in resource_uris:
            try:
                resp = await self._client.get(
                    f"{ARM_BASE}{resource_uri}/providers/Microsoft.Insights/metrics",
                    params={"api-version": "2021-05-01", "metricnames": metric_names, "timespan": timespan},
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning(f"Azure Monitor fetch_metrics {resource_uri} failed: HTTP {resp.status_code}")
                    continue
                body = resp.json()
                # resource name is the last path segment of the ARM resource URI
                resource_name = resource_uri.rstrip("/").split("/")[-1]
                for m in body.get("value", []):
                    metric_name = m.get("name", {}).get("value", "unknown")
                    unit = m.get("unit", "")
                    for series in m.get("timeseries", []):
                        for dp in series.get("data", []):
                            # Azure returns None for buckets with no data in the window — skip those.
                            value = dp.get("average", dp.get("total", dp.get("count")))
                            if value is None or dp.get("timeStamp") is None:
                                continue
                            points.append(MetricPoint(
                                name=f"azure.{metric_name}",
                                value=float(value),
                                timestamp=dp["timeStamp"],
                                tags={"resource": resource_name, "resource_uri": resource_uri},
                                unit=unit,
                                metric_type="gauge",
                            ))
            except Exception as e:
                logger.warning(f"Azure Monitor fetch_metrics {resource_uri} error: {e}")
        return points

    def _timespan(self, since: Optional[str]) -> str:
        end = datetime.now(timezone.utc)
        if since:
            try:
                start = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except Exception:
                start = end - timedelta(minutes=30)
        else:
            start = end - timedelta(minutes=30)
        return f"{start.isoformat()}/{end.isoformat()}"

    async def get_ai_context(self, minutes: int = 60, **params) -> Dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        points = await self.fetch_metrics(since=since)
        if not points and self._unavailable_reason:
            return {"tool": "connector_azure_monitor_context", "count": 0, "data": [],
                    "summary": self._unavailable_reason}
        confidence = ConfidenceResult(score=min(1.0, len(points) / 30), basis=f"{len(points)} data points over {minutes}m")
        return {
            "tool": "connector_azure_monitor_context",
            "params": {"minutes": minutes, "resource_uris": self._resource_uris(), "metric_names": self._metric_names()},
            "count": len(points),
            "data": [p.to_ingest_dict() for p in points],
            "summary": f"{len(points)} Azure Monitor data points across {len(self._resource_uris())} resource(s) over the last {minutes}m",
            "confidence": confidence.to_dict(),
        }
