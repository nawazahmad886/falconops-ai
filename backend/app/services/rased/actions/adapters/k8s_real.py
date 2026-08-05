"""
Real Kubernetes adapter — powers RASED's restart_pod action against an actual
cluster. Every other action (scale_out_service, clear_queue_backlog,
failover_dependency, rollback_deployment) stays on its existing mock adapter;
this is deliberately scoped to the one action approved for real execution.

Auth: an external cluster connection (API server URL + bearer token), not
in-cluster ServiceAccount config — FalconOps runs via docker-compose, not
inside the Kubernetes cluster it might be asked to act on, so in-cluster auth
doesn't apply. Configured via the "kubernetes_cluster" integration (see
integration_management_service.py's catalog entry), same pattern as the
Azure/GCP connectors added earlier: encrypted-at-rest credential, a real
test_connection()-style health check.

RASED's scenarios use abstract service slugs (checkout-api, invoice-db, ...),
not real Kubernetes namespaces/pod names — there is no inherent mapping from
one to the other. The integration config's `service_pod_mapping` field
supplies that mapping explicitly (JSON: {"service-slug": {"namespace":
"...", "label_selector": "app=..."}}). A service with no entry in that
mapping cannot be targeted for real; the caller (executors.py) falls back to
the existing simulated executor rather than failing outright — see that
module for why a GUARDED action failing over missing infra config would be a
worse outcome than a clearly-labeled simulated result.

The `kubernetes` Python client is synchronous — every call here runs via
asyncio.to_thread so it never blocks the event loop, same pattern already
used for google-auth's synchronous token refresh in the GCP connector.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_k8s_available = False
try:
    from kubernetes import client as k8s_client
    from kubernetes.client import ApiException
    _k8s_available = True
except ImportError:
    logger.info("kubernetes client not available — restart_pod will use the simulated executor")


class KubernetesUnavailable(Exception):
    """Raised (and caught by executors.py) whenever the real path can't run —
    client missing, cluster unreachable, or no pod mapping for this service.
    Distinct from a real API failure so the caller can tell "we didn't even
    try" from "we tried and the cluster rejected it"."""


def build_api_client(cluster_config: Dict[str, Any]):
    if not _k8s_available:
        raise KubernetesUnavailable("kubernetes client library not installed")
    api_url = (cluster_config.get("api_server_url") or "").strip()
    token = cluster_config.get("bearer_token") or ""
    if not api_url or not token:
        raise KubernetesUnavailable("api_server_url/bearer_token not configured")

    configuration = k8s_client.Configuration()
    configuration.host = api_url
    configuration.api_key = {"authorization": f"Bearer {token}"}
    # verify_ssl arrives from stored integration config as a string ("true"/"false"),
    # not a Python bool — every non-empty string is truthy, so `or True` / a bare
    # truthiness check here would silently ignore an intentional "false".
    raw_verify = cluster_config.get("verify_ssl", "true")
    configuration.verify_ssl = str(raw_verify).strip().lower() not in ("false", "0", "no")
    return k8s_client.ApiClient(configuration)


def _resolve_target(cluster_config: Dict[str, Any], service: str) -> Dict[str, str]:
    import json
    raw_mapping = cluster_config.get("service_pod_mapping") or "{}"
    try:
        mapping = json.loads(raw_mapping) if isinstance(raw_mapping, str) else raw_mapping
    except (TypeError, ValueError) as e:
        raise KubernetesUnavailable(f"service_pod_mapping is not valid JSON: {e}")
    target = mapping.get(service)
    if not target or not target.get("namespace") or not target.get("label_selector"):
        raise KubernetesUnavailable(f"no namespace/label_selector mapped for service '{service}'")
    return target


async def test_connection(cluster_config: Dict[str, Any]) -> Dict[str, Any]:
    """Real connectivity probe — lists namespaces with a small limit. Never
    raises; returns {"healthy": bool, "message": str} like the Connector SDK's
    HealthResult convention used elsewhere this session."""
    try:
        api_client = build_api_client(cluster_config)
    except KubernetesUnavailable as e:
        return {"healthy": False, "message": str(e)}

    def _call():
        core = k8s_client.CoreV1Api(api_client)
        core.list_namespace(limit=1, _request_timeout=10)

    try:
        await asyncio.to_thread(_call)
        return {"healthy": True, "message": "Kubernetes API server reachable"}
    except ApiException as e:
        return {"healthy": False, "message": f"Kubernetes API error: {e.status} {e.reason}"}
    except Exception as e:
        return {"healthy": False, "message": str(e)[:300]}
    finally:
        try:
            api_client.close()
        except Exception:
            pass


async def restart_pod(cluster_config: Dict[str, Any], service: str) -> Dict[str, Any]:
    """Deletes the target pod(s) via the Core V1 API — the standard, safe way
    to "restart" a pod: the owning controller (Deployment/StatefulSet/etc.)
    recreates it. Never a node/cluster-level operation, never touches
    anything not matched by the configured label_selector. Raises
    KubernetesUnavailable if the real path can't run at all (caller falls
    back to simulation); raises ApiException for a real, reported cluster
    error (caller records that as a real failure, does NOT silently fall
    back — a cluster that actively rejected the request is a different,
    more important signal than "not configured")."""
    target = _resolve_target(cluster_config, service)
    api_client = build_api_client(cluster_config)

    def _call() -> List[str]:
        core = k8s_client.CoreV1Api(api_client)
        pods = core.list_namespaced_pod(
            namespace=target["namespace"], label_selector=target["label_selector"], _request_timeout=10,
        )
        deleted = []
        for pod in pods.items:
            core.delete_namespaced_pod(name=pod.metadata.name, namespace=target["namespace"], _request_timeout=10)
            deleted.append(pod.metadata.name)
        return deleted

    try:
        deleted_pods = await asyncio.to_thread(_call)
    finally:
        try:
            api_client.close()
        except Exception:
            pass

    if not deleted_pods:
        raise KubernetesUnavailable(
            f"no pods matched namespace={target['namespace']} label_selector={target['label_selector']}"
        )

    return {
        "namespace": target["namespace"], "label_selector": target["label_selector"],
        "pods_deleted": deleted_pods,
    }


async def list_pods(cluster_config: Dict[str, Any], namespace: str, label_selector: Optional[str] = None) -> Dict[str, Any]:
    """Read-only pod listing — backs the Tool Catalog's k8s_read binding
    (Agent Builder / Workflow Builder tool calls). Never deletes/mutates
    anything; a thin sibling to restart_pod's own list-then-act step."""
    api_client = build_api_client(cluster_config)

    def _call():
        core = k8s_client.CoreV1Api(api_client)
        pods = core.list_namespaced_pod(
            namespace=namespace, label_selector=label_selector or None, _request_timeout=10,
        )
        return [
            {
                "name": p.metadata.name,
                "phase": p.status.phase,
                "restarts": sum(c.restart_count for c in (p.status.container_statuses or [])),
            }
            for p in pods.items
        ]

    try:
        pods = await asyncio.to_thread(_call)
    finally:
        try:
            api_client.close()
        except Exception:
            pass
    return {"namespace": namespace, "label_selector": label_selector, "pods": pods}


__all__ = ["KubernetesUnavailable", "build_api_client", "test_connection", "restart_pod", "list_pods"]
