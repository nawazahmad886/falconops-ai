"""
Tests for restart_pod's real/fallback dispatch (executors.py::_restart_pod_executor)
and the k8s_real adapter's own target-resolution logic. No real cluster —
_get_k8s_cluster_config and k8s_real.restart_pod are mocked so each of the
three outcomes (unconfigured -> simulated, real success, real failure) is
exercised independently.
"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.rased.actions import executors
from app.services.rased.actions.adapters import k8s_real


def test_restart_pod_falls_back_to_simulation_when_unconfigured():
    with patch.object(executors, "_get_k8s_cluster_config", new=AsyncMock(return_value={})):
        result = asyncio.run(executors._restart_pod_executor(
            "restart_pod", {"action_id": "a1", "service": "checkout-api"}, "S1-run-1",
        ))
    assert result.success is True
    assert result.execution_mode == "simulated"
    assert "no kubernetes_cluster integration configured" in result.output["note"]


def test_restart_pod_real_success():
    cluster_config = {"api_server_url": "https://cluster.example", "bearer_token": "t",
                       "service_pod_mapping": '{"checkout-api": {"namespace": "prod", "label_selector": "app=checkout-api"}}'}
    with patch.object(executors, "_get_k8s_cluster_config", new=AsyncMock(return_value=cluster_config)), \
         patch.object(k8s_real, "restart_pod", new=AsyncMock(return_value={
             "namespace": "prod", "label_selector": "app=checkout-api", "pods_deleted": ["checkout-api-abc"],
         })):
        result = asyncio.run(executors._restart_pod_executor(
            "restart_pod", {"action_id": "a1", "service": "checkout-api"}, "S1-run-1",
        ))
    assert result.success is True
    assert result.execution_mode == "live"
    assert result.output["pods_deleted"] == ["checkout-api-abc"]


def test_restart_pod_falls_back_when_no_pod_mapping():
    cluster_config = {"api_server_url": "https://cluster.example", "bearer_token": "t", "service_pod_mapping": "{}"}
    with patch.object(executors, "_get_k8s_cluster_config", new=AsyncMock(return_value=cluster_config)), \
         patch.object(k8s_real, "restart_pod", new=AsyncMock(
             side_effect=k8s_real.KubernetesUnavailable("no namespace/label_selector mapped for service 'checkout-api'"))):
        result = asyncio.run(executors._restart_pod_executor(
            "restart_pod", {"action_id": "a1", "service": "checkout-api"}, "S1-run-1",
        ))
    assert result.success is True
    assert result.execution_mode == "simulated"


def test_restart_pod_real_cluster_error_does_not_fall_back():
    cluster_config = {"api_server_url": "https://cluster.example", "bearer_token": "t",
                       "service_pod_mapping": '{"checkout-api": {"namespace": "prod", "label_selector": "app=checkout-api"}}'}
    with patch.object(executors, "_get_k8s_cluster_config", new=AsyncMock(return_value=cluster_config)), \
         patch.object(k8s_real, "restart_pod", new=AsyncMock(side_effect=RuntimeError("connection refused"))):
        result = asyncio.run(executors._restart_pod_executor(
            "restart_pod", {"action_id": "a1", "service": "checkout-api"}, "S1-run-1",
        ))
    # A real, reported cluster error must surface as a real failure, never a
    # silent fallback to a fake "simulated success".
    assert result.success is False
    assert result.execution_mode == "live"
    assert "connection refused" in result.error


def test_k8s_real_resolve_target_missing_mapping_raises():
    try:
        k8s_real._resolve_target({"service_pod_mapping": "{}"}, "unknown-service")
        assert False, "expected KubernetesUnavailable"
    except k8s_real.KubernetesUnavailable:
        pass
