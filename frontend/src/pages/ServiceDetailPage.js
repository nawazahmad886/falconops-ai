import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    ArrowLeft, RefreshCw, Server, Activity, AlertTriangle, ArrowRight, ArrowUpRight, ArrowDownRight,
    Brain, Sparkles, ChevronRight, Layers, MessageSquareText,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken') || localStorage.getItem('token')}`,
});

const RANGES = [
    { label: '1h', hours: 1 },
    { label: '6h', hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d', hours: 168 },
];

const HEALTH_COLOR = (score) => {
    if (score == null) return 'text-white/40';
    if (score >= 80) return 'text-emerald-400';
    if (score >= 50) return 'text-amber-400';
    return 'text-red-400';
};

const StatTile = ({ icon: Icon, label, value, sub, accent }) => (
    <Card className="bg-black/40 border-white/10">
        <CardContent className="p-4">
            <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${accent}/10 border ${accent}/20`}>
                    <Icon className={`w-4 h-4 ${accent.replace('border-', 'text-').replace('/30', '-400')}`} />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="text-[10px] uppercase tracking-widest text-white/50">{label}</div>
                    <div className="mt-1 text-xl font-semibold text-white tabular-nums">{value}</div>
                    {sub && <div className="text-[11px] text-white/40 mt-0.5">{sub}</div>}
                </div>
            </div>
        </CardContent>
    </Card>
);

// ───────── Overview Tab ─────────
const OverviewTab = ({ serviceName, hours }) => {
    const [rootCause, setRootCause] = useState(null);
    const [rootCauseLoading, setRootCauseLoading] = useState(false);
    const [recs, setRecs] = useState(null);
    const [recsLoading, setRecsLoading] = useState(false);

    const runRootCause = async () => {
        setRootCauseLoading(true);
        try {
            const r = await fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/root-cause?hours=${hours}`, { headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            setRootCause(await r.json());
        } catch (e) {
            toast.error(`AI root cause failed: ${e.message?.slice(0, 200)}`);
        }
        setRootCauseLoading(false);
    };

    const runRecommendations = async () => {
        setRecsLoading(true);
        try {
            const r = await fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/recommendations`, { headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            setRecs(await r.json());
        } catch (e) {
            toast.error(`AI recommendations failed: ${e.message?.slice(0, 200)}`);
        }
        setRecsLoading(false);
    };

    return (
        <div className="space-y-4">
            <Card className="bg-black/40 border-white/10" data-testid="root-cause-card">
                <CardHeader className="pb-3 border-b border-white/5">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2"><Brain className="w-4 h-4 text-violet-400" /> AI Root Cause</CardTitle>
                        <Button variant="outline" size="sm" onClick={runRootCause} disabled={rootCauseLoading}
                            className="bg-violet-500/[0.08] border-violet-500/30 text-violet-200 hover:bg-violet-500/[0.16]" data-testid="run-root-cause-btn">
                            {rootCauseLoading ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Brain className="w-4 h-4 mr-1.5" />}
                            {rootCauseLoading ? 'Analyzing...' : rootCause ? 'Re-run' : 'Run Analysis'}
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="p-4">
                    {!rootCause ? (
                        <p className="text-sm text-white/40">Run AI root cause analysis for {serviceName} on demand — no pre-existing incident required.</p>
                    ) : (
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <Badge className="text-[10px] bg-violet-500/15 text-violet-300 border border-violet-500/30">
                                    confidence {Math.round((rootCause.confidence || 0) * 100)}%
                                </Badge>
                            </div>
                            <p className="text-sm text-white/85">{rootCause.summary}</p>
                            {rootCause.evidence?.length > 0 && (
                                <ul className="space-y-1 mt-2">
                                    {rootCause.evidence.map((e, i) => (
                                        <li key={i} className="text-xs text-white/60 flex items-start gap-1.5"><span className="text-violet-400 mt-0.5">•</span>{e}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card className="bg-black/40 border-white/10" data-testid="recommendations-card">
                <CardHeader className="pb-3 border-b border-white/5">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2"><Sparkles className="w-4 h-4 text-cyan-400" /> AI Recommendations</CardTitle>
                        <Button variant="outline" size="sm" onClick={runRecommendations} disabled={recsLoading}
                            className="bg-cyan-500/[0.08] border-cyan-500/30 text-cyan-200 hover:bg-cyan-500/[0.16]" data-testid="run-recommendations-btn">
                            {recsLoading ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
                            {recsLoading ? 'Thinking...' : recs ? 'Re-run' : 'Get Recommendations'}
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="p-4">
                    {!recs ? (
                        <p className="text-sm text-white/40">Get AI-recommended actions to improve {serviceName}'s performance and reliability.</p>
                    ) : (
                        <div className="space-y-2">
                            <p className="text-sm text-white/85">{recs.summary}</p>
                            {recs.recommended_actions?.length > 0 && (
                                <ul className="space-y-1 mt-2">
                                    {recs.recommended_actions.map((a, i) => (
                                        <li key={i} className="text-xs text-white/70 flex items-start gap-1.5"><ArrowRight className="w-3 h-3 text-cyan-400 mt-0.5 shrink-0" />{a}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

// ───────── Transactions Tab ─────────
const TransactionsTab = ({ serviceName, hours }) => {
    const [ops, setOps] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/operations?minutes=${hours * 60}`, { headers: authHeaders() })
            .then(r => r.json())
            .then(d => { if (alive) { setOps(d.operations || []); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [serviceName, hours]);

    if (loading) return <div className="flex justify-center py-10"><RefreshCw className="w-5 h-5 text-white/40 animate-spin" /></div>;

    return (
        <Card className="bg-black/40 border-white/10" data-testid="transactions-card">
            <CardContent className="p-0">
                {ops.length === 0 ? (
                    <div className="p-10 text-center text-white/40 text-sm"><Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />No operations observed in this window.</div>
                ) : (
                    <div className="divide-y divide-white/5">
                        <div className="grid grid-cols-5 gap-2 px-4 py-2 text-[10px] uppercase tracking-widest text-white/40">
                            <span className="col-span-2">Operation</span>
                            <span>Avg Latency</span>
                            <span>Calls</span>
                            <span>Error Rate</span>
                        </div>
                        {ops.map((op, i) => (
                            <div key={i} className="grid grid-cols-5 gap-2 px-4 py-2.5 items-center hover:bg-white/[0.02]" data-testid={`operation-row-${i}`}>
                                <span className="col-span-2 text-sm text-cyan-300 font-mono truncate">{op.operation}</span>
                                <span className="text-sm text-white/80 tabular-nums">{op.avg_duration_ms}ms <span className="text-white/30">p95 {op.p95_duration_ms}ms</span></span>
                                <span className="text-sm text-white/70 tabular-nums">{op.call_count}</span>
                                <span>
                                    {op.error_rate_pct > 0 ? (
                                        <Badge className="text-[10px] bg-red-500/15 text-red-400 border border-red-500/30">{op.error_rate_pct}%</Badge>
                                    ) : (
                                        <span className="text-xs text-white/30">0%</span>
                                    )}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

// ───────── Dependencies Tab ─────────
const DependenciesTab = ({ serviceName, hours }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        const clampedHours = Math.min(168, Math.max(1, hours));
        fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/correlation?hours=${clampedHours}`, { headers: authHeaders() })
            .then(r => r.json())
            .then(d => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [serviceName, hours]);

    if (loading) return <div className="flex justify-center py-10"><RefreshCw className="w-5 h-5 text-white/40 animate-spin" /></div>;
    if (!data) return null;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="bg-black/40 border-white/10" data-testid="upstream-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><ArrowDownRight className="w-4 h-4 text-white/50" /> Upstream · calls into {serviceName}</CardTitle></CardHeader>
                <CardContent className="p-3 space-y-1.5">
                    {(data.upstream || []).length === 0 && <p className="text-xs text-white/30 p-2">None observed</p>}
                    {(data.upstream || []).map((e, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-white/[0.02]">
                            <span className="text-white/70 truncate">{e.service}</span>
                            <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                            <span className="text-white/50">{serviceName}</span>
                            <span className="ml-auto text-white/40 tabular-nums">{e.call_count} calls</span>
                            {e.error_count > 0 && <Badge className="text-[9px] bg-red-500/15 text-red-400 border-red-500/30">{e.error_count} err</Badge>}
                        </div>
                    ))}
                </CardContent>
            </Card>
            <Card className="bg-black/40 border-white/10" data-testid="downstream-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><ArrowUpRight className="w-4 h-4 text-white/50" /> Downstream · {serviceName} calls</CardTitle></CardHeader>
                <CardContent className="p-3 space-y-1.5">
                    {(data.downstream || []).length === 0 && <p className="text-xs text-white/30 p-2">None observed</p>}
                    {(data.downstream || []).map((e, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-white/[0.02]">
                            <span className="text-white/50">{serviceName}</span>
                            <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                            <span className="text-white/70 truncate">{e.depends_on}</span>
                            <span className="ml-auto text-white/40 tabular-nums">{e.call_count} calls</span>
                            {e.error_count > 0 && <Badge className="text-[9px] bg-red-500/15 text-red-400 border-red-500/30">{e.error_count} err</Badge>}
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    );
};

// ───────── Errors Tab ─────────
const ErrorsTab = ({ serviceName, hours }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        setLoading(true);
        fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/errors?minutes=${hours * 60}`, { headers: authHeaders() })
            .then(r => r.json())
            .then(d => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [serviceName, hours]);

    if (loading) return <div className="flex justify-center py-10"><RefreshCw className="w-5 h-5 text-white/40 animate-spin" /></div>;
    if (!data) return null;

    return (
        <Card className="bg-black/40 border-white/10" data-testid="errors-card">
            <CardContent className="p-0">
                {!data.detail_available && (
                    <div className="p-3 text-xs text-amber-300/80 bg-amber-500/[0.05] border-b border-amber-500/10">
                        No exception details were recorded on any error span in this window — showing counts only. Instrument exception recording (OTel span events) for messages.
                    </div>
                )}
                {(data.errors || []).length === 0 ? (
                    <div className="p-10 text-center text-white/40 text-sm"><AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-40" />No errors in this window.</div>
                ) : (
                    <div className="divide-y divide-white/5">
                        {data.errors.map((e, i) => (
                            <div key={i} className="p-3" data-testid={`error-row-${i}`}>
                                <div className="flex items-center gap-2 flex-wrap mb-1">
                                    <span className="text-sm text-white font-mono">{e.operation}</span>
                                    {e.exception_type && <Badge className="text-[9px] bg-red-500/15 text-red-400 border-red-500/30">{e.exception_type}</Badge>}
                                    <span className="ml-auto text-xs text-white/40">{e.count}x</span>
                                </div>
                                {e.sample_message && <p className="text-xs text-white/60 font-mono truncate">{e.sample_message}</p>}
                                <p className="text-[10px] text-white/30 mt-0.5">last seen {e.last_seen ? new Date(e.last_seen).toLocaleString() : 'n/a'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

// ───────── AI Copilot Tab (scoped to this service) ─────────
const ServiceCopilotTab = ({ serviceName }) => {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const ask = async () => {
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const r = await fetch(`${API}/api/ai-intelligence/ask`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ query, mode: 'auto', service: serviceName }),
            });
            if (r.ok) {
                setResult(await r.json());
            } else {
                setError('Failed to get an answer. Please try again.');
            }
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    };

    const sampleQuestions = [
        `Why is ${serviceName} slow right now?`,
        `Show me recent errors in ${serviceName}`,
        `What changed before the last incident in ${serviceName}?`,
    ];

    return (
        <Card className="bg-black/40 border-white/10" data-testid="service-copilot-card">
            <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-base flex items-center gap-2">
                    <MessageSquareText className="w-4 h-4 text-cyan-400" /> Ask about {serviceName}
                </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
                <div className="flex gap-2">
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && ask()}
                        placeholder={`e.g. Why is ${serviceName} erroring?`}
                        className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-cyan-500/50"
                        data-testid="service-copilot-input"
                    />
                    <Button onClick={ask} disabled={loading || !query.trim()} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="service-copilot-submit">
                        {loading ? 'Asking...' : 'Ask'}
                    </Button>
                </div>

                <div className="flex flex-wrap gap-2">
                    {sampleQuestions.map((q, i) => (
                        <button key={i} onClick={() => setQuery(q)} className="text-xs px-2.5 py-1 bg-white/5 rounded-full text-white/50 hover:text-white/80 hover:bg-white/10">
                            {q}
                        </button>
                    ))}
                </div>

                {error && <p className="text-sm text-red-400">{error}</p>}

                {result && (
                    <div className="bg-black/30 border border-white/10 rounded-lg p-4 space-y-3" data-testid="service-copilot-result">
                        <div className="flex items-center gap-2 flex-wrap">
                            {result.mode && (
                                <Badge className="text-[10px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                                    {result.mode === 'incident' ? 'Incident Analysis Agent' : 'Monitoring Copilot Agent'}
                                </Badge>
                            )}
                            {result.confidence != null && (
                                <Badge className="text-[10px] bg-white/5 text-white/60 border border-white/10">
                                    confidence {Math.round(result.confidence * 100)}%
                                </Badge>
                            )}
                        </div>
                        <p className="text-sm text-white/90">{result.summary}</p>
                        {result.evidence?.length > 0 && (
                            <ul className="space-y-1">
                                {result.evidence.map((e, i) => (
                                    <li key={i} className="text-xs text-white/60 flex items-start gap-1.5"><span className="text-cyan-400 mt-0.5">•</span>{e}</li>
                                ))}
                            </ul>
                        )}
                        {result.recommended_actions?.length > 0 && (
                            <ul className="space-y-1">
                                {result.recommended_actions.map((a, i) => (
                                    <li key={i} className="text-xs text-white/70 flex items-start gap-1.5"><ArrowRight className="w-3 h-3 text-cyan-400 mt-0.5 shrink-0" />{a}</li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

// ───────── Main Page ─────────
export default function ServiceDetailPage() {
    const { serviceName } = useParams();
    const [hours, setHours] = useState(24);
    const [overview, setOverview] = useState(null);
    const [loading, setLoading] = useState(true);

    const loadOverview = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/api/traces/services/${encodeURIComponent(serviceName)}/overview?hours=${hours}`, { headers: authHeaders() });
            if (r.ok) setOverview(await r.json());
        } catch (e) { toast.error('Failed to load service overview'); }
        setLoading(false);
    }, [serviceName, hours]);

    useEffect(() => { loadOverview(); }, [loadOverview]);

    const health = overview?.health;
    const metrics = overview?.metrics;

    return (
        <div className="p-6 space-y-5" data-testid="service-detail-page">
            <div className="flex items-center gap-2 text-sm text-white/40">
                <Link to="/apm-traces" className="hover:text-white/70 flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> Service Map</Link>
                <ChevronRight className="w-3 h-3" />
                <span className="text-white/70">{serviceName}</span>
            </div>

            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Server className="w-6 h-6 text-cyan-400" /> {serviceName}
                    </h1>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 bg-black/40 rounded-lg border border-white/10 p-0.5">
                        {RANGES.map((r) => (
                            <button key={r.label} onClick={() => setHours(r.hours)}
                                className={`px-2.5 py-1 text-[11px] rounded ${hours === r.hours ? 'bg-cyan-500/20 text-cyan-300' : 'text-white/60 hover:text-white/90'}`}>
                                {r.label}
                            </button>
                        ))}
                    </div>
                    <Button variant="outline" size="sm" onClick={loadOverview} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                </div>
            </div>

            {loading && !overview ? (
                <div className="flex justify-center py-16"><RefreshCw className="w-6 h-6 text-white/40 animate-spin" /></div>
            ) : (
                <>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <Card className="bg-black/40 border-white/10" data-testid="health-score-tile">
                            <CardContent className="p-4">
                                <div className="text-[10px] uppercase tracking-widest text-white/50">AI Health Score</div>
                                <div className={`mt-1 text-2xl font-semibold tabular-nums ${HEALTH_COLOR(health?.composite_score)}`}>
                                    {health?.composite_score != null ? `${health.composite_score}/100` : 'n/a'}
                                </div>
                                {health?.available_components?.length > 0 && (
                                    <div className="text-[10px] text-white/30 mt-0.5">{health.available_components.join(', ')}</div>
                                )}
                            </CardContent>
                        </Card>
                        <StatTile icon={Activity} label="Avg Latency" value={`${Math.round(metrics?.avg_latency_ms || 0)}ms`} sub={`p95 ${Math.round(metrics?.p95_latency_ms || 0)}ms`} accent="border-amber-500" />
                        <StatTile icon={AlertTriangle} label="Error Rate" value={`${metrics?.error_rate_pct ?? 0}%`} sub={`${metrics?.error_count ?? 0} errors`} accent="border-red-500" />
                        <StatTile icon={ArrowDownRight} label="Upstream" value={overview?.upstream_count ?? 0} accent="border-cyan-500" />
                        <StatTile icon={ArrowUpRight} label="Downstream" value={overview?.downstream_count ?? 0} accent="border-violet-500" />
                    </div>

                    <Tabs defaultValue="overview" data-testid="service-detail-tabs">
                        <TabsList className="bg-black/40 border border-white/10">
                            <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
                            <TabsTrigger value="transactions" data-testid="tab-transactions">Transactions</TabsTrigger>
                            <TabsTrigger value="dependencies" data-testid="tab-dependencies">Dependencies</TabsTrigger>
                            <TabsTrigger value="errors" data-testid="tab-errors">Errors</TabsTrigger>
                            <TabsTrigger value="copilot" data-testid="tab-copilot"><MessageSquareText className="w-3.5 h-3.5 mr-1.5" />AI Copilot</TabsTrigger>
                        </TabsList>

                        <TabsContent value="overview" className="mt-4"><OverviewTab serviceName={serviceName} hours={hours} /></TabsContent>
                        <TabsContent value="transactions" className="mt-4"><TransactionsTab serviceName={serviceName} hours={hours} /></TabsContent>
                        <TabsContent value="dependencies" className="mt-4"><DependenciesTab serviceName={serviceName} hours={hours} /></TabsContent>
                        <TabsContent value="errors" className="mt-4"><ErrorsTab serviceName={serviceName} hours={hours} /></TabsContent>
                        <TabsContent value="copilot" className="mt-4">
                            <ServiceCopilotTab serviceName={serviceName} />
                        </TabsContent>
                    </Tabs>
                </>
            )}
        </div>
    );
}
