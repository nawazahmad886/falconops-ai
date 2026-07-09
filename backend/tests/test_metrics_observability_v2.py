"""
FalconOps AI - Metrics Observability v2 API Tests
Tests for enterprise metrics ingestion, query, catalog, anomaly detection
"""
import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@falconapps.com"
TEST_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestMetricsIngestion:
    """Tests for metrics ingestion endpoints"""
    
    def test_ingest_single_metric(self, auth_headers):
        """Test POST /api/metrics/v2/ingest - single metric ingestion"""
        payload = {
            "name": "TEST_cpu_usage",
            "value": 75.5,
            "tags": {"host": "test-server-01", "service": "test-api"},
            "unit": "%",
            "type": "gauge"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/ingest",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "queued"
        assert "timestamp" in data
    
    def test_ingest_batch_metrics(self, auth_headers):
        """Test POST /api/metrics/v2/ingest/batch - batch metric ingestion"""
        payload = {
            "metrics": [
                {"name": "TEST_memory_usage", "value": 68.2, "tags": {"host": "test-server-01"}, "unit": "%"},
                {"name": "TEST_disk_usage", "value": 45.0, "tags": {"host": "test-server-01"}, "unit": "%"},
                {"name": "TEST_response_time", "value": 125.5, "tags": {"host": "test-server-01", "service": "test-api"}, "unit": "ms"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/ingest/batch",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["queued"] == 3
        assert "timestamp" in data
    
    def test_ingest_batch_max_limit(self, auth_headers):
        """Test batch ingestion rejects more than 1000 metrics"""
        # Create 1001 metrics
        metrics = [{"name": f"TEST_metric_{i}", "value": i} for i in range(1001)]
        
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/ingest/batch",
            headers=auth_headers,
            json={"metrics": metrics}
        )
        
        assert response.status_code == 400
        assert "1000" in response.json().get("detail", "")


class TestMetricsQuery:
    """Tests for metrics query endpoints"""
    
    def test_query_metrics_get(self, auth_headers):
        """Test GET /api/metrics/v2/query - query with aggregation"""
        params = {
            "metric_name": "cpu_usage",
            "aggregation": "avg",
            "bucket": "5m"
        }
        
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/query",
            headers=auth_headers,
            params=params
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["metric_name"] == "cpu_usage"
        assert data["aggregation"] == "avg"
        assert data["bucket"] == "5m"
        assert "series" in data
        assert "data_points" in data
    
    def test_query_metrics_post(self, auth_headers):
        """Test POST /api/metrics/v2/query - query via POST"""
        payload = {
            "metric_name": "cpu_usage",
            "aggregation": "max",
            "bucket": "1h"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/query",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["metric_name"] == "cpu_usage"
        assert data["aggregation"] == "max"
    
    def test_query_with_all_aggregations(self, auth_headers):
        """Test query with different aggregation types"""
        aggregations = ["avg", "sum", "min", "max", "p50", "p95", "p99"]
        
        for agg in aggregations:
            response = requests.get(
                f"{BASE_URL}/api/metrics/v2/query",
                headers=auth_headers,
                params={"metric_name": "cpu_usage", "aggregation": agg, "bucket": "5m"}
            )
            assert response.status_code == 200, f"Aggregation {agg} failed"
            assert response.json()["aggregation"] == agg
    
    def test_query_invalid_aggregation(self, auth_headers):
        """Test query with invalid aggregation returns error"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/query",
            headers=auth_headers,
            params={"metric_name": "cpu_usage", "aggregation": "invalid_agg", "bucket": "5m"}
        )
        
        assert response.status_code == 400
    
    def test_query_invalid_bucket(self, auth_headers):
        """Test query with invalid bucket returns error"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/query",
            headers=auth_headers,
            params={"metric_name": "cpu_usage", "aggregation": "avg", "bucket": "invalid"}
        )
        
        assert response.status_code == 400


class TestMetricsCatalog:
    """Tests for metrics catalog and discovery endpoints"""
    
    def test_get_catalog(self, auth_headers):
        """Test GET /api/metrics/v2/catalog - get metrics catalog"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/catalog",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "metrics" in data
        assert "total_metrics" in data
        assert "infrastructure" in data["categories"]
        assert "application" in data["categories"]
    
    def test_get_catalog_by_category(self, auth_headers):
        """Test catalog filtering by category"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/catalog",
            headers=auth_headers,
            params={"category": "infrastructure"}
        )
        
        assert response.status_code == 200
    
    def test_get_catalog_invalid_category(self, auth_headers):
        """Test catalog with invalid category returns error"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/catalog",
            headers=auth_headers,
            params={"category": "invalid_category"}
        )
        
        assert response.status_code == 400
    
    def test_get_categories(self, auth_headers):
        """Test GET /api/metrics/v2/categories - get metric categories"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/categories",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "aggregations" in data
        assert "time_buckets" in data
        
        # Verify expected categories
        categories = data["categories"]
        assert "infrastructure" in categories
        assert "application" in categories
        assert "database" in categories
        assert "kubernetes" in categories
        
        # Verify aggregations
        aggregations = data["aggregations"]
        assert "avg" in aggregations
        assert "sum" in aggregations
        assert "p95" in aggregations
        assert "p99" in aggregations
        
        # Verify time buckets
        buckets = data["time_buckets"]
        assert "1m" in buckets
        assert "5m" in buckets
        assert "1h" in buckets


class TestTopMetrics:
    """Tests for top metrics endpoint"""
    
    def test_get_top_metrics(self, auth_headers):
        """Test GET /api/metrics/v2/top - get top N by dimension"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/top",
            headers=auth_headers,
            params={"metric_name": "cpu_usage", "group_by": "host", "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["metric_name"] == "cpu_usage"
        assert data["group_by"] == "host"
        assert "results" in data
        
        # Verify result structure if results exist
        if data["results"]:
            result = data["results"][0]
            assert "host" in result
            assert "avg" in result
            assert "max" in result
            assert "min" in result
            assert "count" in result
    
    def test_get_top_metrics_by_service(self, auth_headers):
        """Test top metrics grouped by service"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/top",
            headers=auth_headers,
            params={"metric_name": "response_time", "group_by": "service", "limit": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["group_by"] == "service"


class TestAnomalyDetection:
    """Tests for anomaly detection endpoints"""
    
    def test_get_anomalies(self, auth_headers):
        """Test GET /api/metrics/v2/anomalies - get detected anomalies"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/anomalies",
            headers=auth_headers,
            params={"limit": 20}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "count" in data
        assert isinstance(data["anomalies"], list)
    
    def test_get_anomalies_by_severity(self, auth_headers):
        """Test anomalies filtered by severity"""
        for severity in ["low", "medium", "high", "critical"]:
            response = requests.get(
                f"{BASE_URL}/api/metrics/v2/anomalies",
                headers=auth_headers,
                params={"severity": severity, "limit": 10}
            )
            assert response.status_code == 200
    
    def test_get_anomalies_by_metric(self, auth_headers):
        """Test anomalies filtered by metric name"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/anomalies",
            headers=auth_headers,
            params={"metric_name": "cpu_usage", "limit": 10}
        )
        
        assert response.status_code == 200
    
    def test_get_anomaly_correlations(self, auth_headers):
        """Test GET /api/metrics/v2/anomalies/correlations"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/anomalies/correlations",
            headers=auth_headers,
            params={"time_window_minutes": 5, "limit": 50}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "anomalies_analyzed" in data
        assert "correlations" in data
        assert "correlation_count" in data


class TestMetricsStats:
    """Tests for metrics statistics endpoint"""
    
    def test_get_stats(self, auth_headers):
        """Test GET /api/metrics/v2/stats - get ingestion stats"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/stats",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert "total_data_points" in data
        assert "metrics_per_hour" in data
        assert "anomalies_per_hour" in data
        assert "unique_metrics" in data
        assert "ingestion_rate" in data
        assert "anomaly_rate" in data
        assert "stream" in data
        
        # Verify stream info
        stream = data["stream"]
        assert "length" in stream
        assert "groups" in stream


class TestStreamManagement:
    """Tests for Redis stream management"""
    
    def test_initialize_stream(self, auth_headers):
        """Test POST /api/metrics/v2/stream/initialize"""
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/stream/initialize",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initialized"
        assert "stream" in data


class TestEndToEndFlow:
    """End-to-end integration tests"""
    
    def test_ingest_and_query_flow(self, auth_headers):
        """Test complete flow: ingest -> wait -> query -> verify"""
        # 1. Ingest a unique metric
        unique_metric = f"TEST_e2e_metric_{int(time.time())}"
        ingest_response = requests.post(
            f"{BASE_URL}/api/metrics/v2/ingest",
            headers=auth_headers,
            json={
                "name": unique_metric,
                "value": 99.9,
                "tags": {"host": "e2e-test-host"},
                "unit": "%"
            }
        )
        assert ingest_response.status_code == 200
        
        # 2. Wait for processing (Redis stream -> MongoDB)
        time.sleep(2)
        
        # 3. Query the metric
        query_response = requests.get(
            f"{BASE_URL}/api/metrics/v2/query",
            headers=auth_headers,
            params={"metric_name": unique_metric, "aggregation": "avg", "bucket": "1m"}
        )
        assert query_response.status_code == 200
        
        # 4. Verify in catalog
        catalog_response = requests.get(
            f"{BASE_URL}/api/metrics/v2/catalog",
            headers=auth_headers,
            params={"search": unique_metric}
        )
        assert catalog_response.status_code == 200


class TestAuthorizationRequired:
    """Tests to verify endpoints require authentication"""
    
    def test_ingest_requires_auth(self):
        """Test ingest endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/metrics/v2/ingest",
            json={"name": "test", "value": 1}
        )
        assert response.status_code == 401
    
    def test_query_requires_auth(self):
        """Test query endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/metrics/v2/query",
            params={"metric_name": "test"}
        )
        assert response.status_code == 401
    
    def test_catalog_requires_auth(self):
        """Test catalog endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/metrics/v2/catalog")
        assert response.status_code == 401
    
    def test_stats_requires_auth(self):
        """Test stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/metrics/v2/stats")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
