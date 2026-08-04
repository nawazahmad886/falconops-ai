"""
FalconOps AI - Kubernetes cluster connector.

Thin wrapper around app.services.rased.actions.adapters.k8s_real, registered
purely so the "kubernetes_cluster" integration gets a real test_connection()
through the same generic Connector-SDK dispatch integration_management_service
.test_integration() already uses for prometheus/aws/azure_monitor/
gcp_cloud_monitoring (added earlier this session) — no new special-cased
branch needed for one more integration.

Deliberately no capability mixins (MetricsCapable, etc.) — RASED's
restart_pod executor calls k8s_real.restart_pod() directly, not through this
connector's dispatch. This class exists only for the admin "Test Connection"
button and connect()/test_connection() reuse; it is not part of any
poll/metrics-ingestion path.
"""
from typing import Any, Dict, Optional

from ..base import BaseConnector, ConnectorMetadata, HealthResult
from ..registry import register_connector


@register_connector("kubernetes_cluster")
class KubernetesConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any], tenant_id: Optional[str] = None):
        super().__init__(config, tenant_id)

    @classmethod
    def metadata(cls) -> ConnectorMetadata:
        return ConnectorMetadata(
            id="kubernetes_cluster", name="Kubernetes Cluster", vendor="Kubernetes",
            version="1.0.0", category="infrastructure",
        )

    async def connect(self) -> None:
        # Nothing to pre-build — k8s_real builds a fresh ApiClient per call
        # (see that module's build_api_client), so there's no persistent
        # client to construct/validate here beyond having config present.
        pass

    async def test_connection(self) -> HealthResult:
        from ...services.rased.actions.adapters import k8s_real
        result = await k8s_real.test_connection(self.config)
        return HealthResult(
            status="healthy" if result["healthy"] else "unhealthy",
            message=result["message"],
        )


__all__ = ["KubernetesConnector"]
