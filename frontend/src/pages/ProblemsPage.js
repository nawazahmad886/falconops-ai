import React, { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Download, RefreshCw, Wifi, WifiOff, Zap } from 'lucide-react';
import ProblemsSummaryCards from '../components/problems/ProblemsSummaryCards';
import ProblemsTimelineChart from '../components/problems/ProblemsTimelineChart';
import ProblemsFilterPanel from '../components/problems/ProblemsFilterPanel';
import ProblemsGrid from '../components/problems/ProblemsGrid';
import ProblemDetailPanel from '../components/problems/ProblemDetailPanel';
import { useTimeRangeParams } from '../hooks/useTimeRangeParams';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;
const DEFAULT_FILTERS = {};

function buildQuery(filters, startTime) {
    const params = new URLSearchParams();
    if (filters.status) params.set('status', filters.status);
    if (filters.severity) params.set('severity', filters.severity);
    if (filters.source) params.set('source', filters.source);
    if (filters.service) params.set('service', filters.service);
    if (filters.assignedToMe) params.set('assigned_to', 'me');
    if (filters.includeSuppressed) params.set('include_suppressed', 'true');
    if (startTime) params.set('start_time', startTime);
    params.set('limit', '200');
    return params.toString();
}

export default function ProblemsPage() {
    const [filters, setFilters] = useState(DEFAULT_FILTERS);
    const { hours, startTime } = useTimeRangeParams();
    const [problems, setProblems] = useState([]);
    const [stats, setStats] = useState(null);
    const [timeline, setTimeline] = useState([]);
    const [loading, setLoading] = useState(true);
    const [connected, setConnected] = useState(false);
    const [selectedProblem, setSelectedProblem] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [fixSuggestion, setFixSuggestion] = useState(null);
    const [fixSuggestionLoading, setFixSuggestionLoading] = useState(false);
    const [assignTarget, setAssignTarget] = useState(null);
    const [assignValue, setAssignValue] = useState('');

    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectDelayRef = useRef(RECONNECT_BASE_MS);
    const closedByUsRef = useRef(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const qs = buildQuery(filters, startTime);
            const [listRes, statsRes, timelineRes] = await Promise.all([
                fetch(`${API}/api/problems?${qs}`, { headers: authHeaders() }),
                fetch(`${API}/api/problems/statistics`, { headers: authHeaders() }),
                fetch(`${API}/api/problems/timeline?hours=${hours}&bucket_minutes=${hours <= 6 ? 15 : 60}`, { headers: authHeaders() }),
            ]);
            if (!listRes.ok) throw new Error(await listRes.text());
            const listData = await listRes.json();
            setProblems(listData.problems || []);
            if (statsRes.ok) setStats(await statsRes.json());
            if (timelineRes.ok) setTimeline((await timelineRes.json()).buckets || []);
        } catch (e) {
            toast.error('Failed to load Problems console data');
        } finally {
            setLoading(false);
        }
    }, [filters, hours, startTime]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // No useAutoRefresh here — the WebSocket live feed below already pushes
    // updates on every problem.* event; polling on top would be redundant
    // load and cause list re-sort flicker.

    // Live feed — capped exponential-backoff reconnect (same pattern as
    // LiveCallFlowPage.js); on any problem.* event, just refetch rather than
    // trying to patch one row into a possibly-stale filtered/sorted page.
    useEffect(() => {
        closedByUsRef.current = false;

        const connect = () => {
            const token = localStorage.getItem('falconToken');
            if (!token) return;
            let wsUrl;
            try {
                const u = new URL(API);
                const scheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
                wsUrl = `${scheme}//${u.host}/api/problems/live?token=${encodeURIComponent(token)}`;
            } catch (_e) {
                return;
            }
            let ws;
            try {
                ws = new WebSocket(wsUrl);
            } catch (_e) {
                return;
            }
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                reconnectDelayRef.current = RECONNECT_BASE_MS;
            };
            ws.onmessage = (evt) => {
                try {
                    const msg = JSON.parse(evt.data);
                    if (msg.type?.startsWith('problem.')) {
                        fetchAll();
                    }
                } catch (_e) { /* ignore malformed message */ }
            };
            const scheduleReconnect = () => {
                setConnected(false);
                if (closedByUsRef.current) return;
                reconnectTimerRef.current = setTimeout(connect, reconnectDelayRef.current);
                reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, RECONNECT_MAX_MS);
            };
            ws.onclose = scheduleReconnect;
            ws.onerror = () => { try { ws.close(); } catch (_e) { /* onclose handles reconnect */ } };
        };

        connect();
        return () => {
            closedByUsRef.current = true;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            try { wsRef.current?.close(); } catch (_e) { /* ignore */ }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fetchAll]);

    const openDetail = useCallback(async (problem) => {
        setSelectedProblem(problem);
        setDetailLoading(true);
        setFixSuggestion(null);
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problem.id)}`, { headers: authHeaders() });
            if (r.ok) setSelectedProblem(await r.json());
        } catch (_e) {
            toast.error('Failed to load problem detail');
        } finally {
            setDetailLoading(false);
        }
        // Best-effort — a 404 here just means nothing's been generated yet,
        // not an error worth surfacing to the user.
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problem.id)}/fix-suggestion`, { headers: authHeaders() });
            if (r.ok) setFixSuggestion(await r.json());
        } catch (_e) { /* no cached suggestion yet */ }
    }, []);

    const notifyOwner = useCallback(async (problemId, channels, message) => {
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problemId)}/notify`, {
                method: 'POST', headers: authHeaders(), body: JSON.stringify({ channels, message }),
            });
            if (!r.ok) throw new Error(await r.text());
            const result = await r.json();
            const summary = Object.entries(result.results || {})
                .map(([channel, res]) => `${channel}: ${res.ok ? 'sent' : res.error}`)
                .join(', ');
            toast.success(`Owner notified — ${summary}`);
        } catch (e) {
            toast.error(`Notify failed: ${e.message?.slice(0, 200)}`);
            throw e;
        }
    }, []);

    const remediateProblem = useCallback(async (problemId, actionId, params) => {
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problemId)}/remediate`, {
                method: 'POST', headers: authHeaders(), body: JSON.stringify({ action_id: actionId, params }),
            });
            if (!r.ok) throw new Error(await r.text());
            const result = await r.json();
            toast.success('Remediation previewed (dry-run — nothing executed)');
            return result;
        } catch (e) {
            toast.error(`Remediation preview failed: ${e.message?.slice(0, 200)}`);
            throw e;
        }
    }, []);

    const generateFixSuggestion = useCallback(async (problemId) => {
        setFixSuggestionLoading(true);
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problemId)}/fix-suggestion`, {
                method: 'POST', headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            setFixSuggestion(await r.json());
        } catch (e) {
            toast.error(`Fix suggestion failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setFixSuggestionLoading(false);
        }
    }, []);

    const runAction = useCallback(async (problem, action) => {
        if (action === 'assign') {
            setAssignTarget(problem);
            setAssignValue(problem.assigned_to || '');
            return;
        }
        try {
            let body;
            if (action === 'suppress') body = { reason: 'Suppressed from Problems console' };
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(problem.id)}/${action}`, {
                method: 'POST', headers: authHeaders(), body: body ? JSON.stringify(body) : undefined,
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`Problem ${action}d`);
            fetchAll();
        } catch (e) {
            toast.error(`${action} failed: ${e.message?.slice(0, 200)}`);
        }
    }, [fetchAll]);

    const submitAssign = async () => {
        try {
            const r = await fetch(`${API}/api/problems/${encodeURIComponent(assignTarget.id)}/assign`, {
                method: 'POST', headers: authHeaders(),
                body: JSON.stringify({ assigned_to: assignValue || null }),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Problem assigned');
            setAssignTarget(null);
            fetchAll();
        } catch (e) {
            toast.error(`Assign failed: ${e.message?.slice(0, 200)}`);
        }
    };

    const exportCsv = async () => {
        try {
            const qs = buildQuery(filters, startTime);
            const r = await fetch(`${API}/api/problems/export?${qs}`, { method: 'POST', headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            const blob = await r.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'problems_export.csv';
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            toast.error(`Export failed: ${e.message?.slice(0, 200)}`);
        }
    };

    return (
        <div className="p-6 space-y-4" data-testid="problems-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Zap className="w-6 h-6 text-rose-400" />
                        Problems
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Unified, AI-correlated view across alert &amp; incident engines and connector-sourced SOC events
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge className={connected
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-red-500/15 text-red-300 border border-red-500/30'}>
                        {connected ? <Wifi className="w-3.5 h-3.5 mr-1.5" /> : <WifiOff className="w-3.5 h-3.5 mr-1.5" />}
                        {connected ? 'Live' : 'Reconnecting…'}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={exportCsv} data-testid="export-csv">
                        <Download className="w-4 h-4 mr-1.5" /> Export CSV
                    </Button>
                    <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading} data-testid="refresh-problems">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                </div>
            </div>

            <ProblemsSummaryCards stats={stats} loading={loading && !stats} />

            <div className="bg-black/40 border border-white/10 rounded-lg p-3">
                <ProblemsTimelineChart buckets={timeline} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                <div className="lg:col-span-1 bg-black/40 border border-white/10 rounded-lg">
                    <ProblemsFilterPanel filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} />
                </div>
                <div className="lg:col-span-4">
                    <ProblemsGrid
                        problems={problems}
                        loading={loading}
                        onSelectProblem={openDetail}
                        onAction={runAction}
                    />
                </div>
            </div>

            {selectedProblem && (
                <ProblemDetailPanel
                    problem={selectedProblem}
                    loading={detailLoading}
                    onClose={() => { setSelectedProblem(null); setFixSuggestion(null); }}
                    onNotify={notifyOwner}
                    onRemediate={remediateProblem}
                    onGenerateFixSuggestion={generateFixSuggestion}
                    fixSuggestion={fixSuggestion}
                    fixSuggestionLoading={fixSuggestionLoading}
                />
            )}

            <Dialog open={!!assignTarget} onOpenChange={(open) => !open && setAssignTarget(null)}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-sm">
                    <DialogHeader>
                        <DialogTitle className="text-white text-sm">Assign problem</DialogTitle>
                    </DialogHeader>
                    <Input
                        placeholder="Assignee email"
                        value={assignValue}
                        onChange={(e) => setAssignValue(e.target.value)}
                        className="bg-black/40 border-white/10"
                        data-testid="assign-input"
                    />
                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" size="sm" onClick={() => setAssignTarget(null)}>Cancel</Button>
                        <Button size="sm" onClick={submitAssign} data-testid="assign-submit">Assign</Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
