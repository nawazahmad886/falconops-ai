/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import {
    Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import {
    AreaChart, Area, BarChart, Bar, LineChart, Line, ResponsiveContainer, Tooltip, Legend, XAxis, YAxis, CartesianGrid,
} from 'recharts';
import { toast } from 'sonner';
import {
    Radio, Activity, RefreshCw, Plus, Trash2, ShieldAlert, BrainCircuit, DollarSign,
    Gauge, Sparkles, Eye, EyeOff, Lock, AlertCircle, CheckCircle2, AlertTriangle,
    PlayCircle, FileLock, FlaskConical, GitBranch, Wifi, WifiOff, Cpu, Terminal, MemoryStick,
} from 'lucide-react';
import LogAnalyzerTab from './LogAnalyzerTab';

// ──────────────────────────────────────────────────────────────────────────────
// API helpers
// ──────────────────────────────────────────────────────────────────────────────
const API = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('falconToken');
const headers = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` });

async function api(path, opts = {}) {
    const r = await fetch(`${API}${path}`, { headers: headers(), ...opts });
    if (!r.ok) throw new Error((await r.text()).slice(0, 300) || `HTTP ${r.status}`);
    const ct = r.headers.get('content-type') || '';
    return ct.includes('application/json') ? r.json() : r.text();
}

// ──────────────────────────────────────────────────────────────────────────────
// Agent meta
// ──────────────────────────────────────────────────────────────────────────────
const AGENT_META = {
    hallucination: { icon: BrainCircuit,  color: 'violet',  label: 'Hallucination',    kind: 'LLM' },
    injection:     { icon: ShieldAlert,   color: 'red',     label: 'Prompt Injection', kind: 'Regex + LLM' },
    cost:          { icon: DollarSign,    color: 'amber',   label: 'Cost',             kind: 'Statistical' },
    performance:   { icon: Gauge,         color: 'cyan',    label: 'Performance',      kind: 'Statistical' },
    quality:       { icon: Sparkles,      color: 'emerald', label: 'Quality',          kind: 'LLM' },
    pii_leak:      { icon: FileLock,      color: 'pink',    label: 'PII / Data Leak',  kind: 'Regex + Luhn' },
    toxicity:      { icon: AlertTriangle, color: 'orange',  label: 'Toxicity & Bias',  kind: 'LLM' },
    policy:        { icon: Lock,          color: 'blue',    label: 'Policy Compliance', kind: 'LLM + Rules' },
    drift:         { icon: GitBranch,     color: 'teal',    label: 'Drift Detection',  kind: 'Statistical' },
    root_cause:    { icon: FlaskConical,  color: 'fuchsia', label: 'Root Cause',       kind: 'LLM' },
};

const COLOR_MAP = {
    violet:  { tile: 'border-violet-500/30 text-violet-300',   chip: 'bg-violet-500/15 text-violet-200 border-violet-500/30' },
    red:     { tile: 'border-red-500/30 text-red-300',         chip: 'bg-red-500/15 text-red-200 border-red-500/30' },
    amber:   { tile: 'border-amber-500/30 text-amber-300',     chip: 'bg-amber-500/15 text-amber-200 border-amber-500/30' },
    cyan:    { tile: 'border-cyan-500/30 text-cyan-300',       chip: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30' },
    emerald: { tile: 'border-emerald-500/30 text-emerald-300', chip: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30' },
    pink:    { tile: 'border-pink-500/30 text-pink-300',       chip: 'bg-pink-500/15 text-pink-200 border-pink-500/30' },
    orange:  { tile: 'border-orange-500/30 text-orange-300',   chip: 'bg-orange-500/15 text-orange-200 border-orange-500/30' },
    blue:    { tile: 'border-blue-500/30 text-blue-300',       chip: 'bg-blue-500/15 text-blue-200 border-blue-500/30' },
    teal:    { tile: 'border-teal-500/30 text-teal-300',       chip: 'bg-teal-500/15 text-teal-200 border-teal-500/30' },
    fuchsia: { tile: 'border-fuchsia-500/30 text-fuchsia-300', chip: 'bg-fuchsia-500/15 text-fuchsia-200 border-fuchsia-500/30' },
};

function VerdictBadge({ status }) {
    const map = {
        healthy:  { cls: 'border-emerald-500/40 text-emerald-300', Icon: CheckCircle2 },
        warning:  { cls: 'border-amber-500/40 text-amber-300',     Icon: AlertTriangle },
        critical: { cls: 'border-red-500/40 text-red-300',         Icon: AlertCircle },
    };
    const m = map[status] || map.healthy;
    return (
        <Badge className={`text-[10px] uppercase tracking-wider bg-black/30 border ${m.cls}`} data-testid={`verdict-${status}`}>
            <m.Icon className="w-3 h-3 mr-1" /> {status || '–'}
        </Badge>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// OVERVIEW TAB
// ──────────────────────────────────────────────────────────────────────────────
function OverviewTab({ refreshKey }) {
    const [dashboard, setDashboard] = useState(null);
    const [series, setSeries] = useState([]);
    const [latencyStats, setLatencyStats] = useState(null);
    const [hours, setHours] = useState(24);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        const bucketMinutes = hours <= 6 ? 5 : hours <= 24 ? 15 : 60;
        Promise.all([
            api(`/api/ai-monitoring/dashboard?hours=${hours}`),
            api(`/api/ai-monitoring/timeseries?hours=${hours}&bucket_minutes=${bucketMinutes}`),
            api(`/api/ai-monitoring/latency-stats?hours=${hours}&bucket_minutes=${bucketMinutes}`),
        ])
            .then(([d, ts, lat]) => { if (!cancelled) { setDashboard(d); setSeries(ts.points || []); setLatencyStats(lat); } })
            .catch((e) => toast.error(`Dashboard load failed: ${e.message}`))
            .finally(() => !cancelled && setLoading(false));
        return () => { cancelled = true; };
    }, [hours, refreshKey]);

    const tiles = useMemo(() => {
        if (!dashboard) return [];
        const overall = latencyStats?.overall;
        return [
            { label: 'Events', value: dashboard.totals.events, sub: `${hours}h window`, color: 'violet' },
            { label: 'Critical', value: dashboard.totals.critical, sub: 'verdict', color: 'red' },
            { label: 'Warning', value: dashboard.totals.warning, sub: 'verdict', color: 'amber' },
            { label: 'Healthy', value: dashboard.totals.healthy, sub: 'verdict', color: 'emerald' },
            { label: 'Tokens', value: dashboard.tokens.total?.toLocaleString?.() || 0, sub: `$${dashboard.tokens.cost_usd?.toFixed(4) || '0.0000'}`, color: 'cyan' },
            { label: 'P95 Latency', value: overall?.p95 != null ? `${overall.p95.toFixed(0)}ms` : 'n/a', sub: overall?.sample_size ? `p50 ${overall.p50?.toFixed(0)}ms · p99 ${overall.p99?.toFixed(0)}ms` : 'no samples yet', color: 'blue' },
        ];
    }, [dashboard, latencyStats, hours]);

    return (
        <div className="space-y-4" data-testid="observability-overview">
            <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-widest text-white/40">Window</div>
                <Select value={String(hours)} onValueChange={(v) => setHours(Number(v))}>
                    <SelectTrigger className="w-[160px] h-8 bg-black/40 border-white/10 text-xs" data-testid="overview-window-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                        {[1, 6, 24, 168, 720].map((h) => (
                            <SelectItem key={h} value={String(h)}>
                                {h === 1 ? 'Last hour' : h === 6 ? 'Last 6h' : h === 24 ? 'Last 24h' : h === 168 ? 'Last 7d' : 'Last 30d'}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* KPI tiles */}
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                {tiles.map((t) => (
                    <Card key={t.label} className={`bg-black/40 border ${COLOR_MAP[t.color].tile}`} data-testid={`tile-${t.label.toLowerCase().replace(/\s+/g, '-')}`}>
                        <CardContent className="p-3">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">{t.label}</div>
                            <div className="text-xl font-bold text-white tabular-nums mt-0.5">{loading ? '–' : t.value}</div>
                            <div className="text-[10px] text-white/50 truncate">{t.sub}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Timeseries area chart */}
            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white">
                        <Activity className="w-4 h-4 text-cyan-400" /> Verdict Mix Over Time
                    </CardTitle>
                </CardHeader>
                <CardContent className="h-[260px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={series}>
                            <defs>
                                <linearGradient id="gC" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f87171" stopOpacity={0.45}/><stop offset="95%" stopColor="#f87171" stopOpacity={0}/></linearGradient>
                                <linearGradient id="gW" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#fbbf24" stopOpacity={0.45}/><stop offset="95%" stopColor="#fbbf24" stopOpacity={0}/></linearGradient>
                                <linearGradient id="gH" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#34d399" stopOpacity={0.35}/><stop offset="95%" stopColor="#34d399" stopOpacity={0}/></linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                            <XAxis dataKey="ts" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v) => (v || '').slice(11, 16)} />
                            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #ffffff20', fontSize: 11 }} />
                            <Area type="monotone" dataKey="healthy"  stackId="1" stroke="#34d399" fill="url(#gH)" />
                            <Area type="monotone" dataKey="warning"  stackId="1" stroke="#fbbf24" fill="url(#gW)" />
                            <Area type="monotone" dataKey="critical" stackId="1" stroke="#f87171" fill="url(#gC)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* LLM latency percentiles — real p50/p90/p95/p99, not the old
                mislabeled max-as-p95 tile */}
            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white">
                        <Gauge className="w-4 h-4 text-blue-400" /> LLM Latency Percentiles
                    </CardTitle>
                </CardHeader>
                <CardContent className="h-[240px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={latencyStats?.points || []}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                            <XAxis dataKey="ts" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v) => (v || '').slice(11, 16)} />
                            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} unit="ms" />
                            <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #ffffff20', fontSize: 11 }} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line type="monotone" dataKey="p50" name="p50" stroke="#22d3ee" dot={false} strokeWidth={1.5} />
                            <Line type="monotone" dataKey="p90" name="p90" stroke="#60a5fa" dot={false} strokeWidth={1.5} />
                            <Line type="monotone" dataKey="p95" name="p95" stroke="#fbbf24" dot={false} strokeWidth={1.5} />
                            <Line type="monotone" dataKey="p99" name="p99" stroke="#f87171" dot={false} strokeWidth={1.5} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Cost + token volume */}
            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white">
                        <DollarSign className="w-4 h-4 text-amber-400" /> Token Volume & Cost
                    </CardTitle>
                </CardHeader>
                <CardContent className="h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={series}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                            <XAxis dataKey="ts" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v) => (v || '').slice(11, 16)} />
                            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ background: '#0a0a0a', border: '1px solid #ffffff20', fontSize: 11 }} />
                            <Bar dataKey="tokens" fill="#22d3ee" />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Per-agent flag counts */}
            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2"><CardTitle className="text-sm text-white">Flags by Agent</CardTitle></CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                        {Object.entries(AGENT_META).filter(([k]) => k !== 'root_cause').map(([k, meta]) => {
                            const count = dashboard?.by_agent?.[k] || 0;
                            const Icon = meta.icon;
                            const c = COLOR_MAP[meta.color];
                            return (
                                <div key={k} className={`rounded-md border ${c.tile} bg-black/40 p-2.5 flex items-center gap-2`} data-testid={`flags-${k}`}>
                                    <Icon className="w-4 h-4" />
                                    <div className="flex-1 min-w-0">
                                        <div className="text-[10px] uppercase tracking-widest text-white/40 truncate">{meta.label}</div>
                                        <div className="text-base font-bold text-white tabular-nums">{count}</div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// AGENTS TAB (drilldown)
// ──────────────────────────────────────────────────────────────────────────────
function AgentsTab({ refreshKey }) {
    const [agents, setAgents] = useState([]);
    const [drill, setDrill] = useState({}); // {agent_id: {total, flagged, rate, sev_mix}}
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        api('/api/ai-monitoring/health')
            .then(async (h) => {
                if (cancelled) return;
                setAgents(h.agents || []);
                const ids = (h.agents || []).map(a => a.id).filter(id => id !== 'root_cause');
                const results = await Promise.allSettled(ids.map(id => api(`/api/ai-monitoring/agents/${id}?hours=24&limit=5`)));
                if (cancelled) return;
                const map = {};
                results.forEach((r, i) => {
                    if (r.status === 'fulfilled') map[ids[i]] = r.value;
                });
                setDrill(map);
            })
            .catch((e) => toast.error(`Agents load failed: ${e.message}`))
            .finally(() => !cancelled && setLoading(false));
        return () => { cancelled = true; };
    }, [refreshKey]);

    return (
        <div className="space-y-4" data-testid="observability-agents">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                {agents.filter(a => a.id !== 'root_cause').map((a) => {
                    const meta = AGENT_META[a.id] || AGENT_META.root_cause;
                    const Icon = meta.icon;
                    const c = COLOR_MAP[meta.color];
                    const d = drill[a.id] || {};
                    return (
                        <Card key={a.id} className={`bg-black/40 border ${c.tile}`} data-testid={`agent-card-${a.id}`}>
                            <CardContent className="p-4 space-y-2">
                                <div className="flex items-center gap-2">
                                    <Icon className="w-4 h-4" />
                                    <div className="text-sm font-semibold text-white flex-1 truncate">{meta.label}</div>
                                    <Badge className={`text-[9px] border ${c.chip}`}>{meta.kind}</Badge>
                                </div>
                                <p className="text-[11px] text-white/55">{a.description}</p>
                                <div className="grid grid-cols-3 gap-2 mt-2">
                                    <div>
                                        <div className="text-[9px] uppercase tracking-widest text-white/40">Evals</div>
                                        <div className="text-base font-bold text-white tabular-nums">{loading ? '–' : (d.total_evaluations ?? 0)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9px] uppercase tracking-widest text-white/40">Flagged</div>
                                        <div className="text-base font-bold text-white tabular-nums">{loading ? '–' : (d.flagged_count ?? 0)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9px] uppercase tracking-widest text-white/40">Rate</div>
                                        <div className="text-base font-bold text-white tabular-nums">
                                            {loading ? '–' : `${Math.round((d.flagged_rate ?? 0) * 100)}%`}
                                        </div>
                                    </div>
                                </div>
                                {d.severity_mix && Object.keys(d.severity_mix).length > 0 && (
                                    <div className="flex items-center gap-1.5 pt-1 flex-wrap">
                                        {['high', 'medium', 'low'].map((s) => d.severity_mix[s] ? (
                                            <Badge key={s} className={`text-[9px] ${s === 'high' ? 'border-red-500/40 text-red-300' : s === 'medium' ? 'border-amber-500/40 text-amber-300' : 'border-white/15 text-white/50'} bg-black/30 border`}>
                                                {s} · {d.severity_mix[s]}
                                            </Badge>
                                        ) : null)}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// LIVE FEED TAB (WebSocket)
// ──────────────────────────────────────────────────────────────────────────────
function LiveFeedTab() {
    const [items, setItems] = useState([]);
    const [connected, setConnected] = useState(false);
    const [hello, setHello] = useState(null);
    const wsRef = useRef(null);

    useEffect(() => {
        const t = token();
        if (!t) return;
        let wsUrl;
        try {
            const u = new URL(API);
            const scheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
            wsUrl = `${scheme}//${u.host}/api/ai-monitoring/live?token=${encodeURIComponent(t)}`;
        } catch (_e) {
            return;
        }
        let ws;
        try {
            ws = new WebSocket(wsUrl);
        } catch (_e) {
            toast.error('WebSocket open failed');
            return;
        }
        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onclose = () => setConnected(false);
        ws.onerror = () => setConnected(false);
        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                if (msg.type === 'ai_monitoring.hello') {
                    setHello(msg);
                } else if (msg.type === 'ai_monitoring.event') {
                    setItems((prev) => [msg, ...prev].slice(0, 200));
                }
            } catch (_e) { /* ignore */ }
        };
        return () => {
            try { ws.close(); } catch (_e) { /* ignore */ }
        };
    }, []);

    return (
        <div className="space-y-3" data-testid="observability-live">
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-3 flex items-center gap-3">
                    {connected
                        ? <Wifi className="w-4 h-4 text-emerald-400" />
                        : <WifiOff className="w-4 h-4 text-red-400" />}
                    <div className="text-sm text-white">
                        {connected ? 'Streaming live AI monitoring events' : 'Disconnected — reload to reconnect'}
                    </div>
                    {hello && <span className="text-[11px] text-white/50 ml-auto">subs: {hello.subscribers}</span>}
                </CardContent>
            </Card>

            {items.length === 0 ? (
                <Card className="bg-black/40 border-white/10 border-dashed">
                    <CardContent className="p-8 text-center text-white/45 text-sm">
                        Listening… events will appear here as LLM calls flow through FalconOps.<br />
                        <span className="text-[11px] text-white/35">Tip: run an evaluation from the legacy /ai-monitoring page or hit the Copilot to populate the feed.</span>
                    </CardContent>
                </Card>
            ) : (
                <ScrollArea className="h-[520px] pr-2">
                    <div className="space-y-2">
                        {items.map((e) => {
                            const flagged = (e.agents || []).filter(a => a.flagged);
                            return (
                                <Card key={e.event_id} className="bg-black/40 border-white/10" data-testid={`live-event-${e.event_id?.slice(0, 8)}`}>
                                    <CardContent className="p-3">
                                        <div className="flex items-center gap-2 mb-1">
                                            <VerdictBadge status={e.verdict?.system_status} />
                                            <span className="text-[11px] text-white/40 font-mono">{e.event_id?.slice(0, 8)}…</span>
                                            <span className="text-[11px] text-white/55 truncate">{e.model || e.provider}</span>
                                            <span className="text-[10px] text-white/35 ml-auto">{(e.received_at || '').slice(11, 19)}</span>
                                        </div>
                                        <p className="text-[12px] text-white/70 italic mb-1">“{e.user_input}”</p>
                                        <div className="flex items-center gap-1.5 flex-wrap">
                                            {flagged.length === 0 ? (
                                                <span className="text-[10px] text-emerald-300/70">All agents healthy</span>
                                            ) : flagged.map((a) => (
                                                <Badge key={a.agent} className="text-[9px] border-red-500/40 text-red-300 bg-black/30 border">
                                                    {AGENT_META[a.agent]?.label || a.agent} · {a.severity}
                                                </Badge>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </ScrollArea>
            )}
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// POLICIES TAB
// ──────────────────────────────────────────────────────────────────────────────
function PoliciesTab({ refreshKey, bumpRefresh }) {
    const [policies, setPolicies] = useState([]);
    const [editing, setEditing] = useState(null);
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        api('/api/ai-monitoring/policies')
            .then((d) => !cancelled && setPolicies(d.policies || []))
            .catch((e) => toast.error(`Policies load failed: ${e.message}`))
            .finally(() => !cancelled && setLoading(false));
        return () => { cancelled = true; };
    }, [refreshKey]);

    const openNew = () => {
        setEditing({ name: '', rule: '', severity: 'medium', enabled: true, tags: '' });
        setOpen(true);
    };
    const openEdit = (p) => {
        setEditing({ ...p, tags: (p.tags || []).join(', ') });
        setOpen(true);
    };

    const save = async () => {
        if (!editing?.name?.trim() || !editing?.rule?.trim()) {
            toast.error('Name and rule are required');
            return;
        }
        const body = {
            name: editing.name,
            rule: editing.rule,
            severity: editing.severity,
            enabled: !!editing.enabled,
            tags: (editing.tags || '').split(',').map(s => s.trim()).filter(Boolean),
        };
        try {
            if (editing.id) {
                await api(`/api/ai-monitoring/policies/${editing.id}`, { method: 'PUT', body: JSON.stringify(body) });
                toast.success('Policy updated');
            } else {
                await api('/api/ai-monitoring/policies', { method: 'POST', body: JSON.stringify(body) });
                toast.success('Policy created');
            }
            setOpen(false);
            bumpRefresh();
        } catch (e) {
            toast.error(`Save failed: ${e.message}`);
        }
    };
    const del = async (p) => {
        if (!window.confirm(`Delete policy "${p.name}"?`)) return;
        try {
            await api(`/api/ai-monitoring/policies/${p.id}`, { method: 'DELETE' });
            toast.success('Policy deleted');
            bumpRefresh();
        } catch (e) {
            toast.error(`Delete failed: ${e.message}`);
        }
    };

    return (
        <div className="space-y-3" data-testid="observability-policies">
            <div className="flex items-center justify-between">
                <div className="text-sm text-white/65">
                    {policies.length} custom polic{policies.length === 1 ? 'y' : 'ies'} — checked by the Policy Compliance agent on every LLM call.
                </div>
                <Button onClick={openNew} className="h-8 bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200 hover:bg-fuchsia-500/30" data-testid="new-policy-btn">
                    <Plus className="w-3.5 h-3.5 mr-1.5" /> New Policy
                </Button>
            </div>

            {loading ? <div className="text-white/50 text-sm">Loading…</div>
                : policies.length === 0 ? (
                    <Card className="bg-black/40 border-white/10 border-dashed">
                        <CardContent className="p-8 text-center text-white/45 text-sm">
                            No policies yet. Add one to enforce custom rules on every LLM response.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid md:grid-cols-2 gap-3">
                        {policies.map((p) => (
                            <Card key={p.id} className="bg-black/40 border-white/10" data-testid={`policy-${p.id}`}>
                                <CardContent className="p-3">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Lock className="w-3.5 h-3.5 text-blue-300" />
                                        <span className="text-sm text-white font-semibold flex-1 truncate">{p.name}</span>
                                        <Badge className={`text-[9px] ${p.severity === 'high' ? 'border-red-500/40 text-red-300' : p.severity === 'medium' ? 'border-amber-500/40 text-amber-300' : 'border-white/15 text-white/55'} bg-black/30 border`}>
                                            {p.severity}
                                        </Badge>
                                        {p.enabled
                                            ? <Eye className="w-3.5 h-3.5 text-emerald-400" />
                                            : <EyeOff className="w-3.5 h-3.5 text-white/40" />}
                                    </div>
                                    <p className="text-[11px] text-white/70 line-clamp-3">{p.rule}</p>
                                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                                        {(p.tags || []).map(t => (
                                            <Badge key={t} className="text-[9px] border-white/15 text-white/55 bg-black/30 border">{t}</Badge>
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-2 mt-2">
                                        <Button size="sm" variant="ghost" className="h-7 text-[11px] text-white/70" onClick={() => openEdit(p)} data-testid={`edit-policy-${p.id}`}>
                                            Edit
                                        </Button>
                                        <Button size="sm" variant="ghost" className="h-7 text-[11px] text-red-300" onClick={() => del(p)} data-testid={`delete-policy-${p.id}`}>
                                            <Trash2 className="w-3 h-3 mr-1" /> Delete
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-2xl" data-testid="policy-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white">{editing?.id ? 'Edit Policy' : 'New Policy'}</DialogTitle>
                        <DialogDescription className="text-white/55">Define a natural-language rule that every AI response must satisfy.</DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <div className="space-y-3">
                            <div className="space-y-1">
                                <Label className="text-xs text-white/60">Name</Label>
                                <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                                       className="bg-black/40 border-white/10 text-white" data-testid="policy-name-input" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs text-white/60">Rule</Label>
                                <Textarea rows={4} value={editing.rule} onChange={(e) => setEditing({ ...editing, rule: e.target.value })}
                                          className="bg-black/40 border-white/10 text-white text-sm" data-testid="policy-rule-input"
                                          placeholder="e.g. The AI must never give specific medical dosage advice." />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs text-white/60">Severity</Label>
                                    <Select value={editing.severity} onValueChange={(v) => setEditing({ ...editing, severity: v })}>
                                        <SelectTrigger className="bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="low">Low</SelectItem>
                                            <SelectItem value="medium">Medium</SelectItem>
                                            <SelectItem value="high">High</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs text-white/60">Tags (comma-sep)</Label>
                                    <Input value={editing.tags} onChange={(e) => setEditing({ ...editing, tags: e.target.value })}
                                           className="bg-black/40 border-white/10 text-white" data-testid="policy-tags-input"
                                           placeholder="safety, legal" />
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <Switch checked={!!editing.enabled} onCheckedChange={(v) => setEditing({ ...editing, enabled: v })} data-testid="policy-enabled-switch" />
                                <span className="text-sm text-white/80">Enabled</span>
                            </div>
                            <div className="flex justify-end gap-2 pt-2">
                                <Button variant="outline" className="border-white/15 text-white/70" onClick={() => setOpen(false)}>Cancel</Button>
                                <Button onClick={save} className="bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200 hover:bg-fuchsia-500/30" data-testid="policy-save-btn">
                                    {editing.id ? 'Update' : 'Create'}
                                </Button>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// QUARANTINE TAB
// ──────────────────────────────────────────────────────────────────────────────
function QuarantineTab({ refreshKey, bumpRefresh }) {
    const [items, setItems] = useState([]);
    const [status, setStatus] = useState('pending');
    const [loading, setLoading] = useState(true);

    const load = () => {
        setLoading(true);
        api(`/api/ai-monitoring/quarantine?status=${status}`)
            .then((d) => setItems(d.items || []))
            .catch((e) => toast.error(`Quarantine load failed: ${e.message}`))
            .finally(() => setLoading(false));
    };
    useEffect(load, [status, refreshKey]);

    const act = async (event_id, action) => {
        try {
            await api(`/api/ai-monitoring/quarantine/${event_id}/${action}`, { method: 'POST' });
            toast.success(`${action === 'release' ? 'Released' : 'Blocked'} successfully`);
            load();
            bumpRefresh();
        } catch (e) {
            toast.error(`${action} failed: ${e.message}`);
        }
    };

    return (
        <div className="space-y-3" data-testid="observability-quarantine">
            <div className="flex items-center justify-between">
                <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger className="w-[160px] h-8 bg-black/40 border-white/10 text-xs" data-testid="quarantine-status-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="released">Released</SelectItem>
                        <SelectItem value="blocked">Blocked</SelectItem>
                        <SelectItem value="all">All</SelectItem>
                    </SelectContent>
                </Select>
                <div className="text-[11px] text-white/55">{items.length} item{items.length !== 1 ? 's' : ''}</div>
            </div>

            {loading ? <div className="text-white/50 text-sm">Loading…</div>
                : items.length === 0 ? (
                    <Card className="bg-black/40 border-white/10 border-dashed">
                        <CardContent className="p-8 text-center text-white/45 text-sm">
                            No items with status “{status}”.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-2">
                        {items.map((q) => (
                            <Card key={q.id} className="bg-black/40 border-white/10" data-testid={`quarantine-${q.id}`}>
                                <CardContent className="p-3">
                                    <div className="flex items-center gap-2 mb-1">
                                        <VerdictBadge status={q.verdict} />
                                        <span className="text-[11px] text-white/40 font-mono">{q.event_id?.slice(0, 8)}…</span>
                                        <span className="text-[11px] text-white/55 truncate">{q.model}</span>
                                        <Badge className={`text-[9px] ml-auto ${q.status === 'pending' ? 'border-amber-500/40 text-amber-300' : q.status === 'released' ? 'border-emerald-500/40 text-emerald-300' : 'border-red-500/40 text-red-300'} bg-black/30 border`}>
                                            {q.status}
                                        </Badge>
                                    </div>
                                    <p className="text-[11px] text-white/55 italic">“{q.preview_input}”</p>
                                    <p className="text-[11px] text-white/80 font-mono mt-1 line-clamp-3 bg-black/30 p-2 rounded">{q.preview_output}</p>
                                    <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                                        {(q.flagged_agents || []).map(a => (
                                            <Badge key={a} className="text-[9px] border-white/15 text-white/65 bg-black/30 border">{a}</Badge>
                                        ))}
                                    </div>
                                    {q.status === 'pending' && (
                                        <div className="flex items-center gap-2 mt-2">
                                            <Button size="sm" className="h-7 text-[11px] bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/25"
                                                    onClick={() => act(q.event_id, 'release')} data-testid={`release-${q.id}`}>
                                                <PlayCircle className="w-3 h-3 mr-1" /> Release
                                            </Button>
                                            <Button size="sm" className="h-7 text-[11px] bg-red-500/15 border border-red-500/40 text-red-200 hover:bg-red-500/25"
                                                    onClick={() => act(q.event_id, 'block')} data-testid={`block-${q.id}`}>
                                                <Lock className="w-3 h-3 mr-1" /> Block
                                            </Button>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// GPU TAB
// ──────────────────────────────────────────────────────────────────────────────
function ProgressBar({ value, colorClass }) {
    const pct = Math.max(0, Math.min(100, value || 0));
    return (
        <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
        </div>
    );
}

function GPUCard({ g }) {
    return (
        <Card className="bg-black/40 border-white/10" data-testid={`gpu-card-${g.host}-${g.gpu_index}`}>
            <CardContent className="p-3 space-y-2.5">
                <div className="flex items-center gap-2">
                    <MemoryStick className="w-4 h-4 text-blue-300 shrink-0" />
                    <div className="min-w-0 flex-1">
                        <div className="text-sm text-white font-semibold truncate">{g.gpu_name || `GPU ${g.gpu_index}`}</div>
                        <div className="text-[10px] text-white/45 truncate">{g.host} · idx {g.gpu_index}</div>
                    </div>
                    <Badge className="text-[9px] uppercase border-white/15 text-white/60 bg-black/30 border">{g.gpu_vendor || 'unknown'}</Badge>
                </div>
                <div className="space-y-1">
                    <div className="flex items-center justify-between text-[10px] text-white/50">
                        <span>Utilization</span><span className="tabular-nums">{(g.utilization_pct ?? 0).toFixed(0)}%</span>
                    </div>
                    <ProgressBar value={g.utilization_pct} colorClass="bg-cyan-400" />
                </div>
                <div className="space-y-1">
                    <div className="flex items-center justify-between text-[10px] text-white/50">
                        <span>Memory</span>
                        <span className="tabular-nums">{(g.memory_used_mb ?? 0).toFixed(0)} / {(g.memory_total_mb ?? 0).toFixed(0)} MB</span>
                    </div>
                    <ProgressBar value={g.memory_pct} colorClass="bg-violet-400" />
                </div>
                <div className="grid grid-cols-3 gap-2 pt-1">
                    <div>
                        <div className="text-[9px] uppercase tracking-widest text-white/40">Temp</div>
                        <div className="text-sm font-semibold text-white tabular-nums">{(g.temperature_c ?? 0).toFixed(0)}°C</div>
                    </div>
                    <div>
                        <div className="text-[9px] uppercase tracking-widest text-white/40">Power</div>
                        <div className="text-sm font-semibold text-white tabular-nums">{(g.power_watts ?? 0).toFixed(0)}W</div>
                    </div>
                    <div>
                        <div className="text-[9px] uppercase tracking-widest text-white/40">Fan</div>
                        <div className="text-sm font-semibold text-white tabular-nums">{(g.fan_pct ?? 0).toFixed(0)}%</div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

function GPUTab({ refreshKey }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        api('/api/ai-monitoring/gpu?hours=1')
            .then((d) => !cancelled && setData(d))
            .catch((e) => toast.error(`GPU load failed: ${e.message}`))
            .finally(() => !cancelled && setLoading(false));
        return () => { cancelled = true; };
    }, [refreshKey]);

    if (loading && !data) {
        return <div className="text-white/50 text-sm" data-testid="observability-gpu-loading">Loading…</div>;
    }

    if (!data?.detected) {
        return (
            <div className="space-y-3" data-testid="observability-gpu">
                <Card className="bg-black/40 border-white/10 border-dashed">
                    <CardContent className="p-8 text-center text-white/45 text-sm">
                        <MemoryStick className="w-8 h-8 mx-auto mb-2 opacity-40" />
                        {data?.not_available_reason || 'No GPU metrics reported yet.'}
                        <br />
                        <span className="text-[11px] text-white/35">
                            Add <code className="text-white/50">gpu</code> to <code className="text-white/50">enabled_plugins</code> in a OneAgent host's agent.yaml (requires nvidia-smi or rocm-smi).
                        </span>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const gpus = data.gpus || [];
    const avgUtil = gpus.reduce((s, g) => s + (g.utilization_pct || 0), 0) / gpus.length;
    const avgTemp = gpus.reduce((s, g) => s + (g.temperature_c || 0), 0) / gpus.length;
    const totalUsed = gpus.reduce((s, g) => s + (g.memory_used_mb || 0), 0);
    const totalMem = gpus.reduce((s, g) => s + (g.memory_total_mb || 0), 0);

    return (
        <div className="space-y-4" data-testid="observability-gpu">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card className="bg-black/40 border-white/10" data-testid="gpu-summary-count">
                    <CardContent className="p-3">
                        <div className="text-[10px] uppercase tracking-widest text-white/40">GPUs</div>
                        <div className="text-xl font-bold text-white tabular-nums mt-0.5">{data.gpu_count}</div>
                    </CardContent>
                </Card>
                <Card className="bg-black/40 border-white/10" data-testid="gpu-summary-utilization">
                    <CardContent className="p-3">
                        <div className="text-[10px] uppercase tracking-widest text-white/40">Avg Utilization</div>
                        <div className="text-xl font-bold text-white tabular-nums mt-0.5">{avgUtil.toFixed(0)}%</div>
                    </CardContent>
                </Card>
                <Card className="bg-black/40 border-white/10" data-testid="gpu-summary-temp">
                    <CardContent className="p-3">
                        <div className="text-[10px] uppercase tracking-widest text-white/40">Avg Temp</div>
                        <div className="text-xl font-bold text-white tabular-nums mt-0.5">{avgTemp.toFixed(0)}°C</div>
                    </CardContent>
                </Card>
                <Card className="bg-black/40 border-white/10" data-testid="gpu-summary-memory">
                    <CardContent className="p-3">
                        <div className="text-[10px] uppercase tracking-widest text-white/40">Memory</div>
                        <div className="text-xl font-bold text-white tabular-nums mt-0.5">{(totalUsed / 1024).toFixed(1)} / {(totalMem / 1024).toFixed(1)}GB</div>
                    </CardContent>
                </Card>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                {gpus.map((g) => <GPUCard key={`${g.host}-${g.gpu_index}`} g={g} />)}
            </div>
        </div>
    );
}

// ──────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ──────────────────────────────────────────────────────────────────────────────
export default function AIObservabilityPage() {
    const location = useLocation();
    const navigate = useNavigate();
    const initialTab = new URLSearchParams(location.search).get('tab') || 'overview';
    const [tab, setTab] = useState(initialTab);
    const [refreshKey, setRefreshKey] = useState(0);
    const bumpRefresh = () => setRefreshKey(k => k + 1);
    const [health, setHealth] = useState(null);

    useEffect(() => {
        api('/api/ai-monitoring/health').then(setHealth).catch(() => {});
    }, [refreshKey]);

    useEffect(() => {
        const search = new URLSearchParams(location.search);
        const t = search.get('tab') || 'overview';
        setTab(t);
    }, [location.search]);

    const onTabChange = (t) => {
        setTab(t);
        const search = new URLSearchParams(location.search);
        search.set('tab', t);
        navigate({ pathname: '/ai-observability', search: search.toString() }, { replace: true });
    };

    return (
        <div className="p-4 md:p-6 space-y-4 max-w-[1600px] mx-auto" data-testid="ai-observability-page">
            {/* Hero */}
            <div className="rounded-md border border-fuchsia-500/30 bg-gradient-to-br from-fuchsia-500/[0.07] via-black/40 to-black/40 p-4">
                <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-md border border-fuchsia-500/40 bg-black/40 flex items-center justify-center">
                        <Radio className="w-5 h-5 text-fuchsia-300" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h1 className="text-lg md:text-xl font-bold text-white">AI Observability Center</h1>
                        <p className="text-[12px] text-white/55">
                            10 specialized agents watching every LLM call · live websocket feed · admin policies · quarantine queue
                        </p>
                    </div>
                    <Button variant="outline" size="sm" className="h-8 border-white/15 text-white/70 hover:text-white" onClick={bumpRefresh} data-testid="refresh-btn">
                        <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                    </Button>
                </div>
                {health && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
                        <Card className="bg-black/40 border-white/10" data-testid="kpi-total-events"><CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Total Events</div>
                            <div className="text-base font-bold text-white">{health.events_total?.toLocaleString?.() || 0}</div>
                        </CardContent></Card>
                        <Card className="bg-black/40 border-white/10" data-testid="kpi-active-agents"><CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Active Agents</div>
                            <div className="text-base font-bold text-white">{(health.agents || []).length}</div>
                        </CardContent></Card>
                        <Card className="bg-black/40 border-white/10" data-testid="kpi-active-policies"><CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Active Policies</div>
                            <div className="text-base font-bold text-white">{health.active_policies ?? 0}</div>
                        </CardContent></Card>
                        <Card className="bg-black/40 border-white/10" data-testid="kpi-pending-quarantine"><CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Pending Quarantine</div>
                            <div className="text-base font-bold text-white">{health.pending_quarantine ?? 0}</div>
                        </CardContent></Card>
                        <Card className="bg-black/40 border-white/10" data-testid="kpi-live-subscribers"><CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Live Subscribers</div>
                            <div className="text-base font-bold text-white">{health.live_subscribers ?? 0}</div>
                        </CardContent></Card>
                    </div>
                )}
            </div>

            <Tabs value={tab} onValueChange={onTabChange}>
                <TabsList className="bg-black/40 border border-white/10">
                    <TabsTrigger value="overview" data-testid="tab-overview"><Activity className="w-3.5 h-3.5 mr-1.5" />Overview</TabsTrigger>
                    <TabsTrigger value="agents" data-testid="tab-agents"><Cpu className="w-3.5 h-3.5 mr-1.5" />Agents</TabsTrigger>
                    <TabsTrigger value="gpu" data-testid="tab-gpu"><MemoryStick className="w-3.5 h-3.5 mr-1.5" />GPU</TabsTrigger>
                    <TabsTrigger value="live" data-testid="tab-live"><Radio className="w-3.5 h-3.5 mr-1.5" />Live Feed</TabsTrigger>
                    <TabsTrigger value="log-analyzer" data-testid="tab-log-analyzer"><Terminal className="w-3.5 h-3.5 mr-1.5" />Log Analyzer</TabsTrigger>
                    <TabsTrigger value="policies" data-testid="tab-policies"><Lock className="w-3.5 h-3.5 mr-1.5" />Policies</TabsTrigger>
                    <TabsTrigger value="quarantine" data-testid="tab-quarantine"><ShieldAlert className="w-3.5 h-3.5 mr-1.5" />Quarantine</TabsTrigger>
                </TabsList>
                <TabsContent value="overview" className="mt-4"><OverviewTab refreshKey={refreshKey} /></TabsContent>
                <TabsContent value="agents" className="mt-4"><AgentsTab refreshKey={refreshKey} /></TabsContent>
                <TabsContent value="gpu" className="mt-4"><GPUTab refreshKey={refreshKey} /></TabsContent>
                <TabsContent value="live" className="mt-4"><LiveFeedTab /></TabsContent>
                <TabsContent value="log-analyzer" className="mt-4"><LogAnalyzerTab /></TabsContent>
                <TabsContent value="policies" className="mt-4"><PoliciesTab refreshKey={refreshKey} bumpRefresh={bumpRefresh} /></TabsContent>
                <TabsContent value="quarantine" className="mt-4"><QuarantineTab refreshKey={refreshKey} bumpRefresh={bumpRefresh} /></TabsContent>
            </Tabs>
        </div>
    );
}
