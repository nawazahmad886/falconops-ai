import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '../components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Plus,
    Trash2,
    GripVertical,
    Play,
    Save,
    Eye,
    ChevronDown,
    ChevronUp,
    Globe,
    Terminal,
    Bell,
    Timer,
    GitBranch,
    Webhook,
    FileText,
    BarChart,
    Power,
    UserCheck,
    Key,
    Database,
    Box,
    Code,
    Variable,
    Repeat,
    Layers,
    ArrowDown,
    Settings,
    X,
    Check,
    AlertCircle,
} from 'lucide-react';

// Action type configurations
const ACTION_TYPES = {
    http_request: { 
        icon: Globe, 
        label: 'HTTP Request', 
        color: 'bg-blue-500',
        description: 'Make REST API calls',
        fields: ['method', 'url', 'headers', 'body', 'timeout']
    },
    shell_command: { 
        icon: Terminal, 
        label: 'Shell Command', 
        color: 'bg-emerald-500',
        description: 'Execute shell commands',
        fields: ['command']
    },
    ssh_command: { 
        icon: Key, 
        label: 'SSH Command', 
        color: 'bg-purple-500',
        description: 'Execute commands via SSH',
        fields: ['host', 'username', 'port', 'command']
    },
    database_query: { 
        icon: Database, 
        label: 'Database Query', 
        color: 'bg-cyan-500',
        description: 'Execute database queries',
        fields: ['database_type', 'database', 'query']
    },
    notification: { 
        icon: Bell, 
        label: 'Notification', 
        color: 'bg-amber-500',
        description: 'Send notifications',
        fields: ['channel', 'message', 'recipients']
    },
    delay: { 
        icon: Timer, 
        label: 'Delay', 
        color: 'bg-gray-500',
        description: 'Wait for specified time',
        fields: ['seconds']
    },
    condition: { 
        icon: GitBranch, 
        label: 'Condition', 
        color: 'bg-orange-500',
        description: 'Evaluate conditions',
        fields: ['type', 'left', 'right']
    },
    webhook: { 
        icon: Webhook, 
        label: 'Webhook', 
        color: 'bg-pink-500',
        description: 'Send webhook payloads',
        fields: ['url', 'payload']
    },
    log_message: { 
        icon: FileText, 
        label: 'Log Message', 
        color: 'bg-slate-500',
        description: 'Write log entries',
        fields: ['level', 'message']
    },
    metric_check: { 
        icon: BarChart, 
        label: 'Metric Check', 
        color: 'bg-indigo-500',
        description: 'Check metric values',
        fields: ['metric', 'operator', 'threshold']
    },
    service_restart: { 
        icon: Power, 
        label: 'Service Restart', 
        color: 'bg-red-500',
        description: 'Restart a service',
        fields: ['service']
    },
    approval: { 
        icon: UserCheck, 
        label: 'Approval', 
        color: 'bg-teal-500',
        description: 'Request approval',
        fields: ['approvers', 'message', 'timeout_minutes']
    },
    kubernetes: { 
        icon: Box, 
        label: 'Kubernetes', 
        color: 'bg-blue-600',
        description: 'Execute kubectl commands',
        fields: ['action', 'resource_type', 'resource_name', 'namespace', 'replicas']
    },
    script: { 
        icon: Code, 
        label: 'Script', 
        color: 'bg-violet-500',
        description: 'Execute scripts',
        fields: ['script_type', 'script']
    },
    set_variable: { 
        icon: Variable, 
        label: 'Set Variable', 
        color: 'bg-lime-500',
        description: 'Set runtime variable',
        fields: ['name', 'value']
    },
    loop: { 
        icon: Repeat, 
        label: 'Loop', 
        color: 'bg-rose-500',
        description: 'Iterate over items',
        fields: ['items', 'max_iterations']
    },
    parallel: { 
        icon: Layers, 
        label: 'Parallel', 
        color: 'bg-fuchsia-500',
        description: 'Execute in parallel',
        fields: ['actions']
    },
};

