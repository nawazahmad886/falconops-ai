"""
FalconOps AI - Enhanced Anomaly Detection Engine
Multi-algorithm anomaly detection: Z-score, EWMA, Isolation Forest, Dynamic Thresholds
"""
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from ..core.database import db

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class AnomalyDetectionEngine:
    """Multi-algorithm anomaly detection with ensemble scoring"""

    SEVERITY_THRESHOLDS = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}

    # --- Individual Detectors ---

    def zscore_detect(self, values: np.ndarray, current: float, threshold: float = 3.0) -> Dict:
        if len(values) < 5:
            return {"is_anomaly": False, "score": 0, "method": "zscore"}
        mean = float(np.mean(values))
        std = float(np.std(values))
        if std == 0:
            return {"is_anomaly": False, "score": 0, "method": "zscore", "mean": mean, "std": 0}
        z = float((current - mean) / std)
        return {
            "is_anomaly": abs(z) > threshold,
            "score": min(abs(z) / 5.0, 1.0),
            "z_score": round(z, 3),
            "mean": round(mean, 3),
            "std": round(std, 3),
            "method": "zscore",
        }

    def ewma_detect(self, values: np.ndarray, current: float, span: int = 20, sigma: float = 2.5) -> Dict:
        if len(values) < span:
            return {"is_anomaly": False, "score": 0, "method": "ewma"}
        alpha = 2 / (span + 1)
        ewma = float(values[0])
        ewma_var = 0.0
        for v in values[1:]:
            diff = float(v) - ewma
            ewma += alpha * diff
            ewma_var = (1 - alpha) * (ewma_var + alpha * diff * diff)
        ewma_std = float(np.sqrt(ewma_var)) if ewma_var > 0 else 1.0
        deviation = abs(current - ewma) / ewma_std if ewma_std > 0 else 0
        return {
            "is_anomaly": deviation > sigma,
            "score": min(deviation / (sigma * 2), 1.0),
            "ewma_mean": round(ewma, 3),
            "ewma_std": round(ewma_std, 3),
            "deviation": round(float(deviation), 3),
            "method": "ewma",
        }

    def isolation_forest_detect(self, values: np.ndarray, current: float) -> Dict:
        if not SKLEARN_AVAILABLE or len(values) < 20:
            return {"is_anomaly": False, "score": 0, "method": "isolation_forest", "available": SKLEARN_AVAILABLE}
        X = values.reshape(-1, 1)
        clf = IsolationForest(contamination=0.05, random_state=42, n_estimators=100)
        clf.fit(X)
        score = float(clf.decision_function(np.array([[current]]))[0])
        pred = int(clf.predict(np.array([[current]]))[0])
        anomaly_score = max(0, -score)
        return {
            "is_anomaly": pred == -1,
            "score": min(anomaly_score / 0.5, 1.0),
            "raw_score": round(score, 4),
            "method": "isolation_forest",
        }

    def dynamic_threshold_detect(self, values: np.ndarray, current: float, percentile: float = 95) -> Dict:
        if len(values) < 10:
            return {"is_anomaly": False, "score": 0, "method": "dynamic_threshold"}
        upper = float(np.percentile(values, percentile))
        lower = float(np.percentile(values, 100 - percentile))
        iqr = float(np.percentile(values, 75) - np.percentile(values, 25))
        is_anomaly = current > upper or current < lower
        if upper != lower:
            distance = max(current - upper, lower - current, 0) / (iqr if iqr > 0 else 1)
        else:
            distance = 0
        return {
            "is_anomaly": is_anomaly,
            "score": min(float(distance) / 3, 1.0),
            "upper_threshold": round(upper, 3),
            "lower_threshold": round(lower, 3),
            "method": "dynamic_threshold",
        }

    def seasonal_detect(self, values: np.ndarray, current: float, period: int = 24) -> Dict:
        """Detect anomalies using simple seasonal decomposition (hourly period)."""
        if len(values) < period * 2:
            return {"is_anomaly": False, "score": 0, "method": "seasonal"}
        # Calculate seasonal component by averaging same-period positions
        seasonal = np.zeros(period)
        counts = np.zeros(period)
        for i, v in enumerate(values):
            idx = i % period
            seasonal[idx] += v
            counts[idx] += 1
        seasonal = seasonal / np.maximum(counts, 1)
        current_season = seasonal[len(values) % period]
        residual = current - current_season
        residuals_all = values - np.array([seasonal[i % period] for i in range(len(values))])
        res_std = float(np.std(residuals_all))
        if res_std == 0:
            return {"is_anomaly": False, "score": 0, "method": "seasonal"}
        z = abs(float(residual)) / res_std
        return {
            "is_anomaly": z > 3,
            "score": min(z / 5, 1.0),
            "seasonal_expected": round(float(current_season), 3),
            "residual": round(float(residual), 3),
            "residual_zscore": round(z, 3),
            "method": "seasonal",
        }

    # --- Ensemble ---

    def ensemble_detect(self, values: np.ndarray, current: float) -> Dict:
        """Run all detectors and produce ensemble anomaly score."""
        results = {
            "zscore": self.zscore_detect(values, current),
            "ewma": self.ewma_detect(values, current),
            "dynamic_threshold": self.dynamic_threshold_detect(values, current),
            "seasonal": self.seasonal_detect(values, current),
        }
        if SKLEARN_AVAILABLE and len(values) >= 20:
            results["isolation_forest"] = self.isolation_forest_detect(values, current)

        weights = {"zscore": 0.25, "ewma": 0.25, "dynamic_threshold": 0.2, "seasonal": 0.15, "isolation_forest": 0.15}
        total_weight = sum(weights.get(k, 0) for k in results)
        ensemble_score = sum(results[k]["score"] * weights.get(k, 0) for k in results) / total_weight if total_weight > 0 else 0

        severity = "info"
        for sev, thresh in self.SEVERITY_THRESHOLDS.items():
            if ensemble_score >= thresh:
                severity = sev
                break

        votes = sum(1 for r in results.values() if r.get("is_anomaly"))
        is_anomaly = votes >= 2 or ensemble_score >= 0.7

        return {
            "is_anomaly": is_anomaly,
            "ensemble_score": round(float(ensemble_score), 4),
            "severity": severity,
            "detector_votes": votes,
            "total_detectors": len(results),
            "detectors": results,
        }

    # --- High-level API ---

    async def analyze_metric(
        self,
        metric_name: str,
        host: Optional[str] = None,
        service: Optional[str] = None,
        lookback_hours: int = 6,
        tenant_id: Optional[str] = None,
    ) -> Dict:
        """Fetch recent data and run ensemble anomaly detection on the latest value."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=lookback_hours)
        query = {"name": metric_name, "timestamp": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
        if host:
            query["tags.host"] = host
        if service:
            query["tags.service"] = service
        if tenant_id:
            query["tenant_id"] = tenant_id

        docs = await db.metrics_timeseries.find(query, {"_id": 0, "value": 1, "timestamp": 1}).sort("timestamp", 1).to_list(5000)
        if len(docs) < 5:
            return {"metric_name": metric_name, "status": "insufficient_data", "data_points": len(docs)}

        values = np.array([d["value"] for d in docs], dtype=float)
        current = float(values[-1])
        baseline = values[:-1] if len(values) > 1 else values
        result = self.ensemble_detect(baseline, current)

        return {
            "metric_name": metric_name,
            "host": host,
            "service": service,
            "status": "success",
            "current_value": round(current, 3),
            "data_points": len(docs),
            "lookback_hours": lookback_hours,
            "anomaly": result,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def scan_all_metrics(
        self, lookback_hours: int = 6, tenant_id: Optional[str] = None
    ) -> Dict:
        """Scan all unique metric+host combos and return anomalies."""
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        metric_names = await db.metrics_timeseries.distinct("name", query)

        anomalies = []
        scanned = 0
        for name in metric_names[:30]:
            hosts = await db.metrics_timeseries.distinct("tags.host", {"name": name, **({} if not tenant_id else {"tenant_id": tenant_id})})
            for host in (hosts or [None])[:10]:
                result = await self.analyze_metric(name, host=host, lookback_hours=lookback_hours, tenant_id=tenant_id)
                scanned += 1
                if result.get("status") == "success" and result.get("anomaly", {}).get("is_anomaly"):
                    anomalies.append(result)

        anomalies.sort(key=lambda x: x.get("anomaly", {}).get("ensemble_score", 0), reverse=True)
        return {
            "scanned": scanned,
            "anomalies_found": len(anomalies),
            "anomalies": anomalies,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_metric_baseline(
        self, metric_name: str, host: Optional[str] = None, hours: int = 24, tenant_id: Optional[str] = None
    ) -> Dict:
        """Compute baseline stats for a metric."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        query = {"name": metric_name, "timestamp": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
        if host:
            query["tags.host"] = host
        if tenant_id:
            query["tenant_id"] = tenant_id

        docs = await db.metrics_timeseries.find(query, {"_id": 0, "value": 1}).to_list(10000)
        if not docs:
            return {"metric_name": metric_name, "status": "no_data"}

        values = np.array([d["value"] for d in docs], dtype=float)
        return {
            "metric_name": metric_name,
            "host": host,
            "status": "success",
            "data_points": len(values),
            "mean": round(float(np.mean(values)), 3),
            "std": round(float(np.std(values)), 3),
            "min": round(float(np.min(values)), 3),
            "max": round(float(np.max(values)), 3),
            "p50": round(float(np.percentile(values, 50)), 3),
            "p90": round(float(np.percentile(values, 90)), 3),
            "p95": round(float(np.percentile(values, 95)), 3),
            "p99": round(float(np.percentile(values, 99)), 3),
        }


anomaly_detection_engine = AnomalyDetectionEngine()
