import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Shield, RefreshCw, Plus, Trash2, Edit, CheckCircle, XCircle,
    AlertTriangle, Eye, Zap, Activity, Clock, BarChart3, Target,
    Settings, Brain, Server, Lock, Database,
} from 'lucide-react';

const SEVERITY_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};
const CATEGORY_ICONS = {
    performance: Zap, availability: Activity, resource: Server,
    security: Lock, ai: Brain, custom: Settings,
};

export default function DetectionRulesPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('rules');
    const [rules, setRules] = useState([]);
    const [incidents, setIncidents] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [editingRule, setEditingRule] = useState(null);
    const [form, setForm] = useState({
        name: '', description: '', metric: '', operator: 'gt',
        threshold: '', severity: 'warning', cooldown_min: '10',
        enabled: true, category: 'custom',
    });

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [rRes, iRes, sRes] = await Promise.all([
                api.get('/detection/rules'),
                api.get('/detection/incidents?hours=24&limit=20'),
                api.get('/detection/stats'),
            ]);
            setRules(rRes.data || []);
            setIncidents(iRes.data || []);
            setStats(sRes.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const createRule = useCallback(async () => {
        try {
            await api.post('/detection/rules', { ...form, threshold: parseFloat(form.threshold), cooldown_min: parseInt(form.cooldown_min) });
            setShowAdd(false);
            setForm({ name: '', description: '', metric: '', operator: 'gt', threshold: '', severity: 'warning', cooldown_min: '10', enabled: true, category: 'custom' });
            await fetchData();
        } catch (e) { console.error(e); }
    }, [api, form, fetchData]);

    const updateRule = useCallback(async (ruleId, updates) => {
        try { await api.put(`/detection/rules/${ruleId}`, updates); await fetchData(); setEditingRule(null); } catch (e) { console.error(e); }
    }, [api, fetchData]);

    const deleteRule = useCallback(async (ruleId) => {
        try { await api.delete(`/detection/rules/${ruleId}`); await fetchData(); } catch (e) { console.error(e); }
    }, [api, fetchData]);

    const toggleRule = useCallback(async (ruleId, currentEnabled) => {
        await updateRule(ruleId, { enabled: !currentEnabled });
    }, [updateRule]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const tabs = [
        { id: 'rules', label: 'Detection Rules', icon: Shield },
        { id: 'incidents', label: 'Incident Intelligence', icon: Brain },
    ];

    return (
        <div className="space-y-6" data-testid="detection-rules-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><Shield className="w-6 h-6 text-red-400" /></div>
                        Detection & Intelligence
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Admin-configurable detection rules and AI incident correlation</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
                    <Button size="sm" onClick={() => setShowAdd(!showAdd)} className="bg-red-600 hover:bg-red-700 text-white text-xs" data-testid="add-rule-btn"><Plus className="w-3 h-3 mr-1" /> New Rule</Button>
                </div>
            </div>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><Shield className="w-4 h-4 text-blue-400" /></div>
                        <div><p className="text-xs text-white/50">Active Rules</p><p className="text-lg font-bold text-white">{stats.active_rules}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/15"><AlertTriangle className="w-4 h-4 text-amber-400" /></div>
                        <div><p className="text-xs text-white/50">Alerts (24h)</p><p className="text-lg font-bold text-amber-400">{stats.alerts_fired_24h}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><Target className="w-4 h-4 text-red-400" /></div>
                        <div><p className="text-xs text-white/50">Threats (24h)</p><p className="text-lg font-bold text-red-400">{stats.threats_detected_24h}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><BarChart3 className="w-4 h-4 text-purple-400" /></div>
                        <div><p className="text-xs text-white/50">Categories</p><p className="text-lg font-bold text-white">{Object.keys(stats.categories || {}).length}</p></div>
                    </CardContent></Card>
                </div>
            )}

            {/* Add Rule Form */}
            {showAdd && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="add-rule-form">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Plus className="w-4 h-4 text-red-400" /> New Detection Rule</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Rule Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="High Latency Alert" data-testid="rule-name-input" /></div>
                            <div><Label className="text-xs text-white/60">Metric</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.metric} onChange={e => setForm(p => ({ ...p, metric: e.target.value }))} placeholder="response_time_ms" data-testid="rule-metric-input" /></div>
                            <div><Label className="text-xs text-white/60">Category</Label>
                                <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        {['performance', 'availability', 'resource', 'security', 'ai', 'custom'].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <div><Label className="text-xs text-white/60">Operator</Label>
                                <Select value={form.operator} onValueChange={v => setForm(p => ({ ...p, operator: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        <SelectItem value="gt">&gt; Greater Than</SelectItem>
                                        <SelectItem value="lt">&lt; Less Than</SelectItem>
                                        <SelectItem value="eq">= Equal</SelectItem>
                                        <SelectItem value="gte">&gt;= Greater or Equal</SelectItem>
                                        <SelectItem value="lte">&lt;= Less or Equal</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs text-white/60">Threshold</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.threshold} onChange={e => setForm(p => ({ ...p, threshold: e.target.value }))} data-testid="rule-threshold-input" /></div>
                            <div><Label className="text-xs text-white/60">Severity</Label>
                                <Select value={form.severity} onValueChange={v => setForm(p => ({ ...p, severity: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="critical">Critical</SelectItem><SelectItem value="warning">Warning</SelectItem><SelectItem value="info">Info</SelectItem></SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs text-white/60">Cooldown (min)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.cooldown_min} onChange={e => setForm(p => ({ ...p, cooldown_min: e.target.value }))} /></div>
                            <div className="flex items-end"><Button onClick={createRule} disabled={!form.name || !form.metric || !form.threshold} className="w-full bg-red-600 hover:bg-red-700 text-white" data-testid="submit-rule-btn"><CheckCircle className="w-3 h-3 mr-1" /> Create</Button></div>
                        </div>
                        <div><Label className="text-xs text-white/60">Description</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Describe when this rule should trigger..." /></div>
                    </CardContent>
                </Card>
            )}

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {/* Rules Tab */}
            {tab === 'rules' && (
                <div className="grid grid-cols-1 gap-3" data-testid="rules-list">
                    {rules.map(rule => {
                        const sevStyle = SEVERITY_STYLES[rule.severity] || SEVERITY_STYLES.warning;
                        const CatIcon = CATEGORY_ICONS[rule.category] || Settings;
                        return (
                            <Card key={rule.rule_id} className={`bg-[#0D1117] border-white/5 ${!rule.enabled ? 'opacity-50' : ''}`} data-testid={`rule-card-${rule.rule_id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <div className={`p-2 rounded-lg ${sevStyle.split(' ')[0]}`}><CatIcon className={`w-4 h-4 ${sevStyle.split(' ')[1]}`} /></div>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <h3 className="text-sm font-semibold text-white">{rule.name}</h3>
                                                    <Badge className={`text-[9px] ${sevStyle}`}>{rule.severity}</Badge>
                                                    <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{rule.category}</Badge>
                                                    {rule.is_system && <Badge variant="outline" className="text-[9px] text-white/20 border-white/5">System</Badge>}
                                                </div>
                                                <p className="text-[10px] text-white/40 mt-0.5">{rule.description}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <div className="text-right hidden md:block">
                                                <p className="text-xs text-white/50 font-mono">{rule.metric} {rule.operator} {rule.threshold}</p>
                                                <p className="text-[10px] text-white/30">Cooldown: {rule.cooldown_min}min</p>
                                            </div>
                                            <div className="flex gap-1">
                                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => toggleRule(rule.rule_id, rule.enabled)} title={rule.enabled ? 'Disable' : 'Enable'}>
                                                    {rule.enabled ? <CheckCircle className="w-3 h-3 text-emerald-400" /> : <XCircle className="w-3 h-3 text-red-400" />}
                                                </Button>
                                                {!rule.is_system && <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteRule(rule.rule_id)} data-testid={`delete-rule-${rule.rule_id}`}><Trash2 className="w-3 h-3 text-red-400/50" /></Button>}
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Incidents Tab */}
            {tab === 'incidents' && (
                <div className="space-y-3" data-testid="incidents-list">
                    {incidents.length === 0 ? (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-8 text-center text-white/40"><Brain className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No incidents detected in the last 24 hours.</p></CardContent></Card>
                    ) : incidents.map((inc, i) => {
                        const sevStyle = SEVERITY_STYLES[inc.severity] || SEVERITY_STYLES.warning;
                        return (
                            <Card key={inc.id} className="bg-[#0D1117] border-white/5" data-testid={`incident-card-${i}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <Badge className={`text-[9px] ${sevStyle}`}>{inc.severity}</Badge>
                                            <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{inc.type}</Badge>
                                            <h3 className="text-sm font-semibold text-white">{inc.monitor_name}</h3>
                                        </div>
                                        <span className="text-[10px] text-white/25">{inc.last_seen ? new Date(inc.last_seen).toLocaleString() : ''}</span>
                                    </div>
                                    <p className="text-xs text-white/60 mb-2">{inc.summary}</p>
                                    <div className="flex items-center gap-4">
                                        <div className="flex items-center gap-1 text-[10px] text-white/40"><AlertTriangle className="w-3 h-3" /> {inc.alert_count} alert(s)</div>
                                        <div className="flex items-center gap-1 text-[10px] text-cyan-400"><Brain className="w-3 h-3" /> {inc.root_cause_hint}</div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
