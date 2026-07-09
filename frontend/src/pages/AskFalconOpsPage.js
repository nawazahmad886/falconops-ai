import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
    BrainCircuit, Send, Sparkles, Wrench, History, Gauge, ListChecks,
    FileSearch, RefreshCw, Database, MessageSquareText, ShieldAlert, Clock,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const SUGGESTIONS = [
    'Why is payment-api slow?',
    'Show errors in the last 10 minutes',
    'Which service is failing?',
    'Any deployments in the last 24 hours?',
    'Root cause for order-service errors',
];

const EVIDENCE_HANDLE_RE = /^\s*\[([A-Za-z]{1,2}\d+)\]\s*/;
const EVIDENCE_KIND_LABELS = {
    get_logs: 'LOG',
    get_deployments: 'DEPLOY',
    get_traces: 'TRACE',
    get_incidents: 'INCIDENT',
};

function EvidenceSourceBadge({ evidenceRef }) {
    if (!evidenceRef) return null;
    const label = EVIDENCE_KIND_LABELS[evidenceRef.kind] || evidenceRef.kind || 'SOURCE';
    let time = '';
    if (evidenceRef.timestamp) {
        const d = new Date(evidenceRef.timestamp);
        if (!isNaN(d.getTime())) time = d.toLocaleTimeString();
    }
    return (
        <Badge
            variant="outline"
            title={evidenceRef.id ? `${label} · id ${evidenceRef.id}` : label}
            className="ml-2 shrink-0 text-[9px] px-1.5 py-0 border-amber-500/30 text-amber-300/80 whitespace-nowrap"
        >
            {label}{evidenceRef.service ? ` · ${evidenceRef.service}` : ''}{time ? ` · ${time}` : ''}
        </Badge>
    );
}

function ConfidenceGauge({ value }) {
    const pct = Math.round((value || 0) * 100);
    const color = pct >= 70 ? 'text-emerald-300' : pct >= 40 ? 'text-amber-300' : 'text-red-300';
    const bar = pct >= 70 ? 'bg-emerald-400' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400';
    return (
        <div data-testid="confidence-score" className="flex items-center gap-3">
            <Gauge className={`w-4 h-4 ${color}`} />
            <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                <div className={`h-full ${bar} transition-all duration-700`} style={{ width: `${pct}%` }} />
            </div>
            <span className={`text-sm font-bold tabular-nums ${color}`}>{pct}%</span>
        </div>
    );
}

