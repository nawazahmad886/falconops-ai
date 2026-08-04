import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
    Activity, AlertTriangle, CheckCircle2, Clock, Radio, ShieldAlert, ShieldCheck,
    XCircle, Zap, Gauge, Network, FileDown, MessageCircle, FlaskConical, Send,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const STATUS_STYLES = {
    new: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    investigating: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    awaiting_approval: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    suppressed: 'bg-slate-600/15 text-slate-400 border-slate-600/30',
    resolved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    escalated: 'bg-red-500/15 text-red-300 border-red-500/30',
};

const TIER_STYLES = {
    SAFE: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    GUARDED: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    DESTRUCTIVE: 'bg-red-500/15 text-red-300 border-red-500/30',
};

const TRACE_KIND_ICON = {
    start: Activity, tool_call: Radio, tool_result: Radio, reasoning: Zap,
    decision: CheckCircle2, action: ShieldCheck, verification: Gauge, error: XCircle,
};

const DEMO_SCENARIOS = [
    { id: 'S1', label: 'Payment Gateway Degradation' },
    { id: 'S2', label: 'MQ Backlog' },
    { id: 'S3', label: 'DB Slow Query Cascade' },
    { id: 'S4', label: 'Post-Deploy Memory Leak' },
    { id: 'S5', label: 'Network Flap Alert Storm' },
];

