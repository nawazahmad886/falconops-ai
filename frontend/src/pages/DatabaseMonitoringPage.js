import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    Database, Activity, Clock, AlertTriangle, Lock, RefreshCw, Brain, Search,
    Server, Zap, TrendingUp, BarChart3, Eye, ArrowLeft, Code2, Terminal,
    ChevronRight, Gauge, HardDrive, CheckCircle, XCircle, WifiOff, Wifi,
    ArrowUpRight, ArrowDownRight, Shield,
} from 'lucide-react';
import {
    LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer,
} from 'recharts';
import { CustomQueryDashboard } from '../components/CustomQueryDashboard';
import { AgentDeploySection } from '../components/AgentDeploySection';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const useAuth = () => {
    const token = localStorage.getItem('falconToken');
    const headers = { Authorization: `Bearer ${token}` };
    const get = async (url) => {
        const res = await fetch(`${API_URL}${url}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    };
    const post = async (url, body) => {
        const res = await fetch(`${API_URL}${url}`, {
            method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    };
    return { get, post, headers };
};

// ─── Status Badge ───
const StatusBadge = ({ status }) => {
    const cfg = {
        healthy: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Healthy' },
        warning: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Warning' },
        critical: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Critical' },
        active: { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Active' },
    };
    const c = cfg[status] || { cls: 'bg-white/5 text-white/40 border-white/10', label: status || 'Unknown' };
    return <Badge className={`text-[10px] border ${c.cls}`}>{c.label}</Badge>;
};

// ─── Agent Status Indicator ───
const AgentStatus = ({ status }) => {
    const cfg = {
        online: { icon: Wifi, cls: 'text-emerald-400', label: 'Agent Online', dot: 'bg-emerald-400' },
        stale: { icon: Wifi, cls: 'text-amber-400', label: 'Stale', dot: 'bg-amber-400' },
        offline: { icon: WifiOff, cls: 'text-white/30', label: 'Offline', dot: 'bg-white/20' },
    };
    const c = cfg[status] || cfg.offline;
    const Icon = c.icon;
    return (
        <div className="flex items-center gap-1.5" data-testid={`agent-status-${status}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${c.dot} ${status === 'online' ? 'animate-pulse' : ''}`} />
            <Icon className={`w-3 h-3 ${c.cls}`} />
            <span className={`text-[10px] ${c.cls}`}>{c.label}</span>
        </div>
    );
};

// ─── Health Score Ring ───
const HealthRing = ({ score, size = 48 }) => {
    const r = (size - 8) / 2;
    const c = 2 * Math.PI * r;
    const pct = Math.min(100, Math.max(0, score));
    const offset = c - (pct / 100) * c;
    const color = pct >= 80 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444';
    return (
        <svg width={size} height={size} className="transform -rotate-90">
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#1a1a2e" strokeWidth="4" />
            <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="4"
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
                className="transition-all duration-700" />
            <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
                className="fill-white text-[11px] font-bold transform rotate-90" style={{ transformOrigin: 'center' }}>
                {Math.round(pct)}
            </text>
        </svg>
    );
};

// ─── Mini Sparkline ───
const Sparkline = ({ data, color = '#00E0FF', height = 28 }) => {
    if (!data || data.length < 2) return null;
    return (
        <ResponsiveContainer width="100%" height={height}>
            <LineChart data={data}>
                <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} />
            </LineChart>
        </ResponsiveContainer>
    );
};

// ─── KPI Card ───
const KpiCard = ({ label, value, unit, icon: Icon, color = '#00E0FF', trend }) => (
    <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 flex items-center gap-3" data-testid={`kpi-${label.toLowerCase().replace(/\s/g, '-')}`}>
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15` }}>
            <Icon className="w-4 h-4" style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-mono truncate">{label}</p>
            <div className="flex items-baseline gap-1">
                <span className="text-lg font-bold text-white font-mono">{value ?? '-'}</span>
                {unit && <span className="text-[10px] text-slate-500">{unit}</span>}
                {trend && (
                    <span className={`flex items-center text-[10px] ml-1 ${trend > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {trend > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    </span>
                )}
            </div>
        </div>
    </div>
);

// ─── Chart Card ───
const ChartCard = ({ title, data, dataKey = 'value', color = '#00E0FF', unit = '' }) => (
    <Card className="bg-[#121826] border-[#2D3748]/50">
        <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="text-xs text-slate-500 font-mono uppercase tracking-wider">{title}</CardTitle>
        </CardHeader>
        <CardContent className="px-3 pb-3">
            <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id={`g-${title}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={color} stopOpacity={0.2} />
                            <stop offset="100%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <XAxis dataKey="time" tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} width={40} />
                    <Tooltip contentStyle={{ background: '#121826', border: '1px solid #2D3748', borderRadius: 8, fontSize: 11 }}
                        formatter={(v) => [`${typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : v}${unit ? ' ' + unit : ''}`, title]} />
                    <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fill={`url(#g-${title})`} dot={false} />
                </AreaChart>
            </ResponsiveContainer>
        </CardContent>
    </Card>
);


// ═══════════════════════════════════════════════════
//  OVERVIEW PAGE (FLEET VIEW)
// ═══════════════════════════════════════════════════

const FleetOverview = ({ instances, summary, onSelect, loading, onRefresh }) => {
    if (loading) {
        return (
            <div className="flex items-center justify-center py-20" data-testid="db-overview-loading">
                <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6" data-testid="db-fleet-overview">
            {/* Fleet Summary Bar */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" data-testid="page-title">Database Monitoring</h1>
                    <p className="text-sm text-slate-500 mt-0.5">Fleet overview across all monitored instances</p>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onRefresh} className="text-white/50 h-8" data-testid="refresh-overview-btn">
                        <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Summary KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="fleet-summary">
                <KpiCard label="Instances" value={summary.total_instances} icon={Database} color="#00E0FF" />
                <KpiCard label="Active" value={summary.active_instances} icon={CheckCircle} color="#10B981" />
                <KpiCard label="Avg Health" value={summary.avg_health_score} unit="%" icon={Shield} color={summary.avg_health_score >= 80 ? '#10B981' : '#F59E0B'} />
                <KpiCard label="Slow Queries" value={summary.total_slow_queries_1h} unit="1h" icon={Clock} color="#F59E0B" />
                <KpiCard label="Locks" value={summary.total_locks_1h} unit="1h" icon={Lock} color="#EF4444" />
            </div>

            {/* Instance Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="instance-grid">
                {instances.map((inst) => (
                    <Card
                        key={inst.id}
                        className="bg-[#121826] border-[#2D3748]/50 hover:border-cyan-500/30 cursor-pointer transition-all group"
                        onClick={() => onSelect(inst.id)}
                        data-testid={`db-instance-${inst.id}`}
                    >
                        <CardContent className="p-4">
                            {/* Header */}
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3 min-w-0">
                                    <HealthRing score={inst.health_score || 0} size={44} />
                                    <div className="min-w-0">
                                        <h3 className="text-sm font-semibold text-white truncate group-hover:text-cyan-400 transition-colors">{inst.name}</h3>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <Badge className="text-[9px] bg-white/5 text-slate-500 border-0 font-mono">{(inst.db_type || 'postgres').toUpperCase()}</Badge>
                                            <Badge className="text-[9px] bg-white/5 text-slate-500 border-0 font-mono">{inst.environment || 'prod'}</Badge>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex flex-col items-end gap-1.5">
                                    <StatusBadge status={inst.health_score >= 80 ? 'healthy' : inst.health_score >= 60 ? 'warning' : 'critical'} />
                                    <AgentStatus status={inst.agent_status || 'offline'} />
                                </div>
                            </div>

                            {/* Metrics Row */}
                            <div className="grid grid-cols-4 gap-2 py-2 border-t border-[#2D3748]/30">
                                <div className="text-center">
                                    <p className="text-[9px] text-slate-500 font-mono">SESSIONS</p>
                                    <p className="text-sm font-bold text-white font-mono">{inst.current_metrics?.active_sessions ?? '-'}</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-[9px] text-slate-500 font-mono">CACHE %</p>
                                    <p className="text-sm font-bold text-white font-mono">{inst.current_metrics?.cache_hit_ratio ?? '-'}</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-[9px] text-slate-500 font-mono">SLW QRY</p>
                                    <p className={`text-sm font-bold font-mono ${inst.slow_queries_1h > 0 ? 'text-amber-400' : 'text-white'}`}>{inst.slow_queries_1h ?? 0}</p>
                                </div>
                                <div className="text-center">
                                    <p className="text-[9px] text-slate-500 font-mono">LOCKS</p>
                                    <p className={`text-sm font-bold font-mono ${inst.locks_1h > 0 ? 'text-red-400' : 'text-white'}`}>{inst.locks_1h ?? 0}</p>
                                </div>
                            </div>

                            {/* Footer */}
                            <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#2D3748]/30">
                                <span className="text-[10px] text-slate-600 font-mono">
                                    {inst.host || 'localhost'}:{inst.port || '5432'}
                                </span>
                                <div className="flex items-center gap-1.5">
                                    {inst.custom_queries_count > 0 && (
                                        <Badge className="text-[9px] bg-cyan-500/10 text-cyan-400 border-0">{inst.custom_queries_count} queries</Badge>
                                    )}
                                    <ChevronRight className="w-3.5 h-3.5 text-white/20 group-hover:text-cyan-400 transition-colors" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};


// ═══════════════════════════════════════════════════
//  INSTANCE DETAIL VIEW
// ═══════════════════════════════════════════════════

const InstanceDetail = ({ instanceId, onBack }) => {
    const { get, post } = useAuth();
    const [dashboard, setDashboard] = useState(null);
    const [slowQueries, setSlowQueries] = useState([]);
    const [locks, setLocks] = useState([]);
    const [alertRules, setAlertRules] = useState([]);
    const [aiAnalysis, setAiAnalysis] = useState(null);
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);

    const fetchAll = useCallback(async () => {
        try {
            const [dashRes, sqRes, lockRes, ruleRes] = await Promise.all([
                get(`/api/db-monitoring/dashboard/${instanceId}`),
                get(`/api/db-monitoring/slow-queries/${instanceId}?limit=30`),
                get(`/api/db-monitoring/locks/${instanceId}?limit=20`),
                get(`/api/db-monitoring/alert-rules?instance_id=${instanceId}`),
            ]);
            setDashboard(dashRes);
            setSlowQueries(sqRes.slow_queries || []);
            setLocks(lockRes.locks || []);
            setAlertRules(ruleRes.rules || []);
        } catch (e) {
            toast.error('Failed to load instance data');
        } finally {
            setLoading(false);
        }
    }, [instanceId]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const handleAiAnalyze = async () => {
        setAnalyzing(true);
        try {
            const res = await post(`/api/db-monitoring/ai-analyze/${instanceId}`, {});
            setAiAnalysis(res);
            toast.success('AI analysis complete');
        } catch (e) {
            toast.error('AI analysis failed');
        } finally {
            setAnalyzing(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20" data-testid="detail-loading">
                <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            </div>
        );
    }

    const inst = dashboard?.instance || {};
    const metrics = dashboard?.metrics || [];
    const current = inst.current_metrics || (metrics.length > 0 ? metrics[metrics.length - 1]?.metrics : {}) || {};

    // Build chart data from metrics history
    const chartData = metrics.map(m => ({
        time: new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sessions: m.metrics?.active_sessions ?? 0,
        cache: m.metrics?.cache_hit_ratio ?? 0,
        tps: m.metrics?.tps ?? 0,
        connections: m.metrics?.total_connections ?? 0,
        deadlocks: m.metrics?.deadlocks ?? 0,
        size_mb: m.metrics?.database_size_mb ?? 0,
        cpu: m.metrics?.cpu_usage ?? 0,
        memory: m.metrics?.memory_usage ?? 0,
    }));

    // Agent status
    const heartbeat = inst.agent_heartbeat || inst.last_seen || '';
    let agentStatus = 'offline';
    if (heartbeat) {
        try {
            const age = (Date.now() - new Date(heartbeat).getTime()) / 60000;
            agentStatus = age < 5 ? 'online' : age < 30 ? 'stale' : 'offline';
        } catch (e) { /* */ }
    }

    const healthScore = dashboard?.health_score || 0;

    return (
        <div className="space-y-4" data-testid="instance-detail">
            {/* Sticky Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onBack} className="text-white/50 h-8 px-2" data-testid="back-btn">
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <HealthRing score={healthScore} size={40} />
                    <div>
                        <h1 className="text-lg font-bold text-white tracking-tight">{inst.name || 'Instance'}</h1>
                        <div className="flex items-center gap-2">
                            <Badge className="text-[9px] bg-white/5 text-slate-500 border-0 font-mono">{(inst.db_type || 'postgres').toUpperCase()}</Badge>
                            <span className="text-[10px] text-slate-600 font-mono">{inst.host}:{inst.port}</span>
                            <AgentStatus status={agentStatus} />
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={handleAiAnalyze} disabled={analyzing}
                        className="border-purple-500/30 text-purple-400 h-8 text-xs" data-testid="ai-analyze-btn">
                        {analyzing ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Brain className="w-3 h-3 mr-1" />}
                        AI Analyze
                    </Button>
                    <Button size="sm" variant="ghost" onClick={fetchAll} className="text-white/50 h-8" data-testid="refresh-detail-btn">
                        <RefreshCw className="w-3.5 h-3.5" />
                    </Button>
                </div>
            </div>

            {/* KPI Strip */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2" data-testid="kpi-strip">
                <KpiCard label="Sessions" value={current.active_sessions ?? '-'} icon={Activity} color="#00E0FF" />
                <KpiCard label="Connections" value={current.total_connections ?? '-'} icon={Server} color="#8B5CF6" />
                <KpiCard label="Cache Hit" value={current.cache_hit_ratio ?? '-'} unit="%" icon={Zap} color="#10B981" />
                <KpiCard label="TPS" value={current.tps ?? '-'} icon={TrendingUp} color="#F59E0B" />
                <KpiCard label="DB Size" value={current.database_size_mb ? Math.round(current.database_size_mb) : '-'} unit="MB" icon={HardDrive} color="#EC4899" />
                <KpiCard label="Deadlocks" value={current.deadlocks ?? 0} icon={Lock} color="#EF4444" />
                <KpiCard label="Slow Qry" value={slowQueries.length} icon={Clock} color="#F59E0B" />
                <KpiCard label="Repl Lag" value={current.replication_lag_sec ?? '-'} unit="s" icon={Gauge} color="#6366F1" />
            </div>

            {/* Tabs */}
            <Tabs defaultValue="performance" className="w-full">
                <TabsList className="bg-[#121826] border border-[#2D3748]/50 h-9" data-testid="detail-tabs">
                    <TabsTrigger value="performance" className="text-xs data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 h-7 px-3">
                        <BarChart3 className="w-3.5 h-3.5 mr-1.5" /> Performance
                    </TabsTrigger>
                    <TabsTrigger value="queries" className="text-xs data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-400 h-7 px-3">
                        <Clock className="w-3.5 h-3.5 mr-1.5" /> Queries & Locks
                    </TabsTrigger>
                    <TabsTrigger value="custom" className="text-xs data-[state=active]:bg-purple-500/10 data-[state=active]:text-purple-400 h-7 px-3">
                        <Code2 className="w-3.5 h-3.5 mr-1.5" /> Custom Metrics
                    </TabsTrigger>
                    <TabsTrigger value="settings" className="text-xs data-[state=active]:bg-emerald-500/10 data-[state=active]:text-emerald-400 h-7 px-3">
                        <Terminal className="w-3.5 h-3.5 mr-1.5" /> Settings & Agent
                    </TabsTrigger>
                </TabsList>

                {/* ─── PERFORMANCE TAB ─── */}
                <TabsContent value="performance" className="mt-4" data-testid="tab-performance">
                    {chartData.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            <ChartCard title="Active Sessions" data={chartData} dataKey="sessions" color="#00E0FF" />
                            <ChartCard title="Cache Hit Ratio" data={chartData} dataKey="cache" color="#10B981" unit="%" />
                            <ChartCard title="Transactions / sec" data={chartData} dataKey="tps" color="#8B5CF6" />
                            <ChartCard title="Total Connections" data={chartData} dataKey="connections" color="#F59E0B" />
                            <ChartCard title="Deadlocks" data={chartData} dataKey="deadlocks" color="#EF4444" />
                            <ChartCard title="Database Size" data={chartData} dataKey="size_mb" color="#EC4899" unit="MB" />
                        </div>
                    ) : (
                        <Card className="bg-[#121826] border-[#2D3748]/50">
                            <CardContent className="text-center py-16">
                                <BarChart3 className="w-10 h-10 text-white/10 mx-auto mb-3" />
                                <p className="text-sm text-slate-500">No performance data available yet</p>
                                <p className="text-xs text-slate-600 mt-1">Deploy the agent to start collecting metrics</p>
                            </CardContent>
                        </Card>
                    )}

                    {/* AI Analysis Results */}
                    {aiAnalysis && (
                        <Card className="bg-[#121826] border-purple-500/20 mt-4" data-testid="ai-analysis">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-white flex items-center gap-2">
                                    <Brain className="w-4 h-4 text-purple-400" /> AI Analysis
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                                    {aiAnalysis.analysis || aiAnalysis.recommendations || JSON.stringify(aiAnalysis, null, 2)}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* ─── QUERIES & LOCKS TAB ─── */}
                <TabsContent value="queries" className="mt-4 space-y-4" data-testid="tab-queries">
                    {/* Slow Queries */}
                    <Card className="bg-[#121826] border-[#2D3748]/50">
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-sm text-white flex items-center gap-2">
                                    <Clock className="w-4 h-4 text-amber-400" /> Slow Queries
                                    <Badge className="text-[9px] bg-amber-500/10 text-amber-400 border-0">{slowQueries.length}</Badge>
                                </CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {slowQueries.length === 0 ? (
                                <p className="text-center py-8 text-slate-600 text-sm">No slow queries detected</p>
                            ) : (
                                <div className="overflow-x-auto" data-testid="slow-queries-table">
                                    <table className="w-full text-xs font-mono">
                                        <thead>
                                            <tr className="border-b border-[#2D3748]/50 text-slate-500">
                                                <th className="text-left py-2 px-2 font-medium">PID</th>
                                                <th className="text-left py-2 px-2 font-medium">User</th>
                                                <th className="text-right py-2 px-2 font-medium">Duration</th>
                                                <th className="text-left py-2 px-2 font-medium">Query</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {slowQueries.slice(0, 20).map((sq, i) => (
                                                <tr key={sq.id || i} className="border-b border-[#2D3748]/20 hover:bg-white/[0.02]">
                                                    <td className="py-2 px-2 text-slate-400">{sq.pid || '-'}</td>
                                                    <td className="py-2 px-2 text-slate-400">{sq.user || '-'}</td>
                                                    <td className="py-2 px-2 text-right text-amber-400">{sq.duration_ms ? `${(sq.duration_ms / 1000).toFixed(1)}s` : '-'}</td>
                                                    <td className="py-2 px-2 text-slate-300 max-w-md truncate">{sq.query || sq.fingerprint || '-'}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Locks */}
                    <Card className="bg-[#121826] border-[#2D3748]/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Lock className="w-4 h-4 text-red-400" /> Blocking Locks
                                <Badge className="text-[9px] bg-red-500/10 text-red-400 border-0">{locks.length}</Badge>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {locks.length === 0 ? (
                                <p className="text-center py-8 text-slate-600 text-sm">No blocking locks</p>
                            ) : (
                                <div className="overflow-x-auto" data-testid="locks-table">
                                    <table className="w-full text-xs font-mono">
                                        <thead>
                                            <tr className="border-b border-[#2D3748]/50 text-slate-500">
                                                <th className="text-left py-2 px-2">Blocked PID</th>
                                                <th className="text-left py-2 px-2">Blocked User</th>
                                                <th className="text-left py-2 px-2">Blocking PID</th>
                                                <th className="text-right py-2 px-2">Wait Time</th>
                                                <th className="text-left py-2 px-2">Blocked Query</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {locks.map((l, i) => (
                                                <tr key={i} className="border-b border-[#2D3748]/20 hover:bg-white/[0.02]">
                                                    <td className="py-2 px-2 text-red-400">{l.blocked_pid || '-'}</td>
                                                    <td className="py-2 px-2 text-slate-400">{l.blocked_user || '-'}</td>
                                                    <td className="py-2 px-2 text-amber-400">{l.blocking_pid || '-'}</td>
                                                    <td className="py-2 px-2 text-right text-red-300">{l.wait_time_ms ? `${(l.wait_time_ms / 1000).toFixed(1)}s` : '-'}</td>
                                                    <td className="py-2 px-2 text-slate-300 max-w-sm truncate">{l.blocked_query || '-'}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ─── CUSTOM METRICS TAB ─── */}
                <TabsContent value="custom" className="mt-4" data-testid="tab-custom">
                    <CustomQueryDashboard instanceId={instanceId} instanceName={inst.name} />
                </TabsContent>

                {/* ─── SETTINGS & AGENT TAB ─── */}
                <TabsContent value="settings" className="mt-4 space-y-4" data-testid="tab-settings">
                    {/* Agent Deploy */}
                    <AgentDeploySection instanceId={instanceId} instanceName={inst.name} dbType={inst.db_type} />

                    {/* Alert Rules */}
                    <Card className="bg-[#121826] border-[#2D3748]/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4 text-amber-400" /> Alert Rules
                                <Badge className="text-[9px] bg-white/5 text-slate-500 border-0">{alertRules.length} rules</Badge>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {alertRules.length === 0 ? (
                                <p className="text-center py-6 text-slate-600 text-sm">No alert rules configured</p>
                            ) : (
                                <div className="space-y-2">
                                    {alertRules.map((r, i) => (
                                        <div key={r.id || i} className="flex items-center justify-between p-2 bg-white/[0.02] rounded-lg border border-[#2D3748]/30">
                                            <div className="flex items-center gap-2">
                                                <div className={`w-2 h-2 rounded-full ${r.enabled ? 'bg-emerald-400' : 'bg-white/20'}`} />
                                                <span className="text-xs text-white font-mono">{r.metric}</span>
                                                <span className="text-[10px] text-slate-500">{r.operator} {r.threshold}</span>
                                            </div>
                                            <Badge className={`text-[9px] border-0 ${r.severity === 'critical' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>
                                                {r.severity}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};


// ═══════════════════════════════════════════════════
//  MAIN PAGE COMPONENT
// ═══════════════════════════════════════════════════

const DatabaseMonitoringPage = () => {
    const { get } = useAuth();
    const [instances, setInstances] = useState([]);
    const [summary, setSummary] = useState({});
    const [selectedInstance, setSelectedInstance] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchOverview = useCallback(async () => {
        try {
            setLoading(true);
            const data = await get('/api/db-monitoring/dashboard-overview');
            setInstances(data.instances || []);
            setSummary(data.summary || {});
        } catch (e) {
            toast.error('Failed to load database overview');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchOverview(); }, [fetchOverview]);

    if (selectedInstance) {
        return <InstanceDetail instanceId={selectedInstance} onBack={() => setSelectedInstance(null)} />;
    }

    return (
        <FleetOverview
            instances={instances}
            summary={summary}
            onSelect={setSelectedInstance}
            loading={loading}
            onRefresh={fetchOverview}
        />
    );
};

export { DatabaseMonitoringPage };
export default DatabaseMonitoringPage;
