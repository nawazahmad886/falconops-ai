import React, { useCallback, useImperativeHandle, useRef, useState, forwardRef } from 'react';
import {
    ReactFlow,
    Background,
    Controls,
    MiniMap,
    Handle,
    Position,
    MarkerType,
    addEdge,
    applyNodeChanges,
    applyEdgeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Badge } from './ui/badge';
import {
    Play, Clock, AlertTriangle, Radio, Zap, Webhook, Gauge, Activity,
    Bot, Brain, GitBranch, Sparkles, Scale,
    Database, FileSearch, Server, Globe, BookOpen, HardDrive,
    SplitSquareHorizontal, Shuffle, GitMerge, Repeat, Timer, RotateCcw, Hourglass,
    RefreshCw, ArrowUpCircle, Workflow, Ticket, Mail, MessageSquare, Send, ShieldAlert,
    UserCheck, ShieldCheck, KeyRound, ScrollText, CheckCircle2, HeartPulse, Target,
} from 'lucide-react';

export const NODE_CATEGORY_COLOR = {
    trigger: 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300',
    ai: 'border-violet-500/50 bg-violet-500/10 text-violet-300',
    data: 'border-blue-500/50 bg-blue-500/10 text-blue-300',
    control: 'border-amber-500/50 bg-amber-500/10 text-amber-300',
    action: 'border-red-500/50 bg-red-500/10 text-red-300',
    governance: 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300',
    validation: 'border-pink-500/50 bg-pink-500/10 text-pink-300',
};

const CATEGORY_OF = {};
[['trigger', ['trigger_manual', 'trigger_schedule', 'trigger_alert', 'trigger_incident', 'trigger_api', 'trigger_webhook', 'trigger_threshold', 'trigger_event']],
 ['ai', ['agent', 'planner', 'ai_decision', 'synthesizer', 'judge']],
 ['data', ['data_elasticsearch', 'data_apm', 'data_sql', 'data_metrics', 'data_logs', 'data_http', 'data_rag_search', 'data_memory']],
 ['control', ['condition', 'switch', 'parallel', 'join', 'loop', 'wait', 'retry', 'timeout']],
 ['action', ['action_restart_pod', 'action_scale_service', 'action_run_workflow', 'action_create_ticket', 'action_send_email', 'action_send_teams', 'action_send_slack', 'action_create_incident']],
 ['governance', ['human_approval', 'risk_check', 'permission_check', 'policy_check']],
 ['validation', ['verification', 'health_check', 'slo_check']],
].forEach(([cat, types]) => types.forEach((t) => { CATEGORY_OF[t] = cat; }));

export const NODE_TYPE_ICON = {
    trigger_manual: Play, trigger_schedule: Clock, trigger_alert: AlertTriangle, trigger_incident: ShieldAlert,
    trigger_api: Globe, trigger_webhook: Webhook, trigger_threshold: Gauge, trigger_event: Radio,
    agent: Bot, planner: Brain, ai_decision: GitBranch, synthesizer: Sparkles, judge: Scale,
    data_elasticsearch: FileSearch, data_apm: Activity, data_sql: Database, data_metrics: Gauge,
    data_logs: FileSearch, data_http: Globe, data_rag_search: BookOpen, data_memory: HardDrive,
    condition: SplitSquareHorizontal, switch: Shuffle, parallel: GitMerge, join: GitMerge,
    loop: Repeat, wait: Hourglass, retry: RotateCcw, timeout: Timer,
    action_restart_pod: RefreshCw, action_scale_service: ArrowUpCircle, action_run_workflow: Workflow,
    action_create_ticket: Ticket, action_send_email: Mail, action_send_teams: MessageSquare,
    action_send_slack: Send, action_create_incident: ShieldAlert,
    human_approval: UserCheck, risk_check: ShieldCheck, permission_check: KeyRound, policy_check: ScrollText,
    verification: CheckCircle2, health_check: HeartPulse, slo_check: Target,
};

