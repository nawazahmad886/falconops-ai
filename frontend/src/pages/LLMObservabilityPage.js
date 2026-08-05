import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import {
    AreaChart, Area, BarChart, Bar, LineChart, Line, ResponsiveContainer, Tooltip, Legend, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import {
    Sparkles, RefreshCw, DollarSign, Zap, Gauge, Database, XCircle,
} from 'lucide-react';

const TABS = ['Overview', 'Requests', 'Models', 'Providers', 'Cost', 'Cache', 'Latency', 'Prompts', 'Pricing'];
const RANGES = [
    { label: 'Last 1h', hours: 1 }, { label: 'Last 6h', hours: 6 }, { label: 'Last 24h', hours: 24 },
    { label: 'Last 7d', hours: 168 }, { label: 'Last 30d', hours: 720 },
];

function fmtNum(n) {
    if (n === null || n === undefined) return '—';
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
    return n.toLocaleString();
}
function fmtUsd(n) {
    return n === null || n === undefined ? 'unavailable' : `$${n.toFixed(4)}`;
}
function fmtMs(n) {
    return n === null || n === undefined ? '—' : n >= 1000 ? `${(n / 1000).toFixed(2)}s` : `${Math.round(n)}ms`;
}

function KpiCard({ label, value, sub, icon: Icon }) {
    return (
        <Card className="bg-white/5 border-white/10">
            <CardContent className="p-3">
                <div className="flex items-center justify-between">
                    <div className="text-[10px] text-white/50">{label}</div>
                    {Icon && <Icon className="w-3.5 h-3.5 text-white/30" />}
                </div>
                <div className="text-lg font-semibold text-white">{value}</div>
                {sub && <div className="text-[10px] text-white/40 mt-0.5">{sub}</div>}
            </CardContent>
        </Card>
    );
}

function NotAvailable({ reason }) {
    return <div className="text-xs text-white/40 italic p-4 text-center">Not available{reason ? ` — ${reason}` : ''}</div>;
}

export const LLMObservabilityPage = () => {
    const { api } = useAuth();
    const [hours, setHours] = useState(24);
    const [activeTab, setActiveTab] = useState('Overview');
    const [overview, setOverview] = useState(null);
    const [models, setModels] = useState([]);
    const [providers, setProviders] = useState([]);
    const [tokenSeries, setTokenSeries] = useState([]);
    const [costData, setCostData] = useState(null);
    const [cacheData, setCacheData] = useState(null);
    const [latencyData, setLatencyData] = useState(null);
    const [requests, setRequests] = useState([]);
    const [expensivePrompts, setExpensivePrompts] = useState([]);
    const [slowPrompts, setSlowPrompts] = useState([]);
    const [pricing, setPricing] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [ov, mdl, prov, tok, cost, cache, lat] = await Promise.all([
                api.get('/llm-observability/overview', { params: { hours } }),
                api.get('/llm-observability/models', { params: { hours } }),
                api.get('/llm-observability/providers', { params: { hours } }),
                api.get('/llm-observability/tokens', { params: { hours } }),
                api.get('/llm-observability/cost', { params: { hours } }),
                api.get('/llm-observability/cache', { params: { hours } }),
                api.get('/llm-observability/latency', { params: { hours } }),
            ]);
            setOverview(ov.data);
            setModels(mdl.data.models || []);
            setProviders(prov.data.providers || []);
            setTokenSeries(tok.data.points || []);
            setCostData(cost.data);
            setCacheData(cache.data);
            setLatencyData(lat.data);
        } catch (e) {
            toast.error('Failed to load LLM observability data');
        } finally {
            setLoading(false);
        }
    }, [api, hours]);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        if (activeTab === 'Requests') {
            api.get('/llm-observability/requests', { params: { hours, limit: 100 } })
                .then((r) => setRequests(r.data.requests || [])).catch(() => {});
        }
        if (activeTab === 'Prompts') {
            Promise.all([
                api.get('/llm-observability/prompts/expensive', { params: { hours, limit: 10 } }),
                api.get('/llm-observability/prompts/slow', { params: { hours, limit: 10 } }),
            ]).then(([e, s]) => { setExpensivePrompts(e.data.prompts || []); setSlowPrompts(s.data.prompts || []); }).catch(() => {});
        }
        if (activeTab === 'Pricing') {
            api.get('/llm-observability/pricing').then((r) => setPricing(r.data.rates || [])).catch(() => {});
        }
    }, [activeTab, api, hours]);

    const timeFmt = (t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return (
        <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-violet-400" />LLM Observability
                </h1>
                <div className="flex items-center gap-2">
                    <Select value={String(hours)} onValueChange={(v) => setHours(Number(v))}>
                        <SelectTrigger className="w-36 h-8 text-xs bg-muted/30"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            {RANGES.map((r) => <SelectItem key={r.hours} value={String(r.hours)}>{r.label}</SelectItem>)}
                        </SelectContent>
                    </Select>
                    <Button size="sm" variant="outline" onClick={load}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh</Button>
                </div>
            </div>
            <p className="text-[11px] text-white/40">
                What this AI usage costs and how fast it is — for AI safety/compliance monitoring (hallucination, injection, PII, policy), see AI Observability instead.
            </p>

            <div className="flex gap-1 border-b border-white/10 overflow-x-auto">
                {TABS.map((tab) => (
                    <button key={tab} onClick={() => setActiveTab(tab)}
                        className={`px-3 py-2 text-xs whitespace-nowrap border-b-2 ${activeTab === tab ? 'border-violet-400 text-white' : 'border-transparent text-white/50 hover:text-white/80'}`}>
                        {tab}
                    </button>
                ))}
            </div>

            {activeTab === 'Overview' && (
                overview?.total_requests === 0 ? <NotAvailable reason={overview.message} /> : !overview ? (
                    <div className="text-xs text-white/40">Loading…</div>
                ) : (
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                            <KpiCard label="Total Requests" value={fmtNum(overview.total_requests)}
                                sub={overview.requests_pct_change_vs_previous !== null ? `${overview.requests_pct_change_vs_previous >= 0 ? '↑' : '↓'} ${Math.abs(overview.requests_pct_change_vs_previous)}% vs prior period` : null} />
                            <KpiCard label="Error Rate" value={`${overview.error_rate_pct}%`} sub={`${overview.failed_requests} failed`} icon={XCircle} />
                            <KpiCard label="Total Cost" value={fmtUsd(overview.total_cost_usd)} sub={overview.unpriced_request_count ? `${overview.unpriced_request_count} unpriced` : null} icon={DollarSign} />
                            <KpiCard label="Total Tokens" value={fmtNum(overview.total_tokens)} sub={`${fmtNum(overview.input_tokens)} in / ${fmtNum(overview.output_tokens)} out`} icon={Zap} />
                            <KpiCard label="Avg Latency" value={fmtMs(overview.avg_latency_ms)} sub={`p95 ${fmtMs(overview.latency?.p95)}`} icon={Gauge} />
                            <KpiCard label="Cache Hit Rate" value={overview.cache_hit_rate_pct !== null ? `${overview.cache_hit_rate_pct}%` : '—'} icon={Database} />
                        </div>

                        {cacheData?.total_cache_savings_usd !== undefined && (
                            <Card className="bg-white/5 border-white/10">
                                <CardHeader><CardTitle className="text-sm">Prompt Caching</CardTitle></CardHeader>
                                <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                    <div><div className="text-[10px] text-white/50">Avg Cache Read Tokens</div><div className="text-base text-white">{fmtNum(cacheData.avg_cache_read_tokens)}</div></div>
                                    <div><div className="text-[10px] text-white/50">Cache Hit Rate</div><div className="text-base text-white">{cacheData.cache_hit_rate_pct}%</div></div>
                                    <div><div className="text-[10px] text-white/50">$ Saved</div>
                                        <div className="text-base text-white">{cacheData.total_cache_savings_usd !== null ? fmtUsd(cacheData.total_cache_savings_usd) : 'unavailable'}</div>
                                        {cacheData.cache_savings_unavailable_reason && <div className="text-[9px] text-white/30">{cacheData.cache_savings_unavailable_reason}</div>}
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Token Consumption Over Time</CardTitle></CardHeader>
                            <CardContent style={{ height: 240 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={tokenSeries}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                        <XAxis dataKey="timestamp" tickFormatter={timeFmt} tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <YAxis tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <Tooltip labelFormatter={timeFmt} contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20', fontSize: 11 }} />
                                        <Legend wrapperStyle={{ fontSize: 11 }} />
                                        <Area type="monotone" dataKey="prompt_tokens" stackId="1" stroke="#8b5cf6" fill="#8b5cf640" name="Prompt" />
                                        <Area type="monotone" dataKey="completion_tokens" stackId="1" stroke="#06b6d4" fill="#06b6d440" name="Completion" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    </div>
                )
            )}

            {activeTab === 'Requests' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Time</th><th className="text-left p-2">Model</th><th className="text-left p-2">Provider</th>
                                    <th className="text-left p-2">Tokens</th><th className="text-left p-2">Latency</th><th className="text-left p-2">Cost</th>
                                    <th className="text-left p-2">Status</th><th className="text-left p-2">Trace</th></tr>
                            </thead>
                            <tbody>
                                {requests.map((r) => (
                                    <tr key={r.id} className="border-b border-white/5">
                                        <td className="p-2 text-white/60">{new Date(r.received_at).toLocaleString()}</td>
                                        <td className="p-2 text-white">{r.model}</td>
                                        <td className="p-2 text-white/60">{r.provider}</td>
                                        <td className="p-2 text-white/60">{fmtNum(r.tokens_total)}{r.tokens_source === 'estimated' && <span className="text-amber-400"> ~</span>}</td>
                                        <td className="p-2 text-white/60">{fmtMs(r.latency_ms)}</td>
                                        <td className="p-2 text-white/60">{fmtUsd(r.estimated_cost_usd)}</td>
                                        <td className="p-2"><Badge variant="outline" className={`text-[10px] ${r.errored ? 'text-red-300 border-red-500/30' : 'text-emerald-300 border-emerald-500/30'}`}>{r.errored ? 'error' : 'ok'}</Badge></td>
                                        <td className="p-2 text-white/40 font-mono text-[10px]">{r.trace_id ? r.trace_id.slice(0, 8) : '—'}</td>
                                    </tr>
                                ))}
                                {!loading && requests.length === 0 && <tr><td colSpan={8} className="p-4 text-center text-white/40">No requests in this window.</td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            {activeTab === 'Models' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Model</th><th className="text-left p-2">Provider</th><th className="text-left p-2">Requests</th>
                                    <th className="text-left p-2">Success %</th><th className="text-left p-2">P50</th><th className="text-left p-2">P95</th><th className="text-left p-2">P99</th>
                                    <th className="text-left p-2">Tokens</th><th className="text-left p-2">Cost</th><th className="text-left p-2">$/req</th><th className="text-left p-2">Cache %</th></tr>
                            </thead>
                            <tbody>
                                {models.map((m) => (
                                    <tr key={m.model} className="border-b border-white/5">
                                        <td className="p-2 text-white">{m.model}</td><td className="p-2 text-white/60">{m.provider}</td>
                                        <td className="p-2 text-white/60">{m.requests}</td><td className="p-2 text-white/60">{m.success_pct}%</td>
                                        <td className="p-2 text-white/60">{fmtMs(m.p50_ms)}</td><td className="p-2 text-white/60">{fmtMs(m.p95_ms)}</td><td className="p-2 text-white/60">{fmtMs(m.p99_ms)}</td>
                                        <td className="p-2 text-white/60">{fmtNum(m.tokens)}</td><td className="p-2 text-white/60">{fmtUsd(m.cost_usd)}</td>
                                        <td className="p-2 text-white/60">{m.cost_per_request_usd !== null ? `$${m.cost_per_request_usd.toFixed(5)}` : '—'}</td>
                                        <td className="p-2 text-white/60">{m.cache_hit_pct}%</td>
                                    </tr>
                                ))}
                                {!loading && models.length === 0 && <tr><td colSpan={11} className="p-4 text-center text-white/40">No model data in this window.</td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            {activeTab === 'Providers' && (
                <div className="space-y-3">
                    <Card className="bg-white/5 border-white/10">
                        <CardContent className="p-0">
                            <table className="w-full text-xs">
                                <thead className="text-white/40 border-b border-white/10">
                                    <tr><th className="text-left p-2">Provider</th><th className="text-left p-2">Requests</th><th className="text-left p-2">Error Rate</th>
                                        <th className="text-left p-2">P95</th><th className="text-left p-2">Tokens</th><th className="text-left p-2">Cost</th><th className="text-left p-2">$/req</th></tr>
                                </thead>
                                <tbody>
                                    {providers.map((p) => (
                                        <tr key={p.provider} className="border-b border-white/5">
                                            <td className="p-2 text-white">{p.provider}</td><td className="p-2 text-white/60">{p.requests}</td>
                                            <td className="p-2 text-white/60">{p.error_rate_pct}%</td><td className="p-2 text-white/60">{fmtMs(p.p95_ms)}</td>
                                            <td className="p-2 text-white/60">{fmtNum(p.tokens)}</td><td className="p-2 text-white/60">{fmtUsd(p.cost_usd)}</td>
                                            <td className="p-2 text-white/60">{p.cost_per_request_usd !== null ? `$${p.cost_per_request_usd.toFixed(5)}` : '—'}</td>
                                        </tr>
                                    ))}
                                    {!loading && providers.length === 0 && <tr><td colSpan={7} className="p-4 text-center text-white/40">No provider data — only providers actually seen in telemetry are shown.</td></tr>}
                                </tbody>
                            </table>
                        </CardContent>
                    </Card>
                    {providers.length > 0 && (
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Requests by Provider</CardTitle></CardHeader>
                            <CardContent style={{ height: 220 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={providers}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                        <XAxis dataKey="provider" tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <YAxis tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <Tooltip contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20', fontSize: 11 }} />
                                        <Bar dataKey="requests" fill="#8b5cf6" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeTab === 'Cost' && (
                costData ? (
                    <div className="space-y-3">
                        <div className="grid grid-cols-3 gap-3">
                            <KpiCard label="Total Cost" value={fmtUsd(costData.total_cost_usd)} icon={DollarSign} />
                            <KpiCard label="Priced Requests" value={costData.priced_request_count} />
                            <KpiCard label="Unpriced Requests" value={costData.unpriced_request_count} sub="no rate configured — see Pricing tab" />
                        </div>
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Cost Over Time</CardTitle></CardHeader>
                            <CardContent style={{ height: 220 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={costData.points}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                        <XAxis dataKey="timestamp" tickFormatter={timeFmt} tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <YAxis tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <Tooltip labelFormatter={timeFmt} contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20', fontSize: 11 }} />
                                        <Line type="monotone" dataKey="cost_usd" stroke="#f59e0b" dot={false} name="Cost (USD)" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                        <div className="grid grid-cols-2 gap-3">
                            <Card className="bg-white/5 border-white/10">
                                <CardHeader><CardTitle className="text-sm">Cost by Model</CardTitle></CardHeader>
                                <CardContent className="space-y-1">
                                    {Object.entries(costData.by_model || {}).sort((a, b) => b[1] - a[1]).map(([m, c]) => (
                                        <div key={m} className="flex justify-between text-xs text-white/70"><span>{m}</span><span>{fmtUsd(c)}</span></div>
                                    ))}
                                </CardContent>
                            </Card>
                            <Card className="bg-white/5 border-white/10">
                                <CardHeader><CardTitle className="text-sm">Cost by Provider</CardTitle></CardHeader>
                                <CardContent className="space-y-1">
                                    {Object.entries(costData.by_provider || {}).sort((a, b) => b[1] - a[1]).map(([p, c]) => (
                                        <div key={p} className="flex justify-between text-xs text-white/70"><span>{p}</span><span>{fmtUsd(c)}</span></div>
                                    ))}
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                ) : <div className="text-xs text-white/40">Loading…</div>
            )}

            {activeTab === 'Cache' && (
                !cacheData?.available && cacheData?.available === false ? <NotAvailable reason={cacheData.reason} /> : cacheData ? (
                    <div className="space-y-3">
                        <div className="grid grid-cols-3 gap-3">
                            <KpiCard label="Cache Hit Rate" value={`${cacheData.cache_hit_rate_pct}%`} icon={Database} />
                            <KpiCard label="Avg Cache Read Tokens" value={fmtNum(cacheData.avg_cache_read_tokens)} />
                            <KpiCard label="Total Savings" value={cacheData.total_cache_savings_usd !== null ? fmtUsd(cacheData.total_cache_savings_usd) : 'unavailable'} sub={cacheData.cache_savings_unavailable_reason} />
                        </div>
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Cache Hit Rate Over Time</CardTitle></CardHeader>
                            <CardContent style={{ height: 220 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={cacheData.hit_rate_series}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                        <XAxis dataKey="timestamp" tickFormatter={timeFmt} tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <YAxis tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <Tooltip labelFormatter={timeFmt} contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20', fontSize: 11 }} />
                                        <Line type="monotone" dataKey="cache_hit_rate_pct" stroke="#10b981" dot={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                    </div>
                ) : <div className="text-xs text-white/40">Loading…</div>
            )}

            {activeTab === 'Latency' && (
                !latencyData?.available && latencyData?.available === false ? <NotAvailable reason={latencyData.reason} /> : latencyData ? (
                    <div className="space-y-3">
                        <div className="grid grid-cols-4 gap-3">
                            <KpiCard label="P50" value={fmtMs(latencyData.overall.p50)} />
                            <KpiCard label="P90" value={fmtMs(latencyData.overall.p90)} />
                            <KpiCard label="P95" value={fmtMs(latencyData.overall.p95)} />
                            <KpiCard label="P99" value={fmtMs(latencyData.overall.p99)} />
                        </div>
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Latency Over Time</CardTitle></CardHeader>
                            <CardContent style={{ height: 220 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={latencyData.series}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                        <XAxis dataKey="timestamp" tickFormatter={timeFmt} tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <YAxis tick={{ fontSize: 10, fill: '#ffffff60' }} />
                                        <Tooltip labelFormatter={timeFmt} contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20', fontSize: 11 }} />
                                        <Legend wrapperStyle={{ fontSize: 11 }} />
                                        <Line type="monotone" dataKey="avg_ms" stroke="#06b6d4" dot={false} name="Avg" />
                                        <Line type="monotone" dataKey="p95" stroke="#f59e0b" dot={false} name="P95" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm">Slowest Models (P95)</CardTitle></CardHeader>
                            <CardContent className="space-y-1">
                                {latencyData.slowest_models.map((m) => (
                                    <div key={m.model} className="flex justify-between text-xs text-white/70"><span>{m.model}</span><span>{fmtMs(m.p95_ms)}</span></div>
                                ))}
                            </CardContent>
                        </Card>
                    </div>
                ) : <div className="text-xs text-white/40">Loading…</div>
            )}

            {activeTab === 'Prompts' && (
                <div className="space-y-3">
                    <Card className="bg-white/5 border-white/10">
                        <CardHeader><CardTitle className="text-sm">Top 10 Expensive Prompts</CardTitle></CardHeader>
                        <CardContent className="p-0">
                            <table className="w-full text-xs">
                                <thead className="text-white/40 border-b border-white/10">
                                    <tr><th className="text-left p-2">Prompt</th><th className="text-left p-2">Model</th><th className="text-left p-2">Tokens</th><th className="text-left p-2">Cost</th><th className="text-left p-2">Trace</th></tr>
                                </thead>
                                <tbody>
                                    {expensivePrompts.map((p) => (
                                        <tr key={p.id} className="border-b border-white/5">
                                            <td className="p-2 text-white/70 max-w-xs truncate">{p.prompt_preview}</td>
                                            <td className="p-2 text-white/60">{p.model}</td><td className="p-2 text-white/60">{fmtNum(p.tokens_total)}</td>
                                            <td className="p-2 text-white/60">{fmtUsd(p.estimated_cost_usd)}</td>
                                            <td className="p-2 text-white/40 font-mono text-[10px]">{p.trace_id ? p.trace_id.slice(0, 8) : '—'}</td>
                                        </tr>
                                    ))}
                                    {expensivePrompts.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-white/40">No priced prompts in this window.</td></tr>}
                                </tbody>
                            </table>
                        </CardContent>
                    </Card>
                    <Card className="bg-white/5 border-white/10">
                        <CardHeader><CardTitle className="text-sm">Top 10 Slowest Prompts</CardTitle></CardHeader>
                        <CardContent className="p-0">
                            <table className="w-full text-xs">
                                <thead className="text-white/40 border-b border-white/10">
                                    <tr><th className="text-left p-2">Prompt</th><th className="text-left p-2">Model</th><th className="text-left p-2">Duration</th><th className="text-left p-2">Status</th><th className="text-left p-2">Trace</th></tr>
                                </thead>
                                <tbody>
                                    {slowPrompts.map((p) => (
                                        <tr key={p.id} className="border-b border-white/5">
                                            <td className="p-2 text-white/70 max-w-xs truncate">{p.prompt_preview}</td>
                                            <td className="p-2 text-white/60">{p.model}</td><td className="p-2 text-white/60">{fmtMs(p.latency_ms)}</td>
                                            <td className="p-2"><Badge variant="outline" className={`text-[10px] ${p.errored ? 'text-red-300 border-red-500/30' : 'text-emerald-300 border-emerald-500/30'}`}>{p.errored ? 'error' : 'ok'}</Badge></td>
                                            <td className="p-2 text-white/40 font-mono text-[10px]">{p.trace_id ? p.trace_id.slice(0, 8) : '—'}</td>
                                        </tr>
                                    ))}
                                    {slowPrompts.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-white/40">No prompts with latency data in this window.</td></tr>}
                                </tbody>
                            </table>
                        </CardContent>
                    </Card>
                </div>
            )}

            {activeTab === 'Pricing' && (
                <Card className="bg-white/5 border-white/10">
                    <CardHeader><CardTitle className="text-sm">Pricing Registry ($ per 1K tokens)</CardTitle></CardHeader>
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Provider</th><th className="text-left p-2">Model</th><th className="text-left p-2">Input</th>
                                    <th className="text-left p-2">Output</th><th className="text-left p-2">Cache Read</th><th className="text-left p-2">Updated</th></tr>
                            </thead>
                            <tbody>
                                {pricing.map((r) => (
                                    <tr key={`${r.provider}-${r.model}`} className="border-b border-white/5">
                                        <td className="p-2 text-white">{r.provider}</td><td className="p-2 text-white/60">{r.model}</td>
                                        <td className="p-2 text-white/60">${r.input_price_per_1k}</td><td className="p-2 text-white/60">${r.output_price_per_1k}</td>
                                        <td className="p-2 text-white/60">{r.cache_read_price_per_1k !== null ? `$${r.cache_read_price_per_1k}` : '—'}</td>
                                        <td className="p-2 text-white/40">{r.updated_by}</td>
                                    </tr>
                                ))}
                                {pricing.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-white/40">Loading pricing registry…</td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default LLMObservabilityPage;
