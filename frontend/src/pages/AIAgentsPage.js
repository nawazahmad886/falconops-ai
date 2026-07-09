import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Brain, RefreshCw, Zap, Play, Clock, Activity, Server,
    Shield, Target, Eye, CheckCircle, Settings, History,
    AlertTriangle, Cpu, Wrench, BarChart3, Database,
    Trash2, Search, Power, PowerOff, Workflow,
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

export default function AIAgentsPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('analyze');
    const [agents, setAgents] = useState([]);
    const [llmMode, setLlmMode] = useState(null);
    const [stats, setStats] = useState(null);
    const [analysisHistory, setAnalysisHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);
    const [crewResult, setCrewResult] = useState(null);
    const [selectedAgents, setSelectedAgents] = useState(['rca', 'summarizer', 'healer']);
    const [parallel, setParallel] = useState(false);
    const [inputData, setInputData] = useState('');
    // Memory state
    const [memoryStats, setMemoryStats] = useState(null);
    const [memorySearch, setMemorySearch] = useState([]);
    const [memoryQuery, setMemoryQuery] = useState('');
    const [searching, setSearching] = useState(false);
    // Pipeline state
    const [pipelineConfig, setPipelineConfig] = useState(null);
    const [pipelineEvents, setPipelineEvents] = useState([]);
    const [pipelineStats, setPipelineStats] = useState(null);
    const [toggling, setToggling] = useState(false);
    const [simulating, setSimulating] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [aRes, sRes, hRes] = await Promise.all([
                api.get('/ai/agents'), api.get('/ai/stats'), api.get('/ai/history?limit=15'),
            ]);
            setAgents(aRes.data?.agents || []);
            setLlmMode(aRes.data?.llm_mode);
            setStats(sRes.data);
            setAnalysisHistory(hRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchMemory = useCallback(async () => {
        try { const r = await api.get('/ai/memory/stats'); setMemoryStats(r.data); } catch (e) { console.error(e); }
    }, [api]);

    const fetchPipeline = useCallback(async () => {
        try {
            const [cRes, eRes, sRes] = await Promise.all([
                api.get('/ai/pipeline/config'), api.get('/ai/pipeline/events?limit=20'), api.get('/ai/pipeline/stats'),
            ]);
            setPipelineConfig(cRes.data);
            setPipelineEvents(eRes.data || []);
            setPipelineStats(sRes.data);
        } catch (e) { console.error(e); }
    }, [api]);

    const runAnalysis = useCallback(async () => {
        if (!inputData.trim()) return;
        setAnalyzing(true); setCrewResult(null);
        try {
            let data;
            try { data = JSON.parse(inputData); } catch { data = { description: inputData }; }
            const res = await api.post('/ai/analyze', { data, agents: selectedAgents, parallel });
            setCrewResult(res.data);
            await fetchData();
        } catch (e) { console.error(e); }
        setAnalyzing(false);
    }, [api, inputData, selectedAgents, parallel, fetchData]);

    const searchMemoryFn = useCallback(async () => {
        if (!memoryQuery.trim()) return;
        setSearching(true);
        try {
            let data;
            try { data = JSON.parse(memoryQuery); } catch { data = { description: memoryQuery }; }
            const res = await api.post('/ai/memory/search', { data, limit: 5 });
            setMemorySearch(res.data || []);
        } catch (e) { console.error(e); }
        setSearching(false);
    }, [api, memoryQuery]);

    const clearMemoryFn = useCallback(async () => {
        if (!window.confirm('Clear all agent memory? This cannot be undone.')) return;
        try { await api.delete('/ai/memory/clear'); await fetchMemory(); setMemorySearch([]); } catch (e) { console.error(e); }
    }, [api, fetchMemory]);

    const togglePipeline = useCallback(async () => {
        setToggling(true);
        try {
            const newState = !pipelineConfig?.enabled;
            await api.post('/ai/pipeline/toggle', { enabled: newState });
            await fetchPipeline();
        } catch (e) { console.error(e); }
        setToggling(false);
    }, [api, pipelineConfig, fetchPipeline]);

    const simulateTrigger = useCallback(async () => {
        setSimulating(true);
        try {
            await api.post('/ai/pipeline/simulate', {
                rule_id: 'sim_test', rule_name: 'Simulated Test Rule', severity: 'warning',
                metric: 'cpu_usage', threshold: 90,
                event_data: { server: 'test-server-01', value: 95, description: 'Simulated high CPU for pipeline test' },
            });
            await fetchPipeline();
        } catch (e) { console.error(e); }
        setSimulating(false);
    }, [api, fetchPipeline]);

    const toggleAgent = (aid) => setSelectedAgents(prev => prev.includes(aid) ? prev.filter(a => a !== aid) : [...prev, aid]);

    useEffect(() => { fetchData(); }, [fetchData]);
    useEffect(() => { if (tab === 'memory') fetchMemory(); }, [tab, fetchMemory]);
    useEffect(() => { if (tab === 'pipeline') fetchPipeline(); }, [tab, fetchPipeline]);

    const sampleIncidents = [
        { label: 'API Gateway 502', data: '{"alert":"API Gateway returning 502 errors","affected":"payment-service, user-service","duration":"15 minutes","error_rate":"45%","region":"us-east"}' },
        { label: 'High Memory', data: '{"alert":"Server prod-web-03 memory at 95%","metric":"memory_usage","value":95,"threshold":90,"server":"prod-web-03"}' },
        { label: 'Database Locks', data: '{"alert":"PostgreSQL lock contention detected","blocked_queries":12,"avg_wait_time":"5.2s","database":"prod-orders"}' },
        { label: 'SSL Expiring', data: '{"alert":"SSL certificate expires in 3 days","domain":"api.example.com","issuer":"LetsEncrypt"}' },
    ];

    const tabs = [
        { id: 'analyze', label: 'Analyze', icon: Brain },
        { id: 'memory', label: 'Memory', icon: Database },
        { id: 'pipeline', label: 'Pipeline', icon: Workflow },
        { id: 'history', label: 'History', icon: History },
        { id: 'config', label: 'Config', icon: Settings },
    ];

    return (
        <div className="space-y-6" data-testid="ai-agents-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><Brain className="w-6 h-6 text-purple-400" /></div>
                        AI Agents
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Multi-agent AI with memory & auto-trigger pipeline</p>
                </div>
                <div className="flex items-center gap-2">
                    {llmMode && <Badge className={MODE_STYLES[llmMode.mode] || MODE_STYLES.fallback} data-testid="llm-mode-badge"><Cpu className="w-3 h-3 mr-1" /> {llmMode.mode === 'emergent' ? 'Emergent Key' : llmMode.mode === 'openai' ? 'OpenAI Key' : 'Heuristic'}</Badge>}
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
                </div>
            </div>

            {/* Agent Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {agents.map(agent => {
                    const colors = AGENT_COLORS[agent.id] || AGENT_COLORS.rca;
                    const Icon = AGENT_ICONS[agent.id] || Brain;
                    const agentStat = stats?.by_agent?.find(a => a.agent_id === agent.id);
                    return (
                        <Card key={agent.id} className="bg-[#0D1117] border-white/5" data-testid={`agent-card-${agent.id}`}>
                            <CardContent className="p-4">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className={`p-2 rounded-lg ${colors.bg}`}><Icon className={`w-5 h-5 ${colors.text}`} /></div>
                                    <div><h3 className="text-sm font-semibold text-white">{agent.name}</h3><p className="text-[10px] text-white/40">{agent.role}</p></div>
                                </div>
                                <div className="flex items-center justify-between mt-2">
                                    <span className="text-xs text-white/50">Analyses: {agentStat?.count || 0}</span>
                                    <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{agent.id}</Badge>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {/* ======================== ANALYZE TAB ======================== */}
            {tab === 'analyze' && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Zap className="w-4 h-4 text-purple-400" /> Run AI Analysis</CardTitle></CardHeader>
                        <CardContent className="p-4 space-y-4">
                            <div>
                                <p className="text-xs text-white/60 mb-2">Select Agents:</p>
                                <div className="flex flex-wrap gap-2">
                                    {agents.map(a => { const colors = AGENT_COLORS[a.id] || AGENT_COLORS.rca; const Icon = AGENT_ICONS[a.id] || Brain; return (
                                        <Button key={a.id} variant="outline" size="sm" onClick={() => toggleAgent(a.id)} className={`text-[10px] ${selectedAgents.includes(a.id) ? `${colors.bg} ${colors.text}` : 'text-white/30 border-white/10'}`} data-testid={`select-agent-${a.id}`}><Icon className="w-3 h-3 mr-1" /> {a.name}</Button>
                                    ); })}
                                    <Button variant="outline" size="sm" onClick={() => setParallel(!parallel)} className={`text-[10px] ${parallel ? 'bg-cyan-500/15 text-cyan-400' : 'text-white/30 border-white/10'}`}><Zap className="w-3 h-3 mr-1" /> {parallel ? 'Parallel' : 'Sequential'}</Button>
                                </div>
                            </div>
                            <div>
                                <p className="text-xs text-white/60 mb-2">Incident / Alert Data (JSON or text):</p>
                                <textarea className="w-full h-28 bg-[#161B22] border border-white/10 rounded-md p-3 text-sm text-white/80 font-mono resize-none focus:outline-none focus:border-purple-500/50" value={inputData} onChange={e => setInputData(e.target.value)} placeholder='{"alert":"...","affected":"..."}' data-testid="analysis-input" />
                                <div className="flex flex-wrap gap-1 mt-2">
                                    <span className="text-[10px] text-white/30 mr-1">Samples:</span>
                                    {sampleIncidents.map((s, i) => (<Button key={i} variant="outline" size="sm" onClick={() => setInputData(s.data)} className="text-[9px] border-white/10 text-white/40" data-testid={`sample-${i}`}>{s.label}</Button>))}
                                </div>
                            </div>
                            <Button onClick={runAnalysis} disabled={analyzing || !inputData.trim() || selectedAgents.length === 0} className="bg-purple-600 hover:bg-purple-700 text-white" data-testid="run-analysis-btn">
                                {analyzing ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />} {analyzing ? 'Analyzing...' : 'Run AI Crew'}
                            </Button>
                        </CardContent>
                    </Card>
                    {crewResult && (
                        <Card className="bg-[#0D1117] border-purple-500/20" data-testid="crew-result">
                            <CardHeader className="pb-3 border-b border-white/5">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-base flex items-center gap-2"><Brain className="w-4 h-4 text-purple-400" /> AI Analysis Results</CardTitle>
                                    <div className="flex items-center gap-2"><Badge className={MODE_STYLES[crewResult.llm_mode?.mode] || MODE_STYLES.fallback}>{crewResult.llm_mode?.mode}</Badge><span className="text-xs text-white/40">{crewResult.total_duration_ms}ms</span></div>
                                </div>
                            </CardHeader>
                            <CardContent className="p-0 divide-y divide-white/5">
                                {crewResult.results?.map((r, i) => { const colors = AGENT_COLORS[r.agent_id] || AGENT_COLORS.rca; const Icon = AGENT_ICONS[r.agent_id] || Brain; return (
                                    <div key={i} className="p-4" data-testid={`result-${r.agent_id}`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <div className={`p-1.5 rounded ${colors.bg}`}><Icon className={`w-3.5 h-3.5 ${colors.text}`} /></div>
                                            <span className="text-sm font-semibold text-white">{r.agent_name}</span>
                                            <span className="text-[10px] text-white/30">{r.duration_ms}ms</span>
                                            {r.memory_used > 0 && <Badge variant="outline" className="text-[8px] text-purple-400 border-purple-500/30"><Database className="w-2.5 h-2.5 mr-0.5" /> {r.memory_used} memories</Badge>}
                                        </div>
                                        <div className="text-xs text-white/70 whitespace-pre-wrap leading-relaxed pl-8">{typeof r.analysis === 'string' ? r.analysis : String(r.analysis || '')}</div>
                                    </div>
                                ); })}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* ======================== MEMORY TAB ======================== */}
            {tab === 'memory' && (
                <div className="space-y-4">
                    {memoryStats && (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-purple-500/15"><Database className="w-4 h-4 text-purple-400" /></div><div><p className="text-xs text-white/50">Total Memories</p><p className="text-lg font-bold text-white" data-testid="total-memories">{memoryStats.total_memories}</p></div></CardContent></Card>
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-cyan-500/15"><Eye className="w-4 h-4 text-cyan-400" /></div><div><p className="text-xs text-white/50">Unique Patterns</p><p className="text-lg font-bold text-cyan-400">{memoryStats.unique_patterns}</p></div></CardContent></Card>
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                                <p className="text-xs text-white/50 mb-1">By Agent</p>
                                {Object.entries(memoryStats.by_agent || {}).map(([k, v]) => <p key={k} className="text-[10px] text-white/40">{k}: <span className="text-white/70">{v}</span></p>)}
                            </CardContent></Card>
                        </div>
                    )}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base flex items-center gap-2"><Search className="w-4 h-4 text-purple-400" /> Search Memory</CardTitle>
                                <Button variant="outline" size="sm" onClick={clearMemoryFn} className="border-red-500/20 text-red-400 text-xs" data-testid="clear-memory-btn"><Trash2 className="w-3 h-3 mr-1" /> Clear All</Button>
                            </div>
                        </CardHeader>
                        <CardContent className="p-4 space-y-3">
                            <textarea className="w-full h-20 bg-[#161B22] border border-white/10 rounded-md p-3 text-sm text-white/80 font-mono resize-none focus:outline-none focus:border-purple-500/50" value={memoryQuery} onChange={e => setMemoryQuery(e.target.value)} placeholder='Search past incidents: {"alert":"high cpu"}' data-testid="memory-search-input" />
                            <Button onClick={searchMemoryFn} disabled={searching || !memoryQuery.trim()} className="bg-purple-600 hover:bg-purple-700 text-white text-xs" data-testid="search-memory-btn">
                                {searching ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Search className="w-3 h-3 mr-1" />} Search
                            </Button>
                            {memorySearch.length > 0 && (
                                <div className="space-y-2 mt-3" data-testid="memory-results">
                                    {memorySearch.map((m, i) => (
                                        <div key={i} className="p-3 bg-white/[0.02] rounded-lg border border-white/5" data-testid={`memory-result-${i}`}>
                                            <div className="flex items-center justify-between mb-1">
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="text-[9px] text-purple-400 border-purple-500/30">{m.similarity}% match</Badge>
                                                    <span className="text-xs text-white/50">{m.agent_name}</span>
                                                </div>
                                                <span className="text-[10px] text-white/25">{m.timestamp ? new Date(m.timestamp).toLocaleString() : ''}</span>
                                            </div>
                                            <p className="text-[10px] text-white/40 truncate">{m.input_summary}</p>
                                            <p className="text-[10px] text-white/60 mt-1 truncate">{m.analysis_summary}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ======================== PIPELINE TAB ======================== */}
            {tab === 'pipeline' && (
                <div className="space-y-4">
                    {/* Pipeline Controls */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardContent className="p-4 flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className={`p-2 rounded-lg ${pipelineConfig?.enabled ? 'bg-emerald-500/15' : 'bg-red-500/15'}`}>
                                    {pipelineConfig?.enabled ? <Power className="w-5 h-5 text-emerald-400" /> : <PowerOff className="w-5 h-5 text-red-400" />}
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-white">Auto-Trigger Pipeline</p>
                                    <p className="text-[10px] text-white/40">{pipelineConfig?.description}</p>
                                </div>
                            </div>
                            <div className="flex gap-2">
                                <Button variant="outline" size="sm" onClick={togglePipeline} disabled={toggling} className={`text-xs ${pipelineConfig?.enabled ? 'border-red-500/30 text-red-400' : 'border-emerald-500/30 text-emerald-400'}`} data-testid="toggle-pipeline-btn">
                                    {toggling ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : (pipelineConfig?.enabled ? <PowerOff className="w-3 h-3 mr-1" /> : <Power className="w-3 h-3 mr-1" />)}
                                    {pipelineConfig?.enabled ? 'Disable' : 'Enable'}
                                </Button>
                                <Button variant="outline" size="sm" onClick={simulateTrigger} disabled={simulating} className="border-purple-500/30 text-purple-400 text-xs" data-testid="simulate-trigger-btn">
                                    {simulating ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />} Simulate Trigger
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Pipeline Stats */}
                    {pipelineStats && (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Total Triggers</p><p className="text-lg font-bold text-white" data-testid="total-triggers">{pipelineStats.total_triggers}</p></CardContent></Card>
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Triggers (24h)</p><p className="text-lg font-bold text-amber-400">{pipelineStats.triggers_24h}</p></CardContent></Card>
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                                <p className="text-xs text-white/50 mb-1">Top Rules</p>
                                {pipelineStats.by_rule?.slice(0, 3).map((r, i) => <p key={i} className="text-[10px] text-white/40">{r.rule_name}: <span className="text-white/70">{r.count}</span></p>)}
                                {(!pipelineStats.by_rule || pipelineStats.by_rule.length === 0) && <p className="text-[10px] text-white/30">No triggers yet</p>}
                            </CardContent></Card>
                        </div>
                    )}

                    {/* Pipeline Events */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Workflow className="w-4 h-4 text-amber-400" /> Pipeline Events <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{pipelineEvents.length}</Badge></CardTitle></CardHeader>
                        <CardContent className="p-0">
                            <div className="max-h-[400px] overflow-y-auto divide-y divide-white/5" data-testid="pipeline-events">
                                {pipelineEvents.length === 0 ? (
                                    <div className="p-8 text-center text-white/40"><Workflow className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No pipeline events. Enable the pipeline and simulate a trigger.</p></div>
                                ) : pipelineEvents.map((ev, i) => (
                                    <div key={ev.id || i} className="p-3 hover:bg-white/[0.02]" data-testid={`pipeline-event-${i}`}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2">
                                                <Badge className={ev.severity === 'critical' ? 'text-[9px] bg-red-500/15 text-red-400 border-red-500/30' : 'text-[9px] bg-amber-500/15 text-amber-400 border-amber-500/30'}>{ev.severity}</Badge>
                                                <span className="text-sm text-white/80">{ev.rule_name}</span>
                                            </div>
                                            <span className="text-[10px] text-white/25">{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : ''}</span>
                                        </div>
                                        {ev.crew_result?.results_summary?.map((r, j) => (
                                            <p key={j} className="text-[10px] text-white/40 truncate pl-3 mt-0.5"><span className="text-white/50">{r.agent}:</span> {r.preview}</p>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ======================== HISTORY TAB ======================== */}
            {tab === 'history' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><History className="w-4 h-4 text-white/60" /> Analysis History</CardTitle></CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[600px] overflow-y-auto divide-y divide-white/5" data-testid="history-list">
                            {analysisHistory.length === 0 ? (
                                <div className="p-8 text-center text-white/40"><Brain className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No analyses yet.</p></div>
                            ) : analysisHistory.map((h, i) => {
                                const colors = AGENT_COLORS[h.agent_id] || AGENT_COLORS.rca;
                                const Icon = AGENT_ICONS[h.agent_id] || Brain;
                                return (
                                    <div key={i} className="p-3 hover:bg-white/[0.02]" data-testid={`history-${i}`}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2">
                                                <div className={`p-1 rounded ${colors.bg}`}><Icon className={`w-3 h-3 ${colors.text}`} /></div>
                                                <span className="text-xs text-white/70">{h.agent_name}</span>
                                                <Badge variant="outline" className="text-[8px] text-white/30 border-white/10">{h.llm_mode}</Badge>
                                                {h.memory_used > 0 && <Badge variant="outline" className="text-[8px] text-purple-400 border-purple-500/30"><Database className="w-2 h-2 mr-0.5" /> {h.memory_used}</Badge>}
                                            </div>
                                            <span className="text-[10px] text-white/25">{h.timestamp ? new Date(h.timestamp).toLocaleString() : ''}</span>
                                        </div>
                                        <p className="text-[10px] text-white/50 truncate pl-7">{typeof h.analysis === 'string' ? h.analysis.slice(0, 150) : String(h.analysis || '').slice(0, 150)}...</p>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ======================== CONFIG TAB ======================== */}
            {tab === 'config' && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Settings className="w-4 h-4 text-white/60" /> LLM Configuration</CardTitle></CardHeader>
                        <CardContent className="p-4 space-y-4">
                            <div className="flex items-center gap-4"><span className="text-xs text-white/50">Active Mode:</span><Badge className={MODE_STYLES[llmMode?.mode] || MODE_STYLES.fallback} data-testid="config-mode-badge">{llmMode?.mode === 'emergent' ? 'Emergent Universal Key (Cloud)' : llmMode?.mode === 'openai' ? 'OpenAI API Key (On-Premise)' : 'Heuristic Fallback'}</Badge></div>
                            <div className="bg-white/[0.02] rounded-lg p-4 border border-white/5">
                                <p className="text-xs text-white/60 mb-2">On-Premise Setup:</p>
                                <div className="space-y-1 text-[10px] font-mono text-white/40">
                                    <p className="text-emerald-400">OPENAI_API_KEY=sk-your-openai-key-here</p>
                                    <p># Remove EMERGENT_LLM_KEY to use OpenAI directly</p>
                                </div>
                            </div>
                            <div className="bg-white/[0.02] rounded-lg p-4 border border-white/5">
                                <p className="text-xs text-white/60 mb-2">Priority Order:</p>
                                {[
                                    { n: '1', label: 'EMERGENT_LLM_KEY', desc: 'Cloud-managed universal key', active: llmMode?.mode === 'emergent' },
                                    { n: '2', label: 'OPENAI_API_KEY', desc: 'On-premise / self-hosted', active: llmMode?.mode === 'openai' },
                                    { n: '3', label: 'Heuristic', desc: 'Works offline', active: llmMode?.mode === 'fallback' },
                                ].map(p => (
                                    <div key={p.n} className={`flex items-center gap-3 p-2 rounded mb-1 ${p.active ? 'bg-purple-500/10 border border-purple-500/20' : ''}`}>
                                        <span className={`text-xs font-bold ${p.active ? 'text-purple-400' : 'text-white/30'}`}>{p.n}</span>
                                        <div><p className={`text-xs font-mono ${p.active ? 'text-purple-400' : 'text-white/50'}`}>{p.label}</p><p className="text-[10px] text-white/30">{p.desc}</p></div>
                                        {p.active && <Badge className="ml-auto text-[8px] bg-emerald-500/15 text-emerald-400 border-emerald-500/30">Active</Badge>}
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
