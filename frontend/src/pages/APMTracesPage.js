import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    Activity, AlertTriangle, Clock, CheckCircle2, XCircle, ChevronRight, ChevronDown,
    Layers, RefreshCw, Search, Network, Zap, Server, ArrowRight, Cpu, Hourglass,
    Brain, Bell, Sparkles, FileSearch,
} from 'lucide-react';
import TraceAlertRulesTab from './TraceAlertRulesTab';
import AIOpsDiagnosePanel from '../components/AIOpsDiagnosePanel';
import ForceServiceMap from '../components/ForceServiceMap';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const RANGES = [
    { label: '15m', hours: 0.25 },
    { label: '1h', hours: 1 },
    { label: '6h', hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d', hours: 168 },
    { label: '30d', hours: 720 },
];

const SERVICE_COLORS = [
    'bg-cyan-500', 'bg-emerald-500', 'bg-violet-500', 'bg-amber-500',
    'bg-rose-500', 'bg-blue-500', 'bg-fuchsia-500', 'bg-orange-500',
    'bg-teal-500', 'bg-pink-500',
];

const colorForService = (service, services) => {
    const idx = services.indexOf(service);
    return SERVICE_COLORS[idx % SERVICE_COLORS.length] || 'bg-zinc-500';
};

// ───────── Stat Tile ─────────
const StatTile = ({ icon: Icon, label, value, sub, accent, testid }) => (
    <Card className="bg-black/40 border-white/10" data-testid={testid}>
        <CardContent className="p-5">
            <div className="flex items-start gap-3">
                <div className={`p-2.5 rounded-lg ${accent}/10 border ${accent}/20`}>
                    <Icon className={`w-5 h-5 ${accent.replace('border-', 'text-').replace('/30', '-400')}`} />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="text-[10px] uppercase tracking-widest text-white/50">{label}</div>
                    <div className="mt-1 text-2xl font-semibold text-white tabular-nums">{value}</div>
                    {sub && <div className="text-[11px] text-white/40 mt-0.5">{sub}</div>}
                </div>
            </div>
        </CardContent>
    </Card>
);

// ───────── Waterfall span ─────────
const SpanBar = ({ span, depth, traceStart, traceDur, services, expanded, onToggle, hasChildren }) => {
    const start = new Date(span.start_time).getTime();
    const dur = Math.max(span.duration_ms || 1, 1);
    const offsetPct = traceDur > 0 ? Math.max(0, ((start - traceStart) / traceDur) * 100) : 0;
    const widthPct = traceDur > 0 ? Math.min(100 - offsetPct, (dur / traceDur) * 100) : 100;
    const color = colorForService(span.service, services);
    const isError = span.status === 'ERROR';

    return (
        <div
            className={`group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/[0.03] ${isError ? 'bg-red-500/[0.04]' : ''}`}
            data-testid={`span-row-${span.span_id}`}
        >
            <div className="flex items-center gap-1 shrink-0" style={{ paddingLeft: depth * 16 }}>
                {hasChildren ? (
                    <button onClick={onToggle} className="text-white/40 hover:text-white/80" data-testid={`toggle-${span.span_id}`}>
                        {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                ) : (
                    <span className="w-3.5" />
                )}
            </div>
            <div className="w-44 min-w-0 shrink-0">
                <div className="flex items-center gap-1.5 truncate">
                    <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
                    <span className="text-[11px] text-white/85 truncate">{span.service}</span>
                </div>
                <div className="text-[10px] text-white/40 truncate font-mono">{span.operation}</div>
            </div>
            <div className="flex-1 min-w-0 relative h-6 bg-white/[0.02] rounded">
                <div
                    className={`absolute top-0 bottom-0 ${color} ${isError ? 'opacity-90' : 'opacity-70'} rounded`}
                    style={{ left: `${offsetPct}%`, width: `${Math.max(widthPct, 0.5)}%` }}
                    title={`${span.duration_ms?.toFixed(1)}ms`}
                />
                <div className="absolute inset-0 flex items-center px-2">
                    <span className="text-[10px] text-white/80 font-mono tabular-nums">{(span.duration_ms || 0).toFixed(1)}ms</span>
                </div>
            </div>
            <div className="w-14 shrink-0 text-right">
                {isError ? (
                    <Badge className="text-[9px] bg-red-500/15 text-red-400 border border-red-500/30">ERR</Badge>
                ) : (
                    <Badge className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">OK</Badge>
                )}
            </div>
        </div>
    );
};

const SpanTree = ({ nodes, depth, traceStart, traceDur, services, expandedIds, onToggle }) => {
    // Flatten the tree iteratively so we avoid recursive JSX self-reference
    const rows = [];
    const walk = (list, currentDepth) => {
        for (const n of list) {
            const expanded = expandedIds[n.span_id] !== false;
            const hasChildren = !!(n.children && n.children.length > 0);
            rows.push({ span: n, depth: currentDepth, expanded, hasChildren });
            if (expanded && hasChildren) walk(n.children, currentDepth + 1);
        }
    };
    walk(nodes, depth);

    return (
        <div className="space-y-0.5">
            {rows.map(({ span, depth: d, expanded, hasChildren }) => (
                <SpanBar
                    key={span.span_id}
                    span={span}
                    depth={d}
                    traceStart={traceStart}
                    traceDur={traceDur}
                    services={services}
                    expanded={expanded}
                    hasChildren={hasChildren}
                    onToggle={() => onToggle(span.span_id)}
                />
            ))}
        </div>
    );
};

// ───────── Trace Detail Panel ─────────
// ───────── Trace Detail (with RCA + Diagnose CTA) ─────────
const TraceDetail = ({ trace, onClose, onDiagnose }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [expandedIds, setExpandedIds] = useState({});
    const [rca, setRca] = useState(null);
    const [rcaLoading, setRcaLoading] = useState(false);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        setRca(null);
        fetch(`${API}/api/traces/${trace.trace_id}`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [trace.trace_id]);

    const runRca = async () => {
        setRcaLoading(true);
        try {
            const r = await fetch(`${API}/api/traces/${trace.trace_id}/rca`, {
                method: 'POST', headers: authHeaders(),
            });
            if (!r.ok) {
                const txt = await r.text();
                throw new Error(`${r.status} ${txt}`);
            }
            const d = await r.json();
            setRca(d);
            toast.success(`AI RCA generated (${d.summary?.provider || 'rule-based'})`);
        } catch (e) {
            toast.error(`RCA failed: ${e.message}`);
        } finally {
            setRcaLoading(false);
        }
    };

    const traceStart = useMemo(() => data ? new Date(data.trace.start_time).getTime() : 0, [data]);
    const traceDur = useMemo(() => data ? Math.max(data.trace.duration_ms || 1, 1) : 1, [data]);
    const services = useMemo(() => data ? data.trace.services || [] : [], [data]);

    const toggle = (id) => setExpandedIds((s) => ({ ...s, [id]: !(s[id] !== false) }));

    if (loading) {
        return (
            <Card className="bg-black/60 border-white/10" data-testid="trace-detail-loading">
                <CardContent className="p-8 flex items-center justify-center">
                    <RefreshCw className="w-5 h-5 text-white/40 animate-spin" />
                </CardContent>
            </Card>
        );
    }
    if (!data) return null;

    const t = data.trace;
    return (
        <Card className="bg-black/60 border-white/10" data-testid="trace-detail-panel">
            <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-base font-semibold text-white truncate">{t.root_operation}</span>
                            <Badge className={`text-[10px] ${t.status === 'ERROR' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'} border`}>
                                {t.status}
                            </Badge>
                            <span className="text-[11px] text-white/40 font-mono truncate">{t.trace_id}</span>
                        </div>
                        <div className="text-[11px] text-white/50 mt-1">
                            {t.root_service} · {t.span_count} spans · {(t.duration_ms || 0).toFixed(1)} ms total
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onDiagnose && onDiagnose(t.root_service)}
                            className="bg-violet-500/[0.08] border-violet-500/30 text-violet-200 hover:bg-violet-500/[0.16]"
                            data-testid="diagnose-service-btn"
                        >
                            <Brain className="w-4 h-4 mr-1.5" />
                            Diagnose {t.root_service}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={runRca}
                            disabled={rcaLoading}
                            className="bg-violet-500/[0.08] border-violet-500/30 text-violet-200 hover:bg-violet-500/[0.16]"
                            data-testid="run-rca-btn"
                        >
                            {rcaLoading ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Brain className="w-4 h-4 mr-1.5" />}
                            AI RCA
                        </Button>
                        <Button variant="ghost" size="sm" onClick={onClose} data-testid="close-trace-detail">
                            <XCircle className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {rca && (
                    <div className="mb-3 p-3 rounded-lg border border-violet-500/30 bg-violet-500/[0.05]" data-testid="rca-panel">
                        <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="w-3.5 h-3.5 text-violet-300" />
                            <span className="text-[11px] uppercase tracking-widest text-violet-200/90 font-semibold">
                                AI Root Cause Analysis
                            </span>
                            {rca.summary?.provider && (
                                <Badge className="text-[9px] bg-violet-500/15 text-violet-200 border border-violet-500/30">
                                    {rca.summary.provider}{rca.summary.model ? ` · ${rca.summary.model}` : ''}
                                </Badge>
                            )}
                        </div>
                        <pre className="text-[11px] text-white/85 whitespace-pre-wrap break-words font-sans leading-relaxed" data-testid="rca-text">
                            {rca.summary?.text || 'No analysis available'}
                        </pre>
                        <div className="flex items-center gap-3 mt-3 flex-wrap text-[10px] text-white/50">
                            <span>{rca.slow_spans?.length || 0} slow span(s)</span>
                            <span>·</span>
                            <span>{rca.error_chains?.length || 0} error chain(s)</span>
                            <span>·</span>
                            <span>{rca.hotspots?.length || 0} hotspot(s)</span>
                        </div>
                    </div>
                )}

                <div className="flex items-center gap-2 flex-wrap mb-3">
                    {services.map((s) => (
                        <Badge key={s} className={`text-[10px] ${colorForService(s, services)}/15 text-white/85 border border-white/10`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${colorForService(s, services)} mr-1.5`} />
                            {s}
                        </Badge>
                    ))}
                </div>

                <div className="rounded-lg border border-white/10 bg-black/40 p-2 max-h-[55vh] overflow-y-auto" data-testid="span-waterfall">
                    <div className="flex items-center gap-2 px-2 py-1 text-[10px] uppercase tracking-widest text-white/40 border-b border-white/5 mb-1">
                        <span className="w-3.5 shrink-0" />
                        <span className="w-44 shrink-0">Service / Operation</span>
                        <span className="flex-1">Timeline ({t.duration_ms ? t.duration_ms.toFixed(0) : 0} ms)</span>
                        <span className="w-14 text-right">Status</span>
                    </div>
                    <SpanTree
                        nodes={data.tree || []}
                        depth={0}
                        traceStart={traceStart}
                        traceDur={traceDur}
                        services={services}
                        expandedIds={expandedIds}
                        onToggle={toggle}
                    />
                </div>
            </CardContent>
        </Card>
    );
};

// ───────── Service Dependency Map (D3 force-directed) ─────────
const ServiceMap = ({ hours, onDiagnose }) => {
    const [graph, setGraph] = useState({ nodes: [], edges: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        // Backend caps `/api/traces/services/dependencies` at hours<=168 (7d) — clamp here.
        const clampedHours = Math.min(168, Math.max(1, Math.ceil(hours)));
        fetch(`${API}/api/traces/services/dependencies?hours=${clampedHours}`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setGraph(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [hours]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-10">
                <RefreshCw className="w-5 h-5 text-white/40 animate-spin" />
            </div>
        );
    }

    if (!graph.edges?.length && !graph.nodes?.length) {
        return (
            <div className="text-center py-10 text-white/40 text-sm" data-testid="service-map-empty">
                <Network className="w-8 h-8 mx-auto mb-2 opacity-40" />
                No service dependencies observed yet. Send traces to <code className="text-white/60">/api/otel/v1/traces</code>.
            </div>
        );
    }

    return (
        <div data-testid="service-map-graph">
            <ForceServiceMap
                nodes={graph.nodes || []}
                edges={graph.edges || []}
                height={480}
                onNodeClick={onDiagnose}
            />
        </div>
    );
};

// ───────── Service Correlation Panel (node click drill-down) ─────────
// Shows the clicked service's own latency/error%, its real upstream/downstream
// dependencies, and recent traces through it — picking one of those traces reuses the
// existing TraceDetail component to render the actual source→...→destination span
// waterfall through the backend.
const ServiceCorrelationPanel = ({ service, hours, onClose, onDiagnose, onSelectTrace }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        const clampedHours = Math.min(168, Math.max(1, Math.ceil(hours)));
        fetch(`${API}/api/traces/services/${encodeURIComponent(service)}/correlation?hours=${clampedHours}`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [service, hours]);

    if (loading) {
        return (
            <Card className="bg-black/60 border-white/10" data-testid="correlation-loading">
                <CardContent className="p-8 flex items-center justify-center">
                    <RefreshCw className="w-5 h-5 text-white/40 animate-spin" />
                </CardContent>
            </Card>
        );
    }
    if (!data) return null;

    const m = data.node_metrics || {};
    const isHighError = (m.error_rate_pct || 0) > 5;

    return (
        <Card className="bg-black/60 border-white/10" data-testid="correlation-panel">
            <CardContent className="p-5 space-y-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Server className="w-4 h-4 text-cyan-400 shrink-0" />
                            <span className="text-base font-semibold text-white truncate">{data.service}</span>
                            <Badge className={`text-[10px] border ${isHighError ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}`}>
                                {m.error_rate_pct ?? 0}% error rate
                            </Badge>
                        </div>
                        <div className="text-[11px] text-white/50 mt-1">
                            {m.call_count ?? 0} spans · {Math.round(m.avg_latency_ms || 0)}ms avg · p95 {Math.round(m.p95_latency_ms || 0)}ms
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <Link to={`/apm/services/${encodeURIComponent(data.service)}`} data-testid="view-service-page-link">
                            <Button variant="outline" size="sm" className="text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/10">
                                View full page
                            </Button>
                        </Link>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onDiagnose(data.service)}
                            className="bg-violet-500/[0.08] border-violet-500/30 text-violet-200 hover:bg-violet-500/[0.16]"
                            data-testid="correlation-diagnose-btn"
                        >
                            <Brain className="w-4 h-4 mr-1.5" />
                            Diagnose
                        </Button>
                        <Button variant="ghost" size="sm" onClick={onClose} data-testid="close-correlation-panel">
                            <XCircle className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5">
                            Upstream · calls into {data.service}
                        </div>
                        <div className="space-y-1">
                            {(data.upstream || []).length === 0 && (
                                <div className="text-[11px] text-white/30">None observed</div>
                            )}
                            {(data.upstream || []).map((e, i) => (
                                <div key={i} className="flex items-center gap-1.5 text-[11px] text-white/70 p-1.5 rounded bg-white/[0.02]">
                                    <span className="truncate">{e.service}</span>
                                    <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                                    <span className="text-white/50 truncate">{data.service}</span>
                                    {e.error_count > 0 && (
                                        <Badge className="ml-auto text-[9px] bg-red-500/15 text-red-400 border-red-500/30 shrink-0">
                                            {e.error_count} err
                                        </Badge>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5">
                            Downstream · {data.service} calls
                        </div>
                        <div className="space-y-1">
                            {(data.downstream || []).length === 0 && (
                                <div className="text-[11px] text-white/30">None observed</div>
                            )}
                            {(data.downstream || []).map((e, i) => (
                                <div key={i} className="flex items-center gap-1.5 text-[11px] text-white/70 p-1.5 rounded bg-white/[0.02]">
                                    <span className="text-white/50 truncate">{data.service}</span>
                                    <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                                    <span className="truncate">{e.depends_on}</span>
                                    {e.error_count > 0 && (
                                        <Badge className="ml-auto text-[9px] bg-red-500/15 text-red-400 border-red-500/30 shrink-0">
                                            {e.error_count} err
                                        </Badge>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div>
                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5">
                        Recent traces through {data.service} ({(data.recent_traces || []).length})
                    </div>
                    <div className="space-y-1 max-h-[240px] overflow-y-auto pr-1">
                        {(data.recent_traces || []).length === 0 && (
                            <div className="text-[11px] text-white/30">No traces in this window.</div>
                        )}
                        {(data.recent_traces || []).map((t) => (
                            <button
                                key={t.trace_id}
                                onClick={() => onSelectTrace(t)}
                                className="w-full text-left flex items-center gap-2 text-[11px] p-2 rounded bg-black/30 border border-white/5 hover:border-cyan-500/30 hover:bg-white/[0.03]"
                                data-testid={`correlation-trace-${t.trace_id}`}
                            >
                                {t.status === 'ERROR' ? (
                                    <XCircle className="w-3 h-3 text-red-400 shrink-0" />
                                ) : (
                                    <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                                )}
                                <span className="truncate flex-1">{t.root_service} → {t.root_operation}</span>
                                <span className="text-white/40 tabular-nums shrink-0">{(t.duration_ms || 0).toFixed(0)}ms</span>
                            </button>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

// ───────── Main Page ─────────
export default function APMTracesPage() {
    const [stats, setStats] = useState({});
    const [traces, setTraces] = useState([]);
    const [services, setServices] = useState([]);
    const [hours, setHours] = useState(24);
    const [serviceFilter, setServiceFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [selectedTrace, setSelectedTrace] = useState(null);
    const [diagnoseService, setDiagnoseService] = useState(null);
    const [loading, setLoading] = useState(true);
    const [mapSelectedService, setMapSelectedService] = useState(null);
    const [anomalyReport, setAnomalyReport] = useState(null);
    const [anomalyBusy, setAnomalyBusy] = useState(false);

    const runAnomalyReport = async () => {
        setAnomalyBusy(true);
        try {
            const r = await fetch(`${API}/api/traces/anomalies/report?hours=${Math.max(1, Math.ceil(hours))}`, {
                headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            const d = await r.json();
            setAnomalyReport(d);
            toast.success(`Anomaly report ready (${d.summary?.provider || 'rule-based'})`);
        } catch (e) {
            toast.error(`Bulk RCA failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setAnomalyBusy(false);
        }
    };

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.set('hours', Math.max(1, Math.ceil(hours)));
            if (serviceFilter !== 'all') params.set('service', serviceFilter);
            if (statusFilter !== 'all') params.set('status', statusFilter);

            const [statsR, tracesR, svcR] = await Promise.all([
                fetch(`${API}/api/traces/stats/summary?hours=${Math.max(1, Math.ceil(hours))}`, { headers: authHeaders() }),
                fetch(`${API}/api/traces?${params.toString()}`, { headers: authHeaders() }),
                fetch(`${API}/api/traces/services/list`, { headers: authHeaders() }),
            ]);
            const [statsD, tracesD, svcD] = await Promise.all([statsR.json(), tracesR.json(), svcR.json()]);
            setStats(statsD || {});
            setTraces(tracesD.traces || []);
            setServices(svcD.services || []);
        } catch (e) {
            toast.error('Failed to load traces');
        } finally {
            setLoading(false);
        }
    }, [hours, serviceFilter, statusFilter]);

    useEffect(() => { reload(); }, [reload]);

    const filteredTraces = useMemo(() => {
        if (!search.trim()) return traces;
        const q = search.toLowerCase();
        return traces.filter((t) =>
            (t.trace_id || '').toLowerCase().includes(q) ||
            (t.root_service || '').toLowerCase().includes(q) ||
            (t.root_operation || '').toLowerCase().includes(q)
        );
    }, [search, traces]);

    return (
        <div className="p-6 space-y-5" data-testid="apm-traces-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Cpu className="w-6 h-6 text-cyan-400" />
                        APM Traces
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        OpenTelemetry distributed tracing · ingest at <code className="text-white/70">/api/otel/v1/traces</code>
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={runAnomalyReport} disabled={anomalyBusy}
                        className="bg-violet-500/[0.08] border-violet-500/30 text-violet-200 hover:bg-violet-500/[0.16]"
                        data-testid="bulk-rca-btn">
                        {anomalyBusy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <FileSearch className="w-4 h-4 mr-1.5" />}
                        Anomaly Report
                    </Button>
                    <Button variant="outline" size="sm" onClick={reload} disabled={loading} data-testid="refresh-traces">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            <Tabs defaultValue="traces" data-testid="apm-tabs">
                <TabsList className="bg-black/40 border border-white/10">
                    <TabsTrigger value="traces" data-testid="tab-traces"><Layers className="w-3.5 h-3.5 mr-1.5" /> Traces</TabsTrigger>
                    <TabsTrigger value="servicemap" data-testid="tab-servicemap"><Network className="w-3.5 h-3.5 mr-1.5" /> Service Map</TabsTrigger>
                    <TabsTrigger value="alerts" data-testid="tab-alerts"><Bell className="w-3.5 h-3.5 mr-1.5" /> Alert Rules</TabsTrigger>
                </TabsList>

                <TabsContent value="traces" className="space-y-5 mt-5">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <StatTile testid="stat-total-traces" icon={Activity} label="Total Traces" value={stats.total ?? 0} accent="border-cyan-500" />
                <StatTile testid="stat-error-rate" icon={AlertTriangle} label="Error Rate" value={`${stats.error_rate_pct ?? 0}%`} sub={`${stats.errors ?? 0} errors`} accent="border-red-500" />
                <StatTile testid="stat-avg-duration" icon={Clock} label="Avg Duration" value={`${(stats.avg_duration ?? 0).toFixed(1)}ms`} accent="border-amber-500" />
                <StatTile testid="stat-max-duration" icon={Hourglass} label="Max Duration" value={`${(stats.max_duration ?? 0).toFixed(1)}ms`} accent="border-violet-500" />
                <StatTile testid="stat-services" icon={Server} label="Services" value={stats.services_count ?? 0} sub={`${stats.total_spans ?? 0} spans`} accent="border-emerald-500" />
            </div>

            {/* Anomaly Report (bulk AI RCA) */}
            {anomalyReport && (
                <Card className="bg-gradient-to-br from-violet-500/[0.06] via-black/40 to-black/40 border-violet-500/30" data-testid="anomaly-report-panel">
                    <CardContent className="p-5 space-y-3">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Sparkles className="w-4 h-4 text-violet-300" />
                            <span className="text-xs uppercase tracking-widest text-violet-200/90 font-semibold">
                                AI Anomaly Report · last {anomalyReport.hours}h
                            </span>
                            {anomalyReport.summary?.provider && (
                                <Badge className="text-[10px] bg-violet-500/15 text-violet-200 border border-violet-500/30">
                                    {anomalyReport.summary.provider}{anomalyReport.summary.model ? ` · ${anomalyReport.summary.model}` : ''}
                                </Badge>
                            )}
                            <div className="flex-1" />
                            <Button variant="ghost" size="sm" onClick={() => setAnomalyReport(null)} data-testid="close-anomaly-report">
                                <XCircle className="w-4 h-4" />
                            </Button>
                        </div>
                        <div className="flex items-center gap-3 flex-wrap text-[11px]">
                            <Badge className="bg-white/5 text-white/80 border border-white/10">
                                {anomalyReport.totals.traces} traces · {anomalyReport.totals.error_traces} errors ({anomalyReport.totals.error_rate_pct}%)
                            </Badge>
                            <Badge className="bg-white/5 text-white/80 border border-white/10">
                                p95 {anomalyReport.totals.p95_duration_ms}ms
                            </Badge>
                            <Badge className="bg-white/5 text-white/80 border border-white/10">
                                {anomalyReport.totals.services} services
                            </Badge>
                        </div>
                        <pre className="text-[12px] text-white/85 whitespace-pre-wrap break-words font-sans leading-relaxed" data-testid="anomaly-summary">
                            {anomalyReport.summary?.text || 'No summary available'}
                        </pre>
                        {anomalyReport.anomalies?.length > 0 && (
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5 mt-1">
                                    Top anomalous (service, operation) groups
                                </div>
                                <div className="space-y-1">
                                    {anomalyReport.anomalies.slice(0, 5).map((a, i) => (
                                        <div key={i} className="flex items-center gap-2 text-[11px] p-2 rounded bg-black/40 border border-white/5"
                                            data-testid={`anomaly-row-${i}`}>
                                            <code className="text-cyan-200">{a.service}.{a.operation}</code>
                                            <span className="flex-1" />
                                            {a.error_rate_pct > 0 && (
                                                <Badge className="text-[9px] bg-red-500/15 text-red-300 border border-red-500/30">
                                                    {a.error_rate_pct}% errors
                                                </Badge>
                                            )}
                                            <span className="text-white/60 tabular-nums">p95 {a.p95_duration_ms}ms</span>
                                            <span className="text-white/40">{a.samples} spans</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* AIOps Diagnose Panel (renders when user clicks Diagnose anywhere) */}
            {diagnoseService && (
                <AIOpsDiagnosePanel
                    service={diagnoseService}
                    hours={Math.max(1, Math.ceil(hours))}
                    onClose={() => setDiagnoseService(null)}
                />
            )}

            {/* Filters */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-4">
                    <div className="flex items-center gap-2 flex-wrap">
                        <div className="flex items-center gap-1 bg-black/40 rounded-lg border border-white/10 p-0.5">
                            {RANGES.map((r) => (
                                <button
                                    key={r.label}
                                    onClick={() => setHours(r.hours)}
                                    className={`px-2.5 py-1 text-[11px] rounded ${hours === r.hours ? 'bg-cyan-500/20 text-cyan-300' : 'text-white/60 hover:text-white/90'}`}
                                    data-testid={`range-${r.label}`}
                                >
                                    {r.label}
                                </button>
                            ))}
                        </div>
                        <Select value={serviceFilter} onValueChange={setServiceFilter}>
                            <SelectTrigger className="w-[180px] bg-black/40 border-white/10" data-testid="service-filter">
                                <SelectValue placeholder="All services" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All services</SelectItem>
                                {services.map((s) => (<SelectItem key={s} value={s}>{s}</SelectItem>))}
                            </SelectContent>
                        </Select>
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="w-[140px] bg-black/40 border-white/10" data-testid="status-filter">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All statuses</SelectItem>
                                <SelectItem value="OK">OK only</SelectItem>
                                <SelectItem value="ERROR">Errors only</SelectItem>
                            </SelectContent>
                        </Select>
                        <div className="relative flex-1 min-w-[200px]">
                            <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40" />
                            <Input
                                placeholder="Search trace_id, service, operation…"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="pl-8 bg-black/40 border-white/10"
                                data-testid="trace-search"
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* List + Detail */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="bg-black/40 border-white/10" data-testid="trace-list-card">
                    <CardContent className="p-3">
                        <div className="text-xs uppercase tracking-widest text-white/50 px-2 pt-1 pb-2 flex items-center justify-between">
                            <span><Layers className="w-3.5 h-3.5 inline mr-1.5" /> Traces ({filteredTraces.length})</span>
                            {loading && <RefreshCw className="w-3 h-3 animate-spin text-white/40" />}
                        </div>
                        <ScrollArea className="h-[60vh]">
                            <div className="space-y-1.5 pr-2">
                                {filteredTraces.length === 0 && !loading && (
                                    <div className="text-center py-10 text-white/40 text-sm" data-testid="no-traces">
                                        <Zap className="w-8 h-8 mx-auto mb-2 opacity-40" />
                                        No traces in this range. Try a wider time window or send some via OTLP.
                                    </div>
                                )}
                                {filteredTraces.map((t) => {
                                    const isSel = selectedTrace?.trace_id === t.trace_id;
                                    const isErr = t.status === 'ERROR';
                                    return (
                                        <button
                                            key={t.trace_id}
                                            onClick={() => setSelectedTrace(t)}
                                            className={`w-full text-left p-3 rounded-lg border transition-colors ${
                                                isSel
                                                    ? 'border-cyan-500/40 bg-cyan-500/[0.05]'
                                                    : 'border-white/5 bg-black/30 hover:bg-white/[0.03] hover:border-white/10'
                                            }`}
                                            data-testid={`trace-row-${t.trace_id}`}
                                        >
                                            <div className="flex items-center gap-2 flex-wrap mb-1">
                                                {isErr ? (
                                                    <XCircle className="w-3.5 h-3.5 text-red-400" />
                                                ) : (
                                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                                )}
                                                <span className="text-sm text-white font-medium truncate flex-1">
                                                    {t.root_operation}
                                                </span>
                                                <span className="text-[11px] text-white/60 tabular-nums shrink-0">
                                                    {(t.duration_ms || 0).toFixed(1)}ms
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <span className="text-[11px] text-white/50 truncate">{t.root_service}</span>
                                                <span className="text-[10px] text-white/30">·</span>
                                                <span className="text-[11px] text-white/50">{t.span_count} spans</span>
                                                <span className="text-[10px] text-white/30">·</span>
                                                <span className="text-[11px] text-white/50">{(t.services || []).length} svc</span>
                                                {isErr && (
                                                    <Badge className="text-[9px] bg-red-500/15 text-red-400 border border-red-500/30 ml-auto">
                                                        {t.error_count || 1} err
                                                    </Badge>
                                                )}
                                            </div>
                                            <div className="text-[10px] text-white/30 font-mono mt-1 truncate">{t.trace_id}</div>
                                        </button>
                                    );
                                })}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                <div data-testid="trace-detail-pane">
                    {selectedTrace ? (
                        <TraceDetail
                            trace={selectedTrace}
                            onClose={() => setSelectedTrace(null)}
                            onDiagnose={(s) => setDiagnoseService(s)}
                        />
                    ) : (
                        <Card className="bg-black/30 border-white/10 border-dashed" data-testid="trace-detail-empty">
                            <CardContent className="p-10 text-center">
                                <Layers className="w-10 h-10 text-white/20 mx-auto mb-3" />
                                <div className="text-sm text-white/50">Select a trace to inspect spans, latency, and errors.</div>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
                </TabsContent>

                <TabsContent value="servicemap" className="space-y-4 mt-5">
                    <Card className="bg-black/40 border-white/10" data-testid="service-map-card">
                        <CardContent className="p-5">
                            <div className="flex items-center justify-between mb-3">
                                <div className="text-xs uppercase tracking-widest text-white/50 flex items-center gap-1.5">
                                    <Network className="w-3.5 h-3.5" /> Service Dependency Map · real traces, last {hours >= 24 ? `${Math.round(hours / 24)}d` : `${hours}h`}
                                </div>
                                <div className="flex items-center gap-1 bg-black/40 rounded-lg border border-white/10 p-0.5">
                                    {RANGES.map((r) => (
                                        <button
                                            key={r.label}
                                            onClick={() => setHours(r.hours)}
                                            className={`px-2.5 py-1 text-[11px] rounded ${hours === r.hours ? 'bg-cyan-500/20 text-cyan-300' : 'text-white/60 hover:text-white/90'}`}
                                            data-testid={`map-range-${r.label}`}
                                        >
                                            {r.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <ServiceMap hours={hours} onDiagnose={(s) => { setMapSelectedService(s); setSelectedTrace(null); }} />
                        </CardContent>
                    </Card>

                    {mapSelectedService && (
                        <ServiceCorrelationPanel
                            service={mapSelectedService}
                            hours={hours}
                            onClose={() => setMapSelectedService(null)}
                            onDiagnose={(s) => setDiagnoseService(s)}
                            onSelectTrace={(t) => setSelectedTrace(t)}
                        />
                    )}

                    {diagnoseService && (
                        <AIOpsDiagnosePanel
                            service={diagnoseService}
                            hours={Math.max(1, Math.ceil(hours))}
                            onClose={() => setDiagnoseService(null)}
                        />
                    )}

                    {selectedTrace && (
                        <TraceDetail
                            trace={selectedTrace}
                            onClose={() => setSelectedTrace(null)}
                            onDiagnose={(s) => setDiagnoseService(s)}
                        />
                    )}
                </TabsContent>

                <TabsContent value="alerts" className="mt-5">
                    <TraceAlertRulesTab services={services} />
                </TabsContent>
            </Tabs>
        </div>
    );
}
