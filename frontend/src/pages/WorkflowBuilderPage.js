import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
    Save, CheckCircle2, Rocket, FlaskConical, Sparkles, Download, Upload,
    History, AlertTriangle, XCircle, PlayCircle, MoreHorizontal,
} from 'lucide-react';
import { WorkflowCanvasEditor, NODE_PALETTE, NODE_CATEGORY_COLOR, NODE_TYPE_ICON } from '../components/WorkflowCanvasEditor';
import { NodeConfigPanel } from '../components/NodeConfigPanel';

export const WorkflowBuilderPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const { workflowId: routeWorkflowId } = useParams();

    const [workflowId, setWorkflowId] = useState(routeWorkflowId || null);
    const [workflowName, setWorkflowName] = useState('Untitled Workflow');
    const [definition, setDefinition] = useState(null);
    const [graph, setGraph] = useState({ nodes: [], edges: [] });
    const [selectedNodeId, setSelectedNodeId] = useState(null);
    const [agentCatalog, setAgentCatalog] = useState([]);
    const [toolCatalog, setToolCatalog] = useState([]);
    const [findings, setFindings] = useState([]);
    const [aiPrompt, setAiPrompt] = useState('');
    const [aiPreview, setAiPreview] = useState(null);
    const [showAiDialog, setShowAiDialog] = useState(false);
    const [saving, setSaving] = useState(false);
    const canvasRef = useRef(null);
    const graphRef = useRef(graph);
    graphRef.current = graph;

    const loadCatalogs = useCallback(async () => {
        try {
            const [agentsRes, toolsRes] = await Promise.all([
                api.get('/v1/agent-builder/agent-catalog'),
                api.get('/v1/tools'),
            ]);
            setAgentCatalog(agentsRes.data.agents || []);
            setToolCatalog((toolsRes.data.tools || []).filter((t) => t.status === 'active'));
        } catch (e) { /* honest degrade — pickers just show empty */ }
    }, [api]);

    const loadWorkflow = useCallback(async (id) => {
        try {
            const res = await api.get(`/v1/workflows/${id}`);
            setDefinition(res.data.definition);
            setWorkflowName(res.data.definition?.name || 'Untitled Workflow');
            const version = res.data.version;
            setGraph({ nodes: version?.nodes || [], edges: version?.edges || [] });
        } catch (e) {
            toast.error('Failed to load workflow');
        }
    }, [api]);

    useEffect(() => { loadCatalogs(); }, [loadCatalogs]);
    useEffect(() => { if (routeWorkflowId) loadWorkflow(routeWorkflowId); }, [routeWorkflowId, loadWorkflow]);

    const ensureWorkflow = useCallback(async () => {
        if (workflowId) return workflowId;
        const res = await api.post('/v1/workflows', { payload: { name: workflowName } });
        setWorkflowId(res.data.definition.workflow_id);
        navigate(`/ai/workflow-builder/${res.data.definition.workflow_id}`, { replace: true });
        return res.data.definition.workflow_id;
    }, [workflowId, workflowName, api, navigate]);

    const handleSave = useCallback(async () => {
        setSaving(true);
        try {
            const id = await ensureWorkflow();
            await api.put(`/v1/workflows/${id}/draft`, { updates: { name: workflowName, nodes: graphRef.current.nodes, edges: graphRef.current.edges } });
            toast.success('Draft saved');
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'Save failed');
        } finally { setSaving(false); }
    }, [ensureWorkflow, workflowName, api]);

    const handleValidate = useCallback(async () => {
        const id = await ensureWorkflow();
        await handleSave();
        try {
            const res = await api.post(`/v1/workflows/${id}/validate`);
            setFindings(res.data.findings || []);
            if (!res.data.findings?.length) toast.success('Validation passed');
            else toast.warning(`${res.data.findings.length} finding(s)`);
        } catch (e) {
            toast.error('Validation failed to run');
        }
    }, [ensureWorkflow, handleSave, api]);

    const handlePublish = useCallback(async () => {
        const id = await ensureWorkflow();
        await handleSave();
        try {
            const res = await api.post(`/v1/workflows/${id}/publish`, { force: false });
            toast.success(`Published v${res.data.published_version}`);
            setFindings(res.data.findings || []);
        } catch (e) {
            const detail = e?.response?.data?.detail;
            setFindings(detail?.findings || []);
            toast.error('Publish blocked — fix validation errors first');
        }
    }, [ensureWorkflow, handleSave, api]);

    const runExecution = useCallback(async (mode) => {
        const id = await ensureWorkflow();
        await handleSave();
        try {
            const path = mode === 'dry_run' ? 'dry-run' : mode === 'test_run' ? 'test-run' : 'execute';
            const res = await api.post(`/v1/workflow-executions/${id}/${path}`, { trigger_payload: {} });
            toast.success(`Execution started: ${res.data.execution_id}`);
            navigate(`/ai/workflow-executions/${res.data.execution_id}`);
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'Failed to start execution');
        }
    }, [ensureWorkflow, handleSave, api, navigate]);

    const handleGenerate = useCallback(async () => {
        if (!aiPrompt.trim()) return;
        try {
            const res = await api.post('/v1/workflows/generate', { description: aiPrompt });
            setAiPreview(res.data);
        } catch (e) {
            toast.error('AI generation failed');
        }
    }, [aiPrompt, api]);

    const acceptAiPreview = useCallback(() => {
        if (!aiPreview?.graph) return;
        setGraph(aiPreview.graph);
        setShowAiDialog(false);
        setAiPreview(null);
        toast.info('AI-generated graph loaded into the canvas as a draft — review, then Save.');
    }, [aiPreview]);

    const handleExport = useCallback(async () => {
        if (!workflowId) return;
        const res = await api.get(`/v1/workflows/${workflowId}/export?format=json`);
        const blob = new Blob([res.data.content], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${workflowName}.json`; a.click();
        URL.revokeObjectURL(url);
    }, [workflowId, workflowName, api]);

    const selectedNode = graph.nodes.find((n) => n.node_id === selectedNodeId);
    const canvasNode = selectedNode ? { id: selectedNode.node_id, data: { nodeType: selectedNode.type, label: selectedNode.label, config: selectedNode.config, data_mapping: selectedNode.data_mapping } } : null;
    const upstreamNodeIds = graph.nodes.filter((n) => n.node_id !== selectedNodeId).map((n) => n.node_id);

    const onGraphChange = useCallback((g) => setGraph(g), []);
    const onNodeConfigChange = useCallback((patch) => {
        if (!selectedNodeId) return;
        setGraph((g) => ({ ...g, nodes: g.nodes.map((n) => n.node_id === selectedNodeId ? { ...n, ...patch, config: patch.config ?? n.config, data_mapping: patch.data_mapping ?? n.data_mapping } : n) }));
    }, [selectedNodeId]);

    return (
        <div className="h-screen flex flex-col bg-[#050810]">
            <div className="border-b border-white/10 px-4 py-2 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <Input className="h-8 w-64 text-sm bg-muted/30" value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} />
                    {definition && <Badge variant="outline" className="text-[10px]">{definition.status}</Badge>}
                </div>
                <div className="flex items-center gap-1.5">
                    <Button size="sm" variant="outline" onClick={() => setShowAiDialog(true)}><Sparkles className="w-3.5 h-3.5 mr-1" />Build with AI</Button>
                    <Button size="sm" variant="outline" onClick={handleSave} disabled={saving}><Save className="w-3.5 h-3.5 mr-1" />Save</Button>
                    <Button size="sm" variant="outline" onClick={handleValidate}><CheckCircle2 className="w-3.5 h-3.5 mr-1" />Validate</Button>
                    <Button size="sm" variant="outline" onClick={() => runExecution('dry_run')}><FlaskConical className="w-3.5 h-3.5 mr-1" />Dry Run</Button>
                    <Button size="sm" variant="outline" onClick={() => runExecution('test_run')}><PlayCircle className="w-3.5 h-3.5 mr-1" />Test Run</Button>
                    <Button size="sm" variant="outline" onClick={handleExport}><Download className="w-3.5 h-3.5 mr-1" />Export</Button>
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={handlePublish}><Rocket className="w-3.5 h-3.5 mr-1" />Publish</Button>
                </div>
            </div>

            {findings.length > 0 && (
                <div className="border-b border-white/10 bg-black/30 px-4 py-2 max-h-28 overflow-y-auto shrink-0">
                    {findings.map((f, i) => (
                        <div key={i} className={`text-xs flex items-center gap-2 ${f.severity === 'error' ? 'text-red-400' : 'text-amber-400'}`}>
                            {f.severity === 'error' ? <XCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                            <span>{f.message}</span>
                        </div>
                    ))}
                </div>
            )}

            <div className="flex-1 flex min-h-0">
                <div className="w-48 shrink-0 border-r border-white/10 overflow-y-auto p-2 space-y-3">
                    {NODE_PALETTE.map((group) => (
                        <div key={group.category}>
                            <div className="text-[10px] uppercase text-white/40 mb-1 px-1">{group.label}</div>
                            <div className="space-y-1">
                                {group.types.map(([type, label]) => (
                                    <button
                                        key={type}
                                        className={`w-full text-left text-[11px] px-2 py-1.5 rounded border ${NODE_CATEGORY_COLOR[group.category]} hover:brightness-125 transition`}
                                        onClick={() => canvasRef.current?.addNode(type, label)}
                                        data-testid={`palette-${type}`}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="flex-1 relative min-w-0">
                    <WorkflowCanvasEditor
                        ref={canvasRef}
                        nodes={graph.nodes}
                        edges={graph.edges}
                        onGraphChange={onGraphChange}
                        onNodeSelect={setSelectedNodeId}
                    />
                </div>

                {canvasNode && (
                    <NodeConfigPanel
                        node={canvasNode}
                        upstreamNodeIds={upstreamNodeIds}
                        agentCatalog={agentCatalog}
                        toolCatalog={toolCatalog}
                        onChange={onNodeConfigChange}
                        onClose={() => setSelectedNodeId(null)}
                    />
                )}
            </div>

            {showAiDialog && (
                <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowAiDialog(false)}>
                    <div className="bg-[#0D1117] border border-white/10 rounded-lg p-4 w-[560px] max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2"><Sparkles className="w-4 h-4" />Build with AI</h3>
                        <p className="text-xs text-white/50 mb-2">Describe the workflow. The AI generates a draft graph — nothing is deployed automatically; you review, edit, validate, then Publish.</p>
                        <textarea className="w-full h-24 text-xs bg-muted/30 rounded p-2 border border-white/10" value={aiPrompt}
                            onChange={(e) => setAiPrompt(e.target.value)}
                            placeholder="Create a workflow that investigates high API latency, checks Elastic and APM, checks database performance, asks for approval before restarting the service, then verifies recovery." />
                        <div className="flex justify-end gap-2 mt-2">
                            <Button size="sm" variant="outline" onClick={handleGenerate}>Generate</Button>
                        </div>
                        {aiPreview && (
                            <div className="mt-3 border-t border-white/10 pt-3">
                                <div className="text-xs text-white/70 mb-1">{aiPreview.graph.nodes.length} nodes, {aiPreview.graph.edges.length} edges generated.</div>
                                {aiPreview.validation_result?.length > 0 && (
                                    <div className="text-[10px] text-amber-400 mb-2">{aiPreview.validation_result.length} validation finding(s) — review after loading.</div>
                                )}
                                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={acceptAiPreview}>Load into Canvas</Button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default WorkflowBuilderPage;
