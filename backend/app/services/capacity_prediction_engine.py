"""
FalconOps AI - Capacity Prediction Engine
AI-powered capacity forecasting and trend analysis
"""
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from scipy import stats
from ..core.database import db

logger = logging.getLogger(__name__)

# Try to import sklearn for advanced predictions
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# statsmodels was already a dependency (requirements.txt) but unused anywhere in
# the codebase — real seasonality-aware forecasting (Holt-Winters triple
# exponential smoothing) instead of the single-line linregress() trend fit below,
# which has no concept of daily/weekly cycles at all.
try:
    import pandas as pd
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    SEASONAL_FORECAST_AVAILABLE = True
except ImportError:
    SEASONAL_FORECAST_AVAILABLE = False

# Hourly-resampled data needs at least this many full 24h cycles before Holt-Winters'
# seasonal component is fit on more than noise. Below this, honestly fall back to
# the linear trend fit rather than fitting a seasonal model to ~1 cycle of data.
MIN_SEASONAL_PERIODS = 2
SEASONAL_PERIOD_HOURS = 24


class CapacityPredictionEngine:
    """AI-powered capacity forecasting and prediction"""
    
    def __init__(self):
        self.prediction_horizons = {
            "1h": 60,
            "6h": 360,
            "24h": 1440,
            "7d": 10080,
            "30d": 43200
        }
    
    async def predict_capacity(
        self,
        metric_name: str,
        host: Optional[str] = None,
        service: Optional[str] = None,
        horizon: str = "24h",
        threshold: float = 90,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Predict when a metric will reach a threshold"""
        
        # Get historical data (last 7 days)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)
        
        query = {
            "name": metric_name,
            "timestamp": {"$gte": start_time.isoformat(), "$lte": end_time.isoformat()}
        }
        if host:
            query["tags.host"] = host
        if service:
            query["tags.service"] = service
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        data = await db.metrics_timeseries.find(
            query, {"_id": 0, "value": 1, "timestamp": 1}
        ).sort("timestamp", 1).to_list(10000)

        return self._compute_prediction(metric_name, host, service, horizon, threshold, data)

    def _compute_prediction(
        self,
        metric_name: str,
        host: Optional[str],
        service: Optional[str],
        horizon: str,
        threshold: float,
        data: List[Dict],
    ) -> Dict:
        """Pure computation half of predict_capacity: given already-fetched
        (timestamp, value) points for one metric+host, produce the prediction dict.
        Split out so predict_all_hosts can fetch every host's data in a single grouped
        query instead of one full 7-day scan per host (previously: N hosts x up to 3
        metrics per get_capacity_alerts() call = up to 3N full collection scans)."""
        if len(data) < 10:
            return {
                "metric_name": metric_name,
                "status": "insufficient_data",
                "message": "Not enough data points for prediction",
                "data_points": len(data)
            }

        # Extract values and timestamps
        timestamps = []
        values = []
        base_time = datetime.fromisoformat(data[0]["timestamp"].replace("Z", "+00:00"))
        
        for d in data:
            ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00"))
            minutes_from_start = (ts - base_time).total_seconds() / 60
            timestamps.append(minutes_from_start)
            values.append(d["value"])
        
        timestamps = np.array(timestamps)
        values = np.array(values)
        
        # Calculate current statistics
        current_value = values[-1]
        avg_value = np.mean(values)
        std_value = np.std(values)
        trend = self._calculate_trend(timestamps, values)
        
        prediction_minutes = self.prediction_horizons.get(horizon, 1440)

        # Try real seasonality-aware forecasting first (Holt-Winters); falls back to
        # the linear-regression fit below when there isn't enough data for a
        # seasonal model, or statsmodels/pandas aren't installed — forecast_method
        # on the result says honestly which one actually ran, never claims
        # "seasonal" when it silently fell back.
        seasonal_result = None
        if SEASONAL_FORECAST_AVAILABLE:
            seasonal_result = self._predict_seasonal(data, prediction_minutes, threshold, base_time)

        if seasonal_result is not None:
            predicted_value = seasonal_result["predicted_value"]
            time_to_threshold = seasonal_result["time_to_threshold"]
            confidence = seasonal_result["confidence"]
            forecast_series = seasonal_result["forecast_series"]
            lower_bound = seasonal_result["lower_bound"]
            upper_bound = seasonal_result["upper_bound"]
            forecast_method = "seasonal_holt_winters"
        else:
            predicted_value, time_to_threshold, confidence = self._predict_linear(
                timestamps, values, prediction_minutes, threshold
            )
            lower_bound, upper_bound = self._calculate_prediction_bounds(
                values, predicted_value, std_value
            )
            forecast_series = self._generate_forecast_series(
                timestamps, values, prediction_minutes, base_time
            )
            forecast_method = "linear_regression"

        # Determine risk level
        risk_level, risk_message = self._assess_risk(
            current_value, predicted_value, threshold, time_to_threshold
        )
        
        return {
            "metric_name": metric_name,
            "host": host,
            "service": service,
            "status": "success",
            "current_value": float(round(current_value, 2)),
            "average_value": float(round(avg_value, 2)),
            "std_deviation": float(round(std_value, 2)),
            "trend": trend,
            "prediction": {
                "horizon": horizon,
                "horizon_minutes": prediction_minutes,
                "forecast_method": forecast_method,
                "predicted_value": float(round(predicted_value, 2)),
                "lower_bound": float(round(lower_bound, 2)),
                "upper_bound": float(round(upper_bound, 2)),
                "confidence": float(round(confidence * 100, 1))
            },
            "threshold_analysis": {
                "threshold": float(threshold),
                "will_breach": bool(predicted_value >= threshold),
                "time_to_threshold_minutes": float(round(time_to_threshold, 0)) if time_to_threshold else None,
                "time_to_threshold_hours": float(round(time_to_threshold / 60, 1)) if time_to_threshold else None,
                "estimated_breach_time": (base_time + timedelta(minutes=float(timestamps[-1]) + float(time_to_threshold))).isoformat() if time_to_threshold else None
            },
            "risk_assessment": {
                "level": risk_level,
                "message": risk_message
            },
            "forecast_series": forecast_series,
            "data_points_analyzed": len(data),
            "analysis_period_days": 7,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _calculate_trend(self, timestamps: np.ndarray, values: np.ndarray) -> Dict:
        """Calculate trend direction and strength"""
        if len(timestamps) < 2:
            return {"direction": "stable", "strength": 0, "slope": 0}
        
        # Linear regression for trend
        slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, values)
        
        # Determine direction
        if abs(slope) < 0.001:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        # Calculate rate of change per hour
        rate_per_hour = slope * 60
        
        return {
            "direction": direction,
            "strength": float(round(abs(r_value), 3)),
            "slope": float(round(slope, 6)),
            "rate_per_hour": float(round(rate_per_hour, 4)),
            "r_squared": float(round(r_value ** 2, 3))
        }
    
    def _predict_linear(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        prediction_minutes: int,
        threshold: float
    ) -> Tuple[float, Optional[float], float]:
        """Predict value using linear regression"""
        
        # Fit linear model
        slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, values)
        
        # Predict at horizon
        future_time = timestamps[-1] + prediction_minutes
        predicted_value = slope * future_time + intercept
        
        # Calculate time to threshold
        time_to_threshold = None
        if slope > 0 and values[-1] < threshold:
            # Calculate when we'll hit threshold
            time_needed = (threshold - values[-1]) / slope
            if time_needed > 0:
                time_to_threshold = time_needed
        elif slope < 0 and values[-1] > threshold:
            # Calculate when we'll drop below threshold (for decreasing metrics)
            time_needed = (values[-1] - threshold) / abs(slope)
            if time_needed > 0:
                time_to_threshold = time_needed
        
        # Confidence based on R-squared
        confidence = float(max(0, min(1, r_value ** 2)))

        return float(predicted_value), time_to_threshold, confidence

    def _predict_seasonal(
        self,
        data: List[Dict],
        prediction_minutes: int,
        threshold: float,
        base_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Real seasonality-aware forecast via Holt-Winters triple exponential
        smoothing (statsmodels) — captures a daily cycle (SEASONAL_PERIOD_HOURS),
        unlike the single straight-line linregress() fit in _predict_linear.
        Returns None (caller falls back to linear) when there isn't enough data
        for at least MIN_SEASONAL_PERIODS full cycles — fitting a seasonal model
        on ~1 cycle of data would be fitting noise, not a real pattern."""
        try:
            df = pd.DataFrame(data)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            series = df.set_index("timestamp")["value"].sort_index()
            # Irregular raw points -> regular hourly grid (Holt-Winters' seasonal_periods
            # is a positional offset, not aware of the DatetimeIndex's actual spacing —
            # any row DROPPED here would silently misalign "24 steps back" from "24 hours
            # back". So gaps are always FILLED (interpolate, then ffill/bfill for any
            # edges interpolate can't reach), never dropped — the index stays perfectly
            # regular. If too much of the series had to be filled, the seasonal pattern
            # would mostly be interpolated fiction, not real data — bail out to linear.
            resampled = series.resample("1h").mean()
            gap_fraction = resampled.isna().sum() / max(len(resampled), 1)
            if gap_fraction > 0.2:
                return None
            hourly = resampled.interpolate(limit=3).ffill().bfill()
            if len(hourly) < MIN_SEASONAL_PERIODS * SEASONAL_PERIOD_HOURS:
                return None

            fit = ExponentialSmoothing(
                hourly, trend="add", seasonal="add",
                seasonal_periods=SEASONAL_PERIOD_HOURS, initialization_method="estimated",
            ).fit()

            steps = max(1, round(prediction_minutes / 60))
            # Cap the walk-forward search for a threshold crossing at 30 days —
            # a metric that won't cross within a month isn't a near-term capacity risk.
            max_lookout_steps = max(steps, 24 * 30)
            forecast = fit.forecast(max_lookout_steps)

            resid_std = float(np.std(fit.resid)) if len(fit.resid) else float(hourly.std())
            data_std = float(hourly.std()) or 1e-9
            # A real (if simplified) confidence measure: how much of the data's
            # own variance the fitted model's residuals still contain — not a
            # simulated prediction interval (statsmodels' ETS confidence intervals
            # need the newer ETSModel API), but derived from the actual fit, not guessed.
            confidence = float(max(0.0, min(1.0, 1 - (resid_std / data_std))))

            predicted_value = float(forecast.iloc[steps - 1])
            last_value = float(hourly.iloc[-1])

            time_to_threshold = None
            for i, val in enumerate(forecast.values, start=1):
                crossed = (last_value < threshold <= val) or (last_value > threshold >= val)
                if crossed:
                    time_to_threshold = float(i * 60)  # minutes
                    break

            forecast_series = []
            for i in range(steps + 1):
                idx = min(i, len(forecast) - 1)
                val = float(hourly.iloc[-1]) if i == 0 else float(forecast.iloc[idx])
                ts = hourly.index[-1] if i == 0 else forecast.index[idx]
                margin = 2 * resid_std * (1 + i / max(steps, 1)) ** 0.5  # widen with horizon — real, not arbitrary
                forecast_series.append({
                    "timestamp": ts.isoformat(),
                    "value": round(val, 2),
                    "lower_bound": round(max(0, val - margin), 2),
                    "upper_bound": round(val + margin, 2),
                })

            final_margin = 2 * resid_std * (1 + steps / max(steps, 1)) ** 0.5
            return {
                "predicted_value": predicted_value,
                "time_to_threshold": time_to_threshold,
                "confidence": confidence,
                "lower_bound": max(0.0, predicted_value - final_margin),
                "upper_bound": predicted_value + final_margin,
                "forecast_series": forecast_series,
            }
        except Exception as e:
            logger.warning(f"seasonal forecast failed, falling back to linear: {e}")
            return None

    def _calculate_prediction_bounds(
        self,
        values: np.ndarray,
        predicted_value: float,
        std_value: float
    ) -> Tuple[float, float]:
        """Calculate prediction confidence bounds"""
        # Use 2 standard deviations for ~95% confidence
        margin = 2 * std_value
        lower_bound = max(0, predicted_value - margin)
        upper_bound = predicted_value + margin
        return lower_bound, upper_bound
    
    def _generate_forecast_series(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        prediction_minutes: int,
        base_time: datetime,
        num_points: int = 20
    ) -> List[Dict]:
        """Generate forecast time series for visualization"""
        
        # Fit model
        slope, intercept, _, _, _ = stats.linregress(timestamps, values)
        std_value = np.std(values)
        
        # Generate future timestamps
        last_ts = timestamps[-1]
        step = prediction_minutes / num_points
        
        forecast = []
        for i in range(num_points + 1):
            future_ts = last_ts + (i * step)
            predicted = slope * future_ts + intercept
            future_time = base_time + timedelta(minutes=future_ts)
            
            forecast.append({
                "timestamp": future_time.isoformat(),
                "value": float(round(predicted, 2)),
                "lower_bound": float(round(max(0, predicted - 2 * std_value), 2)),
                "upper_bound": float(round(predicted + 2 * std_value, 2))
            })
        
        return forecast
    
    def _assess_risk(
        self,
        current_value: float,
        predicted_value: float,
        threshold: float,
        time_to_threshold: Optional[float]
    ) -> Tuple[str, str]:
        """Assess risk level based on predictions"""
        
        if current_value >= threshold:
            return "critical", f"Current value ({current_value:.1f}) already exceeds threshold ({threshold})"
        
        if time_to_threshold is None:
            return "low", f"No threshold breach predicted in the analysis horizon"
        
        hours_to_breach = time_to_threshold / 60
        
        if hours_to_breach < 1:
            return "critical", f"Threshold breach expected in {time_to_threshold:.0f} minutes"
        elif hours_to_breach < 4:
            return "high", f"Threshold breach expected in {hours_to_breach:.1f} hours"
        elif hours_to_breach < 24:
            return "medium", f"Threshold breach expected in {hours_to_breach:.1f} hours"
        elif hours_to_breach < 72:
            return "low", f"Threshold breach expected in {hours_to_breach / 24:.1f} days"
        else:
            return "info", f"Threshold breach expected in {hours_to_breach / 24:.1f} days"
    
    async def predict_all_hosts(
        self,
        metric_name: str,
        horizon: str = "24h",
        threshold: float = 90,
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Predict capacity for all hosts with a specific metric.

        Single grouped 7-day query instead of one full collection scan per host: this
        used to call predict_capacity() (a fresh find().to_list(10000)) once per host,
        and get_capacity_alerts() calls this 3x (cpu/memory/disk) — with N hosts that
        was up to 3N full unindexed scans per request."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        query = {
            "name": metric_name,
            "timestamp": {"$gte": start_time.isoformat(), "$lte": end_time.isoformat()}
        }
        if tenant_id:
            query["tenant_id"] = tenant_id

        docs = await db.metrics_timeseries.find(
            query, {"_id": 0, "value": 1, "timestamp": 1, "tags.host": 1}
        ).sort("timestamp", 1).to_list(100000)

        by_host: Dict[str, List[Dict]] = {}
        for d in docs:
            h = (d.get("tags") or {}).get("host")
            if h:
                by_host.setdefault(h, []).append({"value": d["value"], "timestamp": d["timestamp"]})

        predictions = []
        for host, host_data in by_host.items():
            try:
                prediction = self._compute_prediction(metric_name, host, None, horizon, threshold, host_data)
                if prediction.get("status") == "success":
                    predictions.append(prediction)
            except Exception as e:
                print(f"Prediction error for {host}: {e}")

        # Sort by risk level
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        predictions.sort(key=lambda x: risk_order.get(x.get("risk_assessment", {}).get("level", "info"), 4))

        return predictions
    
    async def get_capacity_alerts(
        self,
        threshold: float = 90,
        horizon: str = "24h",
        tenant_id: Optional[str] = None
    ) -> List[Dict]:
        """Get capacity alerts for metrics approaching thresholds"""
        
        alerts = []
        
        # Key metrics to monitor
        capacity_metrics = [
            ("cpu_usage", 90, "CPU"),
            ("memory_usage", 90, "Memory"),
            ("disk_usage", 85, "Disk"),
        ]
        
        for metric_name, default_threshold, label in capacity_metrics:
            predictions = await self.predict_all_hosts(
                metric_name=metric_name,
                horizon=horizon,
                threshold=threshold or default_threshold,
                tenant_id=tenant_id
            )
            
            for pred in predictions:
                risk = pred.get("risk_assessment", {})
                if risk.get("level") in ["critical", "high", "medium"]:
                    alerts.append({
                        "metric": label,
                        "metric_name": metric_name,
                        "host": pred.get("host"),
                        "current_value": pred.get("current_value"),
                        "predicted_value": pred.get("prediction", {}).get("predicted_value"),
                        "threshold": pred.get("threshold_analysis", {}).get("threshold"),
                        "time_to_threshold_hours": pred.get("threshold_analysis", {}).get("time_to_threshold_hours"),
                        "risk_level": risk.get("level"),
                        "risk_message": risk.get("message"),
                        "trend": pred.get("trend", {}).get("direction")
                    })
        
        return alerts
    
    async def get_trends_report(
        self,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """Generate trends report for all monitored metrics"""
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics_analyzed": 0,
            "increasing_trends": [],
            "decreasing_trends": [],
            "stable_trends": [],
            "capacity_warnings": []
        }
        
        # Get unique metrics
        query = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        metrics = await db.metrics_timeseries.distinct("name", query)
        report["metrics_analyzed"] = len(metrics)
        
        for metric_name in metrics[:20]:  # Limit to top 20 metrics
            try:
                prediction = await self.predict_capacity(
                    metric_name=metric_name,
                    horizon="24h",
                    threshold=90,
                    tenant_id=tenant_id
                )
                
                if prediction.get("status") != "success":
                    continue
                
                trend_info = {
                    "metric": metric_name,
                    "current_value": prediction.get("current_value"),
                    "trend": prediction.get("trend"),
                    "predicted_value_24h": prediction.get("prediction", {}).get("predicted_value")
                }
                
                direction = prediction.get("trend", {}).get("direction", "stable")
                if direction == "increasing":
                    report["increasing_trends"].append(trend_info)
                elif direction == "decreasing":
                    report["decreasing_trends"].append(trend_info)
                else:
                    report["stable_trends"].append(trend_info)
                
                # Check for capacity warnings
                if prediction.get("threshold_analysis", {}).get("will_breach"):
                    report["capacity_warnings"].append({
                        "metric": metric_name,
                        "time_to_breach_hours": prediction.get("threshold_analysis", {}).get("time_to_threshold_hours"),
                        "risk_level": prediction.get("risk_assessment", {}).get("level")
                    })
                    
            except Exception as e:
                print(f"Trend analysis error for {metric_name}: {e}")
        
        return report


# Singleton instance
capacity_prediction_engine = CapacityPredictionEngine()
