"""
FalconOps AI - Shared Correlation Grouping Logic
Extracted from ai_correlation.py and smart_correlation_engine.py, which independently
re-implemented the same 5-strategy (topology dependency, metric pattern, severity
cascade, same host, same service) grouping loop against two different alert schemas
(legacy db.alerts vs the newer db.alerts_engine). Both engines now call this one
function, supplying only what genuinely differs between them: field extraction and
confidence scoring — so the actual grouping logic has exactly one implementation.
"""
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict


def multi_dimension_group(
    alerts: List[Dict[str, Any]],
    service_map: Dict[str, Any],
    service_id_map: Dict[str, Any],
    upstream: Dict[str, set],
    downstream: Dict[str, set],
    *,
    get_service: Callable[[Dict[str, Any]], Optional[str]],
    get_host: Callable[[Dict[str, Any]], Optional[str]],
    confidence_fn: Callable[[str, List[Dict[str, Any]]], float],
) -> List[Dict[str, Any]]:
    """Group alerts by topology dependency, cross-host metric pattern, severity
    cascade, same host, and same service. Each alert may appear in more than one
    candidate group; the caller resolves overlaps by processing groups
    highest-confidence-first and skipping alerts already claimed by a higher-confidence
    group.

    Attaches a structured `root_cause_entity` (a real topology node, not prose) to
    'topology_dependency' groups — the shared upstream dependency every alert in the
    group is attributable to, with a confidence based on whether that dependency node
    itself has an active alert in this batch (real corroborating evidence) or whether
    it's inferred purely from topology shape. `root_cause_entity` is `None` for every
    other group type — those signals (metric fleet-wide, severity cascade, host/service
    grouping) don't identify one causal entity, so this never fabricates one.
    """
    groups: List[Dict[str, Any]] = []
    seen_id_sets = set()

    service_alerts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in alerts:
        svc = get_service(a)
        if svc:
            service_alerts[svc].append(a)

    # -- topology dependency: alerts on services sharing an upstream dependency --
    for svc, svc_alerts in service_alerts.items():
        node = service_map.get(svc)
        if not node:
            continue
        for dep_id in upstream.get(node["id"], set()):
            dep_node = service_id_map.get(dep_id)
            if not dep_node:
                continue
            for sib_id in downstream.get(dep_id, set()):
                if sib_id == node["id"]:
                    continue
                sib_node = service_id_map.get(sib_id)
                if sib_node and sib_node["name"] in service_alerts:
                    combined = svc_alerts + service_alerts[sib_node["name"]]
                    ids = frozenset(a["id"] for a in combined)
                    if ids not in seen_id_sets and len(combined) >= 2:
                        seen_id_sets.add(ids)
                        dep_has_own_alert = bool(service_alerts.get(dep_node["name"]))
                        groups.append({
                            "type": "topology_dependency",
                            "reason": f"Shared dependency: {dep_node['name']} affects {svc} and {sib_node['name']}",
                            "alerts": combined,
                            "confidence": confidence_fn("topology_dependency", combined),
                            "root_cause_entity": {
                                "id": dep_id,
                                "name": dep_node["name"],
                                "type": dep_node.get("type"),
                                "confidence": 0.9 if dep_has_own_alert else 0.6,
                            },
                        })

    # -- metric pattern: same metric alerting across >=2 hosts --
    metric_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in alerts:
        mn = a.get("metric_name")
        if mn:
            metric_groups[mn].append(a)
    for metric, m_alerts in metric_groups.items():
        hosts_affected = {get_host(a) for a in m_alerts if get_host(a)}
        if len(hosts_affected) >= 2:
            ids = frozenset(a["id"] for a in m_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "metric_pattern",
                    "reason": f"{metric} anomaly across {len(hosts_affected)} hosts",
                    "alerts": m_alerts,
                    "confidence": confidence_fn("metric_pattern", m_alerts),
                    "root_cause_entity": None,
                })

    # -- severity cascade: many distinct services alerting within the same window --
    services_in_batch = {get_service(a) for a in alerts if get_service(a)}
    if len(services_in_batch) >= 3:
        ids = frozenset(a["id"] for a in alerts)
        if ids not in seen_id_sets:
            seen_id_sets.add(ids)
            groups.append({
                "type": "severity_cascade",
                "reason": f"{len(services_in_batch)} services alerting in the same window — possible cascading failure",
                "alerts": list(alerts),
                "confidence": confidence_fn("severity_cascade", list(alerts)),
                "root_cause_entity": None,
            })

    # -- same host --
    host_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in alerts:
        host = get_host(a)
        if host:
            host_groups[host].append(a)
    for host, h_alerts in host_groups.items():
        if len(h_alerts) >= 2:
            ids = frozenset(a["id"] for a in h_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "same_host",
                    "reason": f"Multiple alerts on host {host}",
                    "alerts": h_alerts,
                    "confidence": confidence_fn("same_host", h_alerts),
                    "root_cause_entity": None,
                })

    # -- same service (fallback) --
    for svc, svc_alerts in service_alerts.items():
        if len(svc_alerts) >= 2:
            ids = frozenset(a["id"] for a in svc_alerts)
            if ids not in seen_id_sets:
                seen_id_sets.add(ids)
                groups.append({
                    "type": "same_service",
                    "reason": f"Multiple alerts on service {svc}",
                    "alerts": svc_alerts,
                    "confidence": confidence_fn("same_service", svc_alerts),
                    "root_cause_entity": None,
                })

    groups.sort(key=lambda g: g["confidence"], reverse=True)
    return groups
