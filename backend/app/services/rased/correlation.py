"""
RASED-owned interface over the shared correlation engine.

Wraps app.services.correlation_shared.multi_dimension_group() rather than
reimplementing alert grouping — that function already backs ai_correlation.py
and smart_correlation_engine.py elsewhere in FalconOps. This module only
adapts RASED's own Alert/service-catalog shapes into the dict-based arguments
that function expects, and keeps the import lazy so importing RASED's
orchestrator never requires correlation_shared's own dependencies to be
present at RASED's import time.
"""
import logging
from typing import Any, Dict, List

from ...models.rased_schemas import Alert

logger = logging.getLogger(__name__)


def correlate_alerts(alerts: List[Alert], service_catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    from ..correlation_shared import multi_dimension_group

    service_map = dict(service_catalog)
    service_id_map = {name: name for name in service_catalog}

    upstream: Dict[str, set] = {}
    downstream: Dict[str, set] = {}
    for service, meta in service_catalog.items():
        for dep in meta.get("depends_on", []):
            downstream.setdefault(dep, set()).add(service)
            upstream.setdefault(service, set()).add(dep)

    alert_dicts = [a.model_dump() for a in alerts]

    return multi_dimension_group(
        alert_dicts,
        service_map,
        service_id_map,
        upstream,
        downstream,
        get_service=lambda a: a.get("service"),
        get_host=lambda a: a.get("host"),
        confidence_fn=lambda signature, group_alerts: min(1.0, 0.5 + 0.05 * len(group_alerts)),
    )


__all__ = ["correlate_alerts"]
