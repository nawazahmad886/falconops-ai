"""
FalconOps AI - Prometheus connector (reference connector #1 for the SDK)

Pull-based metrics via Prometheus's HTTP query API:
https://prometheus.io/docs/prometheus/latest/querying/api/
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from ...services.ssrf_guard import is_safe_outbound_url
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


@register_connector("prometheus")
class PrometheusConnector(BaseConnector, MetricsCapable, AIContextCapable):
    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)
        self._client: Optional[httpx.AsyncClient] = None
        self._unavailable_reason: Optional[str] = None

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(
            id="prometheus", name="Prometheus", vendor="Prometheus", version="1.0.0",
            category="data_source",
        )

    def _queries(self) -> List[str]:
        raw = self.config.get("default_queries") or "up"
        return [q.strip() for q in raw.split(",") if q.strip()]

    async def connect(self) -> None:
        """Never raises on missing/unsafe config — records the reason so
        test_connection()/fetch_metrics() can report an honest unhealthy
        status/empty result instead."""
        url = (self.config.get("prometheus_url") or "").strip()
        if not url:
            self._unavailable_reason = "prometheus_url not configured"
            return
        if not is_safe_outbound_url(url):
            self._unavailable_reason = "prometheus_url resolves to a private/internal address — refused"
            return
        headers = {}
        token = self.config.get("bearer_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=url.rstrip("/"), headers=headers, timeout=10)

    async def test_connection(self) -> HealthResult:
        if self._client is None:
            return HealthResult(status="unhealthy", message=self._unavailable_reason or "not connected")
        try:
            resp = await self._client.get("/api/v1/query", params={"query": "up"})
            if resp.status_code == 200 and resp.json().get("status") == "success":
                return HealthResult(status="healthy", message="Prometheus query API reachable")
            return HealthResult(status="unhealthy", message=f"Prometheus responded with HTTP {resp.status_code}")
        except httpx.ConnectError:
            return HealthResult(status="unhealthy", message="Connection refused — check prometheus_url")
        except httpx.TimeoutException:
            return HealthResult(status="unhealthy", message="Connection timed out")
        except Exception as e:
            return HealthResult(status="unhealthy", message=str(e)[:200])

    async def fetch_metrics(self, since: Optional[str] = None) -> List[MetricPoint]:
        if self._client is None:
            return []  # not configured/reachable — never fabricated data
        points: List[MetricPoint] = []
        for query in self._queries():
            try:
                resp = await self._client.get("/api/v1/query", params={"query": query})
                if resp.status_code != 200:
                    continue
                body = resp.json()
                if body.get("status") != "success":
                    continue
                for result in body.get("data", {}).get("result", []):
                    metric_labels = dict(result.get("metric", {}))
                    name = metric_labels.pop("__name__", query)
                    ts, val = result.get("value", [None, None])
                    if ts is None or val is None:
                        continue
                    points.append(MetricPoint(
                        name=name,
                        value=float(val),
                        timestamp=datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(),
                        tags=metric_labels,
                        metric_type="gauge",
                    ))
            except Exception as e:
                logger.warning(f"prometheus fetch_metrics query '{query}' failed: {e}")
        return points

    async def get_ai_context(self, promql: Optional[str] = None, minutes: int = 60) -> Dict[str, Any]:
        query = promql or (self._queries()[0] if self._queries() else "up")
        if self._client is None:
            return {
                "tool": "connector_prometheus_context", "count": 0, "data": [],
                "summary": self._unavailable_reason or "Prometheus not configured",
            }
        try:
            now = datetime.now(timezone.utc).timestamp()
            resp = await self._client.get("/api/v1/query_range", params={
                "query": query, "start": now - minutes * 60, "end": now,
                "step": max(15, (minutes * 60) // 100),
            })
            body = resp.json() if resp.status_code == 200 else {}
            results = body.get("data", {}).get("result", []) if body.get("status") == "success" else []
            total_points = sum(len(r.get("values", [])) for r in results)
            confidence = ConfidenceResult(score=min(1.0, total_points / 30), basis=f"{total_points} samples over {minutes}m")
            return {
                "tool": "connector_prometheus_context",
                "params": {"promql": query, "minutes": minutes},
                "count": len(results),
                "data": results,
                "summary": f"{len(results)} series, {total_points} samples for '{query}' over the last {minutes}m",
                "confidence": confidence.to_dict(),
            }
        except Exception as e:
            return {"tool": "connector_prometheus_context", "count": 0, "data": [], "summary": f"query failed: {str(e)[:200]}"}
