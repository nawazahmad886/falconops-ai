import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '../components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    BookOpen,
    Plus,
    Play,
    RefreshCw,
    Clock,
    Trash2,
    Zap,
    CheckCircle,
    XCircle,
    AlertTriangle,
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
    Copy,
    Eye,
    History,
    Folder,
    Server,
    Activity,
    Shield,
    Database,
    Network,
    Rocket,
    ChevronRight,
    Settings,
    ArrowRight,
    Key,
    Box,
    Code,
    Variable,
    Repeat,
    Layers,
    Calendar,
    Edit,
    Save,
    Monitor,
    Wand2,
    Bot,
    LayoutGrid,
    Sparkles,
} from 'lucide-react';
import { VisualWorkflowBuilder } from '../components/VisualWorkflowBuilder';
import { WorkflowCanvas } from '../components/WorkflowCanvas';
import { WorkflowTemplateGallery } from '../components/WorkflowTemplateGallery';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Action type icons - expanded
const actionIcons = {
    http_request: Globe,
    shell_command: Terminal,
    ssh_command: Key,
    database_query: Database,
    notification: Bell,
    delay: Timer,
    condition: GitBranch,
    webhook: Webhook,
    log_message: FileText,
    metric_check: BarChart,
    service_restart: Power,
    approval: UserCheck,
    kubernetes: Box,
    script: Code,
    set_variable: Variable,
    loop: Repeat,
    parallel: Layers,
};

// Category icons
const categoryIcons = {
    infrastructure: Server,
    monitoring: Activity,
    incident: AlertTriangle,
    deployment: Rocket,
    security: Shield,
    database: Database,
    network: Network,
    agent: Bot,
    general: Folder,
};

