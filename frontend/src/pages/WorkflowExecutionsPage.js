import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { PlayCircle, CheckCircle2, XCircle, Clock, PauseCircle, Ban, RefreshCw } from 'lucide-react';

const STATUS_STYLE = {
    queued: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
    running: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    waiting: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    paused: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    completed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    failed: 'bg-red-500/15 text-red-300 border-red-500/30',
    cancelled: 'bg-slate-600/15 text-slate-400 border-slate-600/30',
    timed_out: 'bg-red-500/15 text-red-300 border-red-500/30',
};

const STATUS_ICON = {
    queued: Clock, running: RefreshCw, waiting: PauseCircle, paused: PauseCircle,
    completed: CheckCircle2, failed: XCircle, cancelled: Ban, timed_out: XCircle,
};

export const WorkflowExecutionsPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [executions, setExecutions] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        try {
            const [execRes, summaryRes] = await Promise.all([
                api.get('/v1/workflow-executions', { params: { limit: 100 } }),
                api.get('/v1/workflow-executions/observability/summary'),
            ]);
            setExecutions(execRes.data.executions || []);
            setSummary(summaryRes.data);
        } finally { setLoading(false); }
    }, [api]);

    useEffect(() => {
        load();
        const interval = setInterval(load, 15000);
        return () => clearInterval(interval);
    }, [load]);

    return (
        <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-white">Workflow Executions</h1>
                <Button size="sm" variant="outline" onClick={load}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh</Button>
            </div>

            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                    {[
                        ['Total', summary.total_executions],
                        ['Success Rate', summary.success_rate !== null ? `${summary.success_rate}%` : '—'],
                        ['Failure Rate', summary.failure_rate !== null ? `${summary.failure_rate}%` : '—'],
                        ['Avg Duration', summary.avg_duration_ms !== null ? `${summary.avg_duration_ms}ms` : '—'],
                        ['P95 Duration', summary.p95_duration_ms !== null ? `${summary.p95_duration_ms}ms` : '—'],
                        ['Approval Wait (avg)', summary.approval_wait_ms_avg !== null ? `${Math.round(summary.approval_wait_ms_avg / 1000)}s` : '—'],
                    ].map(([label, value]) => (
                        <Card key={label} className="bg-white/5 border-white/10">
                            <CardContent className="p-3">
                                <div className="text-[10px] text-white/50">{label}</div>
                                <div className="text-lg font-semibold text-white">{value}</div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <Card className="bg-white/5 border-white/10">
                <CardHeader><CardTitle className="text-sm">Recent Executions</CardTitle></CardHeader>
                <CardContent className="p-0">
                    <table className="w-full text-xs">
                        <thead className="text-white/40 border-b border-white/10">
                            <tr>
                                <th className="text-left p-2">Execution</th><th className="text-left p-2">Workflow</th>
                                <th className="text-left p-2">Status</th><th className="text-left p-2">Trigger</th>
                                <th className="text-left p-2">Started</th><th className="text-left p-2">Duration</th>
                            </tr>
                        </thead>
                        <tbody>
                            {executions.map((e) => {
                                const Icon = STATUS_ICON[e.status] || Clock;
                                return (
                                    <tr key={e.execution_id} className="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                                        onClick={() => navigate(`/ai/workflow-executions/${e.execution_id}`)}>
                                        <td className="p-2 font-mono text-[10px] text-white/70">{e.execution_id.slice(0, 8)}</td>
                                        <td className="p-2 text-white/70">{e.workflow_id?.slice(0, 8)}</td>
                                        <td className="p-2">
                                            <Badge variant="outline" className={`text-[10px] ${STATUS_STYLE[e.status] || ''}`}>
                                                <Icon className="w-3 h-3 mr-1" />{e.status}
                                            </Badge>
                                        </td>
                                        <td className="p-2 text-white/50">{e.trigger_type}{e.dry_run ? ' (dry run)' : ''}{e.test_run ? ' (test run)' : ''}</td>
                                        <td className="p-2 text-white/50">{e.started_at ? new Date(e.started_at).toLocaleString() : '—'}</td>
                                        <td className="p-2 text-white/50">{e.metrics?.duration_ms ? `${e.metrics.duration_ms}ms` : '—'}</td>
                                    </tr>
                                );
                            })}
                            {!loading && executions.length === 0 && (
                                <tr><td colSpan={6} className="p-4 text-center text-white/40">No executions yet.</td></tr>
                            )}
                        </tbody>
                    </table>
                </CardContent>
            </Card>
        </div>
    );
};

export default WorkflowExecutionsPage;