// Step Configuration Panel
const StepConfigPanel = ({ step, onChange, onClose }) => {
    const actionType = ACTION_TYPES[step.action_type];
    const Icon = actionType?.icon || Terminal;
    
    const updateConfig = (key, value) => {
        onChange({
            ...step,
            config: { ...step.config, [key]: value }
        });
    };

    const renderField = (field) => {
        const value = step.config?.[field] || '';
        
        switch (field) {
            case 'method':
                return (
                    <Select value={value || 'GET'} onValueChange={(v) => updateConfig('method', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="GET">GET</SelectItem>
                            <SelectItem value="POST">POST</SelectItem>
                            <SelectItem value="PUT">PUT</SelectItem>
                            <SelectItem value="DELETE">DELETE</SelectItem>
                            <SelectItem value="PATCH">PATCH</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'channel':
                return (
                    <Select value={value || 'log'} onValueChange={(v) => updateConfig('channel', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="log">Log</SelectItem>
                            <SelectItem value="email">Email</SelectItem>
                            <SelectItem value="slack">Slack</SelectItem>
                            <SelectItem value="pagerduty">PagerDuty</SelectItem>
                            <SelectItem value="teams">Teams</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'level':
                return (
                    <Select value={value || 'info'} onValueChange={(v) => updateConfig('level', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="info">Info</SelectItem>
                            <SelectItem value="warning">Warning</SelectItem>
                            <SelectItem value="error">Error</SelectItem>
                            <SelectItem value="critical">Critical</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'operator':
                return (
                    <Select value={value || 'less_than'} onValueChange={(v) => updateConfig('operator', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="less_than">Less than</SelectItem>
                            <SelectItem value="greater_than">Greater than</SelectItem>
                            <SelectItem value="equals">Equals</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'type':
                return (
                    <Select value={value || 'equals'} onValueChange={(v) => updateConfig('type', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="equals">Equals</SelectItem>
                            <SelectItem value="not_equals">Not Equals</SelectItem>
                            <SelectItem value="contains">Contains</SelectItem>
                            <SelectItem value="greater_than">Greater Than</SelectItem>
                            <SelectItem value="less_than">Less Than</SelectItem>
                            <SelectItem value="regex">Regex Match</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'database_type':
                return (
                    <Select value={value || 'mongodb'} onValueChange={(v) => updateConfig('database_type', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="mongodb">MongoDB</SelectItem>
                            <SelectItem value="postgresql">PostgreSQL</SelectItem>
                            <SelectItem value="mysql">MySQL</SelectItem>
                            <SelectItem value="redis">Redis</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'action':
                return (
                    <Select value={value || 'get'} onValueChange={(v) => updateConfig('action', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="get">Get</SelectItem>
                            <SelectItem value="delete">Delete</SelectItem>
                            <SelectItem value="rollout_restart">Rollout Restart</SelectItem>
                            <SelectItem value="scale">Scale</SelectItem>
                            <SelectItem value="logs">Get Logs</SelectItem>
                            <SelectItem value="describe">Describe</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'resource_type':
                return (
                    <Select value={value || 'pods'} onValueChange={(v) => updateConfig('resource_type', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="pods">Pods</SelectItem>
                            <SelectItem value="deployment">Deployment</SelectItem>
                            <SelectItem value="service">Service</SelectItem>
                            <SelectItem value="configmap">ConfigMap</SelectItem>
                            <SelectItem value="secret">Secret</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'script_type':
                return (
                    <Select value={value || 'bash'} onValueChange={(v) => updateConfig('script_type', v)}>
                        <SelectTrigger className="bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value="bash">Bash</SelectItem>
                            <SelectItem value="python">Python</SelectItem>
                        </SelectContent>
                    </Select>
                );
            case 'body':
            case 'script':
            case 'query':
            case 'payload':
                return (
                    <Textarea
                        value={value}
                        onChange={(e) => updateConfig(field, e.target.value)}
                        className="bg-muted/50 font-mono text-xs min-h-[100px]"
                        placeholder={`Enter ${field}...`}
                    />
                );
            case 'seconds':
            case 'threshold':
            case 'timeout':
            case 'timeout_minutes':
            case 'port':
            case 'replicas':
            case 'max_iterations':
                return (
                    <Input
                        type="number"
                        value={value}
                        onChange={(e) => updateConfig(field, parseInt(e.target.value) || 0)}
                        className="bg-muted/50"
                        placeholder={`Enter ${field}...`}
                    />
                );
            case 'recipients':
            case 'approvers':
            case 'items':
                return (
                    <Input
                        value={Array.isArray(value) ? value.join(', ') : value}
                        onChange={(e) => updateConfig(field, e.target.value.split(',').map(s => s.trim()))}
                        className="bg-muted/50"
                        placeholder="Comma-separated list..."
                    />
                );
            default:
                return (
                    <Input
                        value={value}
                        onChange={(e) => updateConfig(field, e.target.value)}
                        className="bg-muted/50"
                        placeholder={`Enter ${field}...`}
                    />
                );
        }
    };

    return (
        <div className="space-y-4 p-4 bg-muted/20 rounded-lg border border-white/10">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className={`p-2 rounded ${actionType?.color || 'bg-gray-500'}`}>
                        <Icon className="w-4 h-4 text-white" />
                    </div>
                    <div>
                        <h4 className="font-semibold">{actionType?.label || step.action_type}</h4>
                        <p className="text-xs text-muted-foreground">{actionType?.description}</p>
                    </div>
                </div>
                <Button variant="ghost" size="icon" onClick={onClose}>
                    <X className="w-4 h-4" />
                </Button>
            </div>
            
            <div className="space-y-3">
                <div className="space-y-2">
                    <Label>Step Name</Label>
                    <Input
                        value={step.name}
                        onChange={(e) => onChange({ ...step, name: e.target.value })}
                        placeholder="Enter step name..."
                        className="bg-muted/50"
                    />
                </div>
                
                {actionType?.fields?.map((field) => (
                    <div key={field} className="space-y-2">
                        <Label className="capitalize">{field.replace(/_/g, ' ')}</Label>
                        {renderField(field)}
                    </div>
                ))}
                
                <div className="flex items-center gap-2 pt-2">
                    <Switch
                        checked={step.continue_on_failure}
                        onCheckedChange={(checked) => onChange({ ...step, continue_on_failure: checked })}
                    />
                    <Label className="text-sm">Continue on failure</Label>
                </div>
            </div>
        </div>
    );
};

// Visual Step Card
const VisualStepCard = ({ step, index, isSelected, onSelect, onDelete, onMoveUp, onMoveDown, isFirst, isLast }) => {
    const actionType = ACTION_TYPES[step.action_type];
    const Icon = actionType?.icon || Terminal;
    
    return (
        <div className="relative">
            {/* Connection Line */}
            {!isFirst && (
                <div className="absolute left-1/2 -top-4 w-0.5 h-4 bg-white/20 -translate-x-1/2" />
            )}
            
            {/* Arrow */}
            {!isFirst && (
                <div className="absolute left-1/2 -top-6 -translate-x-1/2">
                    <ArrowDown className="w-4 h-4 text-white/30" />
                </div>
            )}
            
            <div 
                className={`relative p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    isSelected 
                        ? 'border-primary bg-primary/10' 
                        : 'border-white/10 bg-muted/30 hover:border-white/20'
                }`}
                onClick={onSelect}
            >
                <div className="flex items-center gap-3">
                    {/* Step Number */}
                    <div className="flex flex-col items-center gap-1">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
                            disabled={isFirst}
                        >
                            <ChevronUp className="w-4 h-4" />
                        </Button>
                        <div className={`w-8 h-8 rounded-full ${actionType?.color || 'bg-gray-500'} flex items-center justify-center text-white font-bold text-sm`}>
                            {index + 1}
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
                            disabled={isLast}
                        >
                            <ChevronDown className="w-4 h-4" />
                        </Button>
                    </div>
                    
                    {/* Step Info */}
                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            <Icon className="w-4 h-4 text-white/70" />
                            <span className="font-medium">{step.name || `Step ${index + 1}`}</span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                            {actionType?.label || step.action_type}
                            {step.continue_on_failure && (
                                <Badge variant="outline" className="ml-2 text-[10px]">Continue on fail</Badge>
                            )}
                        </div>
                        {step.config && Object.keys(step.config).length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1 font-mono truncate max-w-xs">
                                {JSON.stringify(step.config).slice(0, 50)}...
                            </div>
                        )}
                    </div>
                    
                    {/* Delete Button */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="text-red-400 hover:text-red-300"
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>
                </div>
            </div>
        </div>
    );
};

// Main Visual Workflow Builder
export const VisualWorkflowBuilder = ({ steps = [], onChange, onSave }) => {
    const [selectedStepIndex, setSelectedStepIndex] = useState(null);
    const [showActionPicker, setShowActionPicker] = useState(false);

    const addStep = (actionType) => {
        const newStep = {
            name: '',
            action_type: actionType,
            config: {},
            continue_on_failure: false,
        };
        onChange([...steps, newStep]);
        setSelectedStepIndex(steps.length);
        setShowActionPicker(false);
    };

    const updateStep = (index, updatedStep) => {
        const newSteps = [...steps];
        newSteps[index] = updatedStep;
        onChange(newSteps);
    };

    const deleteStep = (index) => {
        const newSteps = steps.filter((_, i) => i !== index);
        onChange(newSteps);
        if (selectedStepIndex === index) {
            setSelectedStepIndex(null);
        } else if (selectedStepIndex > index) {
            setSelectedStepIndex(selectedStepIndex - 1);
        }
    };

    const moveStep = (fromIndex, toIndex) => {
        if (toIndex < 0 || toIndex >= steps.length) return;
        const newSteps = [...steps];
        const [moved] = newSteps.splice(fromIndex, 1);
        newSteps.splice(toIndex, 0, moved);
        onChange(newSteps);
        setSelectedStepIndex(toIndex);
    };

    return (
        <div className="grid grid-cols-2 gap-6">
            {/* Left Panel - Visual Workflow */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">Workflow Steps</h3>
                    <Badge variant="outline">{steps.length} steps</Badge>
                </div>
                
                <div className="space-y-6 min-h-[300px] p-4 rounded-lg bg-muted/10 border border-white/5">
                    {steps.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            <Layers className="w-12 h-12 mx-auto mb-4 opacity-50" />
                            <p className="text-lg font-medium">No steps yet</p>
                            <p className="text-sm">Add your first automation step</p>
                        </div>
                    ) : (
                        steps.map((step, index) => (
                            <VisualStepCard
                                key={index}
                                step={step}
                                index={index}
                                isSelected={selectedStepIndex === index}
                                onSelect={() => setSelectedStepIndex(index)}
                                onDelete={() => deleteStep(index)}
                                onMoveUp={() => moveStep(index, index - 1)}
                                onMoveDown={() => moveStep(index, index + 1)}
                                isFirst={index === 0}
                                isLast={index === steps.length - 1}
                            />
                        ))
                    )}
                    
                    {/* Add Step Button */}
                    <div className="flex justify-center pt-4">
                        <Button
                            variant="outline"
                            onClick={() => setShowActionPicker(true)}
                            className="border-dashed border-2"
                        >
                            <Plus className="w-4 h-4 mr-2" />
                            Add Step
                        </Button>
                    </div>
                </div>
            </div>

            {/* Right Panel - Step Configuration */}
            <div className="space-y-4">
                <h3 className="text-lg font-semibold">Step Configuration</h3>
                
                {selectedStepIndex !== null && steps[selectedStepIndex] ? (
                    <StepConfigPanel
                        step={steps[selectedStepIndex]}
                        onChange={(updated) => updateStep(selectedStepIndex, updated)}
                        onClose={() => setSelectedStepIndex(null)}
                    />
                ) : (
                    <div className="p-8 rounded-lg bg-muted/10 border border-white/5 text-center text-muted-foreground">
                        <Settings className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg font-medium">Select a step to configure</p>
                        <p className="text-sm">Click on any step to edit its settings</p>
                    </div>
                )}
            </div>

            {/* Action Picker Dialog */}
            <Dialog open={showActionPicker} onOpenChange={setShowActionPicker}>
                <DialogContent className="max-w-2xl bg-card border-border max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Add Automation Step</DialogTitle>
                    </DialogHeader>
                    <div className="grid grid-cols-3 gap-3 pt-4">
                        {Object.entries(ACTION_TYPES).map(([key, action]) => {
                            const Icon = action.icon;
                            return (
                                <button
                                    key={key}
                                    onClick={() => addStep(key)}
                                    className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 border border-white/5 hover:border-white/10 transition-all text-left"
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

export default VisualWorkflowBuilder;