function statusBadge(status) { return STATUS_STYLES[status] || STATUS_STYLES.new; }
function fmtPct(value) { return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`; }
function scoreColor(score) {
    if (score === null || score === undefined) return 'text-white/40';
    if (score >= 85) return 'text-emerald-300';
    if (score >= 60) return 'text-amber-300';
    return 'text-red-300';
}

export const IncidentCommanderPage = () => {
    const { api } = useAuth();
    const [incidents, setIncidents] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [incident, setIncident] = useState(null);
    const [trace, setTrace] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [sreScore, setSreScore] = useState(null);
    const [blastRadius, setBlastRadius] = useState(null);
    const [loading, setLoading] = useState(true);
    const [approving, setApproving] = useState(false);
    const [simulating, setSimulating] = useState(false);
    const [chatQuestion, setChatQuestion] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [chatAsking, setChatAsking] = useState(false);
    const abortRef = useRef(null);

    const fetchIncidents = useCallback(async () => {
        try {
            const res = await api.get('/v1/rased/incidents?limit=50');
            setIncidents(res.data?.incidents || []);
        } catch (error) { console.error('Failed to fetch incidents:', error); }
        finally { setLoading(false); }
    }, [api]);

    const fetchMetrics = useCallback(async () => {
        try {
            const res = await api.get('/v1/rased/metrics');
            setMetrics(res.data);
        } catch (error) { console.error('Failed to fetch metrics:', error); }
    }, [api]);

    const fetchSreScore = useCallback(async () => {
        try {
            const res = await api.get('/ai/incidents/overview/sre-score');
            setSreScore(res.data);
        } catch (error) { console.error('Failed to fetch SRE score:', error); }
    }, [api]);

    const fetchIncidentDetail = useCallback(async (incidentId) => {
        try {
            const res = await api.get(`/v1/rased/incidents/${incidentId}`);
            setIncident(res.data);
        } catch (error) { console.error('Failed to fetch incident detail:', error); }
    }, [api]);

    const fetchBlastRadius = useCallback(async (incidentId) => {
        try {
            const res = await api.get(`/ai/incidents/${incidentId}/blast-radius`);
            setBlastRadius(res.data);
        } catch (error) { console.error('Failed to fetch blast radius:', error); }
    }, [api]);

    useEffect(() => {
        fetchIncidents();
        fetchMetrics();
        fetchSreScore();
        const interval = setInterval(() => { fetchIncidents(); fetchMetrics(); fetchSreScore(); }, 15000);
        return () => clearInterval(interval);
    }, [fetchIncidents, fetchMetrics, fetchSreScore]);

    useEffect(() => {
        if (!selectedId) return undefined;
        setTrace([]);
        setChatHistory([]);
        setBlastRadius(null);
        fetchIncidentDetail(selectedId);
        fetchBlastRadius(selectedId);

        const controller = new AbortController();
        abortRef.current = controller;

        const streamTrace = async () => {
            const token = localStorage.getItem('falconToken');
            const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
            try {
                const response = await fetch(`${backendUrl}/api/v1/rased/incidents/${selectedId}/stream`, {
                    headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
                });
                if (!response.ok || !response.body) return;
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const chunks = buffer.split('\n\n');
                    buffer = chunks.pop() || '';
                    for (const chunk of chunks) {
                        const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'));
                        if (!dataLine) continue;
                        try {
                            const payload = JSON.parse(dataLine.slice(5).trim());
                            if (payload.seq !== undefined) {
                                setTrace((prev) => {
                                    if (prev.some((e) => e.seq === payload.seq)) return prev;
                                    return [...prev, payload].sort((a, b) => a.seq - b.seq);
                                });
                                if (payload.kind === 'verification') fetchIncidentDetail(selectedId);
                            }
                        } catch (e) { /* keepalive, ignore */ }
                    }
                }
            } catch (error) {
                if (error.name !== 'AbortError') console.error('Trace stream error:', error);
            }
        };

        streamTrace();
        const detailPoll = setInterval(() => fetchIncidentDetail(selectedId), 4000);
        return () => { controller.abort(); clearInterval(detailPoll); };
    }, [selectedId, fetchIncidentDetail, fetchBlastRadius]);

    const handleDecision = async (approved) => {
        if (!incident) return;
        setApproving(true);
        try {
            const endpoint = approved ? 'approve' : 'reject';
            await api.post(`/v1/rased/incidents/${incident.incident_id}/${endpoint}`, {});
            toast.success(approved ? 'Action approved' : 'Action rejected');
            fetchIncidentDetail(incident.incident_id);
            fetchIncidents();
        } catch (error) {
            toast.error(error?.response?.data?.detail || 'Failed to record decision');
        } finally { setApproving(false); }
    };

    const handleSimulate = async (scenarioId) => {
        setSimulating(true);
        try {
            await api.post(`/v1/rased/demo/run/${scenarioId}`, {});
            toast.success(`Simulating ${scenarioId} — watch the incident feed`);
            setTimeout(fetchIncidents, 1500);
        } catch (error) {
            toast.error('Simulation failed to start');
        } finally { setSimulating(false); }
    };

    const handleAsk = async () => {
        if (!incident || !chatQuestion.trim()) return;
        const question = chatQuestion.trim();
        setChatQuestion('');
        setChatAsking(true);
        setChatHistory((h) => [...h, { role: 'user', text: question }]);
        try {
            const res = await api.post(`/ai/incidents/${incident.incident_id}/ask`, { question });
            setChatHistory((h) => [...h, { role: 'assistant', text: res.data.answer, insufficient: res.data.insufficient_evidence }]);
        } catch (error) {
            setChatHistory((h) => [...h, { role: 'assistant', text: 'Insufficient evidence — request failed.', insufficient: true }]);
        } finally { setChatAsking(false); }
    };

    const handleExportReport = async (format) => {
        if (!incident) return;
        try {
            if (format === 'pdf') {
                // window.open can't attach an Authorization header, and this route
                // requires one (require_auth reads the header, not a query param) —
                // fetch the blob directly instead, same as the markdown path below.
                const token = localStorage.getItem('falconToken');
                const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
                const resp = await fetch(`${backendUrl}/api/ai/incidents/${incident.incident_id}/report?format=pdf`, {
                    method: 'POST', headers: { Authorization: `Bearer ${token}` },
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = `incident_${incident.incident_id}.pdf`; a.click();
                URL.revokeObjectURL(url);
                return;
            }
            const res = await api.post(`/ai/incidents/${incident.incident_id}/report?format=markdown`, {});
            const blob = new Blob([res.data.content], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `incident_${incident.incident_id}.md`; a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            toast.error('Report generation failed');
        }
    };

    const survivingHypotheses = (incident?.hypotheses || []).filter((h) => !h.superseded);
    const supersededHypotheses = (incident?.hypotheses || []).filter((h) => h.superseded);
    const verification = incident?.verification;

    return (
        <div className="min-h-screen bg-[hsl(0_0%_4%)] text-white p-6 relative overflow-hidden">
            <div className="pointer-events-none absolute -top-40 -left-40 w-[32rem] h-[32rem] rounded-full bg-cyan-500/10 blur-[120px]" />
            <div className="pointer-events-none absolute top-1/3 -right-40 w-[28rem] h-[28rem] rounded-full bg-violet-500/10 blur-[120px]" />

            <div className="relative z-10 max-w-[1700px] mx-auto">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-300 bg-clip-text text-transparent">
                            AI Incident Commander
                        </h1>
                        <p className="text-sm text-slate-400 mt-1">Observe → Investigate → Root Cause → Approve → Remediate → Verify</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-right">
                            <p className="text-[10px] uppercase tracking-wide text-slate-500">SRE Score</p>
                            <p className={`text-2xl font-bold ${scoreColor(sreScore?.overall)}`} data-testid="sre-score">
                                {sreScore?.overall ?? '—'}
                            </p>
                        </div>
                        <div className="flex gap-1">
                            {DEMO_SCENARIOS.map((s) => (
                                <Button key={s.id} size="sm" variant="outline" disabled={simulating}
                                        onClick={() => handleSimulate(s.id)} title={s.label}
                                        className="text-[10px] border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10">
                                    <FlaskConical className="w-3 h-3 mr-1" />{s.id}
                                </Button>
                            ))}
                        </div>
                    </div>
                </div>

                {sreScore?.components && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                        {Object.entries(sreScore.components).map(([domain, value]) => (
                            <Card key={domain} className="bg-white/[0.03] border-white/10">
                                <CardContent className="p-3">
                                    <p className="text-[10px] uppercase text-slate-500">{domain}</p>
                                    <p className={`text-lg font-semibold ${scoreColor(value)}`}>{value ?? 'n/a'}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                <div className="grid grid-cols-12 gap-4">
                    <div className="col-span-12 lg:col-span-3">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base">Active Incidents</CardTitle></CardHeader>
                            <CardContent className="space-y-2 max-h-[70vh] overflow-y-auto">
                                {loading && <p className="text-sm text-slate-500">Loading…</p>}
                                {!loading && incidents.length === 0 && <p className="text-sm text-slate-500">No investigations yet — try Simulate Incident above.</p>}
                                {incidents.map((inc) => (
                                    <button key={inc.incident_id} onClick={() => setSelectedId(inc.incident_id)}
                                        className={`w-full text-left rounded-lg border p-3 transition-colors ${
                                            selectedId === inc.incident_id ? 'border-cyan-400/50 bg-cyan-500/10' : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
                                        }`}>
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-mono text-slate-400 truncate">{inc.incident_id?.slice(0, 12)}</span>
                                            <Badge className={`text-[10px] border ${statusBadge(inc.status)}`}>{inc.status}</Badge>
                                        </div>
                                        <p className="text-sm mt-1 truncate">{inc.root_signature || 'Unclassified signature'}</p>
                                    </button>
                                ))}
                            </CardContent>
                        </Card>
                    </div>

                    <div className="col-span-12 lg:col-span-6 space-y-4">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Activity className="w-4 h-4 text-cyan-400" />Agent Execution Trace</CardTitle></CardHeader>
                            <CardContent className="space-y-3 max-h-[45vh] overflow-y-auto">
                                {!selectedId && <p className="text-sm text-slate-500">Select an incident to watch its trace.</p>}
                                <AnimatePresence initial={false}>
                                    {trace.map((event) => {
                                        const Icon = TRACE_KIND_ICON[event.kind] || Activity;
                                        return (
                                            <motion.div key={event.seq} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                                className={`rounded-lg border p-3 ${event.kind === 'verification' ? 'border-violet-500/30 bg-violet-500/5' : 'border-white/10 bg-white/[0.02]'}`}>
                                                <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
                                                    <span className="flex items-center gap-1.5"><Icon className="w-3.5 h-3.5" /><span className="font-mono">{event.agent}</span></span>
                                                    {event.duration_ms != null && <span>{event.duration_ms}ms</span>}
                                                </div>
                                                <p className="text-sm mt-1">{event.title}</p>
                                            </motion.div>
                                        );
                                    })}
                                </AnimatePresence>

                                {supersededHypotheses.length > 0 && (
                                    <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-3 mt-4">
                                        <p className="text-xs uppercase tracking-wide text-violet-300 mb-2">Hypothesis Revision</p>
                                        {supersededHypotheses.map((h) => (
                                            <p key={h.hypothesis_id} className="text-sm text-slate-500 line-through">{h.statement}</p>
                                        ))}
                                        {survivingHypotheses.map((h) => (
                                            <p key={h.hypothesis_id} className="text-sm font-medium text-white mt-1">
                                                {h.statement} <span className="text-cyan-300">({fmtPct(h.confidence)})</span>
                                            </p>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {verification && (
                            <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl" data-testid="verification-panel">
                                <CardHeader><CardTitle className="text-base flex items-center gap-2"><Gauge className="w-4 h-4 text-violet-400" />Verification</CardTitle></CardHeader>
                                <CardContent>
                                    {!verification.available ? (
                                        <p className="text-sm text-slate-500">Not available — {verification.reason}</p>
                                    ) : (
                                        <div className="space-y-2">
                                            <Badge className={`text-xs border ${verification.recovered ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-red-500/15 text-red-300 border-red-500/30'}`}>
                                                {verification.recovered ? 'RECOVERY CONFIRMED' : 'RECOVERY NOT CONFIRMED — REOPENED'}
                                            </Badge>
                                            <table className="w-full text-xs mt-2">
                                                <tbody>
                                                    {(verification.metrics || []).map((m, i) => (
                                                        <tr key={i} className="border-b border-white/5">
                                                            <td className="py-1 text-slate-400">{m.metric}</td>
                                                            <td className="py-1 text-right text-slate-300">{m.before}{m.unit}</td>
                                                            <td className="py-1 text-right text-slate-500">→</td>
                                                            <td className="py-1 text-right text-emerald-300">{m.after}{m.unit}</td>
                                                            <td className="py-1 text-right text-cyan-300">{m.improved_pct}%</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {incident && (
                            <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                                <CardHeader><CardTitle className="text-base flex items-center gap-2"><MessageCircle className="w-4 h-4 text-cyan-400" />Ask About This Incident</CardTitle></CardHeader>
                                <CardContent>
                                    <div className="space-y-2 max-h-40 overflow-y-auto mb-2">
                                        {chatHistory.map((m, i) => (
                                            <p key={i} className={`text-sm ${m.role === 'user' ? 'text-cyan-300' : m.insufficient ? 'text-amber-400' : 'text-white/85'}`}>
                                                <span className="text-[10px] uppercase text-slate-500 mr-1">{m.role}:</span>{m.text}
                                            </p>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <Input value={chatQuestion} onChange={(e) => setChatQuestion(e.target.value)}
                                               onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                                               placeholder="Why is this happening? What should I do?"
                                               className="bg-black/30 border-white/10 text-sm" />
                                        <Button size="sm" disabled={chatAsking} onClick={handleAsk}><Send className="w-3.5 h-3.5" /></Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    <div className="col-span-12 lg:col-span-3 space-y-4">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base">Business Impact</CardTitle></CardHeader>
                            <CardContent>
                                {incident?.business_impact ? (
                                    <div className="space-y-1 text-sm">
                                        <p className="text-slate-300">{incident.business_impact.summary}</p>
                                        <p className="text-xs text-slate-500">{incident.business_impact.transactions_at_risk} transactions at risk</p>
                                    </div>
                                ) : <p className="text-sm text-slate-500">No impact computed yet.</p>}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Network className="w-4 h-4 text-cyan-400" />Blast Radius</CardTitle></CardHeader>
                            <CardContent className="space-y-2">
                                {!blastRadius?.impacted?.length && <p className="text-sm text-slate-500">No topology data for affected service(s) yet.</p>}
                                {(blastRadius?.impacted || []).map((entry, i) => (
                                    <div key={i} className="text-xs">
                                        <span className="font-mono text-cyan-300">{entry.service}</span>
                                        {entry.available ? (
                                            <span className="text-slate-400"> → {entry.impacted_count} downstream service(s)</span>
                                        ) : (
                                            <span className="text-slate-600"> — {entry.reason}</span>
                                        )}
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base">Ranked Hypotheses</CardTitle></CardHeader>
                            <CardContent className="space-y-2">
                                {survivingHypotheses.length === 0 && <p className="text-sm text-slate-500">No hypotheses yet.</p>}
                                {survivingHypotheses.slice().sort((a, b) => b.confidence - a.confidence).map((h) => (
                                    <div key={h.hypothesis_id} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm">{h.statement}</span>
                                            <Badge className="text-[10px]">{fmtPct(h.confidence)}</Badge>
                                        </div>
                                        <p className="text-[11px] text-slate-500 mt-1">cites {h.evidence_ids?.length || 0} evidence item(s)</p>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader><CardTitle className="text-base">Proposed Actions</CardTitle></CardHeader>
                            <CardContent className="space-y-2">
                                {(incident?.actions || []).length === 0 && <p className="text-sm text-slate-500">No actions proposed.</p>}
                                {(incident?.actions || []).map((action) => (
                                    <div key={action.action_id} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm font-mono">{action.name}</span>
                                            <Badge className={`text-[10px] border ${TIER_STYLES[action.spec?.tier] || ''}`}>{action.spec?.tier}</Badge>
                                        </div>
                                        <p className="text-[11px] text-slate-500 mt-1">{action.status}</p>
                                    </div>
                                ))}
                                {incident?.status === 'awaiting_approval' && (
                                    <div className="flex gap-2 pt-2">
                                        <Button size="sm" disabled={approving} onClick={() => handleDecision(true)} className="flex-1 bg-emerald-600 hover:bg-emerald-500">
                                            <ShieldCheck className="w-4 h-4 mr-1" /> Approve
                                        </Button>
                                        <Button size="sm" variant="outline" disabled={approving} onClick={() => handleDecision(false)} className="flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10">
                                            <ShieldAlert className="w-4 h-4 mr-1" /> Reject
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {incident && (incident.status === 'resolved' || incident.status === 'escalated') && (
                            <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                                <CardHeader><CardTitle className="text-base flex items-center gap-2"><FileDown className="w-4 h-4 text-cyan-400" />Incident Report</CardTitle></CardHeader>
                                <CardContent className="flex gap-2">
                                    <Button size="sm" variant="outline" onClick={() => handleExportReport('markdown')} className="flex-1">Markdown</Button>
                                    <Button size="sm" variant="outline" onClick={() => handleExportReport('pdf')} className="flex-1">PDF</Button>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4">
                    {[
                        { label: 'Investigations', value: metrics?.total_investigations, icon: Activity },
                        { label: 'Suppressed', value: metrics?.suppressed, icon: Clock },
                        { label: 'Resolved', value: metrics?.resolved, icon: CheckCircle2 },
                        { label: 'Escalated', value: metrics?.escalated, icon: AlertTriangle },
                        { label: 'Actions Auto-Executed', value: metrics?.actions_auto_executed, icon: Zap },
                        { label: 'Suppression Rate', value: metrics ? `${metrics.alerts_suppressed_pct}%` : '—', icon: ShieldCheck },
                    ].map(({ label, value, icon: Icon }) => (
                        <Card key={label} className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardContent className="p-4">
                                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1"><Icon className="w-3.5 h-3.5" />{label}</div>
                                <p className="text-xl font-semibold">{value ?? '—'}</p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
                {metrics?.execution_mode && <p className="text-[11px] text-slate-500 mt-2">execution_mode: {metrics.execution_mode}</p>}
            </div>
        </div>
    );
};

export default IncidentCommanderPage;
