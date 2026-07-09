import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import {
    BrainCircuit, ShieldAlert, DollarSign, Gauge, Sparkles, Search, RefreshCw,
    CheckCircle2, AlertTriangle, Activity, Zap, Cpu, AlertCircle, ChevronRight, Beaker,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const STATUS_TINT = {
    healthy:  { bg: 'from-emerald-500/[0.10]', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: CheckCircle2 },
    warning:  { bg: 'from-amber-500/[0.10]',   border: 'border-amber-500/40',   text: 'text-amber-300',   icon: AlertTriangle },
    critical: { bg: 'from-red-500/[0.10]',     border: 'border-red-500/40',     text: 'text-red-300',     icon: AlertCircle },
};

const AGENT_META = {
    hallucination: { icon: BrainCircuit, color: 'text-violet-300',  label: 'Hallucination' },
    injection:     { icon: ShieldAlert,  color: 'text-red-300',     label: 'Prompt Injection' },
    cost:          { icon: DollarSign,   color: 'text-amber-300',   label: 'Cost' },
    performance:   { icon: Gauge,        color: 'text-cyan-300',    label: 'Performance' },
    quality:       { icon: Sparkles,     color: 'text-emerald-300', label: 'Quality' },
};

function StatTile({ icon: Icon, label, value, sub, tint = 'cyan' }) {
    const tints = {
        cyan: 'border-cyan-500/30 text-cyan-300',
        emerald: 'border-emerald-500/30 text-emerald-300',
        amber: 'border-amber-500/30 text-amber-300',
        red: 'border-red-500/30 text-red-300',
        violet: 'border-violet-500/30 text-violet-300',
        white: 'border-white/15 text-white',
    };
    return (
        <Card className={`bg-black/40 border ${tints[tint] || tints.cyan}`}>
            <CardContent className="p-3 flex items-center gap-3">
                <Icon className={`w-5 h-5 ${tints[tint]?.split(' ')[1] || 'text-cyan-300'}`} />
                <div className="flex-1 min-w-0">
                    <div className="text-[10px] uppercase tracking-widest text-white/40">{label}</div>
                    <div className="text-lg font-bold text-white tabular-nums">{value}</div>
                    {sub && <div className="text-[10px] text-white/50 truncate">{sub}</div>}
                </div>
            </CardContent>
        </Card>
    );
}

function VerdictBadge({ status }) {
    const t = STATUS_TINT[status] || STATUS_TINT.healthy;
    const Icon = t.icon;
    return (
        <Badge className={`text-[10px] uppercase tracking-wider ${t.text} bg-black/30 border ${t.border}`}>
            <Icon className="w-3 h-3 mr-1" /> {status}
        </Badge>
    );
}

function EvaluateDialog({ onClose, onDone }) {
    const [form, setForm] = useState({
        user_input: 'What was the population of Tokyo in 2024?',
        ai_output: 'Tokyo had exactly 18.7 million residents on Feb 12, 2024, per the city census released that morning.',
        context: '',
        model: 'claude-sonnet-4-5-20250929',
        latency_ms: 1200,
        source: 'manual',
    });
    const [busy, setBusy] = useState(false);

    const run = async () => {
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/ai-monitoring/evaluate`, {
                method: 'POST',
                headers: headers(),
                body: JSON.stringify(form),
            });
            if (!r.ok) throw new Error(await r.text());
            const d = await r.json();
            toast.success(`Verdict: ${d.verdict.system_status} · ${d.agents.length} agents ran`);
            onDone && onDone(d);
            onClose();
        } catch (e) {
            toast.error(e.message?.slice(0, 200) || 'Evaluate failed');
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-2xl" data-testid="evaluate-dialog">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-white">
                        <Beaker className="w-5 h-5 text-violet-300" /> Run a 6-Agent Evaluation
                    </DialogTitle>
                    <DialogDescription className="text-white/60 text-xs">
                        Submit any user-input / AI-output pair to see what the monitoring stack flags.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    <div>
                        <Label className="text-[11px] text-white/60">User input</Label>
                        <Textarea rows={3} value={form.user_input} onChange={(e) => setForm({ ...form, user_input: e.target.value })} className="bg-black/40 border-white/10 mt-1" data-testid="eval-input" />
                    </div>
                    <div>
                        <Label className="text-[11px] text-white/60">AI output</Label>
                        <Textarea rows={4} value={form.ai_output} onChange={(e) => setForm({ ...form, ai_output: e.target.value })} className="bg-black/40 border-white/10 mt-1" data-testid="eval-output" />
                    </div>
                    <div className="grid md:grid-cols-3 gap-3">
                        <div>
                            <Label className="text-[11px] text-white/60">Model</Label>
                            <Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} className="bg-black/40 border-white/10 mt-1 text-xs" />
                        </div>
                        <div>
                            <Label className="text-[11px] text-white/60">Latency (ms)</Label>
                            <Input type="number" value={form.latency_ms} onChange={(e) => setForm({ ...form, latency_ms: Number(e.target.value) })} className="bg-black/40 border-white/10 mt-1 text-xs" />
                        </div>
                        <div>
                            <Label className="text-[11px] text-white/60">Source tag</Label>
                            <Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="bg-black/40 border-white/10 mt-1 text-xs" />
                        </div>
                    </div>
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-white/10">
                    <Button variant="outline" onClick={onClose} className="border-white/15 text-white/80">Cancel</Button>
                    <Button onClick={run} disabled={busy} className="bg-violet-500/[0.18] border border-violet-500/40 text-violet-200" data-testid="eval-run">
                        {busy ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
                        Run 6-Agent Evaluation
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

function EventDetailDialog({ event, onClose }) {
    if (!event) return null;
    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-4xl max-h-[88vh] overflow-hidden flex flex-col" data-testid="event-detail">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-white">
                        <VerdictBadge status={event.verdict?.system_status} />
                        <span className="font-mono text-[11px] text-white/40">{event.id?.slice(0, 8)}…</span>
                        <span className="text-white/70 text-sm font-normal">{event.model || event.provider}</span>
                    </DialogTitle>
                    <DialogDescription className="text-white/55 text-[11px]">
                        {event.received_at} · source={event.source} · {event.tokens_total} tokens · ${(event.estimated_cost_usd || 0).toFixed(5)} · {event.latency_ms?.toFixed(0)}ms
                    </DialogDescription>
                </DialogHeader>

                <ScrollArea className="flex-1 pr-3 mt-2">
                    <div className="space-y-3">
                        {/* I/O */}
                        <div className="grid md:grid-cols-2 gap-3">
                            <Card className="bg-black/40 border-white/10">
                                <CardContent className="p-3">
                                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">User Input</div>
                                    <pre className="text-[11px] text-white/80 font-mono whitespace-pre-wrap leading-relaxed">{event.user_input || '(empty)'}</pre>
                                </CardContent>
                            </Card>
                            <Card className="bg-black/40 border-white/10">
                                <CardContent className="p-3">
                                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">AI Output</div>
                                    <pre className="text-[11px] text-white/80 font-mono whitespace-pre-wrap leading-relaxed">{event.ai_output || '(empty)'}</pre>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Verdict */}
                        <Card className="bg-gradient-to-br from-violet-500/[0.05] via-black/40 to-black/40 border-violet-500/30">
                            <CardContent className="p-4 space-y-2">
                                <div className="flex items-center gap-2">
                                    <Sparkles className="w-4 h-4 text-violet-300" />
                                    <span className="text-sm font-semibold text-white">Aggregated Verdict</span>
                                    <VerdictBadge status={event.verdict?.system_status} />
                                </div>
                                {event.verdict?.priority_issues?.length > 0 && (
                                    <div>
                                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Priority issues</div>
                                        <ul className="space-y-1">
                                            {event.verdict.priority_issues.map((i, idx) => (
                                                <li key={idx} className="text-[12px] text-white/85 flex items-start gap-1.5">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-violet-400/70 shrink-0" />
                                                    <span>{i}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {event.verdict?.recommended_actions?.length > 0 && (
                                    <div>
                                        <div className="text-[10px] uppercase tracking-widest text-cyan-300/80 mb-1">Recommended actions</div>
                                        <ul className="space-y-1">
                                            {event.verdict.recommended_actions.map((a, idx) => (
                                                <li key={idx} className="text-[12px] text-white/85 flex items-start gap-1.5">
                                                    <Zap className="w-3 h-3 mt-0.5 text-cyan-400/70 shrink-0" />
                                                    <span>{a}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Root cause */}
                        {event.root_cause && (
                            <Card className="bg-amber-500/[0.04] border-amber-500/30">
                                <CardContent className="p-3 space-y-1">
                                    <div className="text-[10px] uppercase tracking-widest text-amber-300/80">Root Cause Analysis ({event.root_cause.confidence})</div>
                                    <p className="text-[13px] text-white/85"><strong className="text-amber-200">{event.root_cause.category}:</strong> {event.root_cause.root_cause}</p>
                                    {event.root_cause.fixes?.length > 0 && (
                                        <ul className="mt-1 space-y-1">
                                            {event.root_cause.fixes.map((f, i) => (
                                                <li key={i} className="text-[12px] text-white/75 flex items-start gap-1.5">
                                                    <ChevronRight className="w-3 h-3 mt-0.5 text-amber-400/70 shrink-0" />
                                                    <span>{f}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Per-agent breakdown */}
                        <div className="grid md:grid-cols-2 gap-3">
                            {(event.agents || []).map((a) => {
                                const meta = AGENT_META[a.agent] || { icon: Activity, color: 'text-white/60', label: a.agent };
                                const Icon = meta.icon;
                                return (
                                    <Card key={a.agent} className="bg-black/40 border-white/10" data-testid={`agent-${a.agent}`}>
                                        <CardContent className="p-3 space-y-1.5">
                                            <div className="flex items-center gap-2">
                                                <Icon className={`w-4 h-4 ${meta.color}`} />
                                                <span className="text-sm font-semibold text-white">{meta.label}</span>
                                                {a.severity && (
                                                    <Badge className={`text-[9px] ml-auto bg-black/30 border ${a.severity === 'high' ? 'border-red-500/40 text-red-300' : a.severity === 'medium' ? 'border-amber-500/40 text-amber-300' : 'border-white/15 text-white/60'}`}>
                                                        {a.severity}
                                                    </Badge>
                                                )}
                                            </div>
                                            <pre className="text-[11px] text-white/70 font-mono whitespace-pre-wrap">
{JSON.stringify(a, null, 2).slice(0, 600)}
                                            </pre>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </div>
                </ScrollArea>
            </DialogContent>
        </Dialog>
    );
}

export default function AIMonitoringPage() {
    const [dash, setDash] = useState(null);
    const [events, setEvents] = useState([]);
    const [filter, setFilter] = useState({ status: '', hours: 24 });
    const [loading, setLoading] = useState(true);
    const [showEval, setShowEval] = useState(false);
    const [activeEvent, setActiveEvent] = useState(null);

    const load = async () => {
        setLoading(true);
        try {
            const [d, e] = await Promise.all([
                fetch(`${API}/api/ai-monitoring/dashboard?hours=${filter.hours}`, { headers: headers() }).then((r) => r.json()),
                fetch(`${API}/api/ai-monitoring/events?hours=${filter.hours}&limit=100${filter.status ? `&status=${filter.status}` : ''}`, { headers: headers() }).then((r) => r.json()),
            ]);
            setDash(d);
            setEvents(e.events || []);
        } catch {
            toast.error('Failed to load AI monitoring data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter.hours, filter.status]);

    const totals = dash?.totals || {};
    const healthScore = totals.events ? Math.round((totals.healthy / totals.events) * 100) : null;

    return (
        <div className="p-6 space-y-5 max-w-7xl" data-testid="ai-monitoring-page">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <BrainCircuit className="w-6 h-6 text-violet-300" />
                        AI Monitoring · Multi-Agent
                    </h1>
                    <p className="text-sm text-white/55 mt-1">
                        6 specialized agents watch every LLM call: hallucination · prompt injection · cost · performance · quality · RCA.
                    </p>
                </div>
                <div className="flex gap-2 flex-wrap">
                    <select
                        value={filter.hours}
                        onChange={(e) => setFilter({ ...filter, hours: Number(e.target.value) })}
                        className="bg-black/40 border border-white/10 rounded-md px-3 py-2 text-xs text-white/85"
                        data-testid="filter-hours"
                    >
                        <option value={1}>Last 1h</option>
                        <option value={6}>Last 6h</option>
                        <option value={24}>Last 24h</option>
                        <option value={168}>Last 7d</option>
                        <option value={720}>Last 30d</option>
                    </select>
                    <select
                        value={filter.status}
                        onChange={(e) => setFilter({ ...filter, status: e.target.value })}
                        className="bg-black/40 border border-white/10 rounded-md px-3 py-2 text-xs text-white/85"
                        data-testid="filter-status"
                    >
                        <option value="">All verdicts</option>
                        <option value="healthy">Healthy only</option>
                        <option value="warning">Warning only</option>
                        <option value="critical">Critical only</option>
                    </select>
                    <Button onClick={load} variant="outline" className="border-white/15 text-white/80" data-testid="refresh-btn">
                        <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button onClick={() => setShowEval(true)} className="bg-violet-500/[0.18] border border-violet-500/40 text-violet-200" data-testid="evaluate-btn">
                        <Beaker className="w-3.5 h-3.5 mr-1.5" /> Run Evaluation
                    </Button>
                </div>
            </div>

            {/* Top stat strip */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                <StatTile icon={Activity} label="Events" value={totals.events ?? 0} sub={`${filter.hours}h window`} tint="white" />
                <StatTile icon={CheckCircle2} label="Health %" value={healthScore != null ? `${healthScore}%` : '—'} sub={`${totals.healthy ?? 0} healthy`} tint="emerald" />
                <StatTile icon={AlertTriangle} label="Warning" value={totals.warning ?? 0} tint="amber" />
                <StatTile icon={AlertCircle} label="Critical" value={totals.critical ?? 0} tint="red" />
                <StatTile icon={DollarSign} label="Tokens" value={Number(dash?.tokens?.total || 0).toLocaleString()} sub={`$${(dash?.tokens?.cost_usd || 0).toFixed(4)}`} tint="amber" />
                <StatTile icon={Gauge} label="Avg Latency" value={`${dash?.performance?.avg_latency_ms ?? 0}ms`} sub={`max ${dash?.performance?.max_latency_ms ?? 0}ms`} tint="cyan" />
                <StatTile icon={ShieldAlert} label="Errored" value={dash?.performance?.errored_count ?? 0} tint={dash?.performance?.errored_count ? 'red' : 'white'} />
            </div>

            <Tabs defaultValue="events" className="space-y-3">
                <TabsList className="bg-black/40 border border-white/10">
                    <TabsTrigger value="events" data-testid="tab-events">Events</TabsTrigger>
                    <TabsTrigger value="agents" data-testid="tab-agents">Agent Flags</TabsTrigger>
                    <TabsTrigger value="models" data-testid="tab-models">By Model</TabsTrigger>
                </TabsList>

                <TabsContent value="events">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-0">
                            <div className="px-4 py-2.5 border-b border-white/10 text-[11px] uppercase tracking-widest text-white/40 flex items-center gap-2">
                                <Activity className="w-3 h-3" /> {events.length} events · click any to inspect
                            </div>
                            <ScrollArea className="max-h-[60vh]">
                                <table className="w-full text-[12px]">
                                    <thead className="text-[10px] uppercase text-white/40">
                                        <tr className="border-b border-white/5">
                                            <th className="text-left px-3 py-2">Time</th>
                                            <th className="text-left px-3 py-2">Verdict</th>
                                            <th className="text-left px-3 py-2">Source</th>
                                            <th className="text-left px-3 py-2">Model</th>
                                            <th className="text-right px-3 py-2">Tokens</th>
                                            <th className="text-right px-3 py-2">Latency</th>
                                            <th className="text-left px-3 py-2">Flags</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {events.length === 0 && (
                                            <tr><td colSpan={7} className="text-center py-10 text-white/40 text-xs">No events in window. Run an evaluation to seed data.</td></tr>
                                        )}
                                        {events.map((e) => (
                                            <tr
                                                key={e.id}
                                                className="border-b border-white/5 hover:bg-white/[0.03] cursor-pointer"
                                                onClick={() => setActiveEvent(e)}
                                                data-testid={`event-row-${e.id}`}
                                            >
                                                <td className="px-3 py-2 text-white/50 font-mono text-[11px]">{(e.received_at || '').slice(11, 19)}</td>
                                                <td className="px-3 py-2"><VerdictBadge status={e.verdict?.system_status} /></td>
                                                <td className="px-3 py-2 text-white/70 text-[11px]">{e.source}</td>
                                                <td className="px-3 py-2 text-white/70 text-[11px] truncate max-w-[200px]">{e.model || e.provider}</td>
                                                <td className="px-3 py-2 text-right text-white/80 tabular-nums">{e.tokens_total}</td>
                                                <td className="px-3 py-2 text-right text-white/80 tabular-nums">{Math.round(e.latency_ms || 0)}ms</td>
                                                <td className="px-3 py-2">
                                                    <div className="flex gap-1 flex-wrap">
                                                        {(e.agents || []).filter((a) => {
                                                            if (a.agent === 'hallucination') return a.hallucination_detected || (a.risk_score || 0) >= 60;
                                                            if (a.agent === 'injection') return a.is_attack;
                                                            if (a.agent === 'cost') return a.anomaly_detected;
                                                            if (a.agent === 'performance') return a.performance_issue && a.severity !== 'low';
                                                            if (a.agent === 'quality') return (a.quality_score || 10) <= 4;
                                                            return false;
                                                        }).map((a) => {
                                                            const meta = AGENT_META[a.agent];
                                                            const Icon = meta?.icon || Activity;
                                                            return (
                                                                <Badge key={a.agent} className={`text-[9px] bg-black/30 border ${a.severity === 'high' ? 'border-red-500/40 text-red-300' : 'border-amber-500/30 text-amber-300'}`}>
                                                                    <Icon className="w-2.5 h-2.5 mr-0.5" /> {a.agent}
                                                                </Badge>
                                                            );
                                                        })}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </ScrollArea>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="agents">
                    <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-3">
                        {Object.entries(AGENT_META).map(([key, meta]) => {
                            const Icon = meta.icon;
                            const count = dash?.by_agent?.[key] || 0;
                            return (
                                <Card key={key} className="bg-black/40 border-white/10" data-testid={`agent-tile-${key}`}>
                                    <CardContent className="p-4 space-y-2">
                                        <div className="flex items-center gap-2">
                                            <Icon className={`w-4 h-4 ${meta.color}`} />
                                            <span className="text-sm font-semibold text-white">{meta.label}</span>
                                        </div>
                                        <div className="text-3xl font-bold text-white tabular-nums">{count}</div>
                                        <div className="text-[10px] uppercase tracking-widest text-white/40">flagged in window</div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </TabsContent>

                <TabsContent value="models">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-0">
                            <table className="w-full text-[12px]">
                                <thead className="text-[10px] uppercase text-white/40">
                                    <tr className="border-b border-white/5">
                                        <th className="text-left px-3 py-2">Model</th>
                                        <th className="text-right px-3 py-2">Calls</th>
                                        <th className="text-right px-3 py-2">Tokens</th>
                                        <th className="text-right px-3 py-2">Cost (USD)</th>
                                        <th className="text-right px-3 py-2">Avg Latency</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(dash?.by_model || []).length === 0 && (
                                        <tr><td colSpan={5} className="text-center py-10 text-white/40 text-xs">No data yet.</td></tr>
                                    )}
                                    {(dash?.by_model || []).map((m) => (
                                        <tr key={m.model} className="border-b border-white/5">
                                            <td className="px-3 py-2 text-white/85 font-mono text-[11px]">{m.model}</td>
                                            <td className="px-3 py-2 text-right text-white/80 tabular-nums">{m.count}</td>
                                            <td className="px-3 py-2 text-right text-white/80 tabular-nums">{m.tokens.toLocaleString()}</td>
                                            <td className="px-3 py-2 text-right text-white/80 tabular-nums">${m.cost_usd.toFixed(4)}</td>
                                            <td className="px-3 py-2 text-right text-white/80 tabular-nums">{m.avg_latency_ms}ms</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {showEval && <EvaluateDialog onClose={() => setShowEval(false)} onDone={() => load()} />}
            {activeEvent && <EventDetailDialog event={activeEvent} onClose={() => setActiveEvent(null)} />}
        </div>
    );
}
