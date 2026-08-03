import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Sparkles, Send, RefreshCw, ArrowRight, Network, TrendingUp, Search,
    ScrollText, ShieldCheck, ExternalLink, ChevronRight, Zap, Database,
    Brain, CheckCircle2, XCircle, Play,
} from 'lucide-react';
import { AgenticWorkflowLogoFull } from '../components/AgenticWorkflowLogo';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const ROUTE_META = {
    copilot: { label: 'Copilot', color: 'cyan' },
    diagnoser: { label: 'Diagnoser', color: 'violet' },
    forecaster: { label: 'Forecaster', color: 'amber' },
    blast_radius: { label: 'Blast Radius', color: 'rose' },
    memory: { label: 'Incident Memory', color: 'emerald' },
};

const COLOR_CLS = {
    cyan: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    violet: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    rose: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
};

const DIAGNOSER_PIPELINE_STAGES = [
    { agent: 'diagnoser', stage: 'start', label: 'Diagnoser', icon: Zap },
    { agent: 'diagnoser', stage: 'gather_evidence', label: 'Gather Evidence', icon: Search },
    { agent: 'diagnoser', stage: 'search_memory', label: 'Search Memory', icon: Database },
    { agent: 'diagnoser', stage: 'llm_rank', label: 'Propose Hypotheses', icon: Brain },
    { agent: 'diagnoser', stage: 'validate', label: 'Judge — Validate', icon: ShieldCheck },
    { agent: 'diagnoser', stage: 'done', label: 'Complete', icon: CheckCircle2 },
];

// Real tool calls incident_analysis() makes in parallel (see
// agentic_workflow_service.py's tool_trace fan-out emit) — not fabricated
// sub-agents, just friendlier labels for what actually ran.
const TOOL_LABELS = {
    get_logs: 'Logs',
    get_metrics: 'Metrics',
    get_traces: 'Traces',
    get_deployments: 'Deploys',
    get_incidents: 'Incidents',
    get_agent_status: 'Agent Health',
};

function stageStatus(events, agent, stage) {
    const matches = events.filter((e) => e.agent === agent && e.stage === stage);
    if (matches.length === 0) return { status: 'pending', event: null };
    const latest = matches[matches.length - 1];
    const status = latest.status === 'running' ? 'running' : latest.status === 'error' ? 'error' : 'done';
    return { status, event: latest };
}

function PipelineNode({ def, statusInfo, isLast }) {
    const Icon = def.icon;
    const { status, event } = statusInfo;
    const ringCls = {
        pending: 'border-white/15 text-white/30 bg-black/30',
        running: 'border-cyan-400 text-cyan-300 bg-cyan-500/10 animate-pulse',
        done: 'border-emerald-500/50 text-emerald-300 bg-emerald-500/10',
        error: 'border-red-500/50 text-red-300 bg-red-500/10',
    }[status];

    return (
        <div className="flex items-center flex-1 min-w-0">
            <div className="flex flex-col items-center gap-1.5 shrink-0">
                <div className={`w-11 h-11 rounded-full border-2 flex items-center justify-center ${ringCls}`}>
                    {status === 'done' ? <CheckCircle2 className="w-5 h-5" /> : status === 'error' ? <XCircle className="w-5 h-5" /> : <Icon className="w-4 h-4" />}
                </div>
                <span className={`text-[10px] text-center max-w-[86px] ${status === 'pending' ? 'text-white/30' : 'text-white/70'}`}>{def.label}</span>
                {event?.duration_ms !== undefined && event?.duration_ms !== null && (
                    <span className="text-[9px] text-white/35 tabular-nums">{event.duration_ms}ms</span>
                )}
            </div>
            {!isLast && <div className={`h-0.5 flex-1 mx-1 ${status === 'done' ? 'bg-emerald-500/40' : 'bg-white/10'}`} />}
        </div>
    );
}

