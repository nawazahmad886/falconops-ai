import React, { useMemo, useState } from 'react';
import {
    ReactFlow,
    Background,
    Controls,
    Handle,
    Position,
    MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog';
import { Zap, Plus, X, Trash2, Bot, Clock, AlertTriangle, Radio, Play } from 'lucide-react';
import { ACTION_TYPES, StepConfigPanel } from './VisualWorkflowBuilder';

const TRIGGER_ICONS = {
    on_demand: Play,
    problem: AlertTriangle,
    event: Radio,
    ai_anomaly: Zap,
    schedule: Clock,
};

// ======================== Custom Nodes ========================

const TriggerNodeCard = ({ data }) => {
    const Icon = TRIGGER_ICONS[data.triggerType] || Play;
    return (
        <div
            className="min-w-[220px] rounded-lg border-2 border-cyan-500/40 bg-[#0D1117] p-3 cursor-pointer hover:border-cyan-400 transition-colors"
            onClick={data.onClick}
            data-testid="canvas-trigger-node"
        >
            <div className="flex items-center gap-2">
                <div className="p-1.5 rounded bg-cyan-500/15">
                    <Icon className="w-4 h-4 text-cyan-400" />
                </div>
                <div>
                    <div className="text-xs text-cyan-400 font-semibold">{data.label}</div>
                    <div className="text-[10px] text-white/40">{data.subtitle}</div>
                </div>
            </div>
            <Handle type="source" position={Position.Bottom} className="!bg-cyan-500" />
        </div>
    );
};

const StepNodeCard = ({ data }) => {
    const actionType = ACTION_TYPES[data.step.action_type];
    const Icon = actionType?.icon || Bot;
    return (
        <div
            className="min-w-[220px] rounded-lg border-2 border-white/10 bg-[#0D1117] p-3 cursor-pointer hover:border-white/30 transition-colors relative group"
            onClick={data.onClick}
            data-testid={`canvas-step-node-${data.index}`}
        >
            <Handle type="target" position={Position.Top} className="!bg-white/30" />
            <div className="flex items-center gap-2">
                <div className={`p-1.5 rounded ${actionType?.color || 'bg-gray-500'}`}>
                    <Icon className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold text-white truncate">
                        {data.step.name || actionType?.label || data.step.action_type}
                    </div>
                    <div className="text-[10px] text-white/40">{actionType?.label}</div>
                </div>
                <button
                    className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300"
                    onClick={(e) => { e.stopPropagation(); data.onDelete(); }}
                    data-testid={`canvas-step-delete-${data.index}`}
                >
                    <Trash2 className="w-3.5 h-3.5" />
                </button>
            </div>
            <Handle type="source" position={Position.Bottom} className="!bg-white/30" />
        </div>
    );
};

const nodeTypes = { triggerNode: TriggerNodeCard, stepNode: StepNodeCard };

// ======================== Trigger Config Panel ========================

const TriggerConfigPanel = ({ trigger, triggerTypes, onChange, onClose }) => {
    const typeInfo = triggerTypes.find(t => t.id === trigger.type) || triggerTypes[0];

    const updateFilterField = (filterKey, fieldName, value) => {
        onChange({
            ...trigger,
            [filterKey]: { ...(trigger[filterKey] || {}), [fieldName]: value },
        });
    };

    const filterKeyFor = (typeId) => ({
        problem: 'problem_filter',
        event: 'event_filter',
        ai_anomaly: 'anomaly_filter',
        schedule: 'schedule',
    }[typeId]);

    const filterKey = filterKeyFor(trigger.type);
    const filterValues = (filterKey && trigger[filterKey]) || {};

    return (
        <div className="space-y-4 p-4 bg-muted/20 rounded-lg border border-white/10">
            <div className="flex items-center justify-between">
                <h4 className="font-semibold">Trigger</h4>
                <Button variant="ghost" size="icon" onClick={onClose}><X className="w-4 h-4" /></Button>
            </div>
            <div className="space-y-2">
                <Label>Trigger Type</Label>
                <Select value={trigger.type} onValueChange={(v) => onChange({ type: v })}>
                    <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                    <SelectContent>
                        {triggerTypes.map(t => (
                            <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {typeInfo?.description && (
                    <p className="text-xs text-muted-foreground">{typeInfo.description}</p>
                )}
            </div>

            {typeInfo?.filter_fields?.map((field) => {
                const val = filterValues[field.name] ?? '';
                if (field.type === 'multiselect') {
                    const selected = Array.isArray(val) ? val : [];
                    return (
                        <div key={field.name} className="space-y-2">
                            <Label>{field.label}</Label>
                            <div className="flex flex-wrap gap-1">
                                {field.options.map(opt => (
                                    <Badge
                                        key={opt}
                                        variant={selected.includes(opt) ? 'default' : 'outline'}
                                        className="cursor-pointer text-[10px]"
                                        onClick={() => {
                                            const next = selected.includes(opt)
                                                ? selected.filter(s => s !== opt)
                                                : [...selected, opt];
                                            updateFilterField(filterKey, field.name, next);
                                        }}
                                    >
                                        {opt}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    );
                }
                if (field.type === 'select') {
                    return (
                        <div key={field.name} className="space-y-2">
                            <Label>{field.label}</Label>
                            <Select value={val || ''} onValueChange={(v) => updateFilterField(filterKey, field.name, v)}>
                                <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {field.options.map(opt => (
                                        <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    );
                }
                return (
                    <div key={field.name} className="space-y-2">
                        <Label>{field.label}</Label>
                        <Input
                            type={field.type === 'number' ? 'number' : 'text'}
                            value={val}
                            onChange={(e) => updateFilterField(filterKey, field.name, e.target.value)}
                            className="bg-muted/50"
                        />
                    </div>
                );
            })}
        </div>
    );
};

// ======================== Main Canvas ========================

export const WorkflowCanvas = ({
    trigger,
    onTriggerChange,
    steps = [],
    onStepsChange,
    triggerTypes = [],
    agentCatalog = [],
}) => {
    const [selected, setSelected] = useState(null); // { kind: 'trigger' } | { kind: 'step', index }
    const [showActionPicker, setShowActionPicker] = useState(false);

    const effectiveTrigger = trigger || { type: 'on_demand' };
    const effectiveTriggerTypes = triggerTypes.length > 0 ? triggerTypes : [
        { id: 'on_demand', name: 'On-Demand', description: 'Only runs when manually executed', filter_fields: [] },
    ];

    const addStep = (actionType) => {
        onStepsChange([...steps, { name: '', action_type: actionType, config: {}, continue_on_failure: false }]);
        setSelected({ kind: 'step', index: steps.length });
        setShowActionPicker(false);
    };

    const updateStep = (index, updated) => {
        const next = [...steps];
        next[index] = updated;
        onStepsChange(next);
    };

    const deleteStep = (index) => {
        onStepsChange(steps.filter((_, i) => i !== index));
        if (selected?.kind === 'step' && selected.index === index) setSelected(null);
    };

    const { nodes, edges } = useMemo(() => {
        const ns = [
            {
                id: 'trigger',
                type: 'triggerNode',
                position: { x: 40, y: 0 },
                data: {
                    label: effectiveTriggerTypes.find(t => t.id === effectiveTrigger.type)?.name || 'Trigger',
                    subtitle: effectiveTrigger.type === 'on_demand' ? 'Manual execution only' : 'Click to configure',
                    triggerType: effectiveTrigger.type,
                    onClick: () => setSelected({ kind: 'trigger' }),
                },
                draggable: false,
            },
            ...steps.map((step, index) => ({
                id: `step-${index}`,
                type: 'stepNode',
                position: { x: 40, y: (index + 1) * 130 },
                data: {
                    step,
                    index,
                    onClick: () => setSelected({ kind: 'step', index }),
                    onDelete: () => deleteStep(index),
                },
                draggable: false,
            })),
        ];

        const es = [];
        for (let i = -1; i < steps.length - 1; i++) {
            es.push({
                id: `e-${i}`,
                source: i === -1 ? 'trigger' : `step-${i}`,
                target: i === -1 ? 'step-0' : `step-${i + 1}`,
                animated: true,
                markerEnd: { type: MarkerType.ArrowClosed },
                style: { stroke: '#22d3ee55' },
            });
        }
        return { nodes: ns, edges: es };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [steps, effectiveTrigger, effectiveTriggerTypes]);

    return (
        <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2 h-[520px] rounded-lg border border-white/10 bg-[#090C10] relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    fitView
                    nodesDraggable={false}
                    nodesConnectable={false}
                    elementsSelectable={true}
                    proOptions={{ hideAttribution: true }}
                >
                    <Background color="#ffffff10" gap={20} />
                    <Controls showInteractive={false} />
                </ReactFlow>
                <div className="absolute bottom-4 right-4">
                    <Button size="sm" onClick={() => setShowActionPicker(true)} data-testid="canvas-add-step-btn">
                        <Plus className="w-4 h-4 mr-1" /> Add Step
                    </Button>
                </div>
            </div>

            <div>
                {selected?.kind === 'trigger' && (
                    <TriggerConfigPanel
                        trigger={effectiveTrigger}
                        triggerTypes={effectiveTriggerTypes}
                        onChange={(updated) => onTriggerChange({ ...effectiveTrigger, ...updated })}
                        onClose={() => setSelected(null)}
                    />
                )}
                {selected?.kind === 'step' && steps[selected.index] && (
                    <StepConfigPanel
                        step={steps[selected.index]}
                        onChange={(updated) => updateStep(selected.index, updated)}
                        onClose={() => setSelected(null)}
                        agentCatalog={agentCatalog}
                    />
                )}
                {!selected && (
                    <div className="p-8 rounded-lg bg-muted/10 border border-white/5 text-center text-muted-foreground text-sm">
                        Click the trigger or any step node to configure it.
                    </div>
                )}
            </div>

            <Dialog open={showActionPicker} onOpenChange={setShowActionPicker}>
                <DialogContent className="max-w-2xl bg-card border-border max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Add Workflow Step</DialogTitle>
                    </DialogHeader>
                    <div className="grid grid-cols-3 gap-3 pt-4">
                        {Object.entries(ACTION_TYPES).map(([key, action]) => {
                            const Icon = action.icon;
                            return (
                                <button
                                    key={key}
                                    onClick={() => addStep(key)}
                                    className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 border border-white/5 hover:border-white/10 transition-all text-left"
                                    data-testid={`canvas-add-action-${key}`}
                                >
                                    <div className={`p-2 rounded ${action.color}`}>
                                        <Icon className="w-4 h-4 text-white" />
                                    </div>
                                    <div>
                                        <div className="font-medium text-sm">{action.label}</div>
                                        <div className="text-xs text-muted-foreground">{action.description}</div>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default WorkflowCanvas;