function InsightsPanel({ analysis }) {
    if (!analysis) {
        return (
            <Card className="bg-black/40 border-white/10 h-full">
                <CardContent className="p-8 text-center text-white/40 flex flex-col items-center gap-3">
                    <BrainCircuit className="w-10 h-10 text-cyan-500/40" />
                    <p className="text-sm">Ask a question to see the AI Insights panel — root cause, evidence, confidence and recommended actions.</p>
                </CardContent>
            </Card>
        );
    }
    return (
        <div data-testid="insights-panel" className="space-y-3">
            <Card className="bg-black/40 border-cyan-500/30">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-white flex items-center gap-2">
                        <Gauge className="w-4 h-4 text-cyan-300" /> Confidence
                        <Badge variant="outline" className="ml-auto text-[10px] border-white/20 text-white/60">
                            {analysis.mode === 'incident' ? 'Incident Analysis Agent' : 'Monitoring Copilot'}
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    <ConfidenceGauge value={analysis.confidence} />
                    <div className="mt-2 flex items-center gap-2 text-[10px] text-white/40">
                        <Clock className="w-3 h-3" /> {Math.round(analysis.duration_ms || 0)}ms
                        {analysis.llm_provider && <span>· {analysis.llm_provider}{analysis.llm_model ? ` / ${analysis.llm_model}` : ''}</span>}
                        {analysis.blocked && <Badge className="bg-red-500/20 text-red-300 text-[10px]"><ShieldAlert className="w-3 h-3 mr-1" />blocked</Badge>}
                    </div>
                </CardContent>
            </Card>

            {(analysis.evidence || []).length > 0 && (
                <Card className="bg-black/40 border-white/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <FileSearch className="w-4 h-4 text-amber-300" /> Evidence
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <ul data-testid="evidence-list" className="space-y-1.5">
                            {analysis.evidence.map((e, i) => {
                                const evidenceRef = (analysis.evidence_refs || [])[i];
                                const text = e.replace(EVIDENCE_HANDLE_RE, '');
                                return (
                                    <li key={i} className="text-xs text-white/70 flex gap-2 items-start">
                                        <span className="text-amber-400/70 shrink-0">▸</span>
                                        <span className="break-words flex-1">{text}</span>
                                        <EvidenceSourceBadge evidenceRef={evidenceRef} />
                                    </li>
                                );
                            })}
                        </ul>
                    </CardContent>
                </Card>
            )}

            {(analysis.recommended_actions || []).length > 0 && (
                <Card className="bg-black/40 border-emerald-500/20">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <ListChecks className="w-4 h-4 text-emerald-300" /> Recommended Actions
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0">
                        <ol data-testid="recommended-actions" className="space-y-1.5 list-decimal list-inside">
                            {analysis.recommended_actions.map((a, i) => (
                                <li key={i} className="text-xs text-emerald-100/80">{a}</li>
                            ))}
                        </ol>
                    </CardContent>
                </Card>
            )}

            {(analysis.similar_incidents || []).length > 0 && (
                <Card className="bg-black/40 border-violet-500/20">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <Database className="w-4 h-4 text-violet-300" /> Similar Past Incidents (RAG)
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0 space-y-2">
                        {analysis.similar_incidents.map((s, i) => (
                            <div key={i} className="text-xs text-white/60 border-l-2 border-violet-500/40 pl-2">
                                <span className="text-violet-300 font-mono">{Math.round(s.similarity * 100)}%</span> {s.text?.slice(0, 180)}
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}

            {(analysis.tool_trace || []).length > 0 && (
                <Card className="bg-black/40 border-white/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <Wrench className="w-4 h-4 text-cyan-300" /> Tool Calls
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-0 space-y-1">
                        {analysis.tool_trace.map((t, i) => (
                            <div key={i} data-testid="tool-trace-item" className="text-[11px] text-white/50 font-mono flex items-center gap-2">
                                <Badge variant="outline" className="text-[10px] border-cyan-500/30 text-cyan-300">{t.tool}</Badge>
                                <span className="truncate">{t.summary}</span>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

function ChatMessage({ msg }) {
    if (msg.role === 'user') {
        return (
            <div data-testid="chat-message-user" className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-cyan-500/15 border border-cyan-500/30 px-4 py-2.5 text-sm text-white">
                    {msg.text}
                </div>
            </div>
        );
    }
    return (
        <div data-testid="chat-message-agent" className="flex gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500/30 to-violet-500/30 border border-white/10 flex items-center justify-center shrink-0">
                <BrainCircuit className="w-4 h-4 text-cyan-300" />
            </div>
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white/[0.04] border border-white/10 px-4 py-3 text-sm text-white/85 whitespace-pre-wrap break-words">
                {msg.loading ? (
                    <span className="flex items-center gap-2 text-white/50">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Correlating logs, metrics & traces…
                    </span>
                ) : msg.text}
                {msg.analysis && !msg.loading && (
                    <div className="mt-2 flex items-center gap-2">
                        <Badge className={`text-[10px] ${msg.analysis.mode === 'incident' ? 'bg-violet-500/20 text-violet-300' : 'bg-cyan-500/20 text-cyan-300'}`}>
                            {msg.analysis.mode === 'incident' ? 'RCA' : 'Copilot'}
                        </Badge>
                        {msg.analysis.service && <Badge variant="outline" className="text-[10px] border-white/20 text-white/50">{msg.analysis.service}</Badge>}
                        <Badge variant="outline" className="text-[10px] border-white/20 text-white/50">conf {Math.round((msg.analysis.confidence || 0) * 100)}%</Badge>
                    </div>
                )}
            </div>
        </div>
    );
}

export default function AskFalconOpsPage() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [busy, setBusy] = useState(false);
    const [lastAnalysis, setLastAnalysis] = useState(null);
    const [ragStats, setRagStats] = useState(null);
    const [reindexing, setReindexing] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        fetch(`${API}/api/ai-intelligence/rag/stats`, { headers: headers() })
            .then(r => r.json()).then(setRagStats).catch(() => {});
    }, []);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages]);

    const send = async (text) => {
        const q = (text || input).trim();
        if (!q || busy) return;
        setInput('');
        setBusy(true);
        setMessages(m => [...m, { role: 'user', text: q }, { role: 'agent', loading: true }]);
        try {
            const r = await fetch(`${API}/api/ai-intelligence/ask`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ query: q, mode: 'auto' }),
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            setLastAnalysis(data);
            setMessages(m => [...m.slice(0, -1), { role: 'agent', text: data.summary, analysis: data }]);
        } catch (e) {
            setMessages(m => [...m.slice(0, -1), { role: 'agent', text: `Analysis failed: ${e.message}` }]);
            toast.error('AI Intelligence request failed');
        } finally {
            setBusy(false);
        }
    };

    const reindex = async () => {
        setReindexing(true);
        try {
            const r = await fetch(`${API}/api/ai-intelligence/rag/reindex`, { method: 'POST', headers: headers() });
            const data = await r.json();
            toast.success(`Indexed ${data.incidents_indexed} incidents, ${data.logs_indexed} logs`);
            const s = await fetch(`${API}/api/ai-intelligence/rag/stats`, { headers: headers() }).then(x => x.json());
            setRagStats(s);
        } catch {
            toast.error('Reindex failed');
        } finally {
            setReindexing(false);
        }
    };

    return (
        <div data-testid="ask-falconops-page" className="p-4 lg:p-6 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h1 className="text-xl font-bold text-white flex items-center gap-2">
                        <MessageSquareText className="w-5 h-5 text-cyan-300" /> Ask FalconOpsAI
                        <Badge className="bg-violet-500/20 text-violet-300 text-[10px]">AI Intelligence Layer</Badge>
                    </h1>
                    <p className="text-xs text-white/40 mt-0.5">
                        Natural-language debugging — the Incident Analysis Agent & Monitoring Copilot correlate logs, metrics, traces and deployments via tools.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {ragStats?.available && (
                        <Badge variant="outline" className="text-[10px] border-violet-500/30 text-violet-300">
                            <Database className="w-3 h-3 mr-1" />
                            RAG: {ragStats.incident_history_count} incidents · {ragStats.recent_logs_count} logs
                        </Badge>
                    )}
                    <Button data-testid="rag-reindex-btn" size="sm" variant="outline"
                        className="border-white/15 text-white/70 h-7 text-xs" onClick={reindex} disabled={reindexing}>
                        <RefreshCw className={`w-3 h-3 mr-1 ${reindexing ? 'animate-spin' : ''}`} /> Reindex Memory
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <Card className="lg:col-span-2 bg-black/40 border-white/10 flex flex-col" style={{ height: 'calc(100vh - 190px)' }}>
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
                        {messages.length === 0 && (
                            <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
                                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-white/10 flex items-center justify-center">
                                    <Sparkles className="w-7 h-7 text-cyan-300" />
                                </div>
                                <p className="text-sm text-white/50 max-w-sm">Ask why a service is slow, show recent errors, or investigate an incident — I'll query your observability data and reason over it.</p>
                                <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                                    {SUGGESTIONS.map((s, i) => (
                                        <button key={i} data-testid={`suggestion-chip-${i}`}
                                            onClick={() => send(s)}
                                            className="text-xs px-3 py-1.5 rounded-full border border-cyan-500/25 text-cyan-200/80 hover:bg-cyan-500/10 transition-colors">
                                            {s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                        {messages.map((m, i) => <ChatMessage key={i} msg={m} />)}
                    </div>
                    <div className="p-3 border-t border-white/10 flex gap-2">
                        <Input
                            data-testid="ask-input"
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && send()}
                            placeholder='e.g. "Why is payment-api slow?" or "Show errors in last 10 minutes"'
                            className="bg-white/5 border-white/15 text-white placeholder:text-white/30"
                            disabled={busy}
                        />
                        <Button data-testid="ask-submit-btn" onClick={() => send()} disabled={busy || !input.trim()}
                            className="bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 hover:bg-cyan-500/30">
                            <Send className="w-4 h-4" />
                        </Button>
                    </div>
                </Card>

                <div className="lg:col-span-1 overflow-y-auto min-w-0 pr-1" style={{ height: 'calc(100vh - 190px)' }}>
                    <InsightsPanel analysis={lastAnalysis} />
                </div>
            </div>
        </div>
    );
}
