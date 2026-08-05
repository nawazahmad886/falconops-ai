import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { CheckCircle2, XCircle, ShieldAlert } from 'lucide-react';
import { WorkflowCanvasEditor } from '../components/WorkflowCanvasEditor';

export const WorkflowExecutionDetailPage = () => {
    const { api } = useAuth();
    const { executionId } = useParams();
    const [execution, setExecution] = useState(null);
    const [nodeExecutions, setNodeExecutions] = useState([]);
    const [pendingApprovals, setPendingApprovals] = useState([]);
    const [trace, setTrace] = useState([]);
    const [graph, setGraph] = useState({ nodes: [], edges: [] });
    const [selectedNodeId, setSelectedNodeId] = useState(null);
    const eventSourceRef = useRef(null);

    const load = useCallback(async () => {
        try {
            const res = await api.get(`/v1/workflow-executions/${executionId}`);
            setExecution(res.data.execution);
            setNodeExecutions(res.data.node_executions || []);
            setPendingApprovals(res.data.pending_approvals || []);
            setGraph({ nodes: res.data.execution.execution_graph_snapshot?.nodes || [], edges: res.data.execution.execution_graph_snapshot?.edges || [] });
        } catch (e) {
            toast.error('Failed to load execution');
        }
    }, [api, executionId]);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        const token = localStorage.getItem('falconToken');
        const backendUrl = process.env.REACT_APP_BACKEND_URL;
        const controller = new AbortController();
        (async () => {
            try {
                const response = await fetch(`${backendUrl}/api/v1/workflow-executions/${executionId}/stream`, {
                    headers: { Authorization: `Bearer ${token}` }, signal: controller.signal,
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const parts = buffer.split('\n\n');
                    buffer = parts.pop();
                    for (const part of parts) {
                        const dataLine = part.split('\n').find((l) => l.startsWith('data:'));
                        if (!dataLine) continue;
                        try {
                            const evt = JSON.parse(dataLine.slice(5).trim());
                            setTrace((t) => [...t, evt]);
                            if (evt.kind === 'end' || evt.kind === 'approval') load();
                        } catch (e) { /* skip malformed frame */ }
                    }
                }
            } catch (e) { /* stream ended or aborted */ }
        })();
        const poll = setInterval(load, 8000);
        return () => { controller.abort(); clearInterval(poll); };
    }, [executionId, load]);

    const nodeExecutionByNodeId = {};
    for (const ne of nodeExecutions) {
        if (!nodeExecutionByNodeId[ne.node_id] || new Date(ne.started_at) > new Date(nodeExecutionByNodeId[ne.node_id].started_at)) {
            nodeExecutionByNodeId[ne.node_id] = ne;
        }
    }

    const decide = useCallback(async (approvalId, approved) => {
        try {
            await api.post(`/v1/workflow-executions/approvals/${approvalId}/${approved ? 'approve' : 'reject'}`, {});
            toast.success(approved ? 'Approved' : 'Rejected');
            load();
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'Decision failed');
        }
    }, [api, load]);

    const selectedNodeExec = selectedNodeId ? nodeExecutionByNodeId[selectedNodeId] : null;

    return (
        <div className="h-screen flex flex-col bg-[#050810]">
            <div className="border-b border-white/10 px-4 py-2 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-white/70">{executionId}</span>
                    {execution && <Badge variant="outline" className="text-[10px]">{execution.status}</Badge>}
                    {execution?.dry_run && <Badge variant="outline" className="text-[10px] text-amber-300 border-amber-500/40">DRY RUN</Badge>}
                    {execution?.test_run && <Badge variant="outline" className="text-[10px] text-cyan-300 border-cyan-500/40">TEST RUN</Badge>}
                </div>
            </div>

            {pendingApprovals.length > 0 && (
                <div className="border-b border-white/10 bg-amber-500/10 px-4 py-2 space-y-1 shrink-0">
                    {pendingApprovals.map((a) => (
                        <div key={a.approval_id} className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2 text-amber-300">
                                <ShieldAlert className="w-3.5 h-3.5" />
                                <span>{a.title} (risk: {a.risk_tier})</span>
                            </div>
                            <div className="flex gap-1.5">
                                <Button size="sm" className="h-6 text-[10px] bg-emerald-600 hover:bg-emerald-700" onClick={() => decide(a.approval_id, true)}>
                                    <CheckCircle2 className="w-3 h-3 mr-1" />Approve
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => decide(a.approval_id, false)}>
                                    <XCircle className="w-3 h-3 mr-1" />Reject
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div className="flex-1 flex min-h-0">
                <div className="flex-1 relative min-w-0">
                    <WorkflowCanvasEditor
                        nodes={graph.nodes} edges={graph.edges} readOnly
                        nodeExecutionByNodeId={nodeExecutionByNodeId}
                        onNodeSelect={setSelectedNodeId}
                    />
                </div>
                <div className="w-96 shrink-0 border-l border-white/10 overflow-y-auto">
                    {selectedNodeExec && (
                        <div className="p-3 border-b border-white/10 space-y-2">
                            <div className="text-xs font-semibold text-white">{selectedNodeId} — {selectedNodeExec.status}</div>
                            <div className="text-[10px] text-white/50">Input</div>
                            <pre className="text-[10px] bg-black/30 rounded p-2 overflow-x-auto text-white/70">{JSON.stringify(selectedNodeExec.input, null, 2)}</pre>
                            <div className="text-[10px] text-white/50">Output</div>
                            <pre className="text-[10px] bg-black/30 rounded p-2 overflow-x-auto text-white/70">{JSON.stringify(selectedNodeExec.output, null, 2)}</pre>
                            {selectedNodeExec.error && <div className="text-[10px] text-red-400">{selectedNodeExec.error}</div>}
                        </div>
                    )}
                    <Card className="bg-transparent border-0 rounded-none">
                        <CardHeader className="p-3"><CardTitle className="text-xs">Live Trace</CardTitle></CardHeader>
                        <CardContent className="p-3 pt-0 space-y-1.5">
                            {trace.map((t, i) => (
                                <div key={i} className="text-[10px] border-l-2 border-white/10 pl-2">
                                    <span className="text-white/40">[{t.kind}]</span> <span className="text-white/70">{t.title}</span>
                                    {t.node_id && <span className="text-white/30"> ({t.node_id})</span>}
                                </div>
                            ))}
                            {trace.length === 0 && <div className="text-white/30 text-[10px]">Waiting for trace events…</div>}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
};

export default WorkflowExecutionDetailPage;
