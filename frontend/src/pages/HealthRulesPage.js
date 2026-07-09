import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Shield, Plus, Trash2, Pencil, RefreshCw, Activity, Database, Server,
    Globe, AlertTriangle, CheckCircle, XCircle, Zap, Clock, Filter,
    ChevronRight, Cpu, HardDrive, Play, Copy,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const getAuth = () => ({ Authorization: `Bearer ${localStorage.getItem('falconToken')}` });

const SEVERITY_CONFIG = {
    critical: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', icon: XCircle },
    warning: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', icon: AlertTriangle },
    info: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', icon: Activity },
};

const CATEGORY_ICONS = {
    infrastructure: Server,
    application: Cpu,
    database: Database,
    network: Globe,
    security: Shield,
    custom: Zap,
};

const DURATION_OPTIONS = [
    { value: 0, label: 'Immediate' },
    { value: 60, label: '1 minute' },
    { value: 120, label: '2 minutes' },
    { value: 300, label: '5 minutes' },
    { value: 600, label: '10 minutes' },
    { value: 900, label: '15 minutes' },
    { value: 1800, label: '30 minutes' },
];

const formatDuration = (sec) => {
    if (!sec || sec === 0) return 'Immediate';
    if (sec < 60) return `${sec}s`;
    return `${Math.round(sec / 60)} min`;
};

const EMPTY_RULE = {
    name: '', description: '', metric: '', operator: 'greater_than',
    threshold: 0, threshold_max: null, duration: 300, severity: 'warning',
    category: 'infrastructure', component_type: 'infrastructure',
    service_filter: '', host_filter: '', conditions: [], action: 'alert',
};

const EMPTY_CONDITION = { metric: '', operator: 'greater_than', threshold: 0, logic: 'AND' };

