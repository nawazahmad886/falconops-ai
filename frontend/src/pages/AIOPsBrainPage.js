import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
    Brain, Activity, AlertTriangle, Shield, Zap, RefreshCw,
    TrendingUp, Server, Database, ArrowRight, Target,
    GitBranch, Eye, CheckCircle2, XCircle, Clock, Network,
    Fingerprint, Cpu, MemoryStick, HardDrive, TrendingDown, ChevronRight,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RISK_COLORS = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    minimal: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
};

export const AIOPsBrainPage = () => {
    const { token } = useAuth();
    const [activeTab, setActiveTab] = useState('overview');
    const [systemRisk, setSystemRisk] = useState(null);
    const [anomalyScan, setAnomalyScan] = useState(null);
    const [blastRadius, setBlastRadius] = useState(null);
    const [selectedService, setSelectedService] = useState('postgres-primary');
    const [correlationResult, setCorrelationResult] = useState(null);
    const [anomalyDetail, setAnomalyDetail] = useState(null);
    const [loading, setLoading] = useState({});
    const [topology, setTopology] = useState(null);

    // New: Correlation + RCA + Prediction state
    const [violationCorrelation, setViolationCorrelation] = useState(null);
    const [rcaResult, setRcaResult] = useState(null);
    const [forecastResult, setForecastResult] = useState(null);
    const [expandedIncident, setExpandedIncident] = useState(null);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const setLoad = (key, val) => setLoading(prev => ({ ...prev, [key]: val }));

    const fetchSystemRisk = useCallback(async () => {
        setLoad('risk', true);
        try {
            const res = await fetch(`${API_URL}/api/impact/system-risk`, { headers: headers() });
            if (res.ok) setSystemRisk(await res.json());
        } catch (e) { console.error(e); }
        setLoad('risk', false);
    }, [headers]);

    const fetchTopology = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/topology/v2/stats`, { headers: headers() });
            if (res.ok) setTopology(await res.json());
        } catch (e) { console.error(e); }
    }, [headers]);

    const runAnomalyScan = async () => {
        setLoad('scan', true);
        try {
            const res = await fetch(`${API_URL}/api/anomaly-detection/scan?lookback_hours=24`, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setAnomalyScan(data);
                toast.success(`Scan complete: ${data.anomalies_found} anomalies found`);
            }
        } catch (e) { toast.error(e.message); }
        setLoad('scan', false);
    };

    const runSmartCorrelation = async () => {
        setLoad('correlate', true);
        try {
            const res = await fetch(`${API_URL}/api/smart-correlation/run?time_window_minutes=60&min_signals=2`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                setCorrelationResult(data);
                toast.success(`Correlation: ${data.incidents_created} incidents created`);
            }
        } catch (e) { toast.error(e.message); }
        setLoad('correlate', false);
    };

    const fetchBlastRadius = async (svc) => {
        setLoad('blast', true);
        try {
            const res = await fetch(`${API_URL}/api/impact/blast-radius?service_name=${encodeURIComponent(svc)}`, { headers: headers() });
            if (res.ok) setBlastRadius(await res.json());
        } catch (e) { console.error(e); }
        setLoad('blast', false);
    };

    const analyzeMetric = async (metric, host) => {
        setLoad('detail', true);
        try {
            let url = `${API_URL}/api/anomaly-detection/analyze?metric_name=${metric}&lookback_hours=24`;
            if (host) url += `&host=${host}`;
            const res = await fetch(url, { headers: headers() });
            if (res.ok) setAnomalyDetail(await res.json());
        } catch (e) { console.error(e); }
        setLoad('detail', false);
    };

    const seedData = async () => {
        setLoad('seed', true);
        try {
            const res = await fetch(`${API_URL}/api/seed/full`, { method: 'POST', headers: headers() });
            if (res.ok) {
                toast.success('Demo data seeded');
                fetchSystemRisk();
            }
        } catch (e) { toast.error(e.message); }
        setLoad('seed', false);
    };

    const runViolationCorrelation = async () => {
        setLoad('vcorr', true);
        try {
            const res = await fetch(`${API_URL}/api/correlation/correlate-violations?time_window_minutes=2880&min_group_size=1`, {
                method: 'POST', headers: headers(),
            });
            if (res.ok) {
                const data = await res.json();
                setViolationCorrelation(data);
                toast.success(`${data.incidents_created} incident groups found`);
            }
        } catch (e) { toast.error(e.message); }
        setLoad('vcorr', false);
    };

    const runRCA = async () => {
        setLoad('rca', true);
        try {
            const res = await fetch(`${API_URL}/api/correlation/rca-violations`, {
                method: 'POST', headers: headers(),
            });
            if (res.ok) {
                const data = await res.json();
                setRcaResult(data);
                toast.success(data.ai_powered ? 'AI-powered RCA complete' : 'Rule-based RCA complete');
            }
        } catch (e) { toast.error(e.message); }
        setLoad('rca', false);
    };

    const fetchForecast = async () => {
        setLoad('forecast', true);
        try {
            const res = await fetch(`${API_URL}/api/capacity/forecast-summary`, { headers: headers() });
            if (res.ok) {
                setForecastResult(await res.json());
            }
        } catch (e) { console.error(e); }
        setLoad('forecast', false);
    };

    useEffect(() => { fetchSystemRisk(); }, [fetchSystemRisk]);
    useEffect(() => { if (selectedService) fetchBlastRadius(selectedService); }, [selectedService]);

    return (
        <div data-testid="aiops-brain-page" className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white font-[Barlow_Condensed] uppercase tracking-wide flex items-center gap-2">
                        <Brain className="h-6 w-6 text-[#D4AF37]" /> AIOps Brain
                    </h1>
                    <p className="text-sm text-[#A3A3A3]">Multi-algorithm anomaly detection, smart correlation, and impact analysis</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button data-testid="seed-demo-btn" variant="outline" size="sm" onClick={seedData}
                        disabled={loading.seed}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white hover:border-[#D4AF37]">
                        <Zap className="h-4 w-4 mr-1" /> {loading.seed ? 'Seeding...' : 'Seed Demo'}
                    </Button>
                    <Button data-testid="refresh-brain-btn" variant="outline" size="sm" onClick={fetchSystemRisk}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                        <RefreshCw className="h-4 w-4 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* System Risk Banner */}
            {systemRisk && (
                <Card data-testid="system-risk-card" className={`border ${RISK_COLORS[systemRisk.risk_level] || RISK_COLORS.low}`}>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="text-center">
                                    <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">System Risk</p>
                                    <p className={`text-4xl font-bold font-[JetBrains_Mono] ${RISK_COLORS[systemRisk.risk_level]?.split(' ')[0]}`}>
                                        {systemRisk.risk_score}
                                    </p>
                                    <Badge className={`text-xs mt-1 ${RISK_COLORS[systemRisk.risk_level]}`}>
                                        {systemRisk.risk_level?.toUpperCase()}
                                    </Badge>
                                </div>
                                <div className="h-16 w-px bg-[#1F1F1F]" />
                                <div className="grid grid-cols-4 gap-6">
                                    <MiniStat label="Active Alerts" value={systemRisk.active_alerts} icon={AlertTriangle} />
                                    <MiniStat label="Active Incidents" value={systemRisk.active_incidents} icon={Shield} />
                                    <MiniStat label="Services" value={systemRisk.total_services} icon={Server} />
                                    <MiniStat label="Unhealthy" value={systemRisk.unhealthy_services} icon={XCircle}
                                        color={systemRisk.unhealthy_services > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-[#0A0A0A] border border-[#1F1F1F]">
                    <TabsTrigger data-testid="tab-overview" value="overview" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        <Eye className="h-3.5 w-3.5 mr-1" /> Overview
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-anomaly" value="anomaly" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        <Activity className="h-3.5 w-3.5 mr-1" /> Anomaly Detection
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-correlation" value="correlation" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        <GitBranch className="h-3.5 w-3.5 mr-1" /> Smart Correlation
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-impact" value="impact" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        <Target className="h-3.5 w-3.5 mr-1" /> Impact Analysis
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-alert-correlation" value="alert-correlation" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-red-400">
                        <Fingerprint className="h-3.5 w-3.5 mr-1" /> Alert Correlation
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-rca" value="rca" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-emerald-400">
                        <Brain className="h-3.5 w-3.5 mr-1" /> Root Cause
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-prediction" value="prediction" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-blue-400">
                        <TrendingUp className="h-3.5 w-3.5 mr-1" /> Prediction
                    </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="mt-4 space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <AILayerCard title="Anomaly Detection" desc="Multi-algorithm ensemble: Z-score, EWMA, Isolation Forest, Dynamic Thresholds, Seasonal"
                            icon={Activity} color="text-cyan-400" status={anomalyScan ? `${anomalyScan.anomalies_found} anomalies` : 'Ready'}
                            action="Run Scan" onAction={runAnomalyScan} loading={loading.scan} />
                        <AILayerCard title="Smart Correlation" desc="Topology-aware event correlation using dependency graphs, host patterns, and metric signals"
                            icon={GitBranch} color="text-purple-400" status={correlationResult ? `${correlationResult.incidents_created} correlated` : 'Ready'}
                            action="Run Correlation" onAction={runSmartCorrelation} loading={loading.correlate} />
                        <AILayerCard title="Impact Analysis" desc="Blast radius calculation, business impact scoring, and service dependency cascade analysis"
                            icon={Target} color="text-amber-400" status={systemRisk ? `Risk: ${systemRisk.risk_score}/100` : 'Ready'} />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <AILayerCard title="Alert Correlation Engine" desc="Groups health rule violations by source, metric family, and severity cascade into incidents"
                            icon={Fingerprint} color="text-red-400" status={violationCorrelation ? `${violationCorrelation.incidents_created} groups` : 'Ready'}
                            action="Correlate Alerts" onAction={runViolationCorrelation} loading={loading.vcorr} />
                        <AILayerCard title="Root Cause Analysis" desc="AI-powered RCA engine that identifies root causes from active violations using LLM + heuristics"
                            icon={Brain} color="text-emerald-400" status={rcaResult ? (rcaResult.ai_powered ? 'AI Analysis' : 'Rule Analysis') : 'Ready'}
                            action="Run RCA" onAction={runRCA} loading={loading.rca} />
                        <AILayerCard title="Capacity Prediction" desc="Statistical forecasting of resource metrics to predict threshold breaches before they happen"
                            icon={TrendingUp} color="text-blue-400" status={forecastResult ? `${forecastResult.at_risk} at risk` : 'Ready'}
                            action="Forecast" onAction={fetchForecast} loading={loading.forecast} />
                    </div>

                    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                                AI Engine Architecture
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center justify-between gap-2 overflow-x-auto pb-2">
                                {[
                                    { label: 'Data Ingestion', icon: Database, color: 'text-blue-400' },
                                    { label: 'Anomaly Detection', icon: Activity, color: 'text-cyan-400' },
                                    { label: 'Event Correlation', icon: GitBranch, color: 'text-purple-400' },
                                    { label: 'Root Cause', icon: Brain, color: 'text-red-400' },
                                    { label: 'Impact Analysis', icon: Target, color: 'text-amber-400' },
                                    { label: 'Automation', icon: Zap, color: 'text-emerald-400' },
                                ].map((step, i, arr) => (
                                    <React.Fragment key={step.label}>
                                        <div className="flex flex-col items-center gap-1 min-w-[100px]">
                                            <div className={`p-2 rounded-lg bg-[#121212] border border-[#1F1F1F]`}>
                                                <step.icon className={`h-5 w-5 ${step.color}`} />
                                            </div>
                                            <span className="text-[10px] text-[#A3A3A3] text-center font-[Barlow_Condensed] uppercase">{step.label}</span>
                                        </div>
                                        {i < arr.length - 1 && <ArrowRight className="h-4 w-4 text-[#525252] shrink-0" />}
                                    </React.Fragment>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Anomaly Detection Tab */}
                <TabsContent value="anomaly" className="mt-4 space-y-4">
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-[#A3A3A3]">Multi-algorithm ensemble anomaly detection across all metrics</p>
                        <Button data-testid="run-anomaly-scan-btn" size="sm" onClick={runAnomalyScan} disabled={loading.scan}
                            className="bg-[#D4AF37] text-black hover:bg-[#D4AF37]/90">
                            <Activity className="h-4 w-4 mr-1" /> {loading.scan ? 'Scanning...' : 'Run Full Scan'}
                        </Button>
                    </div>

                    {anomalyScan && (
                        <>
                            <div className="grid grid-cols-3 gap-4">
                                <StatCard label="Metrics Scanned" value={anomalyScan.scanned} icon={Eye} />
                                <StatCard label="Anomalies Found" value={anomalyScan.anomalies_found}
                                    icon={AlertTriangle} color={anomalyScan.anomalies_found > 0 ? 'text-red-400' : 'text-emerald-400'} />
                                <StatCard label="Detection Methods" value="5" icon={Brain} />
                            </div>

                            {anomalyScan.anomalies?.length > 0 ? (
                                <div className="space-y-2">
                                    {anomalyScan.anomalies.map((a, i) => (
                                        <Card key={i} data-testid={`anomaly-card-${i}`}
                                            className="bg-[#0A0A0A] border-[#1F1F1F] hover:border-[#2A2A2A] transition-colors cursor-pointer"
                                            onClick={() => analyzeMetric(a.metric_name, a.host)}>
                                            <CardContent className="p-4">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3">
                                                        <div className={`w-2 h-2 rounded-full ${a.anomaly.severity === 'critical' ? 'bg-red-500' : a.anomaly.severity === 'high' ? 'bg-orange-500' : 'bg-amber-500'}`} />
                                                        <div>
                                                            <span className="text-sm font-medium text-white">{a.metric_name}</span>
                                                            <span className="text-xs text-[#525252] ml-2">on {a.host || 'all hosts'}</span>
                                                            <div className="flex items-center gap-3 mt-1 text-[10px] text-[#525252]">
                                                                <span>Current: <span className="text-white font-[JetBrains_Mono]">{a.current_value}</span></span>
                                                                <span>Points: {a.data_points}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-3">
                                                        <div className="text-right">
                                                            <p className="text-lg font-bold font-[JetBrains_Mono] text-white">{a.anomaly.ensemble_score}</p>
                                                            <p className="text-[10px] text-[#525252]">ensemble score</p>
                                                        </div>
                                                        <Badge className={`${RISK_COLORS[a.anomaly.severity] || ''} text-xs`}>{a.anomaly.severity}</Badge>
                                                        <Badge className="bg-[#1F1F1F] text-[#A3A3A3] text-[10px]">
                                                            {a.anomaly.detector_votes}/{a.anomaly.total_detectors} votes
                                                        </Badge>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            ) : (
                                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                                    <CardContent className="py-8 text-center">
                                        <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto mb-2" />
                                        <p className="text-white font-medium">No Anomalies Detected</p>
                                        <p className="text-xs text-[#A3A3A3]">All {anomalyScan.scanned} metric series within normal baselines</p>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}

                    {/* Anomaly Detail */}
                    {anomalyDetail?.status === 'success' && (
                        <Card className="bg-[#0A0A0A] border-cyan-500/20">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-cyan-400 font-[Barlow_Condensed] uppercase tracking-wider">
                                    Detailed Analysis: {anomalyDetail.metric_name}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                                    {Object.entries(anomalyDetail.anomaly?.detectors || {}).map(([name, det]) => (
                                        <div key={name} className={`p-2 rounded-lg border ${det.is_anomaly ? 'border-red-500/30 bg-red-500/5' : 'border-[#1F1F1F] bg-[#121212]'}`}>
                                            <p className="text-[10px] text-[#A3A3A3] uppercase font-[Barlow_Condensed]">{name.replace('_', ' ')}</p>
                                            <p className={`text-sm font-bold font-[JetBrains_Mono] ${det.is_anomaly ? 'text-red-400' : 'text-emerald-400'}`}>
                                                {det.is_anomaly ? 'ANOMALY' : 'NORMAL'}
                                            </p>
                                            <p className="text-[10px] text-[#525252]">Score: {(det.score || 0).toFixed(3)}</p>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {!anomalyScan && (
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardContent className="py-12 text-center">
                                <Activity className="h-12 w-12 text-[#525252] mx-auto mb-3" />
                                <p className="text-white font-medium">Run Anomaly Scan</p>
                                <p className="text-xs text-[#A3A3A3]">Click "Run Full Scan" to analyze all metrics with 5 detection algorithms</p>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Smart Correlation Tab */}
                <TabsContent value="correlation" className="mt-4 space-y-4">
                    <div className="flex items-center justify-between">
                        <p className="text-sm text-[#A3A3A3]">Topology-aware alert correlation reduces noise by grouping related signals</p>
                        <Button data-testid="run-correlation-btn" size="sm" onClick={runSmartCorrelation} disabled={loading.correlate}
                            className="bg-[#D4AF37] text-black hover:bg-[#D4AF37]/90">
                            <GitBranch className="h-4 w-4 mr-1" /> {loading.correlate ? 'Correlating...' : 'Run Smart Correlation'}
                        </Button>
                    </div>

                    {correlationResult && (
                        <>
                            <div className="grid grid-cols-3 gap-4">
                                <StatCard label="Alerts Processed" value={correlationResult.alerts_processed} icon={AlertTriangle} />
                                <StatCard label="Incidents Created" value={correlationResult.incidents_created} icon={Shield} />
                                <StatCard label="Noise Reduction" value={
                                    correlationResult.alerts_processed > 0
                                        ? `${Math.round((1 - correlationResult.incidents_created / Math.max(correlationResult.alerts_processed, 1)) * 100)}%`
                                        : 'N/A'
                                } icon={TrendingUp} />
                            </div>

                            <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                                        Correlation Methods Used
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-4 gap-3 mb-4">
                                        {['topology_dependency', 'same_host', 'metric_pattern', 'same_service'].map(type => {
                                            const count = (correlationResult.correlation_details || []).filter(d => d.type === type).length;
                                            return (
                                                <div key={type} className="p-3 rounded-lg bg-[#121212] border border-[#1F1F1F] text-center">
                                                    <p className="text-[10px] text-[#A3A3A3] uppercase font-[Barlow_Condensed]">{type.replace(/_/g, ' ')}</p>
                                                    <p className="text-xl font-bold text-white font-[JetBrains_Mono]">{count}</p>
                                                </div>
                                            );
                                        })}
                                    </div>

                                    {correlationResult.correlation_details?.length > 0 && (
                                        <div className="space-y-2">
                                            {correlationResult.correlation_details.map((det, i) => (
                                                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-[#121212] border border-[#1F1F1F]">
                                                    <div className="flex items-center gap-2">
                                                        <Badge className="text-[10px] bg-purple-500/20 text-purple-400">{det.type.replace(/_/g, ' ')}</Badge>
                                                        <span className="text-sm text-white">{det.reason}</span>
                                                    </div>
                                                    <div className="flex items-center gap-3 text-xs text-[#A3A3A3]">
                                                        <span>{det.alerts} alerts</span>
                                                        <span className="font-[JetBrains_Mono]">conf: {det.confidence}</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </>
                    )}

                    {!correlationResult && (
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardContent className="py-12 text-center">
                                <GitBranch className="h-12 w-12 text-[#525252] mx-auto mb-3" />
                                <p className="text-white font-medium">Run Smart Correlation</p>
                                <p className="text-xs text-[#A3A3A3]">Correlates alerts using topology dependency, host, metric pattern, and service grouping</p>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Impact Analysis Tab */}
                <TabsContent value="impact" className="mt-4 space-y-4">
                    <div className="flex items-center gap-3">
                        <p className="text-sm text-[#A3A3A3]">Blast radius for:</p>
                        <Select value={selectedService} onValueChange={(v) => { setSelectedService(v); fetchBlastRadius(v); }}>
                            <SelectTrigger data-testid="blast-service-select" className="w-[220px] bg-[#121212] border-[#1F1F1F] text-white">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0A0A0A] border-[#1F1F1F]">
                                {['postgres-primary', 'redis-cache', 'api-gateway', 'rabbitmq', 'order-service', 'auth-service', 'payment-service'].map(s => (
                                    <SelectItem key={s} value={s}>{s}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {blastRadius && !blastRadius.error && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-3 gap-4">
                                <StatCard label="Impacted Services" value={blastRadius.total_impacted} icon={Network} />
                                <StatCard label="Risk Level" value={blastRadius.risk_level?.toUpperCase()} icon={Shield}
                                    color={RISK_COLORS[blastRadius.risk_level]?.split(' ')[0] || 'text-white'} />
                                <StatCard label="Source Service" value={blastRadius.service} icon={Server} />
                            </div>

                            {blastRadius.impacted_services?.length > 0 && (
                                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                                            Cascade Impact Map
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            {/* Source */}
                                            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                                                <XCircle className="h-4 w-4 text-red-400" />
                                                <span className="text-sm font-medium text-red-400">{blastRadius.service}</span>
                                                <Badge className="text-[10px] bg-red-500/20 text-red-400">FAILURE ORIGIN</Badge>
                                            </div>

                                            {/* Group by depth */}
                                            {[1, 2, 3, 4, 5].map(depth => {
                                                const atDepth = blastRadius.impacted_services.filter(s => s.depth === depth);
                                                if (atDepth.length === 0) return null;
                                                return (
                                                    <div key={depth} className="ml-6">
                                                        <p className="text-[10px] text-[#525252] uppercase font-[Barlow_Condensed] mb-1">
                                                            Depth {depth} - {depth === 1 ? 'Direct dependents' : `${depth} hops away`}
                                                        </p>
                                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                                            {atDepth.map((s, i) => (
                                                                <div key={i} className="flex items-center gap-2 p-2 rounded bg-[#121212] border border-[#1F1F1F]">
                                                                    <ArrowRight className="h-3 w-3 text-amber-400" />
                                                                    <span className="text-xs text-white">{s.service}</span>
                                                                    <Badge className="text-[9px] bg-[#1F1F1F] text-[#A3A3A3]">{s.type}</Badge>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}

                    {blastRadius?.error && (
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardContent className="py-8 text-center">
                                <Target className="h-10 w-10 text-[#525252] mx-auto mb-2" />
                                <p className="text-white font-medium">{blastRadius.error}</p>
                                <p className="text-xs text-[#A3A3A3] mt-1">Seed demo data to populate the topology graph</p>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* ════════ ALERT CORRELATION TAB ════════ */}
                <TabsContent value="alert-correlation" className="mt-4 space-y-4" data-testid="alert-correlation-tab-content">
                    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-sm text-white flex items-center gap-2">
                                        <Fingerprint className="h-4 w-4 text-red-400" /> Alert Correlation Engine
                                    </CardTitle>
                                    <CardDescription className="mt-1">Groups related health rule violations into correlated incident clusters</CardDescription>
                                </div>
                                <Button size="sm" onClick={runViolationCorrelation} disabled={loading.vcorr}
                                    className="bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30" data-testid="run-correlation-btn">
                                    {loading.vcorr ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <Zap className="h-4 w-4 mr-1" />}
                                    Correlate Violations
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {violationCorrelation ? (
                                <div className="space-y-4">
                                    {/* Summary */}
                                    <div className="grid grid-cols-3 gap-3">
                                        <div className="p-3 bg-red-500/[0.06] border border-red-500/20 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-red-400">{violationCorrelation.incidents_created}</div>
                                            <div className="text-[10px] text-white/40">Incident Groups</div>
                                        </div>
                                        <div className="p-3 bg-[#F5B841]/[0.06] border border-[#F5B841]/20 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-[#F5B841]">{violationCorrelation.violations_processed}</div>
                                            <div className="text-[10px] text-white/40">Violations Processed</div>
                                        </div>
                                        <div className="p-3 bg-white/[0.03] border border-white/10 rounded-lg text-center">
                                            <div className="text-sm font-medium text-white/70 mt-1">{violationCorrelation.summary}</div>
                                        </div>
                                    </div>

                                    {/* Incident Groups */}
                                    {violationCorrelation.groups?.map((g) => (
                                        <div key={g.id} className={`rounded-xl border transition-all cursor-pointer ${
                                            expandedIncident === g.id ? 'border-red-500/40 bg-red-500/[0.04]' : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                                        }`} onClick={() => setExpandedIncident(expandedIncident === g.id ? null : g.id)}
                                            data-testid={`incident-group-${g.id}`}>
                                            <div className="p-4 flex items-center justify-between">
                                                <div className="flex items-center gap-4">
                                                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                                        g.severity === 'critical' ? 'bg-red-500/15' : 'bg-yellow-500/15'
                                                    }`}>
                                                        <AlertTriangle className={`w-5 h-5 ${g.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'}`} />
                                                    </div>
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <h4 className="text-sm font-medium text-white">{g.root_cause}</h4>
                                                        </div>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <Badge variant="outline" className="text-[9px] border-white/15 text-white/40">{g.strategy.replace(/_/g, ' ')}</Badge>
                                                            <span className="text-[10px] text-white/30">Confidence: {Math.round(g.confidence * 100)}%</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    <div className="text-center"><div className="text-lg font-bold text-white">{g.violation_count}</div><div className="text-[9px] text-white/30">Total</div></div>
                                                    <div className="text-center"><div className="text-lg font-bold text-red-400">{g.critical_count}</div><div className="text-[9px] text-white/30">Critical</div></div>
                                                    <div className="text-center"><div className="text-lg font-bold text-yellow-400">{g.warning_count}</div><div className="text-[9px] text-white/30">Warning</div></div>
                                                    <ChevronRight className={`w-4 h-4 text-white/20 transition-transform ${expandedIncident === g.id ? 'rotate-90' : ''}`} />
                                                </div>
                                            </div>
                                            {expandedIncident === g.id && (
                                                <div className="px-4 pb-4 border-t border-white/5 space-y-3 mt-0 pt-3">
                                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                        <div>
                                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Rules Triggered</h5>
                                                            <div className="flex flex-wrap gap-1">{g.rules?.map((r,i) => <Badge key={i} variant="outline" className="text-[10px] border-red-500/20 text-red-400/80">{r}</Badge>)}</div>
                                                        </div>
                                                        <div>
                                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Metrics</h5>
                                                            <div className="flex flex-wrap gap-1">{g.metrics?.map((m,i) => <Badge key={i} variant="outline" className="text-[10px] border-white/15 text-white/50">{m}</Badge>)}</div>
                                                        </div>
                                                        <div>
                                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Sources</h5>
                                                            <div className="flex flex-wrap gap-1">{g.sources?.map((s,i) => <Badge key={i} variant="outline" className="text-[10px] border-blue-500/20 text-blue-400/80">{s}</Badge>)}</div>
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Fingerprints</h5>
                                                        <div className="flex flex-wrap gap-1.5">{g.fingerprints?.map((fp,i) => (
                                                            <span key={i} className="font-mono text-[10px] text-[#00E0FF]/70 px-1.5 py-0.5 bg-[#00E0FF]/[0.05] rounded border border-[#00E0FF]/20">
                                                                <Fingerprint className="w-2.5 h-2.5 inline mr-0.5" />{fp}
                                                            </span>
                                                        ))}</div>
                                                    </div>
                                                    <div>
                                                        <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Suggested Actions</h5>
                                                        <ol className="space-y-1 list-decimal list-inside">
                                                            {g.suggested_actions?.map((a,i) => <li key={i} className="text-xs text-white/60">{a}</li>)}
                                                        </ol>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-12">
                                    <Fingerprint className="w-14 h-14 mx-auto text-white/10 mb-4" />
                                    <p className="text-white/40 mb-2">Click "Correlate Violations" to group active alerts into incidents</p>
                                    <p className="text-xs text-white/25">Uses 3 strategies: same source, fleet-wide metric, severity cascade</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ════════ RCA TAB ════════ */}
                <TabsContent value="rca" className="mt-4 space-y-4" data-testid="rca-tab-content">
                    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-sm text-white flex items-center gap-2">
                                        <Brain className="h-4 w-4 text-emerald-400" /> Root Cause Analysis
                                    </CardTitle>
                                    <CardDescription className="mt-1">AI-powered analysis of active violations to identify root causes</CardDescription>
                                </div>
                                <Button size="sm" onClick={runRCA} disabled={loading.rca}
                                    className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30" data-testid="run-rca-btn">
                                    {loading.rca ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <Brain className="h-4 w-4 mr-1" />}
                                    Run RCA
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {rcaResult ? (
                                <div className="space-y-4">
                                    {/* Context summary */}
                                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                                        <div className="p-3 bg-white/[0.03] border border-white/10 rounded-lg text-center">
                                            <div className="text-xl font-bold text-white">{rcaResult.context?.total_violations}</div>
                                            <div className="text-[10px] text-white/30">Active Violations</div>
                                        </div>
                                        <div className="p-3 bg-red-500/[0.06] border border-red-500/20 rounded-lg text-center">
                                            <div className="text-xl font-bold text-red-400">{rcaResult.context?.critical}</div>
                                            <div className="text-[10px] text-white/30">Critical</div>
                                        </div>
                                        <div className="p-3 bg-yellow-500/[0.06] border border-yellow-500/20 rounded-lg text-center">
                                            <div className="text-xl font-bold text-yellow-400">{rcaResult.context?.warning}</div>
                                            <div className="text-[10px] text-white/30">Warning</div>
                                        </div>
                                        <div className="p-3 bg-white/[0.03] border border-white/10 rounded-lg text-center">
                                            <div className="text-xl font-bold text-white">{rcaResult.context?.sources?.length}</div>
                                            <div className="text-[10px] text-white/30">Sources</div>
                                        </div>
                                        <div className="p-3 rounded-lg text-center" style={{ background: rcaResult.ai_powered ? 'rgba(16,185,129,0.06)' : 'rgba(245,184,65,0.06)', border: `1px solid ${rcaResult.ai_powered ? 'rgba(16,185,129,0.2)' : 'rgba(245,184,65,0.2)'}` }}>
                                            <div className="text-sm font-bold" style={{ color: rcaResult.ai_powered ? '#10B981' : '#F5B841' }}>
                                                {rcaResult.ai_powered ? 'AI' : 'Rules'}
                                            </div>
                                            <div className="text-[10px] text-white/30">Engine Used</div>
                                        </div>
                                    </div>

                                    {/* AI Analysis */}
                                    {rcaResult.llm_analysis && (
                                        <Card className="bg-emerald-500/[0.04] border-emerald-500/20">
                                            <CardHeader className="pb-2">
                                                <CardTitle className="text-sm text-emerald-400 flex items-center gap-2">
                                                    <Brain className="h-4 w-4" /> AI-Powered Analysis
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <div className="prose prose-invert prose-sm max-w-none text-white/70 text-sm leading-relaxed whitespace-pre-wrap">
                                                    {rcaResult.llm_analysis}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Rule-based analysis */}
                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                        <Card className="bg-white/[0.02] border-white/10">
                                            <CardHeader className="pb-2">
                                                <CardTitle className="text-sm text-red-400 flex items-center gap-2">
                                                    <AlertTriangle className="h-4 w-4" /> Root Cause
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-white/70">{rcaResult.rule_analysis?.root_cause}</p>
                                                <div className="mt-3 p-2.5 bg-white/[0.03] rounded-lg">
                                                    <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Impact</p>
                                                    <p className="text-xs text-white/60">{rcaResult.rule_analysis?.impact}</p>
                                                </div>
                                                <div className="mt-2 p-2.5 bg-yellow-500/[0.04] border border-yellow-500/20 rounded-lg">
                                                    <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Prediction</p>
                                                    <p className="text-xs text-yellow-400/80">{rcaResult.rule_analysis?.prediction}</p>
                                                </div>
                                            </CardContent>
                                        </Card>

                                        <Card className="bg-white/[0.02] border-white/10">
                                            <CardHeader className="pb-2">
                                                <CardTitle className="text-sm text-emerald-400 flex items-center gap-2">
                                                    <CheckCircle2 className="h-4 w-4" /> Recommended Actions
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <ol className="space-y-2 list-decimal list-inside">
                                                    {rcaResult.rule_analysis?.recommended_actions?.map((a,i) => (
                                                        <li key={i} className="text-sm text-white/60">{a}</li>
                                                    ))}
                                                </ol>
                                                {rcaResult.rule_analysis?.correlation_patterns?.length > 0 && (
                                                    <div className="mt-4 pt-3 border-t border-white/5">
                                                        <p className="text-[10px] text-white/40 uppercase tracking-wider mb-2">Correlation Patterns</p>
                                                        {rcaResult.rule_analysis.correlation_patterns.map((p,i) => (
                                                            <div key={i} className="flex items-start gap-2 mb-1.5">
                                                                <Network className="w-3 h-3 mt-0.5 text-purple-400 shrink-0" />
                                                                <p className="text-xs text-white/50">{p}</p>
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                    </div>

                                    {/* Affected metrics and sources */}
                                    <div className="flex flex-wrap gap-4">
                                        <div>
                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Metrics Affected</h5>
                                            <div className="flex flex-wrap gap-1">{rcaResult.context?.metrics?.map((m,i) => <Badge key={i} variant="outline" className="text-[10px] border-white/15 text-white/50">{m}</Badge>)}</div>
                                        </div>
                                        <div>
                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Sources</h5>
                                            <div className="flex flex-wrap gap-1">{rcaResult.context?.sources?.map((s,i) => <Badge key={i} variant="outline" className="text-[10px] border-blue-500/20 text-blue-400/80">{s}</Badge>)}</div>
                                        </div>
                                        <div>
                                            <h5 className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Rules</h5>
                                            <div className="flex flex-wrap gap-1">{rcaResult.context?.rules?.map((r,i) => <Badge key={i} variant="outline" className="text-[10px] border-red-500/20 text-red-400/80">{r}</Badge>)}</div>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-12">
                                    <Brain className="w-14 h-14 mx-auto text-white/10 mb-4" />
                                    <p className="text-white/40 mb-2">Click "Run RCA" to analyze active violations</p>
                                    <p className="text-xs text-white/25">Uses AI (when available) + rule-based heuristics to identify root cause</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ════════ PREDICTION TAB ════════ */}
                <TabsContent value="prediction" className="mt-4 space-y-4" data-testid="prediction-tab-content">
                    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-sm text-white flex items-center gap-2">
                                        <TrendingUp className="h-4 w-4 text-blue-400" /> Capacity Prediction Engine
                                    </CardTitle>
                                    <CardDescription className="mt-1">Forecast resource metrics and predict threshold breaches before they happen</CardDescription>
                                </div>
                                <Button size="sm" onClick={fetchForecast} disabled={loading.forecast}
                                    className="bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/30" data-testid="run-forecast-btn">
                                    {loading.forecast ? <RefreshCw className="h-4 w-4 mr-1 animate-spin" /> : <TrendingUp className="h-4 w-4 mr-1" />}
                                    Run Forecast
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {forecastResult ? (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-3 gap-3">
                                        <div className="p-3 bg-blue-500/[0.06] border border-blue-500/20 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-blue-400">{forecastResult.total}</div>
                                            <div className="text-[10px] text-white/30">Metrics Forecasted</div>
                                        </div>
                                        <div className="p-3 bg-red-500/[0.06] border border-red-500/20 rounded-lg text-center">
                                            <div className="text-2xl font-bold text-red-400">{forecastResult.at_risk}</div>
                                            <div className="text-[10px] text-white/30">At Risk (24h)</div>
                                        </div>
                                        <div className="p-3 bg-white/[0.03] border border-white/10 rounded-lg text-center">
                                            <div className="text-sm font-medium text-white/60 mt-1">{forecastResult.summary}</div>
                                        </div>
                                    </div>

                                    {forecastResult.predictions?.length > 0 ? (
                                        <div className="space-y-3">
                                            {/* Chart: bar chart of current vs predicted */}
                                            <Card className="bg-white/[0.02] border-white/10">
                                                <CardHeader className="pb-2">
                                                    <CardTitle className="text-sm text-white/70">Current vs Predicted (24h)</CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="h-[250px]">
                                                        <ResponsiveContainer width="100%" height="100%">
                                                            <BarChart data={forecastResult.predictions.map(p => ({
                                                                name: `${p.metric.replace(/_/g,' ')} (${p.host?.slice(0,12) || 'all'})`,
                                                                current: Math.round(p.current * 10) / 10,
                                                                predicted: Math.round(p.predicted_24h * 10) / 10,
                                                            }))} margin={{ left: 10 }}>
                                                                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                                                                <XAxis dataKey="name" stroke="#666" tick={{ fill: '#999', fontSize: 10 }} angle={-15} />
                                                                <YAxis stroke="#666" tick={{ fill: '#999', fontSize: 11 }} />
                                                                <RTooltip contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '8px' }} />
                                                                <Legend />
                                                                <Bar dataKey="current" fill="#00E0FF" name="Current" radius={[4, 4, 0, 0]} />
                                                                <Bar dataKey="predicted" fill="#F59E0B" name="Predicted 24h" radius={[4, 4, 0, 0]} />
                                                            </BarChart>
                                                        </ResponsiveContainer>
                                                    </div>
                                                </CardContent>
                                            </Card>

                                            {/* Prediction cards */}
                                            {forecastResult.predictions.map((p, i) => {
                                                const riskColor = p.risk_level === 'critical' ? 'border-red-500/30 bg-red-500/[0.04]'
                                                    : p.risk_level === 'warning' ? 'border-yellow-500/30 bg-yellow-500/[0.04]'
                                                    : 'border-white/10 bg-white/[0.02]';
                                                const MetricIcon = p.metric.includes('cpu') ? Cpu : p.metric.includes('mem') ? MemoryStick : HardDrive;
                                                return (
                                                    <div key={i} className={`p-4 rounded-xl border ${riskColor}`}>
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-3">
                                                                <MetricIcon className="w-5 h-5 text-white/40" />
                                                                <div>
                                                                    <h4 className="text-sm font-medium text-white">{p.metric.replace(/_/g, ' ')} <span className="text-white/30">on {p.host}</span></h4>
                                                                    <div className="flex items-center gap-3 mt-1 text-xs text-white/40">
                                                                        <span>Current: <strong className="text-white">{Math.round(p.current * 10) / 10}</strong></span>
                                                                        <ArrowRight className="w-3 h-3" />
                                                                        <span>Predicted: <strong className="text-[#F5B841]">{Math.round(p.predicted_24h * 10) / 10}</strong></span>
                                                                        <span>Trend: <strong className={p.trend === 'increasing' ? 'text-red-400' : p.trend === 'decreasing' ? 'text-emerald-400' : 'text-white/50'}>
                                                                            {p.trend === 'increasing' ? 'Rising' : p.trend === 'decreasing' ? 'Falling' : 'Stable'}
                                                                        </strong></span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <div className="text-right">
                                                                <Badge variant="outline" className={`text-[10px] ${
                                                                    p.risk_level === 'critical' ? 'border-red-500/30 text-red-400' :
                                                                    p.risk_level === 'warning' ? 'border-yellow-500/30 text-yellow-400' :
                                                                    'border-emerald-500/30 text-emerald-400'
                                                                }`}>{p.risk_level}</Badge>
                                                                {p.will_breach && (
                                                                    <p className="text-[10px] text-red-400 mt-1">
                                                                        <Clock className="w-3 h-3 inline mr-0.5" /> Breach: {p.breach_time ? new Date(p.breach_time).toLocaleString() : 'Soon'}
                                                                    </p>
                                                                )}
                                                                <p className="text-[10px] text-white/30 mt-0.5">Confidence: {Math.round(p.confidence * 100)}%</p>
                                                            </div>
                                                        </div>
                                                        <p className="text-xs text-white/40 mt-2">{p.risk_message}</p>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="text-center py-8">
                                            <TrendingUp className="w-12 h-12 mx-auto text-white/10 mb-3" />
                                            <p className="text-white/40">No metrics data available for forecasting</p>
                                            <p className="text-xs text-white/25 mt-1">Push server metrics via agents to enable capacity prediction</p>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-center py-12">
                                    <TrendingUp className="w-14 h-14 mx-auto text-white/10 mb-4" />
                                    <p className="text-white/40 mb-2">Click "Run Forecast" to predict capacity breaches</p>
                                    <p className="text-xs text-white/25">Uses statistical regression to forecast CPU, memory, and disk usage</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

const MiniStat = ({ label, value, icon: Icon, color = 'text-white' }) => (
    <div className="text-center">
        <div className="flex items-center gap-1 justify-center">
            <Icon className="h-3.5 w-3.5 text-[#525252]" />
            <span className={`text-lg font-bold font-[JetBrains_Mono] ${color}`}>{value}</span>
        </div>
        <p className="text-[10px] text-[#525252] font-[Barlow_Condensed] uppercase">{label}</p>
    </div>
);

const StatCard = ({ label, value, icon: Icon, color = 'text-white' }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
        <CardContent className="p-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">{label}</p>
                    <p className={`text-2xl font-bold font-[JetBrains_Mono] mt-1 ${color}`}>{value}</p>
                </div>
                <Icon className="h-5 w-5 text-[#525252]" />
            </div>
        </CardContent>
    </Card>
);

const AILayerCard = ({ title, desc, icon: Icon, color, status, action, onAction, loading }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F] hover:border-[#2A2A2A] transition-colors">
        <CardContent className="p-4">
            <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg bg-[#121212] border border-[#1F1F1F]`}>
                    <Icon className={`h-5 w-5 ${color}`} />
                </div>
                <div className="flex-1">
                    <p className="text-sm font-medium text-white">{title}</p>
                    <p className="text-[10px] text-[#525252] mt-1">{desc}</p>
                    <div className="flex items-center justify-between mt-3">
                        <Badge className="text-[10px] bg-[#1F1F1F] text-[#A3A3A3]">{status}</Badge>
                        {action && (
                            <Button size="sm" variant="outline" onClick={onAction} disabled={loading}
                                className="text-[10px] h-6 px-2 border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                                {loading ? <RefreshCw className="h-3 w-3 animate-spin" /> : action}
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        </CardContent>
    </Card>
);

export default AIOPsBrainPage;
