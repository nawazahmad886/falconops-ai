"""
Unit tests for network flow enrichment (network_flow_service.py) and the new
netflow-sourced threat detectors added to security_service.py's
ThreatDetectionEngine. Mocked, following the pattern established in
test_network_path_analyzer_unit.py: unittest.mock + asyncio.run(), no running
server or real Mongo/Redis needed.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import network_flow_service as nfs
from app.services import security_service as secsvc


def _mock_db_with_netflow_collection():
    """A MagicMock standing in for app.services.network_flow_service.db, with the
    async methods network_flow_service actually calls pre-wired as AsyncMock."""
    mock_db = MagicMock()
    mock_db.oneagent_netflows.create_index = AsyncMock(return_value="ok")
    mock_db.oneagent_netflows.insert_many = AsyncMock(return_value=None)
    return mock_db


class TestEnrichAndPersistBatch:
    def test_private_remote_ip_skips_enrichment_http_calls(self):
        mock_db = _mock_db_with_netflow_collection()
        raw_flows = [{
            "local_ip": "10.0.0.5", "local_port": 8080,
            "remote_ip": "10.0.0.6", "remote_port": 54321,
            "state": "ESTABLISHED", "pid": 123, "process_name": "checkout",
            "service": "checkout",
        }]

        with patch.object(nfs, "db", mock_db), \
             patch.object(nfs.geo_ip_service, "get_ip_intel", AsyncMock(return_value={})) as mock_intel, \
             patch.object(nfs.threat_intel_service, "is_malicious_ip", AsyncMock(return_value=None)) as mock_ioc, \
             patch.object(secsvc.threat_engine, "process_netflow", AsyncMock(return_value=None)) as mock_detect:
            result = asyncio.run(nfs.network_flow_service.enrich_and_persist_batch("host-a", raw_flows))

        # get_ip_intel/is_malicious_ip are still called (they internally no-op on
        # private IPs without an HTTP call -- that's their own contract, verified
        # in test_network_path_analyzer_unit.py) but must be called with the exact
        # private IP, and the batch must still persist.
        mock_intel.assert_awaited_once_with("10.0.0.6")
        mock_ioc.assert_awaited_once_with("10.0.0.6")
        mock_detect.assert_awaited_once()
        assert result["ingested"] == 1
        assert result["threats_detected"] == 0
        mock_db.oneagent_netflows.insert_many.assert_awaited_once()

    def test_malicious_remote_ip_fires_detection_and_records_threat_match(self):
        mock_db = _mock_db_with_netflow_collection()
        raw_flows = [{
            "local_ip": "10.0.0.5", "local_port": 443,
            "remote_ip": "45.83.222.10", "remote_port": 54321,
            "state": "ESTABLISHED", "pid": 456, "process_name": "checkout",
            "service": "checkout",
        }]
        ioc = {"source": "feodo_tracker", "malware_family": "banking_trojan"}

        with patch.object(nfs, "db", mock_db), \
             patch.object(nfs.geo_ip_service, "get_ip_intel", AsyncMock(return_value={"asn": "AS1234"})), \
             patch.object(nfs.threat_intel_service, "is_malicious_ip", AsyncMock(return_value=ioc)), \
             patch.object(secsvc.threat_engine, "process_netflow", AsyncMock(return_value=[{"id": "t1"}])) as mock_detect:
            result = asyncio.run(nfs.network_flow_service.enrich_and_persist_batch("host-a", raw_flows))

        mock_detect.assert_awaited_once()
        called_flow, called_ioc = mock_detect.await_args.args
        assert called_flow["remote_ip"] == "45.83.222.10"
        assert called_ioc == ioc
        assert result["threats_detected"] == 1

        persisted_docs = mock_db.oneagent_netflows.insert_many.await_args.args[0]
        assert persisted_docs[0]["threat_match"]["source"] == "feodo_tracker"
        assert persisted_docs[0]["remote_ip_intel"]["asn"] == "AS1234"

    def test_flow_missing_ips_is_skipped(self):
        mock_db = _mock_db_with_netflow_collection()
        raw_flows = [{"local_port": 80, "remote_port": 54321}]  # no local_ip/remote_ip

        with patch.object(nfs, "db", mock_db), \
             patch.object(nfs.geo_ip_service, "get_ip_intel", AsyncMock(return_value={})), \
             patch.object(nfs.threat_intel_service, "is_malicious_ip", AsyncMock(return_value=None)), \
             patch.object(secsvc.threat_engine, "process_netflow", AsyncMock(return_value=None)):
            result = asyncio.run(nfs.network_flow_service.enrich_and_persist_batch("host-a", raw_flows))

        assert result["ingested"] == 0
        mock_db.oneagent_netflows.insert_many.assert_not_awaited()


class TestFlowSummary:
    def test_aggregation_counts_top_talkers_and_threats(self):
        mock_db = MagicMock()
        flows = [
            {"remote_ip": "1.1.1.1", "service": "checkout", "threat_match": None},
            {"remote_ip": "1.1.1.1", "service": "checkout", "threat_match": None},
            {"remote_ip": "2.2.2.2", "service": "payments", "threat_match": {"source": "feodo_tracker"}},
        ]
        mock_db.oneagent_netflows.find.return_value.to_list = AsyncMock(return_value=flows)

        with patch.object(nfs, "db", mock_db):
            summary = asyncio.run(nfs.network_flow_service.get_flow_summary(hours=1))

        assert summary["total_flows"] == 3
        assert summary["distinct_remote_ips"] == 2
        assert summary["threat_flagged_flows"] == 1
        assert summary["top_talkers"][0] == {"remote_ip": "1.1.1.1", "count": 2}


class TestNetworkDependencies:
    def test_best_effort_edges_from_flows(self):
        mock_db = MagicMock()
        flows = [
            {"host": "host-a", "service": "checkout", "remote_ip": "10.0.0.9"},
            {"host": "host-a", "service": "checkout", "remote_ip": "10.0.0.9"},
        ]
        mock_db.oneagent_netflows.find.return_value.to_list = AsyncMock(return_value=flows)
        mock_db.oneagent_agents.find.return_value.to_list = AsyncMock(return_value=[])

        with patch.object(nfs, "db", mock_db):
            deps = asyncio.run(nfs.network_flow_service.get_network_dependencies(hours=24))

        assert deps["edge_count"] == 1
        assert deps["edges"][0]["count"] == 2
        assert deps["edges"][0]["source"] == "host-a:checkout"


# ──────────────────── security_service.py netflow detectors ────────────────────

class TestNetflowMaliciousIPDetector:
    def test_builds_threat_with_correct_shape(self):
        flow = {"host": "host-a", "local_port": 443, "remote_ip": "45.83.222.10", "service": "checkout"}
        ioc = {"source": "feodo_tracker", "malware_family": "banking_trojan"}
        threat = asyncio.run(secsvc.threat_engine._check_netflow_malicious_ip(flow, ioc))

        assert threat["type"] == "malicious_ip"
        assert threat["severity"] == "critical"
        assert threat["source_ip"] == "45.83.222.10"
        assert threat["detection_source"] == "netflow"
        assert threat["ioc_source"] == "feodo_tracker"


class TestNetflowScanPatternDetector:
    def setup_method(self):
        secsvc._port_connections.clear()

    def test_below_threshold_returns_none(self):
        flow = {"host": "scan-test-host-1", "local_port": 22, "remote_ip": "10.1.1.1"}
        result = asyncio.run(secsvc.threat_engine._check_netflow_scan_pattern(flow))
        assert result is None

    def test_threshold_exceeded_flags_scan(self):
        host, port = "scan-test-host-2", 22
        result = None
        for i in range(secsvc.NETFLOW_SCAN_DISTINCT_IP_THRESHOLD):
            flow = {"host": host, "local_port": port, "remote_ip": f"10.2.2.{i}"}
            result = asyncio.run(secsvc.threat_engine._check_netflow_scan_pattern(flow))
        assert result is not None
        assert result["type"] == "port_scan"
        assert result["detection_source"] == "netflow"
        assert result["distinct_ip_count"] == secsvc.NETFLOW_SCAN_DISTINCT_IP_THRESHOLD

    def test_same_ip_repeated_does_not_trigger(self):
        host, port = "scan-test-host-3", 22
        result = None
        for _ in range(secsvc.NETFLOW_SCAN_DISTINCT_IP_THRESHOLD + 5):
            flow = {"host": host, "local_port": port, "remote_ip": "10.3.3.3"}
            result = asyncio.run(secsvc.threat_engine._check_netflow_scan_pattern(flow))
        assert result is None

    def test_missing_local_port_or_remote_ip_returns_none(self):
        assert asyncio.run(secsvc.threat_engine._check_netflow_scan_pattern(
            {"host": "h", "remote_ip": "1.1.1.1"})) is None
        assert asyncio.run(secsvc.threat_engine._check_netflow_scan_pattern(
            {"host": "h", "local_port": 22})) is None


class TestProcessNetflow:
    def test_no_ioc_and_no_scan_returns_none(self):
        secsvc._port_connections.clear()
        with patch.object(secsvc.threat_engine, "_store_threat", AsyncMock()) as mock_store:
            result = asyncio.run(secsvc.threat_engine.process_netflow(
                {"host": "h", "local_port": 9999, "remote_ip": "10.9.9.9"}, ioc_match=None))
        assert result is None
        mock_store.assert_not_awaited()

    def test_ioc_match_fires_store_threat(self):
        secsvc._port_connections.clear()
        with patch.object(secsvc.threat_engine, "_store_threat", AsyncMock()) as mock_store:
            result = asyncio.run(secsvc.threat_engine.process_netflow(
                {"host": "h", "local_port": 443, "remote_ip": "45.83.222.10"},
                ioc_match={"source": "feodo_tracker", "malware_family": "x"}))
        assert result is not None
        assert len(result) == 1
        mock_store.assert_awaited_once()