export const RunbooksPage = () => {
    const { api } = useAuth();
    const [runbooks, setRunbooks] = useState([]);
    const [templates, setTemplates] = useState([]);
    const [categories, setCategories] = useState([]);
    const [actionTypes, setActionTypes] = useState([]);
    const [stats, setStats] = useState(null);
    const [scheduledRunbooks, setScheduledRunbooks] = useState([]);
    const [schedulePresets, setSchedulePresets] = useState([]);
    const [agentCatalog, setAgentCatalog] = useState([]);
    const [triggerTypes, setTriggerTypes] = useState([]);
    const [galleryOpen, setGalleryOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('runbooks');
    const [dialogOpen, setDialogOpen] = useState(false);
    const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
    const [executionDialogOpen, setExecutionDialogOpen] = useState(false);
    const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
    const [selectedRunbookForSchedule, setSelectedRunbookForSchedule] = useState(null);
    const [selectedExecution, setSelectedExecution] = useState(null);
    const [executing, setExecuting] = useState(null);
    const [selectedCategory, setSelectedCategory] = useState('all');
    // Edit mode states
    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editingRunbook, setEditingRunbook] = useState(null);
    const [builderMode, setBuilderMode] = useState('canvas'); // 'canvas' | 'visual' | 'json'
    const [scheduleForm, setScheduleForm] = useState({
        enabled: true,
        cron_expression: '0 * * * *',
        timezone: 'UTC'
    });
    
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        service: '',
        category: 'general',
        auto_execute: false,
        tags: [],
        steps: [{ name: '', action_type: 'shell_command', config: {}, continue_on_failure: false }],
    });

    const fetchRunbooks = async () => {
        setLoading(true);
        try {
            const [runbooksRes, templatesRes, categoriesRes, actionTypesRes, statsRes, scheduledRes, presetsRes, agentCatalogRes, triggerTypesRes] = await Promise.all([
                api.get('/runbooks'),
                api.get('/runbooks/templates'),
                api.get('/runbooks/categories'),
                api.get('/runbooks/action-types'),
                api.get('/runbooks/stats/summary'),
                api.get('/runbooks/scheduled').catch(() => ({ data: { scheduled_runbooks: [] } })),
                api.get('/runbooks/schedules/presets').catch(() => ({ data: { presets: [] } })),
                api.get('/runbooks/agent-catalog').catch(() => ({ data: { agents: [] } })),
                api.get('/runbooks/trigger-types').catch(() => ({ data: { trigger_types: [] } })),
            ]);
            setRunbooks(runbooksRes.data);
            setTemplates(templatesRes.data.templates || []);
            setCategories(categoriesRes.data.categories || []);
            setActionTypes(actionTypesRes.data.action_types || []);
            setStats(statsRes.data);
            setScheduledRunbooks(scheduledRes.data.scheduled_runbooks || []);
            setSchedulePresets(presetsRes.data.presets || []);
            setAgentCatalog(agentCatalogRes.data.agents || []);
            setTriggerTypes(triggerTypesRes.data.trigger_types || []);
        } catch (error) {
            toast.error('Failed to fetch runbooks data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRunbooks();
    }, []);

    const handleCreateRunbook = async (e) => {
        e.preventDefault();
        try {
            await api.post('/runbooks', {
                name: formData.name,
                description: formData.description,
                service: formData.service,
                category: formData.category,
                auto_execute: formData.auto_execute,
                tags: formData.tags,
                steps: formData.steps.filter(s => s.name && s.action_type),
            });
            toast.success('Runbook created successfully');
            setDialogOpen(false);
            resetForm();
            fetchRunbooks();
        } catch (error) {
            toast.error('Failed to create runbook');
        }
    };

    const handleCreateFromTemplate = async (templateId, service) => {
        try {
            await api.post(`/runbooks/from-template/${templateId}?service=${service}`);
            toast.success('Runbook created from template');
            setTemplateDialogOpen(false);
            fetchRunbooks();
        } catch (error) {
            toast.error('Failed to create runbook from template');
        }
    };

    const handleExecuteRunbook = async (runbookId) => {
        setExecuting(runbookId);
        try {
            const response = await api.post(`/runbooks/${runbookId}/execute`, { variables: {}, trigger_source: 'manual' });
            if (response.data.success) {
                toast.success('Runbook executed successfully');
            } else {
                toast.error('Runbook execution failed');
            }
            setSelectedExecution(response.data);
            setExecutionDialogOpen(true);
            fetchRunbooks();
        } catch (error) {
            toast.error('Failed to execute runbook');
        } finally {
            setExecuting(null);
        }
    };

    const handleDryRun = async (runbookId) => {
        try {
            const response = await api.post(`/runbooks/${runbookId}/dry-run`);
            if (response.data.valid) {
                toast.success('Validation passed - all steps are valid');
            } else {
                toast.warning('Validation found issues');
            }
        } catch (error) {
            toast.error('Failed to validate runbook');
        }
    };

    const handleDeleteRunbook = async (runbookId) => {
        if (!window.confirm('Are you sure you want to delete this runbook?')) return;
        try {
            await api.delete(`/runbooks/${runbookId}`);
            toast.success('Runbook deleted');
            fetchRunbooks();
        } catch (error) {
            toast.error('Failed to delete runbook');
        }
    };

    const handleEditRunbook = async (runbook) => {
        setEditingRunbook({
            ...runbook,
            steps: runbook.steps || [],
            trigger: runbook.trigger || { type: 'on_demand' },
        });
        setEditDialogOpen(true);
    };

    const handleUpdateRunbook = async (e) => {
        e.preventDefault();
        if (!editingRunbook) return;
        
        try {
            await api.put(`/runbooks/${editingRunbook.id}`, {
                name: editingRunbook.name,
                description: editingRunbook.description,
                service: editingRunbook.service,
                category: editingRunbook.category,
                auto_execute: editingRunbook.auto_execute,
                tags: editingRunbook.tags || [],
                steps: editingRunbook.steps.filter(s => s.action_type),
                trigger: editingRunbook.trigger || { type: 'on_demand' },
            });
            toast.success('Runbook updated successfully');
            setEditDialogOpen(false);
            setEditingRunbook(null);
            fetchRunbooks();
        } catch (error) {
            toast.error('Failed to update runbook');
        }
    };

    const resetForm = () => {
        setFormData({
            name: '',
            description: '',
            service: '',
            category: 'general',
            auto_execute: false,
            tags: [],
            steps: [{ name: '', action_type: 'shell_command', config: {}, continue_on_failure: false }],
        });
    };

    const addStep = () => {
        setFormData({
            ...formData,
            steps: [...formData.steps, { name: '', action_type: 'shell_command', config: {}, continue_on_failure: false }],
        });
    };

    const updateStep = (index, field, value) => {
        const newSteps = [...formData.steps];
        if (field === 'config') {
            newSteps[index].config = { ...newSteps[index].config, ...value };
        } else {
            newSteps[index][field] = value;
        }
        setFormData({ ...formData, steps: newSteps });
    };

    const removeStep = (index) => {
        const newSteps = formData.steps.filter((_, i) => i !== index);
        setFormData({ ...formData, steps: newSteps });
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return 'Never';
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'completed': return 'text-emerald-400';
            case 'failed': return 'text-red-400';
            case 'running': return 'text-amber-400';
            default: return 'text-white/50';
        }
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'completed': 
            case 'success': return <CheckCircle className="w-4 h-4 text-emerald-400" />;
            case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
            case 'running': return <RefreshCw className="w-4 h-4 text-amber-400 animate-spin" />;
            default: return <Clock className="w-4 h-4 text-white/50" />;
        }
    };

    const filteredRunbooks = selectedCategory === 'all' 
        ? runbooks 
        : runbooks.filter(r => r.category === selectedCategory);

    const renderStepConfigFields = (step, index) => {
        const actionType = step.action_type;
        
        switch (actionType) {
            case 'http_request':
                return (
                    <div className="grid grid-cols-2 gap-2 mt-2">
                        <Select
                            value={step.config.method || 'GET'}
                            onValueChange={(value) => updateStep(index, 'config', { method: value })}
                        >
                            <SelectTrigger className="bg-muted/50">
                                <SelectValue placeholder="Method" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="GET">GET</SelectItem>
                                <SelectItem value="POST">POST</SelectItem>
                                <SelectItem value="PUT">PUT</SelectItem>
                                <SelectItem value="DELETE">DELETE</SelectItem>
                            </SelectContent>
                        </Select>
                        <Input
                            placeholder="URL"
                            value={step.config.url || ''}
                            onChange={(e) => updateStep(index, 'config', { url: e.target.value })}
                            className="bg-muted/50 font-mono text-xs"
                        />
                    </div>
                );
            case 'shell_command':
                return (
                    <Input
                        placeholder="Command (e.g., echo 'Hello World')"
                        value={step.config.command || ''}
                        onChange={(e) => updateStep(index, 'config', { command: e.target.value })}
                        className="bg-muted/50 font-mono text-xs mt-2"
                    />
                );
            case 'delay':
                return (
                    <Input
                        type="number"
                        placeholder="Delay in seconds"
                        value={step.config.seconds || ''}
                        onChange={(e) => updateStep(index, 'config', { seconds: parseInt(e.target.value) })}
                        className="bg-muted/50 w-32 mt-2"
                    />
                );
            case 'notification':
                return (
                    <div className="space-y-2 mt-2">
                        <Select
                            value={step.config.channel || 'log'}
                            onValueChange={(value) => updateStep(index, 'config', { channel: value })}
                        >
                            <SelectTrigger className="bg-muted/50">
                                <SelectValue placeholder="Channel" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="log">Log</SelectItem>
                                <SelectItem value="email">Email</SelectItem>
                                <SelectItem value="slack">Slack</SelectItem>
                                <SelectItem value="pagerduty">PagerDuty</SelectItem>
                            </SelectContent>
                        </Select>
                        <Input
                            placeholder="Message"
                            value={step.config.message || ''}
                            onChange={(e) => updateStep(index, 'config', { message: e.target.value })}
                            className="bg-muted/50"
                        />
                    </div>
                );
            case 'metric_check':
                return (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                        <Input
                            placeholder="Metric name"
                            value={step.config.metric || ''}
                            onChange={(e) => updateStep(index, 'config', { metric: e.target.value })}
                            className="bg-muted/50 text-xs"
                        />
                        <Select
                            value={step.config.operator || 'less_than'}
                            onValueChange={(value) => updateStep(index, 'config', { operator: value })}
                        >
                            <SelectTrigger className="bg-muted/50">
                                <SelectValue placeholder="Operator" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="less_than">Less than</SelectItem>
                                <SelectItem value="greater_than">Greater than</SelectItem>
                                <SelectItem value="equals">Equals</SelectItem>
                            </SelectContent>
                        </Select>
                        <Input
                            type="number"
                            placeholder="Threshold"
                            value={step.config.threshold || ''}
                            onChange={(e) => updateStep(index, 'config', { threshold: parseInt(e.target.value) })}
                            className="bg-muted/50"
                        />
                    </div>
                );
            case 'service_restart':
                return (
                    <Input
                        placeholder="Service name"
                        value={step.config.service || ''}
                        onChange={(e) => updateStep(index, 'config', { service: e.target.value })}
                        className="bg-muted/50 mt-2"
                    />
                );
            default:
                return null;
        }
    };

    return (
        <>
            <div className="space-y-6" data-testid="runbooks-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 className="font-heading font-semibold text-2xl md:text-3xl flex items-center gap-2">
                            <BookOpen className="w-7 h-7 text-primary" />
                            Automation Engine
                        </h1>
                        <p className="text-muted-foreground text-sm">Enterprise runbook automation & orchestration</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button onClick={fetchRunbooks} variant="outline" size="sm">
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                        <Button onClick={() => setGalleryOpen(true)} variant="outline" size="sm" data-testid="browse-templates-btn">
                            <Sparkles className="w-4 h-4 mr-2" />
                            Create from Template
                        </Button>
                        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                            <DialogTrigger asChild>
                                <Button data-testid="create-runbook-btn">
                                    <Plus className="w-4 h-4 mr-2" />
                                    New Runbook
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-card border-border">
                                <DialogHeader>
                                    <DialogTitle className="font-heading">Create Automation Runbook</DialogTitle>
                                </DialogHeader>
                                <form onSubmit={handleCreateRunbook} className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="name">Runbook Name</Label>
                                            <Input
                                                id="name"
                                                value={formData.name}
                                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                                placeholder="High CPU Remediation"
                                                required
                                                className="bg-muted/50"
                                                data-testid="runbook-name"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="service">Target Service</Label>
                                            <Input
                                                id="service"
                                                value={formData.service}
                                                onChange={(e) => setFormData({ ...formData, service: e.target.value })}
                                                placeholder="payment-service"
                                                required
                                                className="bg-muted/50"
                                                data-testid="runbook-service"
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Category</Label>
                                            <Select
                                                value={formData.category}
                                                onValueChange={(value) => setFormData({ ...formData, category: value })}
                                            >
                                                <SelectTrigger className="bg-muted/50">
                                                    <SelectValue placeholder="Select category" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {categories.map(cat => (
                                                        <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                                            <div>
                                                <Label htmlFor="auto_execute">Auto-Execute</Label>
                                                <p className="text-xs text-muted-foreground">Run on matching alerts</p>
                                            </div>
                                            <Switch
                                                id="auto_execute"
                                                checked={formData.auto_execute}
                                                onCheckedChange={(checked) => setFormData({ ...formData, auto_execute: checked })}
                                                data-testid="runbook-auto-execute"
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <Label htmlFor="description">Description</Label>
                                        <Textarea
                                            id="description"
                                            value={formData.description}
                                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                            placeholder="Describe what this runbook does..."
                                            className="bg-muted/50"
                                            data-testid="runbook-description"
                                        />
                                    </div>
                                    
                                    {/* Steps Builder */}
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <Label>Automation Steps</Label>
                                            <Button type="button" variant="outline" size="sm" onClick={addStep}>
                                                <Plus className="w-4 h-4 mr-1" />
                                                Add Step
                                            </Button>
                                        </div>
                                        {formData.steps.map((step, idx) => {
                                            const ActionIcon = actionIcons[step.action_type] || Terminal;
                                            return (
                                                <div key={idx} className="p-4 rounded-lg bg-muted/30 border border-white/5">
                                                    <div className="flex items-start gap-3">
                                                        <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-mono text-sm">
                                                            {idx + 1}
                                                        </div>
                                                        <div className="flex-1 space-y-3">
                                                            <div className="grid grid-cols-2 gap-2">
                                                                <Input
                                                                    placeholder="Step name"
                                                                    value={step.name}
                                                                    onChange={(e) => updateStep(idx, 'name', e.target.value)}
                                                                    className="bg-muted/50"
                                                                />
                                                                <Select
                                                                    value={step.action_type}
                                                                    onValueChange={(value) => updateStep(idx, 'action_type', value)}
                                                                >
                                                                    <SelectTrigger className="bg-muted/50">
                                                                        <SelectValue placeholder="Action type" />
                                                                    </SelectTrigger>
                                                                    <SelectContent>
                                                                        {actionTypes.map(action => (
                                                                            <SelectItem key={action.id} value={action.id}>
                                                                                <div className="flex items-center gap-2">
                                                                                    <ActionIcon className="w-4 h-4" />
                                                                                    {action.name}
                                                                                </div>
                                                                            </SelectItem>
                                                                        ))}
                                                                    </SelectContent>
                                                                </Select>
                                                            </div>
                                                            {renderStepConfigFields(step, idx)}
                                                            <div className="flex items-center gap-2">
                                                                <Switch
                                                                    checked={step.continue_on_failure}
                                                                    onCheckedChange={(checked) => updateStep(idx, 'continue_on_failure', checked)}
                                                                />
                                                                <span className="text-xs text-muted-foreground">Continue on failure</span>
                                                            </div>
                                                        </div>
                                                        {formData.steps.length > 1 && (
                                                            <Button
                                                                type="button"
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => removeStep(idx)}
                                                                className="text-destructive hover:text-destructive"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                    
                                    <div className="flex justify-end gap-2 pt-4">
                                        <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                                            Cancel
                                        </Button>
                                        <Button type="submit" data-testid="submit-runbook">
                                            Create Runbook
                                        </Button>
                                    </div>
                                </form>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>

                {/* Stats Cards */}
                {stats && (
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-4">
                                <div className="text-2xl font-bold text-white">{stats.total_runbooks}</div>
                                <div className="text-xs text-muted-foreground">Total Runbooks</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-4">
                                <div className="text-2xl font-bold text-emerald-400">{stats.successful_executions}</div>
                                <div className="text-xs text-muted-foreground">Successful</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-4">
                                <div className="text-2xl font-bold text-red-400">{stats.failed_executions}</div>
                                <div className="text-xs text-muted-foreground">Failed</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-4">
                                <div className="text-2xl font-bold text-primary">{stats.success_rate?.toFixed(1)}%</div>
                                <div className="text-xs text-muted-foreground">Success Rate</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-4">
                                <div className="text-2xl font-bold text-cyan-400">{stats.auto_execute_enabled}</div>
                                <div className="text-xs text-muted-foreground">Auto-Enabled</div>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="bg-muted/50">
                        <TabsTrigger value="runbooks">Runbooks</TabsTrigger>
                        <TabsTrigger value="templates">Templates ({templates.length})</TabsTrigger>
                        <TabsTrigger value="scheduled">
                            <Calendar className="w-4 h-4 mr-1" />
                            Scheduled ({scheduledRunbooks.length})
                        </TabsTrigger>
                        <TabsTrigger value="executions">Executions</TabsTrigger>
                    </TabsList>

                    <TabsContent value="runbooks" className="space-y-4">
                        {/* Category Filter */}
                        <div className="flex items-center gap-2 flex-wrap">
                            <Button
                                variant={selectedCategory === 'all' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setSelectedCategory('all')}
                            >
                                All
                            </Button>
                            {categories.map(cat => {
                                const CatIcon = categoryIcons[cat.id] || Folder;
                                return (
                                    <Button
                                        key={cat.id}
                                        variant={selectedCategory === cat.id ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={() => setSelectedCategory(cat.id)}
                                    >
                                        <CatIcon className="w-4 h-4 mr-1" />
                                        {cat.name}
                                    </Button>
                                );
                            })}
                        </div>

                        {/* Runbooks Grid */}
                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                            </div>
                        ) : filteredRunbooks.length === 0 ? (
                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="py-20 text-center text-muted-foreground">
                                    <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p className="text-lg font-medium">No runbooks yet</p>
                                    <p className="text-sm">Create your first runbook or use a template</p>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {filteredRunbooks.map((runbook) => {
                                    const CatIcon = categoryIcons[runbook.category] || Folder;
                                    return (
                                        <Card 
                                            key={runbook.id} 
                                            className="bg-card/50 border-border/40 hover:border-primary/30 transition-colors"
                                            data-testid={`runbook-${runbook.id}`}
                                        >
                                            <CardHeader className="pb-2">
                                                <div className="flex items-start justify-between">
                                                    <div className="flex items-start gap-3">
                                                        <div className="p-2 rounded-lg bg-primary/10">
                                                            <CatIcon className="w-5 h-5 text-primary" />
                                                        </div>
                                                        <div>
                                                            <CardTitle className="text-lg">{runbook.name}</CardTitle>
                                                            <CardDescription className="font-mono text-xs">
                                                                {runbook.service}
                                                            </CardDescription>
                                                        </div>
                                                    </div>
                                                    {runbook.auto_execute && (
                                                        <Badge variant="outline" className="border-primary text-primary">
                                                            <Zap className="w-3 h-3 mr-1" />
                                                            Auto
                                                        </Badge>
                                                    )}
                                                </div>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                                                    {runbook.description || 'No description'}
                                                </p>
                                                <div className="flex items-center justify-between text-xs text-muted-foreground mb-4">
                                                    <span>{runbook.steps?.length || 0} steps</span>
                                                    <span className="flex items-center gap-1">
                                                        <Clock className="w-3 h-3" />
                                                        {formatDate(runbook.last_executed)}
                                                    </span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs text-muted-foreground">
                                                        {runbook.execution_count}x executed
                                                    </span>
                                                    <div className="flex items-center gap-1">
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleEditRunbook(runbook)}
                                                            title="Edit runbook"
                                                        >
                                                            <Edit className="w-4 h-4" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleDryRun(runbook.id)}
                                                            title="Validate"
                                                        >
                                                            <Eye className="w-4 h-4" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleDeleteRunbook(runbook.id)}
                                                            className="text-red-400 hover:text-red-300"
                                                            title="Delete"
                                                        >
                                                            <Trash2 className="w-4 h-4" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handleExecuteRunbook(runbook.id)}
                                                            disabled={executing === runbook.id}
                                                            data-testid={`execute-${runbook.id}`}
                                                        >
                                                            {executing === runbook.id ? (
                                                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                                            ) : (
                                                                <Play className="w-4 h-4 mr-2" />
                                                            )}
                                                            Run
                                                        </Button>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        )}
                    </TabsContent>

                    <TabsContent value="templates" className="space-y-4">
                        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {templates.map((template) => {
                                const CatIcon = categoryIcons[template.category] || Folder;
                                return (
                                    <Card 
                                        key={template.id} 
                                        className="bg-card/50 border-border/40 hover:border-primary/30 transition-colors"
                                    >
                                        <CardHeader className="pb-2">
                                            <div className="flex items-start gap-3">
                                                <div className="p-2 rounded-lg bg-cyan-500/10">
                                                    <CatIcon className="w-5 h-5 text-cyan-400" />
                                                </div>
                                                <div>
                                                    <CardTitle className="text-lg">{template.name}</CardTitle>
                                                    <Badge variant="secondary" className="text-xs">
                                                        {template.category}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-sm text-muted-foreground mb-4">
                                                {template.description}
                                            </p>
                                            <div className="space-y-2 mb-4">
                                                {template.steps.slice(0, 3).map((step, idx) => (
                                                    <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                                                        <ChevronRight className="w-3 h-3" />
                                                        {step.name}
                                                    </div>
                                                ))}
                                                {template.steps.length > 3 && (
                                                    <div className="text-xs text-muted-foreground">
                                                        +{template.steps.length - 3} more steps
                                                    </div>
                                                )}
                                            </div>
                                            <Dialog>
                                                <DialogTrigger asChild>
                                                    <Button size="sm" className="w-full">
                                                        <Copy className="w-4 h-4 mr-2" />
                                                        Use Template
                                                    </Button>
                                                </DialogTrigger>
                                                <DialogContent className="bg-card">
                                                    <DialogHeader>
                                                        <DialogTitle>Create from Template: {template.name}</DialogTitle>
                                                    </DialogHeader>
                                                    <div className="space-y-4">
                                                        <div className="space-y-2">
                                                            <Label>Target Service</Label>
                                                            <Input
                                                                id={`template-service-${template.id}`}
                                                                placeholder="Enter service name"
                                                                className="bg-muted/50"
                                                            />
                                                        </div>
                                                        <Button 
                                                            className="w-full"
                                                            onClick={() => {
                                                                const input = document.getElementById(`template-service-${template.id}`);
                                                                handleCreateFromTemplate(template.id, input.value);
                                                            }}
                                                        >
                                                            Create Runbook
                                                        </Button>
                                                    </div>
                                                </DialogContent>
                                            </Dialog>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </div>
                    </TabsContent>

                    <TabsContent value="executions" className="space-y-4">
                        {stats?.recent_executions?.length > 0 ? (
                            <div className="space-y-3">
                                {stats.recent_executions.map((exec) => (
                                    <Card key={exec.id} className="bg-card/50 border-border/40">
                                        <CardContent className="p-4">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    {getStatusIcon(exec.status)}
                                                    <div>
                                                        <div className="font-medium">{exec.runbook_name}</div>
                                                        <div className="text-xs text-muted-foreground">
                                                            {exec.trigger_source} • {formatDate(exec.started_at)}
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    <div className="text-right">
                                                        <div className={`text-sm font-medium ${getStatusColor(exec.status)}`}>
                                                            {exec.status}
                                                        </div>
                                                        <div className="text-xs text-muted-foreground">
                                                            {exec.steps_completed}/{exec.steps_total} steps
                                                        </div>
                                                    </div>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => {
                                                            setSelectedExecution(exec);
                                                            setExecutionDialogOpen(true);
                                                        }}
                                                    >
                                                        <Eye className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : (
                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="py-20 text-center text-muted-foreground">
                                    <History className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p className="text-lg font-medium">No executions yet</p>
                                    <p className="text-sm">Run a runbook to see execution history</p>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* Scheduled Tab */}
                    <TabsContent value="scheduled" className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-medium">Scheduled Runbooks</h3>
                                <p className="text-sm text-muted-foreground">Configure cron-based automated execution</p>
                            </div>
                        </div>

                        {scheduledRunbooks.length > 0 ? (
                            <div className="space-y-3">
                                {scheduledRunbooks.map((runbook) => {
                                    const CatIcon = categoryIcons[runbook.category] || Folder;
                                    return (
                                        <Card key={runbook.id} className="bg-card/50 border-border/40">
                                            <CardContent className="p-4">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3">
                                                        <div className="p-2 rounded-lg bg-cyan-500/10">
                                                            <CatIcon className="w-5 h-5 text-cyan-400" />
                                                        </div>
                                                        <div>
                                                            <div className="font-medium">{runbook.name}</div>
                                                            <div className="text-xs text-muted-foreground font-mono">
                                                                {runbook.schedule?.cron_expression}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-4">
                                                        <div className="text-right">
                                                            <div className="text-sm text-cyan-400">
                                                                Next: {formatDate(runbook.schedule?.next_run)}
                                                            </div>
                                                            <div className="text-xs text-muted-foreground">
                                                                {runbook.service}
                                                            </div>
                                                        </div>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleExecuteRunbook(runbook.id)}
                                                        >
                                                            <Play className="w-4 h-4" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    );
                                })}
                            </div>
                        ) : (
                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="py-20 text-center text-muted-foreground">
                                    <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p className="text-lg font-medium">No scheduled runbooks</p>
                                    <p className="text-sm">Add a schedule to any runbook to automate execution</p>
                                </CardContent>
                            </Card>
                        )}

                        {/* Schedule Presets Reference */}
                        <Card className="bg-card/50 border-border/40">
                            <CardHeader>
                                <CardTitle className="text-lg">Schedule Presets</CardTitle>
                                <CardDescription>Common cron expressions for scheduling</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                    {schedulePresets.map((preset, idx) => (
                                        <div key={idx} className="p-3 rounded-lg bg-muted/30 border border-white/5">
                                            <div className="font-medium text-sm">{preset.name}</div>
                                            <div className="text-xs text-muted-foreground font-mono">{preset.cron}</div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Execution Detail Dialog */}
                <Dialog open={executionDialogOpen} onOpenChange={setExecutionDialogOpen}>
                    <DialogContent className="max-w-2xl bg-card border-border">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                {selectedExecution && getStatusIcon(selectedExecution.status)}
                                Execution Details
                            </DialogTitle>
                        </DialogHeader>
                        {selectedExecution && (
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <div className="text-muted-foreground">Runbook</div>
                                        <div className="font-medium">{selectedExecution.runbook_name}</div>
                                    </div>
                                    <div>
                                        <div className="text-muted-foreground">Status</div>
                                        <div className={`font-medium ${getStatusColor(selectedExecution.status)}`}>
                                            {selectedExecution.status}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-muted-foreground">Started</div>
                                        <div className="font-medium">{formatDate(selectedExecution.started_at)}</div>
                                    </div>
                                    <div>
                                        <div className="text-muted-foreground">Completed</div>
                                        <div className="font-medium">{formatDate(selectedExecution.completed_at)}</div>
                                    </div>
                                </div>
                                
                                <div>
                                    <div className="text-sm text-muted-foreground mb-2">Step Results</div>
                                    <div className="space-y-2 max-h-60 overflow-y-auto">
                                        {selectedExecution.step_results?.map((step, idx) => (
                                            <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                                                {getStatusIcon(step.status)}
                                                <div className="flex-1">
                                                    <div className="font-medium text-sm">{step.name}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {step.action_type}
                                                    </div>
                                                    {step.error && (
                                                        <div className="text-xs text-red-400 mt-1">{step.error}</div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Edit Runbook Dialog with Visual Workflow Builder */}
                <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                    <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto bg-card border-border">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <Edit className="w-5 h-5 text-primary" />
                                Edit Runbook: {editingRunbook?.name}
                            </DialogTitle>
                        </DialogHeader>
                        {editingRunbook && (
                            <form onSubmit={handleUpdateRunbook} className="space-y-6">
                                {/* Basic Info */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="edit-name">Runbook Name</Label>
                                        <Input
                                            id="edit-name"
                                            value={editingRunbook.name}
                                            onChange={(e) => setEditingRunbook({ ...editingRunbook, name: e.target.value })}
                                            className="bg-muted/50"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="edit-service">Target Service</Label>
                                        <Input
                                            id="edit-service"
                                            value={editingRunbook.service}
                                            onChange={(e) => setEditingRunbook({ ...editingRunbook, service: e.target.value })}
                                            className="bg-muted/50"
                                        />
                                    </div>
                                </div>
                                
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Category</Label>
                                        <Select
                                            value={editingRunbook.category}
                                            onValueChange={(value) => setEditingRunbook({ ...editingRunbook, category: value })}
                                        >
                                            <SelectTrigger className="bg-muted/50">
                                                <SelectValue placeholder="Select category" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {categories.map(cat => (
                                                    <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                                        <div>
                                            <Label htmlFor="edit-auto">Auto-Execute</Label>
                                            <p className="text-xs text-muted-foreground">Run on matching alerts</p>
                                        </div>
                                        <Switch
                                            id="edit-auto"
                                            checked={editingRunbook.auto_execute}
                                            onCheckedChange={(checked) => setEditingRunbook({ ...editingRunbook, auto_execute: checked })}
                                        />
                                    </div>
                                </div>
                                
                                <div className="space-y-2">
                                    <Label htmlFor="edit-description">Description</Label>
                                    <Textarea
                                        id="edit-description"
                                        value={editingRunbook.description}
                                        onChange={(e) => setEditingRunbook({ ...editingRunbook, description: e.target.value })}
                                        className="bg-muted/50"
                                    />
                                </div>

                                {/* Toggle between Workflow Canvas / Visual Builder / JSON */}
                                <div className="flex items-center justify-between border-t border-white/10 pt-4">
                                    <h3 className="text-lg font-semibold">Automation Steps</h3>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            type="button"
                                            variant={builderMode === 'canvas' ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setBuilderMode('canvas')}
                                            data-testid="builder-mode-canvas"
                                        >
                                            <LayoutGrid className="w-4 h-4 mr-1" />
                                            Workflow Canvas
                                        </Button>
                                        <Button
                                            type="button"
                                            variant={builderMode === 'visual' ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setBuilderMode('visual')}
                                            data-testid="builder-mode-visual"
                                        >
                                            <Wand2 className="w-4 h-4 mr-1" />
                                            Visual Builder
                                        </Button>
                                        <Button
                                            type="button"
                                            variant={builderMode === 'json' ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => setBuilderMode('json')}
                                            data-testid="builder-mode-json"
                                        >
                                            <Code className="w-4 h-4 mr-1" />
                                            JSON
                                        </Button>
                                    </div>
                                </div>

                                {/* Workflow Canvas, Visual Workflow Builder, or JSON Editor */}
                                {builderMode === 'canvas' ? (
                                    <WorkflowCanvas
                                        trigger={editingRunbook.trigger}
                                        onTriggerChange={(trigger) => setEditingRunbook({ ...editingRunbook, trigger })}
                                        steps={editingRunbook.steps}
                                        onStepsChange={(steps) => setEditingRunbook({ ...editingRunbook, steps })}
                                        triggerTypes={triggerTypes}
                                        agentCatalog={agentCatalog}
                                    />
                                ) : builderMode === 'visual' ? (
                                    <VisualWorkflowBuilder
                                        steps={editingRunbook.steps}
                                        onChange={(steps) => setEditingRunbook({ ...editingRunbook, steps })}
                                        agentCatalog={agentCatalog}
                                    />
                                ) : (
                                    <div className="space-y-2">
                                        <Label>Steps (JSON)</Label>
                                        <Textarea
                                            value={JSON.stringify(editingRunbook.steps, null, 2)}
                                            onChange={(e) => {
                                                try {
                                                    const steps = JSON.parse(e.target.value);
                                                    setEditingRunbook({ ...editingRunbook, steps });
                                                } catch (err) {
                                                    // Invalid JSON, don't update
                                                }
                                            }}
                                            className="bg-muted/50 font-mono text-xs min-h-[300px]"
                                        />
                                    </div>
                                )}
                                
                                <div className="flex justify-end gap-2 pt-4 border-t border-white/10">
                                    <Button type="button" variant="outline" onClick={() => setEditDialogOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button type="submit">
                                        <Save className="w-4 h-4 mr-2" />
                                        Save Changes
                                    </Button>
                                </div>
                            </form>
                        )}
                    </DialogContent>
                </Dialog>

                <WorkflowTemplateGallery
                    open={galleryOpen}
                    onOpenChange={setGalleryOpen}
                    templates={templates}
                    onUseTemplate={(templateId, service) => handleCreateFromTemplate(templateId, service)}
                />
            </div>
        </>
    );
};