export const HealthRulesPage = () => {
    const [rules, setRules] = useState([]);
    const [metrics, setMetrics] = useState([]);
    const [operators, setOperators] = useState([]);
    const [categories, setCategories] = useState([]);
    const [templates, setTemplates] = useState([]);
    const [stats, setStats] = useState({});
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingRule, setEditingRule] = useState(null);
    const [form, setForm] = useState(EMPTY_RULE);
    const [filterCategory, setFilterCategory] = useState('all');

    const fetchAll = useCallback(async () => {
        try {
            const headers = getAuth();
            const [rulesRes, metricsRes, opsRes, catsRes, tmplRes, statsRes] = await Promise.all([
                fetch(`${API_URL}/api/health-rules`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/health-rules/metrics`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/health-rules/operators`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/health-rules/categories`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/health-rules/templates`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/health-rules/stats`, { headers }).then(r => r.json()),
            ]);
            setRules(rulesRes.rules || []);
            setMetrics(metricsRes.metrics || []);
            setOperators(opsRes.operators || []);
            setCategories(catsRes.categories || []);
            setTemplates(tmplRes.templates || []);
            setStats(statsRes);
        } catch (e) { toast.error('Failed to load health rules'); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const filteredRules = filterCategory === 'all'
        ? rules
        : rules.filter(r => r.category === filterCategory);

    const handleSave = async () => {
        if (!form.name || !form.metric) { toast.error('Name and metric are required'); return; }
        try {
            const url = editingRule
                ? `${API_URL}/api/health-rules/${editingRule.id}`
                : `${API_URL}/api/health-rules`;
            const method = editingRule ? 'PUT' : 'POST';
            const body = { ...form };
            if (body.service_filter === '') delete body.service_filter;
            if (body.host_filter === '') delete body.host_filter;
            const res = await fetch(url, {
                method, headers: { ...getAuth(), 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error('Failed');
            toast.success(editingRule ? 'Rule updated' : 'Rule created');
            setShowForm(false); setEditingRule(null); setForm(EMPTY_RULE);
            fetchAll();
        } catch (e) { toast.error(e.message); }
    };

    const handleDelete = async (id) => {
        try {
            await fetch(`${API_URL}/api/health-rules/${id}`, { method: 'DELETE', headers: getAuth() });
            toast.success('Rule deleted'); fetchAll();
        } catch (e) { toast.error('Delete failed'); }
    };

    const handleToggle = async (id) => {
        try {
            await fetch(`${API_URL}/api/health-rules/${id}/toggle`, { method: 'POST', headers: getAuth() });
            fetchAll();
        } catch (e) { toast.error('Toggle failed'); }
    };

    const handleCreateFromTemplate = async (templateId) => {
        try {
            const res = await fetch(`${API_URL}/api/health-rules/from-template/${templateId}`, {
                method: 'POST', headers: getAuth(),
            });
            if (!res.ok) throw new Error('Failed');
            toast.success('Rule created from template'); fetchAll();
        } catch (e) { toast.error(e.message); }
    };

    const openEdit = (rule) => {
        setEditingRule(rule);
        setForm({
            name: rule.name, description: rule.description || '', metric: rule.metric,
            operator: rule.operator, threshold: rule.threshold, threshold_max: rule.threshold_max || null,
            duration: rule.duration, severity: rule.severity, category: rule.category,
            component_type: rule.component_type || rule.category || 'infrastructure',
            service_filter: rule.service_filter || '', host_filter: rule.host_filter || '',
            conditions: rule.conditions || [], action: rule.action || 'alert',
        });
        setShowForm(true);
    };

    const openCreate = () => { setEditingRule(null); setForm(EMPTY_RULE); setShowForm(true); };

    const addCondition = () => setForm({ ...form, conditions: [...(form.conditions || []), { ...EMPTY_CONDITION }] });
    const removeCondition = (i) => setForm({ ...form, conditions: form.conditions.filter((_, idx) => idx !== i) });
    const updateCondition = (i, field, value) => {
        const conds = [...form.conditions];
        conds[i] = { ...conds[i], [field]: value };
        setForm({ ...form, conditions: conds });
    };

    // Get metrics filtered by selected component type
    const filteredMetrics = metrics.filter(m => !form.component_type || m.category === form.component_type || form.component_type === 'custom');
    const getMetricName = (id) => metrics.find(m => m.id === id)?.name || id;
    const getMetricUnit = (id) => metrics.find(m => m.id === id)?.unit || '';
    const getOperatorSymbol = (id) => operators.find(o => o.id === id)?.symbol || id;

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20" data-testid="health-rules-loading">
                <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6" data-testid="health-rules-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" data-testid="page-title">Health Rules</h1>
                    <p className="text-sm text-slate-500 mt-0.5">Configure monitoring thresholds and alerting policies</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={fetchAll} className="text-white/50 h-8">
                        <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 h-8 text-xs" onClick={openCreate} data-testid="create-rule-btn">
                        <Plus className="w-3.5 h-3.5 mr-1" /> New Rule
                    </Button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="health-rule-stats">
                <StatCard label="Total Rules" value={stats.total_rules || rules.length} icon={Shield} color="#00E0FF" />
                <StatCard label="Active" value={stats.active_rules || rules.filter(r => r.enabled).length} icon={CheckCircle} color="#10B981" />
                <StatCard label="Critical" value={rules.filter(r => r.severity === 'critical' && r.enabled).length} icon={XCircle} color="#EF4444" />
                <StatCard label="Warning" value={rules.filter(r => r.severity === 'warning' && r.enabled).length} icon={AlertTriangle} color="#F59E0B" />
                <StatCard label="Templates" value={templates.length} icon={Copy} color="#8B5CF6" />
            </div>

            {/* Filter Bar */}
            <div className="flex items-center gap-2 flex-wrap" data-testid="category-filter">
                <Button size="sm" variant={filterCategory === 'all' ? 'default' : 'ghost'}
                    className={`h-7 text-xs ${filterCategory === 'all' ? 'bg-white/10 text-white' : 'text-white/40'}`}
                    onClick={() => setFilterCategory('all')}>
                    All ({rules.length})
                </Button>
                {categories.map(cat => {
                    const Icon = CATEGORY_ICONS[cat.id] || Shield;
                    const count = rules.filter(r => r.category === cat.id).length;
                    return (
                        <Button key={cat.id} size="sm" variant={filterCategory === cat.id ? 'default' : 'ghost'}
                            className={`h-7 text-xs ${filterCategory === cat.id ? 'bg-white/10 text-white' : 'text-white/40'}`}
                            onClick={() => setFilterCategory(cat.id)}>
                            <Icon className="w-3 h-3 mr-1" /> {cat.name} ({count})
                        </Button>
                    );
                })}
            </div>

            {/* Rules List */}
            <div className="space-y-3" data-testid="rules-list">
                {filteredRules.length === 0 ? (
                    <Card className="bg-[#121826] border-[#2D3748]/50">
                        <CardContent className="text-center py-16">
                            <Shield className="w-12 h-12 text-white/10 mx-auto mb-4" />
                            <p className="text-white/40 text-sm">No health rules configured</p>
                            <p className="text-white/20 text-xs mt-1">Create rules or apply templates to start monitoring</p>
                            <div className="flex gap-2 justify-center mt-4">
                                <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 text-xs" onClick={openCreate}>
                                    <Plus className="w-3 h-3 mr-1" /> Create Rule
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ) : filteredRules.map(rule => (
                    <RuleCard key={rule.id} rule={rule} metrics={metrics} operators={operators}
                        onEdit={() => openEdit(rule)} onDelete={() => handleDelete(rule.id)}
                        onToggle={() => handleToggle(rule.id)}
                        getMetricName={getMetricName} getMetricUnit={getMetricUnit} getOperatorSymbol={getOperatorSymbol} />
                ))}
            </div>

            {/* Templates */}
            {templates.length > 0 && (
                <Card className="bg-[#121826] border-[#2D3748]/50" data-testid="templates-section">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <Copy className="w-4 h-4 text-purple-400" /> Quick Templates
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                            {templates.map(t => (
                                <button key={t.id} onClick={() => handleCreateFromTemplate(t.id)}
                                    className="text-left p-2.5 rounded-lg bg-white/[0.02] border border-[#2D3748]/30 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all"
                                    data-testid={`template-${t.id}`}>
                                    <p className="text-xs font-medium text-white truncate">{t.name}</p>
                                    <p className="text-[10px] text-slate-500 mt-0.5 truncate">{t.description}</p>
                                    <div className="flex items-center gap-1 mt-1">
                                        <Badge className={`text-[8px] border-0 ${t.severity === 'critical' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>
                                            {t.severity}
                                        </Badge>
                                        <span className="text-[9px] text-slate-600">{getOperatorSymbol(t.operator)} {t.threshold}{getMetricUnit(t.metric)}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Create/Edit Dialog */}
            <Dialog open={showForm} onOpenChange={(open) => { if (!open) { setShowForm(false); setEditingRule(null); } }}>
                <DialogContent className="bg-[#0d1117] border-[#2D3748]/50 max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="rule-form-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white flex items-center gap-2">
                            <Shield className="w-5 h-5 text-cyan-400" />
                            {editingRule ? 'Edit Health Rule' : 'Create Health Rule'}
                        </DialogTitle>
                    </DialogHeader>

                    <div className="space-y-4">
                        {/* Name & Description */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Rule Name</Label>
                                <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                                    placeholder="e.g. High CPU Usage" className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="rule-name-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Description</Label>
                                <Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                                    placeholder="What this rule monitors" className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="rule-desc-input" />
                            </div>
                        </div>

                        {/* Component Type & Category */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Component Type</Label>
                                <Select value={form.component_type} onValueChange={v => setForm({ ...form, component_type: v, category: v, metric: '' })}>
                                    <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="component-type-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                        {categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Severity</Label>
                                <Select value={form.severity} onValueChange={v => setForm({ ...form, severity: v })}>
                                    <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="severity-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                        <SelectItem value="critical">Critical</SelectItem>
                                        <SelectItem value="warning">Warning</SelectItem>
                                        <SelectItem value="info">Info</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Condition Builder */}
                        <div className="space-y-2">
                            <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Primary Condition</Label>
                            <div className="p-3 rounded-lg bg-white/[0.02] border border-[#2D3748]/30">
                                <div className="flex items-center gap-2 text-xs text-slate-500 mb-2 font-mono">IF</div>
                                <div className="flex items-center gap-2">
                                    <Select value={form.metric} onValueChange={v => setForm({ ...form, metric: v })}>
                                        <SelectTrigger className="bg-white/5 border-[#2D3748] h-8 text-xs flex-1" data-testid="metric-select">
                                            <SelectValue placeholder="Select metric" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                            {filteredMetrics.map(m => <SelectItem key={m.id} value={m.id}>{m.name} ({m.unit})</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Select value={form.operator} onValueChange={v => setForm({ ...form, operator: v })}>
                                        <SelectTrigger className="bg-white/5 border-[#2D3748] h-8 text-xs w-[140px]" data-testid="operator-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                            {operators.map(o => <SelectItem key={o.id} value={o.id}>{o.symbol} {o.name}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Input type="number" value={form.threshold} onChange={e => setForm({ ...form, threshold: parseFloat(e.target.value) || 0 })}
                                        className="bg-white/5 border-[#2D3748] h-8 text-xs w-[100px] font-mono" data-testid="threshold-input" />
                                    {(form.operator === 'between' || form.operator === 'not_between') && (
                                        <>
                                            <span className="text-xs text-slate-500">and</span>
                                            <Input type="number" value={form.threshold_max || ''} onChange={e => setForm({ ...form, threshold_max: parseFloat(e.target.value) || null })}
                                                className="bg-white/5 border-[#2D3748] h-8 text-xs w-[100px] font-mono" data-testid="threshold-max-input" />
                                        </>
                                    )}
                                    {form.metric && <span className="text-[10px] text-slate-500">{getMetricUnit(form.metric)}</span>}
                                </div>
                            </div>
                        </div>

                        {/* Additional Conditions */}
                        {(form.conditions || []).map((cond, i) => (
                            <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-[#2D3748]/30" data-testid={`condition-${i}`}>
                                <div className="flex items-center justify-between mb-2">
                                    <Select value={cond.logic || 'AND'} onValueChange={v => updateCondition(i, 'logic', v)}>
                                        <SelectTrigger className="bg-cyan-500/10 border-cyan-500/20 h-6 text-xs w-[80px] text-cyan-400 font-mono">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                            <SelectItem value="AND">AND</SelectItem>
                                            <SelectItem value="OR">OR</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-white/30 hover:text-red-400" onClick={() => removeCondition(i)}>
                                        <Trash2 className="w-3 h-3" />
                                    </Button>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Select value={cond.metric} onValueChange={v => updateCondition(i, 'metric', v)}>
                                        <SelectTrigger className="bg-white/5 border-[#2D3748] h-8 text-xs flex-1">
                                            <SelectValue placeholder="Select metric" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                            {filteredMetrics.map(m => <SelectItem key={m.id} value={m.id}>{m.name} ({m.unit})</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Select value={cond.operator} onValueChange={v => updateCondition(i, 'operator', v)}>
                                        <SelectTrigger className="bg-white/5 border-[#2D3748] h-8 text-xs w-[120px]">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                            {operators.map(o => <SelectItem key={o.id} value={o.id}>{o.symbol}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                    <Input type="number" value={cond.threshold} onChange={e => updateCondition(i, 'threshold', parseFloat(e.target.value) || 0)}
                                        className="bg-white/5 border-[#2D3748] h-8 text-xs w-[100px] font-mono" />
                                </div>
                            </div>
                        ))}

                        <Button variant="ghost" size="sm" className="text-xs text-cyan-400 h-7" onClick={addCondition} data-testid="add-condition-btn">
                            <Plus className="w-3 h-3 mr-1" /> Add Condition (AND / OR)
                        </Button>

                        {/* Evaluation & Action */}
                        <div className="grid grid-cols-3 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider flex items-center gap-1"><Clock className="w-3 h-3" /> Evaluation Window</Label>
                                <Select value={String(form.duration)} onValueChange={v => setForm({ ...form, duration: parseInt(v) })}>
                                    <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="duration-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                        {DURATION_OPTIONS.map(d => <SelectItem key={d.value} value={String(d.value)}>{d.label}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Action</Label>
                                <Select value={form.action} onValueChange={v => setForm({ ...form, action: v })}>
                                    <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="action-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                        <SelectItem value="alert">Send Alert</SelectItem>
                                        <SelectItem value="email">Send Email</SelectItem>
                                        <SelectItem value="webhook">Trigger Webhook</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500 uppercase tracking-wider">Host Filter</Label>
                                <Input value={form.host_filter} onChange={e => setForm({ ...form, host_filter: e.target.value })}
                                    placeholder="Optional" className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="host-filter-input" />
                            </div>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
                        <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={handleSave} data-testid="save-rule-btn">
                            {editingRule ? 'Update Rule' : 'Create Rule'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

// ─── Stat Card ───
const StatCard = ({ label, value, icon: Icon, color }) => (
    <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 flex items-center gap-3">
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15` }}>
            <Icon className="w-4 h-4" style={{ color }} />
        </div>
        <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">{label}</p>
            <span className="text-lg font-bold text-white font-mono">{value ?? 0}</span>
        </div>
    </div>
);

// ─── Rule Card ───
const RuleCard = ({ rule, onEdit, onDelete, onToggle, getMetricName, getMetricUnit, getOperatorSymbol }) => {
    const sevCfg = SEVERITY_CONFIG[rule.severity] || SEVERITY_CONFIG.warning;
    const SevIcon = sevCfg.icon;
    const CatIcon = CATEGORY_ICONS[rule.category] || Shield;

    return (
        <Card className={`bg-[#121826] border-[#2D3748]/50 ${!rule.enabled ? 'opacity-50' : ''}`} data-testid={`rule-${rule.id}`}>
            <CardContent className="p-4">
                <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className={`p-2 rounded-lg mt-0.5 ${rule.severity === 'critical' ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
                            <SevIcon className={`w-4 h-4 ${rule.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <h3 className="text-sm font-semibold text-white truncate">{rule.name}</h3>
                                <Badge className={`text-[9px] border ${sevCfg.cls}`}>{rule.severity}</Badge>
                                <Badge className="text-[9px] bg-white/5 text-slate-500 border-0 font-mono">
                                    <CatIcon className="w-2.5 h-2.5 mr-0.5" />{rule.category}
                                </Badge>
                            </div>

                            {/* Rule Condition Display */}
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[10px] text-cyan-400 font-mono">IF</span>
                                <Badge className="text-[10px] bg-cyan-500/10 text-cyan-300 border-0 font-mono">
                                    {getMetricName(rule.metric)}
                                </Badge>
                                <span className="text-[10px] text-white/60 font-mono font-bold">{getOperatorSymbol(rule.operator)}</span>
                                <span className="text-[10px] text-white font-mono font-bold">{rule.threshold}{getMetricUnit(rule.metric)}</span>
                                {rule.threshold_max != null && (
                                    <><span className="text-[10px] text-white/40">and</span><span className="text-[10px] text-white font-mono font-bold">{rule.threshold_max}</span></>
                                )}
                                <span className="text-[10px] text-slate-500 font-mono">FOR {formatDuration(rule.duration)}</span>
                                <span className="text-[10px] text-amber-400 font-mono">THEN {rule.action || 'alert'}</span>
                            </div>

                            {/* Additional conditions */}
                            {rule.conditions && rule.conditions.length > 0 && rule.conditions.map((c, i) => (
                                <div key={i} className="flex items-center gap-1.5 mt-1">
                                    <Badge className="text-[9px] bg-purple-500/10 text-purple-400 border-0 font-mono">{c.logic}</Badge>
                                    <Badge className="text-[10px] bg-white/5 text-slate-300 border-0 font-mono">{getMetricName(c.metric)}</Badge>
                                    <span className="text-[10px] text-white/60 font-mono">{getOperatorSymbol(c.operator)}</span>
                                    <span className="text-[10px] text-white font-mono">{c.threshold}{getMetricUnit(c.metric)}</span>
                                </div>
                            ))}

                            {rule.description && <p className="text-[10px] text-slate-600 mt-1">{rule.description}</p>}
                        </div>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0 ml-3">
                        <Switch checked={rule.enabled} onCheckedChange={onToggle} data-testid={`toggle-rule-${rule.id}`} />
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-white/30 hover:text-blue-400" onClick={onEdit} data-testid={`edit-rule-${rule.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-white/30 hover:text-red-400" onClick={onDelete} data-testid={`delete-rule-${rule.id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

export default HealthRulesPage;
