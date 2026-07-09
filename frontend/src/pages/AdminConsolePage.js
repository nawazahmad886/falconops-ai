import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Settings, RefreshCw, Brain, Shield, Target, Wrench,
    Database, Activity, Zap, Server, CheckCircle, XCircle,
    Power, PowerOff, Eye, AlertTriangle, Cpu, Clock,
    BarChart3, Globe, Workflow, Save,
} from 'lucide-react';

const AGENT_ICONS = { rca: Target, summarizer: AlertTriangle, healer: Wrench };
const AGENT_COLORS = {
    rca: { bg: 'bg-red-500/15', text: 'text-red-400' },
    summarizer: { bg: 'bg-amber-500/15', text: 'text-amber-400' },
    healer: { bg: 'bg-emerald-500/15', text: 'text-emerald-400' },
};
const MODE_STYLES = {
    emergent: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    openai: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    fallback: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
};

export default function AdminConsolePage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('overview');
    const [overview, setOverview] = useState(null);
    const [agents, setAgents] = useState([]);
    const [ingestionConfig, setIngestionConfig] = useState(null);
    const [ingestionStats, setIngestionStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [editingAgent, setEditingAgent] = useState(null);
    const [agentForm, setAgentForm] = useState({});

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [oRes, aRes, cRes, sRes] = await Promise.all([
                api.get('/soc-engine/admin/overview'),
                api.get('/soc-engine/admin/agents'),
                api.get('/soc-engine/config'),
                api.get('/soc-engine/stats'),
            ]);
            setOverview(oRes.data);
            setAgents(aRes.data || []);
            setIngestionConfig(cRes.data);
            setIngestionStats(sRes.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const saveAgentConfig = useCallback(async () => {
        if (!editingAgent) return;
        setSaving(true);
        try {
            await api.put('/soc-engine/admin/agents', { agent_id: editingAgent, ...agentForm });
            setEditingAgent(null);
            await fetchData();
        } catch (e) { console.error(e); }
        setSaving(false);
    }, [api, editingAgent, agentForm, fetchData]);

    const saveIngestionConfig = useCallback(async (updates) => {
        setSaving(true);
        try {
            await api.put('/soc-engine/config', updates);
            await fetchData();
        } catch (e) { console.error(e); }
        setSaving(false);
    }, [api, fetchData]);

    const togglePipeline = useCallback(async () => {
        try {
            const newState = !overview?.pipeline?.enabled;
            await api.post('/ai/pipeline/toggle', { enabled: newState });
            await fetchData();
        } catch (e) { console.error(e); }
    }, [api, overview, fetchData]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const tabs = [
        { id: 'overview', label: 'System Overview', icon: BarChart3 },
        { id: 'agents', label: 'Agent Config', icon: Brain },
        { id: 'ingestion', label: 'SOC Ingestion', icon: Workflow },
        { id: 'pipeline', label: 'AI Pipeline', icon: Zap },
    ];

    return (
        <div className="space-y-6" data-testid="admin-console-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><Settings className="w-6 h-6 text-red-400" /></div>
                        Admin Console
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Full platform configuration: AI agents, SOC engine, pipeline controls</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
            </div>

            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {/* ======================== OVERVIEW ======================== */}
            {tab === 'overview' && overview && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-purple-500/15"><Cpu className="w-4 h-4 text-purple-400" /></div>
                            <div><p className="text-xs text-white/50">LLM Mode</p><Badge className={MODE_STYLES[overview.llm?.mode] || MODE_STYLES.fallback} data-testid="llm-mode">{overview.llm?.mode}</Badge></div>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-blue-500/15"><Brain className="w-4 h-4 text-blue-400" /></div>
                            <div><p className="text-xs text-white/50">Total Analyses</p><p className="text-lg font-bold text-white">{overview.agents?.total_analyses || 0}</p></div>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-cyan-500/15"><Database className="w-4 h-4 text-cyan-400" /></div>
                            <div><p className="text-xs text-white/50">Memory Items</p><p className="text-lg font-bold text-cyan-400">{overview.memory?.total_memories || 0}</p></div>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${overview.pipeline?.enabled ? 'bg-emerald-500/15' : 'bg-red-500/15'}`}>
                                {overview.pipeline?.enabled ? <Power className="w-4 h-4 text-emerald-400" /> : <PowerOff className="w-4 h-4 text-red-400" />}
                            </div>
                            <div><p className="text-xs text-white/50">Pipeline</p><p className={`text-sm font-bold ${overview.pipeline?.enabled ? 'text-emerald-400' : 'text-red-400'}`}>{overview.pipeline?.enabled ? 'Active' : 'Disabled'}</p></div>
                        </CardContent></Card>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm">SOC Engine Status</CardTitle></CardHeader>
                            <CardContent className="p-4 space-y-2">
                                <div className="flex justify-between text-xs"><span className="text-white/50">Total Events</span><span className="text-white/80">{overview.ingestion?.total_events || 0}</span></div>
                                <div className="flex justify-between text-xs"><span className="text-white/50">Events (1h)</span><span className="text-white/80">{overview.ingestion?.events_last_hour || 0}</span></div>
                                <div className="flex justify-between text-xs"><span className="text-white/50">Open Incidents</span><span className="text-amber-400">{overview.ingestion?.open_incidents || 0}</span></div>
                                <div className="flex justify-between text-xs"><span className="text-white/50">Auto-Correlate</span><span className={overview.ingestion?.auto_correlate ? 'text-emerald-400' : 'text-red-400'}>{overview.ingestion?.auto_correlate ? 'ON' : 'OFF'}</span></div>
                                <div className="flex justify-between text-xs"><span className="text-white/50">Auto-AI Trigger</span><span className={overview.ingestion?.auto_ai_trigger ? 'text-emerald-400' : 'text-red-400'}>{overview.ingestion?.auto_ai_trigger ? 'ON' : 'OFF'}</span></div>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm">Agent Performance</CardTitle></CardHeader>
                            <CardContent className="p-4 space-y-2">
                                {overview.agents?.by_agent?.map(a => (
                                    <div key={a.agent_id} className="flex justify-between text-xs">
                                        <span className="text-white/50">{a.name}</span>
                                        <span className="text-white/80">{a.count} runs</span>
                                    </div>
                                ))}
                                <div className="flex justify-between text-xs pt-2 border-t border-white/5"><span className="text-white/50">Memory Patterns</span><span className="text-cyan-400">{overview.memory?.unique_patterns || 0}</span></div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}

            {/* ======================== AGENT CONFIG ======================== */}
            {tab === 'agents' && (
                <div className="space-y-3">
                    {agents.map(agent => {
                        const colors = AGENT_COLORS[agent.agent_id] || AGENT_COLORS.rca;
                        const Icon = AGENT_ICONS[agent.agent_id] || Brain;
                        const isEditing = editingAgent === agent.agent_id;
                        return (
                            <Card key={agent.agent_id} className={`bg-[#0D1117] border-white/5 ${!agent.enabled ? 'opacity-50' : ''}`} data-testid={`admin-agent-${agent.agent_id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <div className={`p-2 rounded-lg ${colors.bg}`}><Icon className={`w-5 h-5 ${colors.text}`} /></div>
                                            <div>
                                                <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
                                                <p className="text-[10px] text-white/40">{agent.role}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge className={agent.enabled ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30'}>
                                                {agent.enabled ? 'Enabled' : 'Disabled'}
                                            </Badge>
                                            <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">temp: {agent.temperature}</Badge>
                                            <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{agent.max_tokens} tokens</Badge>
                                            <Button variant="outline" size="sm" className="border-white/10 text-xs" data-testid={`edit-agent-${agent.agent_id}`}
                                                onClick={() => {
                                                    if (isEditing) { setEditingAgent(null); } else {
                                                        setEditingAgent(agent.agent_id);
                                                        setAgentForm({ name: agent.name, role: agent.role, system_prompt: agent.system_prompt, enabled: agent.enabled, temperature: agent.temperature, max_tokens: agent.max_tokens });
                                                    }
                                                }}>
                                                <Settings className="w-3 h-3 mr-1" /> {isEditing ? 'Cancel' : 'Configure'}
                                            </Button>
                                        </div>
                                    </div>
                                    {!isEditing && <p className="text-[10px] text-white/30 truncate">{agent.system_prompt?.slice(0, 120)}...</p>}

                                    {isEditing && (
                                        <div className="mt-3 pt-3 border-t border-white/5 space-y-3">
                                            <div className="grid grid-cols-2 gap-3">
                                                <div><Label className="text-xs text-white/60">Agent Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={agentForm.name || ''} onChange={e => setAgentForm(p => ({ ...p, name: e.target.value }))} /></div>
                                                <div><Label className="text-xs text-white/60">Role</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={agentForm.role || ''} onChange={e => setAgentForm(p => ({ ...p, role: e.target.value }))} /></div>
                                            </div>
                                            <div className="grid grid-cols-3 gap-3">
                                                <div><Label className="text-xs text-white/60">Temperature (0-1)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" step="0.1" min="0" max="1" value={agentForm.temperature || 0.3} onChange={e => setAgentForm(p => ({ ...p, temperature: parseFloat(e.target.value) }))} /></div>
                                                <div><Label className="text-xs text-white/60">Max Tokens</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={agentForm.max_tokens || 1000} onChange={e => setAgentForm(p => ({ ...p, max_tokens: parseInt(e.target.value) }))} /></div>
                                                <div className="flex items-end">
                                                    <Button variant="outline" size="sm" className={`w-full ${agentForm.enabled ? 'border-emerald-500/30 text-emerald-400' : 'border-red-500/30 text-red-400'}`}
                                                        onClick={() => setAgentForm(p => ({ ...p, enabled: !p.enabled }))}>
                                                        {agentForm.enabled ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                                                        {agentForm.enabled ? 'Enabled' : 'Disabled'}
                                                    </Button>
                                                </div>
                                            </div>
                                            <div><Label className="text-xs text-white/60">System Prompt</Label>
                                                <textarea className="w-full h-28 bg-[#161B22] border border-white/10 rounded-md p-3 text-xs text-white/70 font-mono mt-1 resize-none focus:outline-none focus:border-purple-500/50"
                                                    value={agentForm.system_prompt || ''} onChange={e => setAgentForm(p => ({ ...p, system_prompt: e.target.value }))} />
                                            </div>
                                            <Button onClick={saveAgentConfig} disabled={saving} className="bg-purple-600 hover:bg-purple-700 text-white text-xs" data-testid={`save-agent-${agent.agent_id}`}>
                                                <Save className="w-3 h-3 mr-1" /> {saving ? 'Saving...' : 'Save Configuration'}
                                            </Button>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* ======================== INGESTION CONFIG ======================== */}
            {tab === 'ingestion' && ingestionConfig && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Total Events</p><p className="text-lg font-bold text-white" data-testid="soc-total-events">{ingestionStats?.total_events || 0}</p></CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Events (1h)</p><p className="text-lg font-bold text-cyan-400">{ingestionStats?.events_last_hour || 0}</p></CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Incidents</p><p className="text-lg font-bold text-amber-400">{ingestionStats?.total_incidents || 0}</p></CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Open</p><p className="text-lg font-bold text-red-400">{ingestionStats?.open_incidents || 0}</p></CardContent></Card>
                    </div>

                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><Settings className="w-4 h-4 text-white/60" /> Ingestion Engine Settings</CardTitle></CardHeader>
                        <CardContent className="p-4 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                    <div><p className="text-xs text-white/70">Auto-Correlate Events</p><p className="text-[10px] text-white/30">Group related events into incidents</p></div>
                                    <Button variant="outline" size="sm" onClick={() => saveIngestionConfig({ auto_correlate: !ingestionConfig.auto_correlate })}
                                        className={`text-xs ${ingestionConfig.auto_correlate ? 'border-emerald-500/30 text-emerald-400' : 'border-red-500/30 text-red-400'}`} data-testid="toggle-correlate">
                                        {ingestionConfig.auto_correlate ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                                        {ingestionConfig.auto_correlate ? 'ON' : 'OFF'}
                                    </Button>
                                </div>
                                <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                    <div><p className="text-xs text-white/70">Auto-AI Trigger</p><p className="text-[10px] text-white/30">Run AI agents on new incidents</p></div>
                                    <Button variant="outline" size="sm" onClick={() => saveIngestionConfig({ auto_ai_trigger: !ingestionConfig.auto_ai_trigger })}
                                        className={`text-xs ${ingestionConfig.auto_ai_trigger ? 'border-emerald-500/30 text-emerald-400' : 'border-red-500/30 text-red-400'}`} data-testid="toggle-ai-trigger">
                                        {ingestionConfig.auto_ai_trigger ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                                        {ingestionConfig.auto_ai_trigger ? 'ON' : 'OFF'}
                                    </Button>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div><Label className="text-xs text-white/60">Correlation Window (min)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={ingestionConfig.correlation_window_min}
                                    onChange={e => saveIngestionConfig({ correlation_window_min: parseInt(e.target.value) || 10 })} /></div>
                                <div><Label className="text-xs text-white/60">Incident Threshold (events)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={ingestionConfig.incident_threshold}
                                    onChange={e => saveIngestionConfig({ incident_threshold: parseInt(e.target.value) || 3 })} /></div>
                            </div>
                            {ingestionStats?.by_source?.length > 0 && (
                                <div><p className="text-xs text-white/50 mb-2">Events by Source</p>
                                    <div className="flex flex-wrap gap-2">{ingestionStats.by_source.map(s => (
                                        <Badge key={s.source} variant="outline" className="text-[10px] text-white/50 border-white/10">{s.source}: {s.count}</Badge>
                                    ))}</div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ======================== PIPELINE ======================== */}
            {tab === 'pipeline' && overview && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardContent className="p-5 flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className={`p-3 rounded-xl ${overview.pipeline?.enabled ? 'bg-emerald-500/15' : 'bg-red-500/15'}`}>
                                    {overview.pipeline?.enabled ? <Power className="w-6 h-6 text-emerald-400" /> : <PowerOff className="w-6 h-6 text-red-400" />}
                                </div>
                                <div>
                                    <p className="text-lg font-bold text-white">AI Auto-Trigger Pipeline</p>
                                    <p className="text-xs text-white/40">Detection rules + SOC incidents auto-trigger AI agents</p>
                                </div>
                            </div>
                            <Button onClick={togglePipeline} className={overview.pipeline?.enabled ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'} data-testid="toggle-pipeline-main">
                                {overview.pipeline?.enabled ? <><PowerOff className="w-4 h-4 mr-1" /> Disable Pipeline</> : <><Power className="w-4 h-4 mr-1" /> Enable Pipeline</>}
                            </Button>
                        </CardContent>
                    </Card>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardContent className="p-4">
                                <p className="text-xs text-white/50 mb-2">Data Flow</p>
                                <div className="space-y-2 text-xs text-white/60">
                                    {[
                                        { label: 'Event Ingested', icon: Globe, active: true },
                                        { label: 'Normalized & Stored', icon: Database, active: true },
                                        { label: 'Correlation Check', icon: Activity, active: overview.ingestion?.auto_correlate },
                                        { label: 'Incident Created', icon: AlertTriangle, active: overview.ingestion?.auto_correlate },
                                        { label: 'AI Agents Triggered', icon: Brain, active: overview.pipeline?.enabled && overview.ingestion?.auto_ai_trigger },
                                        { label: 'Results to Dashboard', icon: Eye, active: true },
                                    ].map((s, i) => (
                                        <div key={i} className="flex items-center gap-2">
                                            <div className={`w-5 h-5 rounded-full flex items-center justify-center ${s.active ? 'bg-emerald-500/15' : 'bg-white/5'}`}>
                                                <s.icon className={`w-2.5 h-2.5 ${s.active ? 'text-emerald-400' : 'text-white/20'}`} />
                                            </div>
                                            <span className={s.active ? 'text-white/70' : 'text-white/30'}>{s.label}</span>
                                            {!s.active && <Badge variant="outline" className="text-[8px] text-white/20 border-white/5">OFF</Badge>}
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0D1117] border-white/5 md:col-span-2">
                            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm">Agent Run Configuration</CardTitle></CardHeader>
                            <CardContent className="p-4 space-y-2">
                                <p className="text-xs text-white/50 mb-2">Agents run on auto-trigger:</p>
                                {overview.agents?.available_agents?.map(a => {
                                    const colors = AGENT_COLORS[a.id] || AGENT_COLORS.rca;
                                    const Icon = AGENT_ICONS[a.id] || Brain;
                                    return (
                                        <div key={a.id} className="flex items-center justify-between p-2 rounded bg-white/[0.02]">
                                            <div className="flex items-center gap-2"><div className={`p-1 rounded ${colors.bg}`}><Icon className={`w-3 h-3 ${colors.text}`} /></div><span className="text-xs text-white/70">{a.name}</span></div>
                                            <Badge variant="outline" className="text-[9px] text-white/40 border-white/10">{a.role}</Badge>
                                        </div>
                                    );
                                })}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