function ToolFanOut({ events }) {
    // Every distinct `agent === "tool"` event seen so far, in arrival order —
    // this is the real parallel fan-out inside incident_analysis(), surfaced
    // as it actually reports in, not a fixed pre-drawn list.
    const toolEvents = events.filter((e) => e.agent === 'tool');
    if (toolEvents.length === 0) return null;

    return (
        <div className="relative pl-6 -mt-1 mb-1">
            <div className="absolute left-2 top-0 bottom-3 w-px bg-cyan-500/20" />
            <div className="flex flex-wrap gap-1.5">
                {toolEvents.map((ev) => (
                    <motion.div
                        key={ev.stage}
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="flex items-center gap-1 text-[10px] bg-cyan-500/10 border border-cyan-500/25 text-cyan-200 rounded-full px-2 py-0.5"
                    >
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        {TOOL_LABELS[ev.stage] || ev.stage}
                        {ev.detail?.count != null && <span className="text-cyan-300/60">({ev.detail.count})</span>}
                    </motion.div>
                ))}
            </div>
        </div>
    );
}

function LiveDiagnoserPipeline() {
    const [target, setTarget] = useState('');
    const [running, setRunning] = useState(false);
    const [runId, setRunId] = useState(null);
    const [events, setEvents] = useState([]);
    const [finalRun, setFinalRun] = useState(null);
    const abortRef = useRef(null);

    useEffect(() => () => abortRef.current?.abort(), []);

    const streamTrace = async (run_id) => {
        const controller = new AbortController();
        abortRef.current = controller;
        try {
            const token = localStorage.getItem('falconToken');
            const response = await fetch(`${API}/api/agentic-workflow/trace/${run_id}/stream`, {
                headers: { Authorization: `Bearer ${token}` },
                signal: controller.signal,
            });
            if (!response.ok || !response.body) throw new Error('stream unavailable');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let eventName = 'message';

            // eslint-disable-next-line no-constant-condition
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const chunks = buffer.split('\n\n');
                buffer = chunks.pop() || '';
                for (const chunk of chunks) {
                    let data = null;
                    for (const line of chunk.split('\n')) {
                        if (line.startsWith('event:')) eventName = line.slice(6).trim();
                        if (line.startsWith('data:')) data = line.slice(5).trim();
                    }
                    if (!data) continue;
                    try {
                        const payload = JSON.parse(data);
                        if (eventName === 'trace') {
                            setEvents((prev) => [...prev, payload]);
                        } else if (eventName === 'final') {
                            setFinalRun(payload);
                        }
                    } catch (_e) { /* keepalive/non-JSON, ignore */ }
                }
            }
        } catch (e) {
            if (e.name !== 'AbortError') toast.error('Trace stream disconnected');
        } finally {
            setRunning(false);
        }
    };

    const start = async () => {
        if (!target.trim() || running) return;
        setRunning(true);
        setEvents([]);
        setFinalRun(null);
        try {
            const r = await fetch(`${API}/api/agentic-workflow/diagnose/trigger`, {
                method: 'POST', headers: authHeaders(),
                body: JSON.stringify({ service_or_incident: target, hours: 24 }),
            });
            if (!r.ok) throw new Error(await r.text());
            const { run_id } = await r.json();
            setRunId(run_id);
            streamTrace(run_id);
        } catch (e) {
            toast.error(`Failed to start diagnoser: ${e.message?.slice(0, 200)}`);
            setRunning(false);
        }
    };

    const errored = finalRun?.status === 'error' || events.some((e) => e.status === 'error');
    const hypotheses = finalRun?.result?.hypotheses || [];

    return (
        <Card className="bg-black/40 border-cyan-500/20" data-testid="live-diagnoser-pipeline">
            <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-base flex items-center gap-2 text-white">
                    <Play className="w-4 h-4 text-cyan-400" /> Live Agent Pipeline — Diagnoser
                </CardTitle>
                <p className="text-[12px] text-white/50">
                    Watch the Diagnoser run in real time — every stage below is a real, timestamped step from the
                    actual execution, not a scripted animation.
                </p>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
                <div className="flex gap-2">
                    <Input
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && start()}
                        placeholder="service name or incident id"
                        className="bg-black/40 border-white/10 text-white"
                        disabled={running}
                        data-testid="live-pipeline-input"
                    />
                    <Button onClick={start} disabled={running || !target.trim()} className="bg-cyan-600 hover:bg-cyan-700" data-testid="live-pipeline-run">
                        {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : (<><Play className="w-4 h-4 mr-1.5" /> Run Live</>)}
                    </Button>
                </div>

                {runId && (
                    <>
                        <div className="flex items-center py-2 overflow-x-auto">
                            {DIAGNOSER_PIPELINE_STAGES.map((def, i) => (
                                <PipelineNode
                                    key={def.stage}
                                    def={def}
                                    statusInfo={stageStatus(events, def.agent, def.stage)}
                                    isLast={i === DIAGNOSER_PIPELINE_STAGES.length - 1}
                                />
                            ))}
                        </div>

                        {/* Real parallel fan-out: incident_analysis() ran these seven tool
                            calls in one asyncio.gather() — this row fills in as each one's
                            trace event arrives, exactly like Trace/Logs/Net agents branching
                            off a Planner in a classic multi-agent diagram, except every node
                            here corresponds to a call that actually executed. */}
                        <ToolFanOut events={events} />

                        {errored && (
                            <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded p-2">
                                {finalRun?.error || 'The run failed — see the trace log below for the last successful step.'}
                            </div>
                        )}

                        <div className="bg-black/60 border border-white/10 rounded-lg max-h-56 overflow-y-auto p-2 space-y-1 font-mono">
                            <AnimatePresence initial={false}>
                                {events.map((ev) => (
                                    <motion.div
                                        key={ev.seq}
                                        initial={{ opacity: 0, y: 6 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="flex items-center gap-2 text-[11px]"
                                    >
                                        <span className={`shrink-0 ${ev.status === 'error' ? 'text-red-400' : ev.agent === 'tool' ? 'text-emerald-400/70' : 'text-cyan-400/70'}`}>
                                            [{ev.agent.toUpperCase()}:{ev.stage.toUpperCase()}]
                                        </span>
                                        <span className="text-white/70 flex-1 truncate">{ev.title}</span>
                                        {ev.duration_ms != null && <span className="text-white/35 tabular-nums shrink-0">{ev.duration_ms}ms</span>}
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                            {events.length === 0 && <div className="text-[11px] text-white/30 p-1">Waiting for the first step…</div>}
                        </div>

                        {hypotheses.length > 0 && (
                            <div className="space-y-2">
                                <p className="text-[11px] text-white/40 uppercase tracking-wide">Result — Ranked Hypotheses</p>
                                {hypotheses.map((h) => (
                                    <div key={h.rank} className="bg-black/30 border border-white/10 rounded-lg p-3">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge className="text-[10px] bg-violet-500/15 text-violet-300 border border-violet-500/30">#{h.rank}</Badge>
                                            <span className="text-sm text-white/90 flex-1">{h.root_cause}</span>
                                            <span className="text-[11px] text-white/50 tabular-nums">{Math.round(h.confidence * 100)}%</span>
                                        </div>
                                        {h.evidence?.length > 0 && (
                                            <ul className="pl-1 space-y-0.5">
                                                {h.evidence.slice(0, 3).map((e, i) => <li key={i} className="text-[11px] text-white/50">• {e}</li>)}
                                            </ul>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    );
}

function AskAnything() {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [response, setResponse] = useState(null);

    const ask = async () => {
        if (!query.trim()) return;
        setLoading(true);
        setResponse(null);
        try {
            const r = await fetch(`${API}/api/agentic-workflow/ask`, {
                method: 'POST', headers: authHeaders(), body: JSON.stringify({ query }),
            });
            if (!r.ok) throw new Error(await r.text());
            setResponse(await r.json());
        } catch (e) {
            toast.error(`Ask failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setLoading(false);
        }
    };

    const routeMeta = response ? (ROUTE_META[response.routed_to] || ROUTE_META.copilot) : null;
    const result = response?.result;
    const summary = result?.summary
        || (result?.hypotheses?.[0]?.root_cause)
        || (result?.risk_assessment?.message)
        || (result?.similar_incidents?.length ? `${result.similar_incidents.length} similar incident(s) found` : null);
    const evidence = result?.evidence || result?.hypotheses?.[0]?.evidence || [];

    return (
        <Card className="bg-black/40 border-white/10" data-testid="ask-anything-card">
            <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-base flex items-center gap-2 text-white">
                    <Sparkles className="w-4 h-4 text-cyan-400" /> Ask the Supervisor
                </CardTitle>
                <p className="text-[12px] text-white/50">
                    Ask anything — the Supervisor classifies your question and routes it to the right specialist automatically.
                </p>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
                <div className="flex gap-2">
                    <Input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && ask()}
                        placeholder="e.g. Why is payment-api slow? / Blast radius of checkout-service / Have we seen this before?"
                        className="bg-black/40 border-white/10 text-white"
                        data-testid="ask-anything-input"
                    />
                    <Button onClick={ask} disabled={loading || !query.trim()} className="bg-cyan-600 hover:bg-cyan-700" data-testid="ask-anything-submit">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </Button>
                </div>

                {response && (
                    <div className="bg-black/30 border border-white/10 rounded-lg p-4 space-y-2" data-testid="ask-anything-result">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={`text-[10px] border ${COLOR_CLS[routeMeta.color]}`}>
                                routed to {routeMeta.label}
                            </Badge>
                            <span className="text-[11px] text-white/35">{response.classification?.reason}</span>
                        </div>
                        <p className="text-sm text-white/90">{summary || 'No summary available.'}</p>
                        {evidence.length > 0 && (
                            <ul className="space-y-1">
                                {evidence.slice(0, 5).map((e, i) => (
                                    <li key={i} className="text-xs text-white/60 flex items-start gap-1.5">
                                        <span className="text-cyan-400 mt-0.5">•</span>{typeof e === 'string' ? e : JSON.stringify(e)}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

function DiagnoserCard() {
    const [target, setTarget] = useState('');
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState(null);

    const run = async () => {
        if (!target.trim()) return;
        setLoading(true);
        setData(null);
        try {
            const r = await fetch(`${API}/api/agentic-workflow/diagnose/${encodeURIComponent(target)}`, { headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            setData(await r.json());
        } catch (e) {
            toast.error(`Diagnose failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card className="bg-black/40 border-white/10" data-testid="diagnoser-card">
            <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-base flex items-center gap-2 text-white">
                    <Search className="w-4 h-4 text-violet-400" /> Diagnoser — Ranked Root-Cause Hypotheses
                </CardTitle>
                <p className="text-[12px] text-white/50">Never a single answer — competing hypotheses, ranked by confidence, each with its own evidence.</p>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
                <div className="flex gap-2">
                    <Input value={target} onChange={(e) => setTarget(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && run()}
                        placeholder="service name or incident id" className="bg-black/40 border-white/10 text-white" data-testid="diagnoser-input" />
                    <Button onClick={run} disabled={loading || !target.trim()} variant="outline" data-testid="diagnoser-submit">
                        {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Diagnose'}
                    </Button>
                </div>
                {data && (
                    <div className="space-y-2">
                        {(data.hypotheses || []).map((h) => (
                            <div key={h.rank} className="bg-black/30 border border-white/10 rounded-lg p-3" data-testid={`hypothesis-${h.rank}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Badge className="text-[10px] bg-violet-500/15 text-violet-300 border border-violet-500/30">#{h.rank}</Badge>
                                    <span className="text-sm text-white/90 flex-1">{h.root_cause}</span>
                                    <span className="text-[11px] text-white/50 tabular-nums">{Math.round(h.confidence * 100)}%</span>
                                </div>
                                {h.evidence?.length > 0 && (
                                    <ul className="pl-1 space-y-0.5">
                                        {h.evidence.slice(0, 3).map((e, i) => (
                                            <li key={i} className="text-[11px] text-white/50">• {e}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ))}
                        {data.similar_past_incidents?.length > 0 && (
                            <p className="text-[11px] text-white/40">{data.similar_past_incidents.length} similar past incident(s) found in memory.</p>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

function QuickLookups() {
    const [metric, setMetric] = useState('cpu_usage');
    const [forecast, setForecast] = useState(null);
    const [service, setService] = useState('');
    const [blast, setBlast] = useState(null);
    const [loadingF, setLoadingF] = useState(false);
    const [loadingB, setLoadingB] = useState(false);

    const runForecast = async () => {
        setLoadingF(true);
        try {
            const r = await fetch(`${API}/api/agentic-workflow/forecast?metric=${encodeURIComponent(metric)}`, { headers: authHeaders() });
            if (r.ok) setForecast(await r.json());
        } catch (_e) { /* ignore */ } finally { setLoadingF(false); }
    };
    const runBlast = async () => {
        if (!service.trim()) return;
        setLoadingB(true);
        try {
            const r = await fetch(`${API}/api/agentic-workflow/blast-radius/${encodeURIComponent(service)}`, { headers: authHeaders() });
            setBlast(r.ok ? await r.json() : { error: await r.text() });
        } catch (_e) { /* ignore */ } finally { setLoadingB(false); }
    };

    return (
        <div className="grid md:grid-cols-2 gap-4">
            <Card className="bg-black/40 border-white/10" data-testid="forecaster-card">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white"><TrendingUp className="w-4 h-4 text-amber-400" /> Forecaster</CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-2">
                    <div className="flex gap-2">
                        <Input value={metric} onChange={(e) => setMetric(e.target.value)} className="bg-black/40 border-white/10 text-white text-sm" data-testid="forecast-metric-input" />
                        <Button size="sm" variant="outline" onClick={runForecast} disabled={loadingF}>{loadingF ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Predict'}</Button>
                    </div>
                    {forecast && (
                        forecast.status === 'insufficient_data' ? (
                            <p className="text-[11px] text-white/40">Not enough data points yet ({forecast.data_points || 0}).</p>
                        ) : (
                            <div className="text-xs text-white/70 space-y-1">
                                <div>Risk: <span className="text-white/90">{forecast.risk_assessment?.level || 'unknown'}</span></div>
                                <div>Predicted ({forecast.prediction?.horizon}): <span className="tabular-nums">{forecast.prediction?.predicted_value}</span> (confidence {forecast.prediction?.confidence}%)</div>
                            </div>
                        )
                    )}
                    <Link to="/capacity-prediction" className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
                        Full Capacity Prediction page <ExternalLink className="w-3 h-3" />
                    </Link>
                </CardContent>
            </Card>

            <Card className="bg-black/40 border-white/10" data-testid="blast-radius-card">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white"><Network className="w-4 h-4 text-rose-400" /> Blast Radius</CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-2">
                    <div className="flex gap-2">
                        <Input value={service} onChange={(e) => setService(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && runBlast()}
                            placeholder="service name" className="bg-black/40 border-white/10 text-white text-sm" data-testid="blast-radius-input" />
                        <Button size="sm" variant="outline" onClick={runBlast} disabled={loadingB || !service.trim()}>{loadingB ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Lookup'}</Button>
                    </div>
                    {blast && (
                        blast.error ? <p className="text-[11px] text-white/40">{blast.error}</p> : (
                            <div className="text-xs text-white/70 space-y-1">
                                <div>{blast.total_impacted} service(s) impacted</div>
                                <Badge className="text-[10px] bg-rose-500/15 text-rose-300 border border-rose-500/30">{blast.risk_level}</Badge>
                            </div>
                        )
                    )}
                    <Link to="/impact-analysis" className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
                        Full Impact Analysis page <ExternalLink className="w-3 h-3" />
                    </Link>
                </CardContent>
            </Card>
        </div>
    );
}

function DecisionLog({ refreshKey }) {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/agentic-workflow/decision-log?limit=20`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setRows(d.decisions || []); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [refreshKey]);

    return (
        <Card className="bg-black/40 border-white/10" data-testid="decision-log-card">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-white"><ScrollText className="w-4 h-4 text-white/60" /> Decision Log</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                {loading ? <div className="p-4 text-xs text-white/40">Loading…</div>
                    : rows.length === 0 ? <div className="p-6 text-center text-xs text-white/35">No decisions logged yet — ask something above.</div>
                    : (
                        <div className="divide-y divide-white/5 max-h-72 overflow-auto">
                            {rows.map((row) => {
                                const meta = ROUTE_META[row.classification] || ROUTE_META.copilot;
                                return (
                                    <div key={row.id} className="p-2.5 flex items-center gap-2" data-testid={`decision-${row.id}`}>
                                        <Badge className={`text-[9px] border ${COLOR_CLS[meta.color]}`}>{meta.label}</Badge>
                                        <span className="text-[11px] text-white/70 truncate flex-1">{row.query}</span>
                                        <span className="text-[10px] text-white/35">{(row.created_at || '').slice(11, 19)}</span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
            </CardContent>
        </Card>
    );
}

function ActionRegistry() {
    const [actions, setActions] = useState([]);
    const [dryRunResults, setDryRunResults] = useState({});

    useEffect(() => {
        fetch(`${API}/api/agentic-workflow/actions`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => setActions(d.actions || []))
            .catch(() => {});
    }, []);

    const runDryRun = async (name) => {
        try {
            const r = await fetch(`${API}/api/agentic-workflow/actions/${encodeURIComponent(name)}/dry-run`, { headers: authHeaders() });
            const data = await r.json();
            setDryRunResults((prev) => ({ ...prev, [name]: data }));
        } catch (e) {
            toast.error(`Dry run failed: ${e.message?.slice(0, 200)}`);
        }
    };

    return (
        <Card className="bg-black/40 border-white/10" data-testid="action-registry-card">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-white"><ShieldCheck className="w-4 h-4 text-emerald-400" /> Action Registry (Preview)</CardTitle>
                <p className="text-[11px] text-amber-300/70">Preview only — no actions execute in this phase. Every action is L0 (observe) by default.</p>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-white/5">
                {actions.map((a) => (
                    <div key={a.name} className="p-3 space-y-1.5" data-testid={`action-${a.name}`}>
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm text-white/90 font-mono">{a.name}</span>
                            <Badge className="text-[9px] border-white/15 text-white/50 bg-black/30 border">{a.blast_radius}</Badge>
                            <Badge className="text-[9px] border-white/15 text-white/50 bg-black/30 border">{a.reversible ? 'reversible' : 'irreversible'}</Badge>
                            <Badge className="text-[9px] border-cyan-500/30 text-cyan-300 bg-cyan-500/10 border">requires {a.required_level}</Badge>
                            <Badge className="text-[9px] border-white/15 text-white/40 bg-black/30 border ml-auto">current: {a.current_autonomy_level}</Badge>
                            <Button size="sm" variant="ghost" className="h-6 text-[10px] text-white/60" onClick={() => runDryRun(a.name)} data-testid={`dry-run-${a.name}`}>
                                Dry Run <ChevronRight className="w-3 h-3 ml-0.5" />
                            </Button>
                        </div>
                        <p className="text-[11px] text-white/40">{a.description}</p>
                        {dryRunResults[a.name] && (
                            <div className="text-[10px] text-white/50 bg-black/30 rounded p-2 mt-1 font-mono">
                                {dryRunResults[a.name].preconditions?.map((p, i) => (
                                    <div key={i}>{p.check}: {p.met === null ? p.reason : (p.met ? 'met' : 'not met')}</div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </CardContent>
        </Card>
    );
}

export default function AgenticWorkflowPage() {
    const [refreshKey, setRefreshKey] = useState(0);

    return (
        <div className="p-6 space-y-4 max-w-[1400px] mx-auto" data-testid="agentic-workflow-page">
            <div className="rounded-md border border-cyan-500/20 bg-gradient-to-br from-cyan-500/[0.06] via-black/40 to-fuchsia-500/[0.05] p-4">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <AgenticWorkflowLogoFull />
                    <div className="flex items-center gap-2">
                        <Link to="/ask-falconops" className="text-[11px] text-white/50 hover:text-white/80 flex items-center gap-1">
                            Ask FalconOpsAI (full chat) <ArrowRight className="w-3 h-3" />
                        </Link>
                        <Button variant="outline" size="sm" onClick={() => setRefreshKey((k) => k + 1)} data-testid="refresh-agentic-workflow">
                            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                        </Button>
                    </div>
                </div>
                <p className="text-[12px] text-white/55 mt-2">
                    A Supervisor that reasons over FalconOps's own telemetry — routes each question to the right specialist,
                    every decision logged, zero actions executed. Read-only, Phase 1.
                </p>
            </div>

            <LiveDiagnoserPipeline />
            <AskAnything />
            <DiagnoserCard />
            <QuickLookups />
            <div className="grid md:grid-cols-2 gap-4">
                <DecisionLog refreshKey={refreshKey} />
                <ActionRegistry />
            </div>
        </div>
    );
}
