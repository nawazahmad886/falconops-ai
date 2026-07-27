"""
FalconOps AI - Connector SDK API routes

Exposes the Connector SDK (app/connectors/) over HTTP: registry listing, a
real per-connector connectivity test (replacing integration_management_service
.test_integration()'s hardcoded per-vendor branches, for SDK-backed connectors
only — non-SDK integrations like slack/pagerduty keep using
POST /api/admin/integrations/{id}/test exactly as before), on-demand polling,
and read-only remediation recommendations.
"""
from fastapi import APIRouter, Depends

from ..connectors.scheduler import poll_connector_once
from ..connectors.service import (
    get_connector_recommendations,
    list_connectors_status,
    test_connector,
)
from ..utils.auth import require_admin, require_auth

router = APIRouter(prefix="/api/connectors", tags=["Connector SDK"])


@router.get("")
async def list_connectors(current_user: dict = Depends(require_auth)):
    """Every registered connector's identity, capabilities, and configured/enabled status."""
    return {"connectors": await list_connectors_status()}


@router.post("/{connector_id}/test")
async def test_connector_route(connector_id: str, current_user: dict = Depends(require_admin)):
    """Real connectivity test for an SDK-registered connector."""
    return await test_connector(connector_id)


@router.post("/{connector_id}/poll")
async def poll_connector_route(connector_id: str, current_user: dict = Depends(require_admin)):
    """On-demand single poll cycle — mirrors POST /api/aws/fetch's on-demand shape."""
    return await poll_connector_once(connector_id)


@router.get("/{connector_id}/recommendations")
async def connector_recommendations_route(connector_id: str, current_user: dict = Depends(require_auth)):
    """Read-only, risk-scored recommendations from a RemediationCapable connector.
    Never executes anything — real remediation execution is a separate,
    still-open capability."""
    return {"recommendations": await get_connector_recommendations(connector_id)}
