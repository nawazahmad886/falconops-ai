import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
    LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import {
    TrendingUp, TrendingDown, Minus, AlertTriangle, Clock,
    RefreshCw, Cpu, HardDrive, Database, Zap, ArrowUp, ArrowDown,
    Activity, Server, BarChart2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RISK_CONFIG = {
    critical: { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: AlertTriangle },
    high: { color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', icon: ArrowUp },
    medium: { color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: TrendingUp },
    low: { color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30', icon: Minus },
    info: { color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/30', icon: Activity },
};

const METRICS = [
    { value: 'cpu_usage', label: 'CPU Usage', icon: Cpu, unit: '%' },
    { value: 'memory_usage', label: 'Memory Usage', icon: Database, unit: '%' },
    { value: 'disk_usage', label: 'Disk Usage', icon: HardDrive, unit: '%' },
];

const HORIZONS = [
    { value: '1h', label: '1 Hour' },
    { value: '6h', label: '6 Hours' },
    { value: '24h', label: '24 Hours' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
];

export const CapacityPredictionPage = () => {
    const { token } = useAuth();
    const [selectedMetric, setSelectedMetric] = useState('cpu_usage');
    const [selectedHost, setSelectedHost] = useState('');
    const [horizon, setHorizon] = useState('24h');
    const [threshold, setThreshold] = useState(90);
    const [prediction, setPrediction] = useState(null);
    const [trends, setTrends] = useState(null);
    const [capacityAlerts, setCapacityAlerts] = useState([]);
    const [loading, setLoading] = useState(false);
    const [trendsLoading, setTrendsLoading] = useState(false);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const fetchPrediction = useCallback(async () => {
        if (!selectedMetric) return;
        setLoading(true);
        try {
            let url = `${API_URL}/api/capacity/predict?metric_name=${selectedMetric}&horizon=${horizon}&threshold=${threshold}`;
            if (selectedHost) url += `&host=${selectedHost}`;
            const res = await fetch(url, { headers: headers() });
            if (res.ok) setPrediction(await res.json());
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [headers, selectedMetric, selectedHost, horizon, threshold]);

    const fetchTrends = useCallback(async () => {
        setTrendsLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/capacity/trends`, { headers: headers() });
            if (res.ok) setTrends(await res.json());
        } catch (e) { console.error(e); }
        setTrendsLoading(false);
    }, [headers]);

    const fetchCapacityAlerts = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/capacity/alerts?threshold=${threshold}&horizon=${horizon}`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setCapacityAlerts(data.alerts || []);
            }
        } catch (e) { console.error(e); }
    }, [headers, threshold, horizon]);

    const seedMetrics = async () => {
        try {
            const res = await fetch(`${API_URL}/api/seed/metrics`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                toast.success(data.message);
                fetchPrediction();
                fetchTrends();
            }
        } catch (e) { toast.error(e.message); }
    };

    useEffect(() => { fetchPrediction(); }, [fetchPrediction]);
    useEffect(() => { fetchTrends(); fetchCapacityAlerts(); }, [fetchTrends, fetchCapacityAlerts]);

    const TrendIcon = ({ direction }) => {
        if (direction === 'increasing') return <TrendingUp className="h-4 w-4 text-red-400" />;
        if (direction === 'decreasing') return <TrendingDown className="h-4 w-4 text-emerald-400" />;
        return <Minus className="h-4 w-4 text-[#A3A3A3]" />;
    };

    return (
        <div data-testid="capacity-prediction-page" className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white font-[Barlow_Condensed] uppercase tracking-wide">
                        Capacity Prediction
                    </h1>
                    <p className="text-sm text-[#A3A3A3]">AI-powered capacity forecasting and trend analysis</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button data-testid="seed-metrics-btn" variant="outline" size="sm" onClick={seedMetrics}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white hover:border-[#D4AF37]">
                        <Zap className="h-4 w-4 mr-1" /> Seed Metrics
                    </Button>
                    <Button data-testid="refresh-prediction-btn" variant="outline" size="sm"
                        onClick={() => { fetchPrediction(); fetchTrends(); fetchCapacityAlerts(); }}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                        <RefreshCw className="h-4 w-4 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Controls */}
            <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                <CardContent className="p-4">
                    <div className="flex items-center gap-3 flex-wrap">
                        <Select value={selectedMetric} onValueChange={setSelectedMetric}>
                            <SelectTrigger data-testid="metric-select" className="w-[180px] bg-[#121212] border-[#1F1F1F] text-white">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0A0A0A] border-[#1F1F1F]">
                                {METRICS.map(m => (
                                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Select value={horizon} onValueChange={setHorizon}>
                            <SelectTrigger data-testid="horizon-select" className="w-[140px] bg-[#121212] border-[#1F1F1F] text-white">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0A0A0A] border-[#1F1F1F]">
                                {HORIZONS.map(h => (
                                    <SelectItem key={h.value} value={h.value}>{h.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <div className="flex items-center gap-2 text-sm text-[#A3A3A3]">
                            <span>Threshold:</span>
                            <input data-testid="threshold-input" type="number" value={threshold}
                                onChange={e => setThreshold(Number(e.target.value))}
                                className="w-16 bg-[#121212] border border-[#1F1F1F] rounded px-2 py-1 text-white text-sm font-[JetBrains_Mono]" />
                            <span>%</span>
                        </div>
                        <Button data-testid="run-prediction-btn" size="sm" onClick={fetchPrediction}
                            className="bg-[#D4AF37] text-black hover:bg-[#D4AF37]/90">
                            <BarChart2 className="h-4 w-4 mr-1" /> Predict
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Prediction Result */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <RefreshCw className="h-6 w-6 text-[#A3A3A3] animate-spin" />
                </div>
            ) : prediction?.status === 'success' ? (
                <div className="space-y-4">
                    {/* Summary Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <SummaryCard label="Current" value={`${prediction.current_value}%`} color="text-white" />
                        <SummaryCard label="Predicted" value={`${prediction.prediction.predicted_value}%`}
                            color={prediction.prediction.predicted_value > threshold ? 'text-red-400' : 'text-emerald-400'} />
                        <SummaryCard label="Confidence" value={`${prediction.prediction.confidence}%`} color="text-cyan-400" />
                        <SummaryCard label="Trend" value={prediction.trend.direction}
                            icon={<TrendIcon direction={prediction.trend.direction} />} />
                        <RiskCard risk={prediction.risk_assessment} />
                    </div>

                    {/* Forecast Chart */}
                    {prediction.forecast_series?.length > 0 && (
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                                    Forecast - {METRICS.find(m => m.value === selectedMetric)?.label || selectedMetric}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ResponsiveContainer width="100%" height={300}>
                                    <AreaChart data={prediction.forecast_series}>
                                        <defs>
                                            <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#00F0FF" stopOpacity={0.3} />
                                                <stop offset="100%" stopColor="#00F0FF" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                                        <XAxis dataKey="timestamp" tickFormatter={t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            stroke="#525252" fontSize={10} fontFamily="JetBrains Mono" />
                                        <YAxis stroke="#525252" fontSize={10} fontFamily="JetBrains Mono" />
                                        <Tooltip contentStyle={{ backgroundColor: '#0A0A0A', border: '1px solid #1F1F1F', borderRadius: 8, fontFamily: 'JetBrains Mono', fontSize: 11 }}
                                            labelFormatter={t => new Date(t).toLocaleString()} />
                                        <ReferenceLine y={threshold} stroke="#FF3B30" strokeDasharray="5 5" label={{ value: `Threshold ${threshold}%`, fill: '#FF3B30', fontSize: 10 }} />
                                        <Area type="monotone" dataKey="upper_bound" stroke="none" fill="#1F1F1F" fillOpacity={0.5} />
                                        <Area type="monotone" dataKey="lower_bound" stroke="none" fill="#050505" />
                                        <Line type="monotone" dataKey="value" stroke="#00F0FF" strokeWidth={2} dot={false} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    )}

                    {/* Threshold Analysis */}
                    {prediction.threshold_analysis?.will_breach && (
                        <Card className="bg-[#0A0A0A] border-red-500/30">
                            <CardContent className="p-4">
                                <div className="flex items-center gap-3">
                                    <AlertTriangle className="h-5 w-5 text-red-400" />
                                    <div>
                                        <p className="text-sm font-medium text-red-400">Threshold Breach Predicted</p>
                                        <p className="text-xs text-[#A3A3A3]">
                                            Expected to breach {threshold}% in{' '}
                                            <span className="text-white font-[JetBrains_Mono]">
                                                {prediction.threshold_analysis.time_to_threshold_hours}h
                                            </span>
                                            {prediction.threshold_analysis.estimated_breach_time && (
                                                <> ({new Date(prediction.threshold_analysis.estimated_breach_time).toLocaleString()})</>
                                            )}
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>
            ) : prediction?.status === 'insufficient_data' ? (
                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                    <CardContent className="py-12 text-center">
                        <BarChart2 className="h-12 w-12 text-[#525252] mx-auto mb-3" />
                        <p className="text-white font-medium">Insufficient Data</p>
                        <p className="text-sm text-[#A3A3A3] mb-4">Need at least 10 data points. Currently: {prediction.data_points || 0}</p>
                        <Button size="sm" onClick={seedMetrics} className="bg-[#D4AF37] text-black hover:bg-[#D4AF37]/90">
                            <Zap className="h-4 w-4 mr-1" /> Seed Demo Metrics
                        </Button>
                    </CardContent>
                </Card>
            ) : null}

            {/* Capacity Alerts */}
            {capacityAlerts.length > 0 && (
                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                            Capacity Warnings ({capacityAlerts.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {capacityAlerts.map((alert, i) => {
                                const risk = RISK_CONFIG[alert.risk_level] || RISK_CONFIG.info;
                                const RiskIcon = risk.icon;
                                return (
                                    <div key={i} data-testid={`capacity-alert-${i}`}
                                        className={`flex items-center justify-between p-3 rounded-lg border ${risk.bg}`}>
                                        <div className="flex items-center gap-3">
                                            <RiskIcon className={`h-4 w-4 ${risk.color}`} />
                                            <div>
                                                <span className="text-sm text-white">{alert.metric}</span>
                                                <span className="text-xs text-[#A3A3A3] ml-2">on {alert.host}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4 text-xs">
                                            <span className="text-[#A3A3A3]">Current: <span className="text-white font-[JetBrains_Mono]">{alert.current_value}%</span></span>
                                            <span className="text-[#A3A3A3]">Predicted: <span className={`font-[JetBrains_Mono] ${risk.color}`}>{alert.predicted_value}%</span></span>
                                            {alert.time_to_threshold_hours && (
                                                <span className="text-[#A3A3A3]">Breach in: <span className="text-white font-[JetBrains_Mono]">{alert.time_to_threshold_hours}h</span></span>
                                            )}
                                            <Badge className={`${risk.color} text-[10px]`}>{alert.risk_level}</Badge>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Trends Summary */}
            {trends && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <TrendCard title="Increasing" count={trends.increasing_trends?.length || 0}
                        items={trends.increasing_trends || []} color="text-red-400" icon={TrendingUp} />
                    <TrendCard title="Stable" count={trends.stable_trends?.length || 0}
                        items={trends.stable_trends || []} color="text-emerald-400" icon={Minus} />
                    <TrendCard title="Decreasing" count={trends.decreasing_trends?.length || 0}
                        items={trends.decreasing_trends || []} color="text-blue-400" icon={TrendingDown} />
                </div>
            )}
        </div>
    );
};

const SummaryCard = ({ label, value, color = 'text-white', icon }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
        <CardContent className="p-3 text-center">
            <p className="text-[10px] text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">{label}</p>
            <div className="flex items-center justify-center gap-1 mt-1">
                {icon}
                <p className={`text-lg font-bold font-[JetBrains_Mono] ${color}`}>{value}</p>
            </div>
        </CardContent>
    </Card>
);

const RiskCard = ({ risk }) => {
    const config = RISK_CONFIG[risk?.level] || RISK_CONFIG.info;
    const Icon = config.icon;
    return (
        <Card className={`border ${config.bg}`}>
            <CardContent className="p-3 text-center">
                <p className="text-[10px] text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">Risk</p>
                <div className="flex items-center justify-center gap-1 mt-1">
                    <Icon className={`h-4 w-4 ${config.color}`} />
                    <p className={`text-lg font-bold font-[Barlow_Condensed] uppercase ${config.color}`}>{risk?.level || 'N/A'}</p>
                </div>
            </CardContent>
        </Card>
    );
};

const TrendCard = ({ title, count, items, color, icon: Icon }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
        <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
                <Icon className={`h-4 w-4 ${color}`} />
                <span className={color}>{title}</span>
                <Badge className="bg-[#1F1F1F] text-[#A3A3A3] text-[10px]">{count}</Badge>
            </CardTitle>
        </CardHeader>
        <CardContent>
            {items.length === 0 ? (
                <p className="text-xs text-[#525252]">No metrics</p>
            ) : (
                <div className="space-y-1">
                    {items.slice(0, 5).map((item, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                            <span className="text-[#A3A3A3] truncate">{item.metric}</span>
                            <span className="text-white font-[JetBrains_Mono]">
                                {item.current_value}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </CardContent>
    </Card>
);

export default CapacityPredictionPage;
