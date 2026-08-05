import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Save, Rocket, FlaskConical, Bot } from 'lucide-react';

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'azure', 'ollama', 'emergent', 'rule_based'];
const TABS = ['Identity', 'Instructions', 'Model', 'Tools', 'Knowledge', 'Memory', 'Guardrails', 'Test'];

export const AgentBuilderPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const { agentId: routeAgentId } = useParams();

    const [agentId, setAgentId] = useState(routeAgentId || null);
    const [definition, setDefinition] = useState(null);
    const [form, setForm] = useState({
        name: 'Untitled Agent', description: '', category: 'custom',
        system_instructions: { template: '', variables: [] },
        llm_config: { provider: 'openai', model: '', temperature: 0.2, max_tokens: 1500 },
        tools: [], knowledge_config: { enabled: false, source: 'none', retrieval_limit: 3, citation_required: true },
        memory_config: { stm_enabled: true, ltm_enabled: false },
        guardrails: { max_iterations: 6, max_execution_seconds: 120, confidence_threshold: 0 },
    });
    const [toolCatalog, setToolCatalog] = useState([]);
    const [activeTab, setActiveTab] = useState('Identity');
    const [testInput, setTestInput] = useState('{}');
    const [testResult, setTestResult] = useState(null);
    const [testing, setTesting] = useState(false);

    const load = useCallback(async () => {
        const toolsRes = await api.get('/v1/tools');
        setToolCatalog((toolsRes.data.tools || []).filter((t) => t.status === 'active'));
        if (routeAgentId) {
            const res = await api.get(`/v1/agent-builder/agents/${routeAgentId}`);
            setDefinition(res.data.definition);
            const v = res.data.version || {};
            setForm({
                name: res.data.definition.name, description: res.data.definition.description,
                category: res.data.definition.category,
                system_instructions: v.system_instructions || { template: '', variables: [] },
                llm_config: v.llm_config || { provider: 'openai', model: '', temperature: 0.2, max_tokens: 1500 },
                tools: v.tools || [], knowledge_config: v.knowledge_config || { enabled: false, source: 'none' },
                memory_config: v.memory_config || { stm_enabled: true, ltm_enabled: false },
                guardrails: v.guardrails || { max_iterations: 6, max_execution_seconds: 120, confidence_threshold: 0 },
            });
        }
    }, [api, routeAgentId]);

    useEffect(() => { load(); }, [load]);

    const isRasedWrapper = definition?.is_rased_wrapper;

    const ensureAgent = useCallback(async () => {
        if (agentId) return agentId;
        const res = await api.post('/v1/agent-builder/agents', { payload: { name: form.name, description: form.description, category: form.category } });
        setAgentId(res.data.definition.agent_id);
        navigate(`/ai/agent-builder/${res.data.definition.agent_id}`, { replace: true });
        return res.data.definition.agent_id;
    }, [agentId, form, api, navigate]);

    const handleSave = useCallback(async () => {
        try {
            const id = await ensureAgent();
            await api.put(`/v1/agent-builder/agents/${id}/draft`, { updates: form });
            toast.success('Draft saved');
        } catch (e) { toast.error(e?.response?.data?.detail || 'Save failed'); }
    }, [ensureAgent, form, api]);

    const handlePublish = useCallback(async () => {
        try {
            const id = await ensureAgent();
            await handleSave();
            const res = await api.post(`/v1/agent-builder/agents/${id}/publish`);
            toast.success(`Published v${res.data.published_version}`);
        } catch (e) { toast.error(e?.response?.data?.detail || 'Publish failed'); }
    }, [ensureAgent, handleSave, api]);

    const runTest = useCallback(async () => {
        setTesting(true);
        try {
            const id = await ensureAgent();
            await handleSave();
            let parsed = {};
            try { parsed = JSON.parse(testInput); } catch (e) { toast.error('Test input must be valid JSON'); setTesting(false); return; }
            const res = await api.post(`/v1/agent-builder/agents/${id}/test`, { input: parsed });
            setTestResult(res.data);
        } catch (e) { toast.error(e?.response?.data?.detail || 'Test failed'); }
        finally { setTesting(false); }
    }, [ensureAgent, handleSave, testInput, api]);

    const toggleTool = (toolId) => {
        setForm((f) => {
            const has = f.tools.some((t) => t.tool_id === toolId);
            return { ...f, tools: has ? f.tools.filter((t) => t.tool_id !== toolId) : [...f.tools, { tool_id: toolId, tool_version: 1 }] };
        });
    };

    return (
        <div className="h-screen flex flex-col bg-[#050810]">
            <div className="border-b border-white/10 px-4 py-2 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <Bot className="w-4 h-4 text-violet-400" />
                    <Input className="h-8 w-56 text-sm bg-muted/30" value={form.name} disabled={isRasedWrapper}
                        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                    {definition && <Badge variant="outline" className="text-[10px]">{definition.status}</Badge>}
                    {isRasedWrapper && <Badge variant="outline" className="text-[10px] text-emerald-300 border-emerald-500/30">RASED — not editable</Badge>}
                </div>
                {!isRasedWrapper && (
                    <div className="flex items-center gap-1.5">
                        <Button size="sm" variant="outline" onClick={handleSave}><Save className="w-3.5 h-3.5 mr-1" />Save</Button>
                        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={handlePublish}><Rocket className="w-3.5 h-3.5 mr-1" />Publish</Button>
                    </div>
                )}
            </div>

            <div className="flex-1 flex min-h-0">
                <div className="w-40 shrink-0 border-r border-white/10 p-2 space-y-1">
                    {TABS.map((tab) => (
                        <button key={tab} onClick={() => setActiveTab(tab)}
                            className={`w-full text-left text-xs px-2 py-1.5 rounded ${activeTab === tab ? 'bg-white/10 text-white' : 'text-white/50 hover:bg-white/5'}`}>
                            {tab}
                        </button>
                    ))}
                </div>

                <div className="flex-1 overflow-y-auto p-4">
                    {activeTab === 'Identity' && (
                        <div className="space-y-3 max-w-lg">
                            <div><Label className="text-xs">Description</Label>
                                <Input className="bg-muted/30" value={form.description} disabled={isRasedWrapper} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} /></div>
                            <div><Label className="text-xs">Category</Label>
                                <Input className="bg-muted/30" value={form.category} disabled={isRasedWrapper} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} /></div>
                        </div>
                    )}

                    {activeTab === 'Instructions' && (
                        <div className="space-y-2 max-w-2xl">
                            <Label className="text-xs">System Instructions</Label>
                            <textarea className="w-full h-64 text-xs bg-muted/30 rounded p-2 border border-white/10 font-mono" disabled={isRasedWrapper}
                                value={form.system_instructions.template}
                                onChange={(e) => setForm((f) => ({ ...f, system_instructions: { ...f.system_instructions, template: e.target.value } }))}
                                placeholder="You are an Elastic observability investigator. Analyze logs, traces and metrics. Never invent telemetry. If evidence is insufficient, state that explicitly. Return evidence, hypotheses and confidence." />
                        </div>
                    )}

                    {activeTab === 'Model' && (
                        <div className="space-y-3 max-w-md">
                            <div><Label className="text-xs">Provider</Label>
                                <Select value={form.llm_config.provider} onValueChange={(v) => setForm((f) => ({ ...f, llm_config: { ...f.llm_config, provider: v } }))}>
                                    <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                                    <SelectContent>{PROVIDERS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs">Model</Label>
                                <Input className="bg-muted/30" value={form.llm_config.model} onChange={(e) => setForm((f) => ({ ...f, llm_config: { ...f.llm_config, model: e.target.value } }))} /></div>
                            <div><Label className="text-xs">Temperature</Label>
                                <Input type="number" step="0.1" className="bg-muted/30" value={form.llm_config.temperature}
                                    onChange={(e) => setForm((f) => ({ ...f, llm_config: { ...f.llm_config, temperature: Number(e.target.value) } }))} /></div>
                            <p className="text-[10px] text-white/40">Secrets/API keys are never stored here — resolved server-side from the platform's configured provider credentials at call time.</p>
                        </div>
                    )}

                    {activeTab === 'Tools' && (
                        <div className="space-y-1 max-w-lg">
                            {toolCatalog.map((t) => (
                                <label key={t.tool_id} className="flex items-center gap-2 text-xs p-1.5 rounded hover:bg-white/5 cursor-pointer">
                                    <input type="checkbox" checked={form.tools.some((x) => x.tool_id === t.tool_id)} onChange={() => toggleTool(t.tool_id)} />
                                    <span className="text-white/80">{t.name}</span>
                                    <Badge variant="outline" className="text-[9px]">{t.risk_tier}</Badge>
                                </label>
                            ))}
                            {toolCatalog.length === 0 && <div className="text-white/40 text-xs">No active tools in the catalog yet — create some in Tool Catalog first.</div>}
                        </div>
                    )}

                    {activeTab === 'Knowledge' && (
                        <div className="space-y-3 max-w-md">
                            <label className="flex items-center gap-2 text-xs">
                                <input type="checkbox" checked={form.knowledge_config.enabled}
                                    onChange={(e) => setForm((f) => ({ ...f, knowledge_config: { ...f.knowledge_config, enabled: e.target.checked } }))} />
                                Enable Knowledge (RAG)
                            </label>
                            {form.knowledge_config.enabled && (
                                <Select value={form.knowledge_config.source} onValueChange={(v) => setForm((f) => ({ ...f, knowledge_config: { ...f.knowledge_config, source: v } }))}>
                                    <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="rag_incidents">Incident history</SelectItem>
                                        <SelectItem value="rag_logs">Logs</SelectItem>
                                    </SelectContent>
                                </Select>
                            )}
                        </div>
                    )}

                    {activeTab === 'Memory' && (
                        <div className="space-y-2 max-w-md text-xs">
                            <label className="flex items-center gap-2"><input type="checkbox" checked={form.memory_config.stm_enabled}
                                onChange={(e) => setForm((f) => ({ ...f, memory_config: { ...f.memory_config, stm_enabled: e.target.checked } }))} />Short-Term Memory</label>
                            <label className="flex items-center gap-2"><input type="checkbox" checked={form.memory_config.ltm_enabled}
                                onChange={(e) => setForm((f) => ({ ...f, memory_config: { ...f.memory_config, ltm_enabled: e.target.checked } }))} />Long-Term Memory</label>
                            <p className="text-[10px] text-white/40">Backed by the platform's existing vector memory store — no separate memory system.</p>
                        </div>
                    )}

                    {activeTab === 'Guardrails' && (
                        <div className="space-y-3 max-w-md">
                            <div><Label className="text-xs">Max iterations</Label>
                                <Input type="number" className="bg-muted/30" value={form.guardrails.max_iterations}
                                    onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, max_iterations: Number(e.target.value) } }))} /></div>
                            <div><Label className="text-xs">Max execution seconds</Label>
                                <Input type="number" className="bg-muted/30" value={form.guardrails.max_execution_seconds}
                                    onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, max_execution_seconds: Number(e.target.value) } }))} /></div>
                            <div><Label className="text-xs">Confidence threshold</Label>
                                <Input type="number" step="0.05" className="bg-muted/30" value={form.guardrails.confidence_threshold}
                                    onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, confidence_threshold: Number(e.target.value) } }))} /></div>
                        </div>
                    )}

                    {activeTab === 'Test' && (
                        <div className="max-w-2xl space-y-3">
                            <Label className="text-xs">Test Input (JSON)</Label>
                            <textarea className="w-full h-24 text-xs bg-muted/30 rounded p-2 border border-white/10 font-mono"
                                value={testInput} onChange={(e) => setTestInput(e.target.value)} />
                            <Button size="sm" onClick={runTest} disabled={testing}><FlaskConical className="w-3.5 h-3.5 mr-1" />{testing ? 'Running…' : 'Test Agent'}</Button>
                            {testResult && (
                                <div className="space-y-2 mt-3">
                                    <div className="text-xs text-white/60">Status: <Badge variant="outline" className="text-[10px]">{testResult.status}</Badge>
                                        {testResult.confidence !== null && testResult.confidence !== undefined && <span className="ml-2">Confidence: {Math.round(testResult.confidence * 100)}%</span>}
                                    </div>
                                    {(testResult.iterations || []).map((it, i) => (
                                        <div key={i} className="text-[11px] border border-white/10 rounded p-2 space-y-1">
                                            <div className="text-white/60">Thought: {it.thought}</div>
                                            {it.action && <div className="text-violet-300">Action: {it.action} {JSON.stringify(it.action_input)}</div>}
                                            {it.observation && <div className="text-white/40">Observation ({it.observation_kind}): {JSON.stringify(it.observation).slice(0, 300)}</div>}
                                            <div className="text-white/30 text-[10px]">{it.latency_ms}ms{it.tokens_input ? ` · ${it.tokens_input}+${it.tokens_output} tokens` : ''}</div>
                                        </div>
                                    ))}
                                    <div className="text-xs text-white/70">Final Output</div>
                                    <pre className="text-[10px] bg-black/30 rounded p-2 overflow-x-auto">{JSON.stringify(testResult.final_output, null, 2)}</pre>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgentBuilderPage;
