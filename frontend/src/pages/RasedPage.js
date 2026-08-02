import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
    Activity,
    AlertTriangle,
    CheckCircle2,
    Clock,
    Radio,
    ShieldAlert,
    ShieldCheck,
    XCircle,
    Zap,
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
    start: Activity,
    tool_call: Radio,
    tool_result: Radio,
    reasoning: Zap,
    decision: CheckCircle2,
    action: ShieldCheck,
    error: XCircle,
};

function statusBadge(status) {
    return STATUS_STYLES[status] || STATUS_STYLES.new;
}

function fmtPct(value) {
    if (value === null || value === undefined) return '—';
    return `${Math.round(value * 100)}%`;
}

export const RasedPage = () => {
    const { api } = useAuth();
    const [incidents, setIncidents] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [incident, setIncident] = useState(null);
    const [trace, setTrace] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [approving, setApproving] = useState(false);
    const abortRef = useRef(null);

    const fetchIncidents = useCallback(async () => {
        try {
            const res = await api.get('/v1/rased/incidents?limit=50');
            setIncidents(res.data?.incidents || []);
        } catch (error) {
            console.error('Failed to fetch RASED incidents:', error);
        } finally {
            setLoading(false);
        }
    }, [api]);

    const fetchMetrics = useCallback(async () => {
        try {
            const res = await api.get('/v1/rased/metrics');
            setMetrics(res.data);
        } catch (error) {
            console.error('Failed to fetch RASED metrics:', error);
        }
    }, [api]);

    const fetchIncidentDetail = useCallback(async (incidentId) => {
        try {
            const res = await api.get(`/v1/rased/incidents/${incidentId}`);
            setIncident(res.data);
        } catch (error) {
            console.error('Failed to fetch RASED incident detail:', error);
        }
    }, [api]);

    useEffect(() => {
        fetchIncidents();
        fetchMetrics();
        const interval = setInterval(() => {
            fetchIncidents();
            fetchMetrics();
        }, 15000);
        return () => clearInterval(interval);
    }, [fetchIncidents, fetchMetrics]);

    useEffect(() => {
        if (!selectedId) return undefined;

        setTrace([]);
        fetchIncidentDetail(selectedId);

        const controller = new AbortController();
        abortRef.current = controller;

        const streamTrace = async () => {
            const token = localStorage.getItem('falconToken');
            const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
            try {
                const response = await fetch(`${backendUrl}/api/v1/rased/incidents/${selectedId}/stream`, {
                    headers: { Authorization: `Bearer ${token}` },
                    signal: controller.signal,
                });
                if (!response.ok || !response.body) return;

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                // Deliberate pacing: an instant trace dump is unimpressive to
                // watch, visible reasoning is the product. Each event is
                // rendered as it arrives from the server rather than all at
                // once, which the SSE stream already paces via when the
                // backend actually emits it.
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
                                setIncident((prev) => (prev ? { ...prev } : prev));
                            }
                        } catch (e) {
                            // non-JSON keepalive/end event, ignore
                        }
                    }
                }
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('RASED trace stream error:', error);
                }
            }
        };

        streamTrace();
        const detailPoll = setInterval(() => fetchIncidentDetail(selectedId), 4000);

        return () => {
            controller.abort();
            clearInterval(detailPoll);
        };
    }, [selectedId, fetchIncidentDetail]);

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
            console.error('Failed to record approval decision:', error);
            toast.error('Failed to record decision');
        } finally {
            setApproving(false);
        }
    };

    const survivingHypotheses = (incident?.hypotheses || []).filter((h) => !h.superseded);
    const supersededHypotheses = (incident?.hypotheses || []).filter((h) => h.superseded);

    return (
        <div className="min-h-screen bg-[hsl(0_0%_4%)] text-white p-6 relative overflow-hidden">
            <div className="pointer-events-none absolute -top-40 -left-40 w-[32rem] h-[32rem] rounded-full bg-cyan-500/10 blur-[120px]" />
            <div className="pointer-events-none absolute top-1/3 -right-40 w-[28rem] h-[28rem] rounded-full bg-violet-500/10 blur-[120px]" />

            <div className="relative z-10 max-w-[1600px] mx-auto">
                <div className="mb-6">
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-300 bg-clip-text text-transparent">
                        RASED — راصد
                    </h1>
                    <p className="text-sm text-slate-400 mt-1">Autonomous investigation, live trace, and approval-gated remediation</p>
                </div>

                <div className="grid grid-cols-12 gap-4">
                    {/* Left: incident feed */}
                    <div className="col-span-12 lg:col-span-3">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-base">Incident Feed</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2 max-h-[70vh] overflow-y-auto">
                                {loading && <p className="text-sm text-slate-500">Loading…</p>}
                                {!loading && incidents.length === 0 && (
                                    <p className="text-sm text-slate-500">No investigations yet.</p>
                                )}
                                {incidents.map((inc) => (
                                    <button
                                        key={inc.incident_id}
                                        onClick={() => setSelectedId(inc.incident_id)}
                                        className={`w-full text-left rounded-lg border p-3 transition-colors ${
                                            selectedId === inc.incident_id
                                                ? 'border-cyan-400/50 bg-cyan-500/10'
                                                : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
                                        }`}
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-mono text-slate-400 truncate">
                                                {inc.incident_id?.slice(0, 8)}
                                            </span>
                                            <Badge className={`text-[10px] border ${statusBadge(inc.status)}`}>{inc.status}</Badge>
                                        </div>
                                        <p className="text-sm mt-1 truncate">{inc.root_signature || 'Unclassified signature'}</p>
                                    </button>
                                ))}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Centre: agent trace panel */}
                    <div className="col-span-12 lg:col-span-6">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl h-full">
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <Activity className="w-4 h-4 text-cyan-400" />
                                    Agent Trace
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3 max-h-[70vh] overflow-y-auto">
                                {!selectedId && <p className="text-sm text-slate-500">Select an incident to watch its trace.</p>}
                                <AnimatePresence initial={false}>
                                    {trace.map((event) => {
                                        const Icon = TRACE_KIND_ICON[event.kind] || Activity;
                                        return (
                                            <motion.div
                                                key={event.seq}
                                                initial={{ opacity: 0, y: 8 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="rounded-lg border border-white/10 bg-white/[0.02] p-3"
                                            >
                                                <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
                                                    <span className="flex items-center gap-1.5">
                                                        <Icon className="w-3.5 h-3.5" />
                                                        <span className="font-mono">{event.agent}</span>
                                                    </span>
                                                    {event.duration_ms !== undefined && event.duration_ms !== null && (
                                                        <span>{event.duration_ms}ms</span>
                                                    )}
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
                                            <p key={h.hypothesis_id} className="text-sm text-slate-500 line-through">
                                                {h.statement}
                                            </p>
                                        ))}
                                        {survivingHypotheses.map((h) => (
                                            <p key={h.hypothesis_id} className="text-sm font-medium text-white mt-1">
                                                {h.statement}{' '}
                                                <span className="text-cyan-300">({fmtPct(h.confidence)})</span>
                                            </p>
                                        ))}
                                        {survivingHypotheses[0]?.revision_reason && (
                                            <p className="text-xs text-slate-400 mt-2 italic">
                                                {survivingHypotheses[0].revision_reason}
                                            </p>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right: analysis + approval */}
                    <div className="col-span-12 lg:col-span-3 space-y-4">
                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-base">Business Impact</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {incident?.business_impact ? (
                                    <div className="space-y-1 text-sm">
                                        <p className="text-slate-300">{incident.business_impact.summary}</p>
                                        <p className="text-xs text-slate-500">
                                            {incident.business_impact.transactions_at_risk} transactions at risk
                                        </p>
                                    </div>
                                ) : (
                                    <p className="text-sm text-slate-500">No impact computed yet.</p>
                                )}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-base">Ranked Hypotheses</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {survivingHypotheses.length === 0 && <p className="text-sm text-slate-500">No hypotheses yet.</p>}
                                {survivingHypotheses
                                    .slice()
                                    .sort((a, b) => b.confidence - a.confidence)
                                    .map((h) => (
                                        <div key={h.hypothesis_id} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                            <div className="flex items-center justify-between">
                                                <span className="text-sm">{h.statement}</span>
                                                <Badge className="text-[10px]">{fmtPct(h.confidence)}</Badge>
                                            </div>
                                            <p className="text-[11px] text-slate-500 mt-1">
                                                cites {h.evidence_ids?.length || 0} evidence item(s)
                                            </p>
                                        </div>
                                    ))}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-base">Policy &amp; SOP Citation</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {incident?.policy_decision ? (
                                    <div className="space-y-1 text-sm">
                                        <div className="flex items-center gap-2">
                                            <Badge className="text-[10px]">{incident.policy_decision.severity_tier}</Badge>
                                            <span className="text-xs text-slate-400">{incident.policy_decision.escalation_target}</span>
                                        </div>
                                        <p className="text-xs text-slate-400">{incident.policy_decision.justification}</p>
                                        {(incident.policy_decision.citations || []).map((c, idx) => (
                                            <p key={idx} className="text-[11px] font-mono text-cyan-300">
                                                {c.document_id} § {c.section}
                                            </p>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-slate-500">No policy decision yet.</p>
                                )}
                            </CardContent>
                        </Card>

                        <Card className="bg-white/[0.03] border-white/10 backdrop-blur-xl">
                            <CardHeader>
                                <CardTitle className="text-base">Proposed Actions</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {(incident?.actions || []).length === 0 && (
                                    <p className="text-sm text-slate-500">No actions proposed.</p>
                                )}
                                {(incident?.actions || []).map((action) => (
                                    <div key={action.action_id} className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm font-mono">{action.name}</span>
                                            <Badge className={`text-[10px] border ${TIER_STYLES[action.spec?.tier] || ''}`}>
                                                {action.spec?.tier}
                                            </Badge>
                                        </div>
                                        <p className="text-[11px] text-slate-500 mt-1">{action.status}</p>
                                    </div>
                                ))}

                                {incident?.status === 'awaiting_approval' && (
                                    <div className="flex gap-2 pt-2">
                                        <Button
                                            size="sm"
                                            disabled={approving}
                                            onClick={() => handleDecision(true)}
                                            className="flex-1 bg-emerald-600 hover:bg-emerald-500"
                                        >
                                            <ShieldCheck className="w-4 h-4 mr-1" /> Approve
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={approving}
                                            onClick={() => handleDecision(false)}
                                            className="flex-1 border-red-500/40 text-red-300 hover:bg-red-500/10"
                                        >
                                            <ShieldAlert className="w-4 h-4 mr-1" /> Reject
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Bottom: metrics strip */}
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
                                <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                                    <Icon className="w-3.5 h-3.5" />
                                    {label}
                                </div>
                                <p className="text-xl font-semibold">{value ?? '—'}</p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
                {metrics?.execution_mode && (
                    <p className="text-[11px] text-slate-500 mt-2">execution_mode: {metrics.execution_mode}</p>
                )}
            </div>
        </div>
    );
};

export default RasedPage;