export const NODE_PALETTE = [
    { category: 'trigger', label: 'Triggers', types: [
        ['trigger_manual', 'Manual'], ['trigger_schedule', 'Schedule'], ['trigger_alert', 'Alert'],
        ['trigger_incident', 'Incident'], ['trigger_api', 'API'], ['trigger_webhook', 'Webhook'],
        ['trigger_threshold', 'Threshold'], ['trigger_event', 'Event'],
    ]},
    { category: 'ai', label: 'AI', types: [
        ['agent', 'Agent'], ['planner', 'Planner'], ['ai_decision', 'AI Decision'],
        ['synthesizer', 'Synthesizer'], ['judge', 'Judge'],
    ]},
    { category: 'data', label: 'Data', types: [
        ['data_elasticsearch', 'Elasticsearch'], ['data_apm', 'APM'], ['data_sql', 'SQL'],
        ['data_metrics', 'Metrics'], ['data_logs', 'Logs'], ['data_http', 'HTTP API'],
        ['data_rag_search', 'RAG Search'], ['data_memory', 'Memory'],
    ]},
    { category: 'control', label: 'Control', types: [
        ['condition', 'Condition'], ['switch', 'Switch'], ['parallel', 'Parallel'], ['join', 'Join'],
        ['loop', 'Loop'], ['wait', 'Wait'], ['retry', 'Retry'], ['timeout', 'Timeout'],
    ]},
    { category: 'action', label: 'Action', types: [
        ['action_restart_pod', 'Restart Pod'], ['action_scale_service', 'Scale Service'],
        ['action_run_workflow', 'Run Workflow'], ['action_create_ticket', 'Create Ticket'],
        ['action_send_email', 'Send Email'], ['action_send_teams', 'Send Teams'],
        ['action_send_slack', 'Send Slack'], ['action_create_incident', 'Create Incident'],
    ]},
    { category: 'governance', label: 'Governance', types: [
        ['human_approval', 'Human Approval'], ['risk_check', 'Risk Check'],
        ['permission_check', 'Permission Check'], ['policy_check', 'Policy Check'],
    ]},
    { category: 'validation', label: 'Validation', types: [
        ['verification', 'Verification'], ['health_check', 'Health Check'], ['slo_check', 'SLO Check'],
    ]},
];

const STATUS_RING = {
    running: 'ring-2 ring-cyan-400 animate-pulse', completed: 'ring-1 ring-emerald-500/60',
    failed: 'ring-2 ring-red-500', waiting_approval: 'ring-2 ring-amber-400 animate-pulse',
    skipped: 'opacity-40', queued: 'ring-1 ring-white/10', cancelled: 'opacity-40',
};

const GenericNode = ({ data }) => {
    const Icon = NODE_TYPE_ICON[data.nodeType] || Bot;
    const category = CATEGORY_OF[data.nodeType] || 'data';
    const colorClass = NODE_CATEGORY_COLOR[category];
    const statusClass = data.status ? (STATUS_RING[data.status] || '') : '';
    return (
        <div
            className={`min-w-[200px] rounded-lg border-2 bg-[#0D1117] p-3 cursor-pointer transition-all ${colorClass} ${statusClass} ${data.selected ? 'outline outline-2 outline-white/60' : ''}`}
            onClick={data.onClick}
            data-testid={`wf-node-${data.nodeType}`}
        >
            <Handle type="target" position={Position.Top} className="!bg-white/40" />
            <div className="flex items-center gap-2">
                <Icon className="w-4 h-4 shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold text-white truncate">{data.label}</div>
                    <div className="text-[10px] text-white/40">{data.nodeType}</div>
                </div>
                {data.status && (
                    <Badge variant="outline" className="text-[9px] px-1 py-0">{data.status}</Badge>
                )}
            </div>
            <Handle type="source" position={Position.Bottom} className="!bg-white/40" />
        </div>
    );
};

const nodeTypes = { generic: GenericNode };

let _idCounter = 0;
const nextId = (prefix) => `${prefix}-${Date.now()}-${_idCounter++}`;

