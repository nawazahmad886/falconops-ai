import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import {
    Activity, Database, Server, Cpu, HardDrive, Clock, RefreshCw,
    CheckCircle, AlertTriangle, XCircle, Zap, Layers, Timer,
    MemoryStick, Gauge, Circle, ArrowUpRight, Play, FileWarning,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const STATUS_CONFIG = {
    healthy: { color: '#10B981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', label: 'Healthy', Icon: CheckCircle },
    warning: { color: '#F59E0B', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: 'Degraded', Icon: AlertTriangle },
    critical: { color: '#EF4444', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Critical', Icon: XCircle },
    operational: { color: '#10B981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', label: 'Operational', Icon: CheckCircle },
    degraded: { color: '#F59E0B', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: 'Degraded', Icon: AlertTriangle },
};

// ═══════════════════════════════════════════
//  RESOURCE GAUGE
// ═══════════════════════════════════════════

const ResourceGauge = ({ label, value, total, unit, icon: Icon, color }) => {
    const pct = total ? Math.round((value / total) * 100) : 0;
    const barColor = pct > 85 ? '#EF4444' : pct > 70 ? '#F59E0B' : color || '#10B981';
    return (
        <div className="p-4 bg-white/[0.03] rounded-xl border border-white/5" data-testid={`gauge-${label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-white/50 flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5" style={{ color: barColor }} /> {label}
                </span>
                <span className="text-sm font-semibold text-white">{pct}%</span>
            </div>
            <Progress value={pct} className="h-2 bg-white/5" style={{ '--progress-color': barColor }} />
            <div className="mt-1.5 text-[10px] text-white/30">
                {value} / {total} {unit}
            </div>
        </div>
    );
};

// ═══════════════════════════════════════════
//  SERVICE STATUS ROW
// ═══════════════════════════════════════════

const ServiceRow = ({ svc }) => {
    const cfg = STATUS_CONFIG[svc.status] || STATUS_CONFIG.degraded;
    return (
        <div className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-white/[0.02] transition-colors" data-testid={`service-${svc.name.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="flex items-center gap-3">
                <Circle className="w-2.5 h-2.5 fill-current" style={{ color: cfg.color }} />
                <div>
                    <div className="text-sm text-white">{svc.name}</div>
                    <div className="text-[10px] text-white/30">{svc.description}</div>
                </div>
            </div>
            <div className="flex items-center gap-3">
                <span className="text-xs text-white/40">{svc.documents?.toLocaleString()} docs</span>
                <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${cfg.border}`} style={{ color: cfg.color }}>
                    {cfg.label}
                </Badge>
            </div>
        </div>
    );
};

// ═══════════════════════════════════════════
//  MAIN PAGE
// ═══════════════════════════════════════════

const SelfMonitoringPage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastRefresh, setLastRefresh] = useState(null);

    const fetchHealth = useCallback(async () => {
        try {
            setLoading(true);
            const r = await fetch(`${API_URL}/api/self-monitor/health`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('falconToken')}` },
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const d = await r.json();
            setData(d);
            setError(null);
            setLastRefresh(new Date());
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, 30000);
        return () => clearInterval(interval);
    }, [fetchHealth]);

    if (!data && loading) {
        return (
            <div className="flex items-center justify-center h-[60vh]">
                <RefreshCw className="w-8 h-8 text-white/30 animate-spin" />
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
                <XCircle className="w-12 h-12 text-red-400" />
                <p className="text-white/50">Failed to reach self-monitor endpoint</p>
                <p className="text-xs text-red-400/70">{error}</p>
                <Button variant="outline" onClick={fetchHealth}>Retry</Button>
            </div>
        );
    }

    const s = data;
    const statusCfg = STATUS_CONFIG[s.status] || STATUS_CONFIG.critical;
    const StatusIcon = statusCfg.Icon;
    const sys = s.system || {};
    const proc = s.process || {};
    const mongo = s.mongodb || {};
    const services = s.services || [];
    const jobs = s.background_jobs || [];
    const recentErrors = s.recent_errors || [];
    const operationalCount = services.filter(sv => sv.status === 'operational').length;

    return (
        <div className="space-y-6" data-testid="self-monitoring-page">
            {/* ── Header ── */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Activity className="w-7 h-7 text-[#00E0FF]" />
                        Platform Self-Monitoring
                    </h1>
                    <p className="text-white/40 mt-1 text-sm">
                        Real-time health of FalconOps AI &mdash; auto-refreshes every 30s
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {lastRefresh && (
                        <span className="text-[10px] text-white/25">
                            Last: {lastRefresh.toLocaleTimeString()}
                        </span>
                    )}
                    <Button variant="outline" size="sm" onClick={fetchHealth} disabled={loading}
                        className="border-white/10 text-white/60" data-testid="refresh-health-btn">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* ── Status Banner ── */}
            <Card className={`${statusCfg.bg} ${statusCfg.border} border`} data-testid="platform-status-banner">
                <CardContent className="p-5">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="p-3 rounded-xl" style={{ background: `${statusCfg.color}20` }}>
                                <StatusIcon className="w-8 h-8" style={{ color: statusCfg.color }} />
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h2 className="text-xl font-bold text-white">FalconOps AI</h2>
                                    <Badge className="text-xs px-2" style={{ background: `${statusCfg.color}25`, color: statusCfg.color }}>
                                        {statusCfg.label}
                                    </Badge>
                                </div>
                                <p className="text-sm text-white/40 mt-0.5">
                                    v{s.version} &bull; {operationalCount}/{services.length} services operational
                                </p>
                            </div>
                        </div>
                        <div className="grid grid-cols-3 gap-6 text-center">
                            <div>
                                <div className="text-lg font-bold text-white">{proc.uptime_human || '—'}</div>
                                <div className="text-[10px] text-white/30">API Uptime</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold" style={{ color: mongo.status === 'healthy' ? '#10B981' : '#EF4444' }}>
                                    {mongo.latency_ms >= 0 ? `${mongo.latency_ms}ms` : 'DOWN'}
                                </div>
                                <div className="text-[10px] text-white/30">DB Latency</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold text-[#00E0FF]">{sys.cpu_percent}%</div>
                                <div className="text-[10px] text-white/30">Host CPU</div>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* ── System Resources ── */}
            <div>
                <h3 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
                    <Server className="w-4 h-4 text-white/40" /> System Resources
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <ResourceGauge label="CPU" value={sys.cpu_percent} total={100} unit="%" icon={Cpu} color="#00E0FF" />
                    <ResourceGauge label="Memory" value={sys.memory_used_gb} total={sys.memory_total_gb} unit="GB" icon={MemoryStick} color="#8B5CF6" />
                    <ResourceGauge label="Disk" value={sys.disk_used_gb} total={sys.disk_total_gb} unit="GB" icon={HardDrive} color="#F59E0B" />
                    <div className="p-4 bg-white/[0.03] rounded-xl border border-white/5" data-testid="gauge-load">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-white/50 flex items-center gap-1.5">
                                <Gauge className="w-3.5 h-3.5 text-emerald-400" /> Load Average
                            </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center mt-2">
                            {[['1m', sys.load_avg_1m], ['5m', sys.load_avg_5m], ['15m', sys.load_avg_15m]].map(([l, v]) => (
                                <div key={l}>
                                    <div className="text-sm font-semibold text-white">{v ?? '—'}</div>
                                    <div className="text-[9px] text-white/30">{l}</div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-2 text-[10px] text-white/30">
                            {sys.os} &bull; Python {sys.python_version} &bull; {sys.cpu_count} cores
                        </div>
                    </div>
                </div>
            </div>

            {/* ── MongoDB + Process ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {/* MongoDB Health */}
                <Card className="bg-[#0a0a0a] border-white/10" data-testid="mongo-health-card">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-white text-base flex items-center gap-2">
                            <Database className="w-4 h-4 text-emerald-400" /> MongoDB
                            <Badge variant="outline" className={`text-[10px] ml-auto ${mongo.status === 'healthy' ? 'border-emerald-500/30 text-emerald-400' : 'border-red-500/30 text-red-400'}`}>
                                {mongo.status === 'healthy' ? 'Connected' : 'Down'}
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                            {[
                                { l: 'Ping Latency', v: `${mongo.latency_ms}ms`, c: '#10B981' },
                                { l: 'Collections', v: mongo.total_collections, c: '#00E0FF' },
                                { l: 'Total Documents', v: mongo.total_documents?.toLocaleString(), c: '#F5B841' },
                                { l: 'Data Size', v: `${mongo.data_size_mb} MB`, c: '#8B5CF6' },
                                { l: 'Storage', v: `${mongo.storage_size_mb} MB`, c: '#F59E0B' },
                                { l: 'Index Size', v: `${mongo.index_size_mb} MB`, c: '#EC4899' },
                            ].map(x => (
                                <div key={x.l} className="p-2.5 bg-white/[0.03] rounded-lg">
                                    <div className="text-[10px] text-white/30">{x.l}</div>
                                    <div className="text-sm font-semibold" style={{ color: x.c }}>{x.v ?? '—'}</div>
                                </div>
                            ))}
                        </div>
                        {mongo.collection_counts && Object.keys(mongo.collection_counts).length > 0 && (
                            <div className="pt-2 border-t border-white/5">
                                <div className="text-[10px] text-white/30 mb-2 uppercase tracking-wider">Key Collections</div>
                                <div className="grid grid-cols-2 gap-1">
                                    {Object.entries(mongo.collection_counts).map(([col, cnt]) => (
                                        <div key={col} className="flex items-center justify-between text-xs py-1 px-2 rounded bg-white/[0.02]">
                                            <span className="text-white/50">{col}</span>
                                            <span className="text-white/70 font-mono">{cnt.toLocaleString()}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Backend Process */}
                <Card className="bg-[#0a0a0a] border-white/10" data-testid="process-health-card">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-white text-base flex items-center gap-2">
                            <Zap className="w-4 h-4 text-[#00E0FF]" /> Backend Process
                            <Badge variant="outline" className="text-[10px] ml-auto border-emerald-500/30 text-emerald-400">
                                PID {proc.pid}
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                            {[
                                { l: 'Uptime', v: proc.uptime_human, c: '#10B981', icon: Clock },
                                { l: 'RSS Memory', v: `${proc.memory_rss_mb} MB`, c: '#8B5CF6', icon: MemoryStick },
                                { l: 'VMS Memory', v: `${proc.memory_vms_mb} MB`, c: '#00E0FF', icon: Layers },
                                { l: 'CPU Usage', v: `${proc.cpu_percent}%`, c: '#F59E0B', icon: Cpu },
                                { l: 'Threads', v: proc.threads, c: '#EC4899', icon: Layers },
                                { l: 'Started', v: proc.started_at ? new Date(proc.started_at).toLocaleTimeString() : '—', c: '#F5B841', icon: Play },
                            ].map(x => (
                                <div key={x.l} className="p-2.5 bg-white/[0.03] rounded-lg flex items-center gap-2.5">
                                    <x.icon className="w-3.5 h-3.5 shrink-0" style={{ color: x.c }} />
                                    <div>
                                        <div className="text-[10px] text-white/30">{x.l}</div>
                                        <div className="text-sm font-semibold text-white">{x.v ?? '—'}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* ── Services Status ── */}
            <Card className="bg-[#0a0a0a] border-white/10" data-testid="services-status-card">
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-white text-base flex items-center gap-2">
                            <Layers className="w-4 h-4 text-[#F5B841]" /> Service Status
                        </CardTitle>
                        <div className="flex items-center gap-2 text-xs text-white/40">
                            <span className="flex items-center gap-1"><Circle className="w-2 h-2 fill-emerald-500 text-emerald-500" /> Operational</span>
                            <span className="flex items-center gap-1"><Circle className="w-2 h-2 fill-amber-500 text-amber-500" /> Degraded</span>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-0.5">
                        {services.map(svc => <ServiceRow key={svc.name} svc={svc} />)}
                    </div>
                </CardContent>
            </Card>

            {/* ── Background Jobs + Recent Errors ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {/* Jobs */}
                <Card className="bg-[#0a0a0a] border-white/10" data-testid="jobs-card">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-white text-base flex items-center gap-2">
                            <Timer className="w-4 h-4 text-emerald-400" /> Background Jobs
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {jobs.length === 0 ? (
                            <p className="text-sm text-white/30 text-center py-6">No active jobs</p>
                        ) : (
                            <div className="space-y-2">
                                {jobs.map(job => (
                                    <div key={job.id} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
                                        <div className="flex items-center gap-2.5">
                                            <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />
                                            <div>
                                                <div className="text-sm text-white">{job.name}</div>
                                                <div className="text-[10px] text-white/30">{job.frequency}</div>
                                            </div>
                                        </div>
                                        <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400">
                                            {job.status}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Recent Errors */}
                <Card className="bg-[#0a0a0a] border-white/10" data-testid="errors-card">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-white text-base flex items-center gap-2">
                            <FileWarning className="w-4 h-4 text-red-400" /> Recent Errors
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {recentErrors.length === 0 ? (
                            <div className="text-center py-8">
                                <CheckCircle className="w-10 h-10 text-emerald-500/30 mx-auto mb-2" />
                                <p className="text-sm text-white/30">No recent errors</p>
                                <p className="text-[10px] text-white/20 mt-1">System is operating normally</p>
                            </div>
                        ) : (
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                {recentErrors.map((err, i) => (
                                    <div key={i} className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/10">
                                        <div className="text-xs text-red-400">{err.message || err.error || 'Unknown error'}</div>
                                        <div className="text-[10px] text-white/20 mt-1">
                                            {err.timestamp ? new Date(err.timestamp).toLocaleString() : ''}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default SelfMonitoringPage;