export function toFlowNodes(nodes, nodeExecutionByNodeId, onNodeClick) {
    return (nodes || []).map((n) => ({
        id: n.node_id,
        type: 'generic',
        position: n.position || { x: 0, y: 0 },
        data: {
            nodeType: n.type, label: n.label || n.type,
            status: nodeExecutionByNodeId ? nodeExecutionByNodeId[n.node_id]?.status : undefined,
            onClick: () => onNodeClick && onNodeClick(n.node_id),
        },
    }));
}

export function toFlowEdges(edges) {
    return (edges || []).map((e) => ({
        id: e.edge_id, source: e.source, target: e.target,
        sourceHandle: e.source_handle || undefined, targetHandle: e.target_handle || undefined,
        label: e.condition_branch || e.label || undefined,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: 'rgba(255,255,255,0.3)' },
    }));
}

/**
 * Editable (readOnly=false) or runtime-locked (readOnly=true) workflow
 * canvas. Generalizes WorkflowCanvas.js's existing @xyflow/react usage
 * (nodesDraggable=false there) into a real editor: drag, connect, delete,
 * multi-select, minimap/controls (all free from the library), plus an
 * in-component undo/redo stack (React Flow has no built-in undo/redo).
 */
export const WorkflowCanvasEditor = forwardRef(({
    nodes: initialNodes, edges: initialEdges, onGraphChange, onNodeSelect, readOnly = false,
    nodeExecutionByNodeId,
}, ref) => {
    const [flowNodes, setFlowNodes] = useState(() => toFlowNodes(initialNodes, nodeExecutionByNodeId, onNodeSelect));
    const [flowEdges, setFlowEdges] = useState(() => toFlowEdges(initialEdges));
    const historyRef = useRef([]);
    const futureRef = useRef([]);
    const lastEmittedRef = useRef(null);

    React.useEffect(() => {
        setFlowNodes(toFlowNodes(initialNodes, nodeExecutionByNodeId, onNodeSelect));
    }, [initialNodes, nodeExecutionByNodeId]); // eslint-disable-line react-hooks/exhaustive-deps

    React.useEffect(() => {
        setFlowEdges(toFlowEdges(initialEdges));
    }, [initialEdges]);

    const emitChange = useCallback((nextNodes, nextEdges) => {
        if (!onGraphChange) return;
        const graph = {
            nodes: nextNodes.map((n) => ({
                node_id: n.id, type: n.data.nodeType, position: n.position,
                label: n.data.label, config: n.data.config || {}, data_mapping: n.data.data_mapping || {},
            })),
            edges: nextEdges.map((e) => ({
                edge_id: e.id, source: e.source, target: e.target,
                source_handle: e.sourceHandle || null, target_handle: e.targetHandle || null,
                condition_branch: typeof e.label === 'string' ? e.label : null,
            })),
        };
        lastEmittedRef.current = JSON.stringify(graph);
        onGraphChange(graph);
    }, [onGraphChange]);

    const pushHistory = useCallback(() => {
        historyRef.current.push({ nodes: flowNodes, edges: flowEdges });
        if (historyRef.current.length > 50) historyRef.current.shift();
        futureRef.current = [];
    }, [flowNodes, flowEdges]);

    const onNodesChange = useCallback((changes) => {
        setFlowNodes((nds) => {
            const next = applyNodeChanges(changes, nds);
            emitChange(next, flowEdges);
            return next;
        });
    }, [flowEdges, emitChange]);

    const onEdgesChange = useCallback((changes) => {
        setFlowEdges((eds) => {
            const next = applyEdgeChanges(changes, eds);
            emitChange(flowNodes, next);
            return next;
        });
    }, [flowNodes, emitChange]);

    const onConnect = useCallback((connection) => {
        if (readOnly) return;
        pushHistory();
        setFlowEdges((eds) => {
            const next = addEdge({ ...connection, id: nextId('edge'), markerEnd: { type: MarkerType.ArrowClosed },
                                    style: { stroke: 'rgba(255,255,255,0.3)' } }, eds);
            emitChange(flowNodes, next);
            return next;
        });
    }, [readOnly, flowNodes, emitChange, pushHistory]);

    const addNode = useCallback((nodeType, label) => {
        pushHistory();
        const id = nextId('node');
        const position = { x: 80 + Math.random() * 300, y: 80 + Math.random() * 400 };
        setFlowNodes((nds) => {
            const next = [...nds, { id, type: 'generic', position,
                data: { nodeType, label, config: {}, data_mapping: {}, onClick: () => onNodeSelect && onNodeSelect(id) } }];
            emitChange(next, flowEdges);
            return next;
        });
        return id;
    }, [flowEdges, emitChange, onNodeSelect, pushHistory]);

    const deleteSelected = useCallback(() => {
        pushHistory();
        setFlowNodes((nds) => {
            const next = nds.filter((n) => !n.selected);
            const removedIds = new Set(nds.filter((n) => n.selected).map((n) => n.id));
            setFlowEdges((eds) => {
                const nextEdges = eds.filter((e) => !e.selected && !removedIds.has(e.source) && !removedIds.has(e.target));
                emitChange(next, nextEdges);
                return nextEdges;
            });
            return next;
        });
    }, [emitChange, pushHistory]);

    const undo = useCallback(() => {
        const prev = historyRef.current.pop();
        if (!prev) return;
        futureRef.current.push({ nodes: flowNodes, edges: flowEdges });
        setFlowNodes(prev.nodes);
        setFlowEdges(prev.edges);
        emitChange(prev.nodes, prev.edges);
    }, [flowNodes, flowEdges, emitChange]);

    const redo = useCallback(() => {
        const next = futureRef.current.pop();
        if (!next) return;
        historyRef.current.push({ nodes: flowNodes, edges: flowEdges });
        setFlowNodes(next.nodes);
        setFlowEdges(next.edges);
        emitChange(next.nodes, next.edges);
    }, [flowNodes, flowEdges, emitChange]);

    const onKeyDown = useCallback((e) => {
        if (readOnly) return;
        if ((e.key === 'Delete' || e.key === 'Backspace') && document.activeElement?.tagName !== 'INPUT') {
            deleteSelected();
        } else if (e.ctrlKey && e.key === 'z') { undo(); }
        else if (e.ctrlKey && e.key === 'y') { redo(); }
    }, [readOnly, deleteSelected, undo, redo]);

    const updateNodeConfig = useCallback((nodeId, updates) => {
        pushHistory();
        setFlowNodes((nds) => {
            const next = nds.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n);
            emitChange(next, flowEdges);
            return next;
        });
    }, [flowEdges, emitChange, pushHistory]);

    useImperativeHandle(ref, () => ({ addNode, deleteSelected, undo, redo, updateNodeConfig }), [addNode, deleteSelected, undo, redo, updateNodeConfig]);

    return (
        <div className="w-full h-full" tabIndex={0} onKeyDown={onKeyDown} data-testid="workflow-canvas">
            <ReactFlow
                nodes={flowNodes}
                edges={flowEdges}
                nodeTypes={nodeTypes}
                onNodesChange={readOnly ? undefined : onNodesChange}
                onEdgesChange={readOnly ? undefined : onEdgesChange}
                onConnect={readOnly ? undefined : onConnect}
                nodesDraggable={!readOnly}
                nodesConnectable={!readOnly}
                elementsSelectable
                selectionOnDrag={!readOnly}
                onlyRenderVisibleElements
                fitView
                proOptions={{ hideAttribution: true }}
            >
                <Background color="#1f2937" gap={20} />
                <Controls />
                <MiniMap pannable zoomable nodeColor={() => '#0D1117'} maskColor="rgba(0,0,0,0.6)" />
            </ReactFlow>
            {!readOnly && (
                <div className="absolute top-2 right-2 flex gap-1 z-10">
                    <button onClick={undo} className="text-xs px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10 text-white/70">Undo</button>
                    <button onClick={redo} className="text-xs px-2 py-1 rounded bg-white/5 border border-white/10 hover:bg-white/10 text-white/70">Redo</button>
                    <button onClick={deleteSelected} className="text-xs px-2 py-1 rounded bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 text-red-300">Delete Selected</button>
                </div>
            )}
        </div>
    );
});

export default WorkflowCanvasEditor;
