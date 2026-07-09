import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Settings, Sparkles, Shield, Network, Activity, RefreshCw,
    Save, Plus, X, Globe, Server, FileText, Clock, Cog,
    AlertCircle, CheckCircle2, History, Edit3, Loader2, Copy,
    Zap, Play, Beaker, Gauge, Lock, XCircle, FileText as FileTextIcon,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const CATEGORY_ICON = {
    AI: Sparkles, AIOps: Activity, Monitoring: Network,
    Reporting: FileText, Commercial: Server, Platform: Globe,
};

// ─────────────────────────────────────────────────────
//  Modules tab
// ─────────────────────────────────────────────────────

const ModulesTab = ({ catalog, config, onChange, busy }) => {
    const grouped = (catalog?.modules || []).reduce((acc, m) => {
        (acc[m.category] = acc[m.category] || []).push(m); return acc;
    }, {});
    const modules = config?.modules || {};

    return (
        <div className="space-y-5">
            {Object.entries(grouped).map(([cat, mods]) => {
                const Icon = CATEGORY_ICON[cat] || Cog;
                return (
                    <Card key={cat} className="bg-[#0a0a0a] border-white/10">
                        <CardHeader className="py-3">
                            <CardTitle className="flex items-center gap-2 text-sm">
                                <Icon className="w-4 h-4 text-[#F5B841]" />
                                {cat}
                                <Badge variant="outline" className="ml-2 text-[10px] border-white/20 text-white/60">
                                    {mods.filter(m => modules[m.key]).length} / {mods.length} on
                                </Badge>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0">
                            <div className="grid sm:grid-cols-2 gap-2">
                                {mods.map(m => (
                                    <div key={m.key} className="flex items-center justify-between p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                                        <div className="min-w-0 flex-1">
                                            <div className="text-sm text-white">{m.label}</div>
                                            <code className="text-[10px] text-white/30">{m.key}</code>
                                        </div>
                                        <Switch
                                            checked={!!modules[m.key]}
                                            onCheckedChange={(v) => onChange({ modules: { [m.key]: v } })}
                                            disabled={busy}
                                            data-testid={`module-${m.key}`}
                                        />
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
};

// ─────────────────────────────────────────────────────
//  AI Copilot tab
// ─────────────────────────────────────────────────────

const AICopilotTab = ({ catalog, config, onChange, busy }) => {
    const ai = config?.ai_copilot || {};
    const [draft, setDraft] = useState({ ...ai });
    const [llmHealth, setLlmHealth] = useState(null);
    const [llmTest, setLlmTest] = useState({ busy: false, result: null });
    useEffect(() => { setDraft({ ...ai }); }, [ai.system_prompt, ai.model, ai.max_history_turns, ai.provider, ai.ollama_base_url]);

    useEffect(() => {
        fetch(`${API}/api/admin/llm/health`, { headers: headers() })
            .then(r => r.ok ? r.json() : null)
            .then(setLlmHealth)
            .catch(() => {});
    }, [config?.ai_copilot?.provider]);

    const dirty = JSON.stringify(draft) !== JSON.stringify(ai);
    const PROVIDERS = [
        { id: 'ollama',     label: 'Ollama (local, free)', desc: 'Self-hosted, runs on your server, zero API cost' },
        { id: 'openai',     label: 'OpenAI',               desc: 'Bring your own OPENAI_API_KEY' },
        { id: 'anthropic',  label: 'Anthropic',            desc: 'Bring your own ANTHROPIC_API_KEY' },
        { id: 'gemini',     label: 'Google Gemini',        desc: 'Bring your own GOOGLE_API_KEY' },
        { id: 'emergent',   label: 'Emergent Universal',   desc: 'Credit-based, supports Claude/GPT/Gemini' },
        { id: 'rule_based', label: 'Rule-based (no LLM)',  desc: 'Fallback parser — handles simple monitor requests' },
    ];

    const modelsForProvider = (catalog?.models || []).filter(m => !draft.provider || m.provider === draft.provider);

    const save = () => {
        const updates = {};
        ['system_prompt', 'provider', 'model', 'ollama_base_url'].forEach(k => {
            if (draft[k] !== ai[k]) updates[k] = draft[k];
        });
        if (Number(draft.max_history_turns) !== Number(ai.max_history_turns)) {
            updates.max_history_turns = Number(draft.max_history_turns);
        }
        if (Object.keys(updates).length) onChange({ ai_copilot: updates });
    };

    const runLlmTest = async () => {
        setLlmTest({ busy: true, result: null });
        try {
            const r = await fetch(`${API}/api/admin/llm/test`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ message: 'Say hello in one short sentence.' }),
            });
            const d = await r.json();
            setLlmTest({ busy: false, result: r.ok ? d : { error: d.detail || 'Failed' } });
        } catch (e) {
            setLlmTest({ busy: false, result: { error: e.message } });
        }
    };

    const providerStatus = (id) => {
        if (!llmHealth) return null;
        const p = llmHealth.providers?.[id] || {};
        if (id === 'ollama') return p.reachable ? 'reachable' : 'offline';
        if (id === 'rule_based') return 'always available';
        return p.key_set ? 'key set' : 'no key';
    };

    return (
        <div className="space-y-4">
            {/* Provider status banner */}
            {llmHealth && (
                <div className={`p-3 rounded-lg border ${
                    llmHealth.configured
                        ? 'bg-emerald-500/[0.04] border-emerald-500/30'
                        : 'bg-amber-500/[0.06] border-amber-500/30'
                }`}>
                    <div className="flex items-center gap-2 text-xs">
                        <Sparkles className="w-3.5 h-3.5 text-[#F5B841]" />
                        <span className="text-white">Active provider:</span>
                        <code className="text-[#F5B841] font-bold">{llmHealth.active_provider}</code>
                        {llmHealth.active_model && <code className="text-white/50">· {llmHealth.active_model}</code>}
                        <Button size="sm" variant="ghost" onClick={runLlmTest} disabled={llmTest.busy}
                                className="ml-auto text-cyan-400 hover:bg-cyan-500/10 h-7 text-xs"
                                data-testid="llm-test-btn">
                            {llmTest.busy ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Beaker className="w-3 h-3 mr-1" />}
                            Ping LLM
                        </Button>
                    </div>
                    {llmTest.result && (
                        <div className="mt-2 p-2 bg-black/40 rounded text-[11px] text-white/70 font-mono">
                            {llmTest.result.error ? (
                                <span className="text-red-400">{llmTest.result.error}</span>
                            ) : (
                                <>
                                    <span className="text-emerald-400">✓ {llmTest.result.provider} responded:</span>{' '}
                                    <span>{llmTest.result.response?.slice(0, 200)}</span>
                                    {llmTest.result.fallback_used && <Badge className="ml-2 text-[9px] bg-amber-500/20 text-amber-300 border-amber-500/30">fallback</Badge>}
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            <Card className="bg-[#0a0a0a] border-white/10">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                        <Sparkles className="w-4 h-4 text-[#F5B841]" />
                        AI Copilot Configuration
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Pick a provider, edit the live system prompt, tune history depth. Changes apply on the next chat message.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Provider picker */}
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">LLM Provider</Label>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {PROVIDERS.map(p => {
                                const status = providerStatus(p.id);
                                const isActive = (draft.provider || '').toLowerCase() === p.id;
                                const statusColor = status === 'reachable' || status === 'key set' || status === 'always available'
                                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                    : 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30';
                                return (
                                    <label
                                        key={p.id}
                                        className={`p-3 rounded-lg border cursor-pointer transition ${
                                            isActive
                                                ? 'bg-[#F5B841]/[0.08] border-[#F5B841]/40'
                                                : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.04]'
                                        }`}>
                                        <div className="flex items-start gap-2">
                                            <input
                                                type="radio" name="llm-provider"
                                                checked={isActive}
                                                onChange={() => setDraft({ ...draft, provider: p.id, model: '' })}
                                                data-testid={`provider-${p.id}`}
                                                className="mt-1 shrink-0"
                                            />
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-white">{p.label}</span>
                                                    {status && <Badge variant="outline" className={`text-[9px] ${statusColor}`}>{status}</Badge>}
                                                </div>
                                                <p className="text-[11px] text-white/40 mt-0.5">{p.desc}</p>
                                            </div>
                                        </div>
                                    </label>
                                );
                            })}
                        </div>
                    </div>

                    {/* Conditional fields */}
                    {draft.provider === 'ollama' && (
                        <div className="space-y-1 p-3 bg-cyan-500/[0.04] border border-cyan-500/25 rounded-lg">
                            <Label className="text-xs text-white/60">Ollama Base URL</Label>
                            <Input value={draft.ollama_base_url || ''}
                                   onChange={(e) => setDraft({ ...draft, ollama_base_url: e.target.value })}
                                   placeholder="http://localhost:11434"
                                   className="bg-black/40 border-white/10 h-9 text-sm"
                                   data-testid="ollama-url-input" />
                            <p className="text-[10px] text-white/40 mt-1">
                                Run <code>ollama pull llama3.1:8b</code> on the host first, or use a different model below.
                            </p>
                        </div>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <Label className="text-xs text-white/60">Model {draft.provider === 'rule_based' && '(N/A in rule-based mode)'}</Label>
                            <Select
                                value={draft.model || '__default__'}
                                onValueChange={(v) => setDraft({ ...draft, model: v === '__default__' ? '' : v })}
                                disabled={draft.provider === 'rule_based'}
                            >
                                <SelectTrigger className="bg-black/40 border-white/10 h-9 text-sm" data-testid="ai-model-select">
                                    <SelectValue placeholder="— provider default —" />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0a0a0a] border-white/10 text-white">
                                    <SelectItem value="__default__" className="text-white/70">— provider default —</SelectItem>
                                    {modelsForProvider.map(m => (
                                        <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1">
                            <Label className="text-xs text-white/60">Max History Turns</Label>
                            <Input
                                type="number" min={2} max={100}
                                value={draft.max_history_turns || 20}
                                onChange={(e) => setDraft({ ...draft, max_history_turns: e.target.value })}
                                className="bg-black/40 border-white/10 h-9 text-sm"
                                data-testid="ai-max-history-input"
                            />
                        </div>
                    </div>
                    <div className="space-y-1">
                        <div className="flex items-center justify-between">
                            <Label className="text-xs text-white/60">System Prompt</Label>
                            <span className="text-[10px] text-white/30">{(draft.system_prompt || '').length} chars</span>
                        </div>
                        <Textarea
                            value={draft.system_prompt || ''}
                            onChange={(e) => setDraft({ ...draft, system_prompt: e.target.value })}
                            className="bg-black/60 border-white/10 text-xs font-mono min-h-[240px]"
                            placeholder="Describe how the AI Copilot should behave..."
                            data-testid="ai-system-prompt-textarea"
                        />
                    </div>
                    <div className="flex items-center justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => setDraft({ ...ai })}
                                disabled={!dirty || busy} className="border-white/10 text-white/70">
                            <X className="w-3.5 h-3.5 mr-1.5" /> Discard
                        </Button>
                        <Button size="sm" onClick={save} disabled={!dirty || busy}
                                className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                data-testid="ai-save-btn">
                            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                            Save Changes
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

// ─────────────────────────────────────────────────────
//  Deny patterns tab
// ─────────────────────────────────────────────────────

const DenyPatternsTab = ({ config, onChange, busy }) => {
    const patterns = config?.deny_patterns || [];
    const [draft, setDraft] = useState([...patterns]);
    const [newP, setNewP] = useState('');
    useEffect(() => { setDraft([...patterns]); }, [patterns.join('|')]);

    const dirty = JSON.stringify(draft) !== JSON.stringify(patterns);
    const add = () => {
        const t = newP.trim();
        if (!t) return;
        if (draft.some(d => d.toLowerCase() === t.toLowerCase())) {
            toast.error('Already in list');
            return;
        }
        setDraft([...draft, t]); setNewP('');
    };
    const remove = (i) => setDraft(draft.filter((_, idx) => idx !== i));

    return (
        <Card className="bg-[#0a0a0a] border-white/10">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                    <Shield className="w-4 h-4 text-[#F5B841]" />
                    Safe-Default Deny Patterns
                </CardTitle>
                <CardDescription className="text-xs">
                    Strings that — if found in any monitor's response body — automatically mark it as <strong>down</strong>.
                    Catches HTTP-200-with-error-body false-positives. Applied to all new monitors when <code>apply_safe_defaults=true</code>.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                    <Input
                        value={newP} onChange={(e) => setNewP(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
                        placeholder="e.g. database connection failed"
                        className="bg-black/40 border-white/10 text-sm"
                        data-testid="deny-pattern-input"
                    />
                    <Button size="sm" onClick={add} disabled={busy || !newP.trim()}
                            className="bg-emerald-500 hover:bg-emerald-500/90 text-black font-semibold"
                            data-testid="deny-pattern-add-btn">
                        <Plus className="w-3.5 h-3.5 mr-1" /> Add
                    </Button>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-72 overflow-y-auto p-2 bg-black/30 rounded border border-white/5">
                    {draft.length === 0 && <p className="text-xs text-white/40">No patterns defined</p>}
                    {draft.map((p, i) => (
                        <Badge key={i} className="bg-red-500/10 text-red-300 border border-red-500/30 hover:bg-red-500/20 group cursor-default font-mono text-[11px] py-1 px-2">
                            {p}
                            <X className="w-3 h-3 ml-1.5 cursor-pointer opacity-50 group-hover:opacity-100"
                                onClick={() => remove(i)} data-testid={`deny-remove-${i}`} />
                        </Badge>
                    ))}
                </div>
                <div className="flex items-center justify-between text-[11px] text-white/40">
                    <span>{draft.length} pattern(s) — {draft.length - patterns.length > 0 ? `+${draft.length - patterns.length}` : draft.length - patterns.length} change</span>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => setDraft([...patterns])}
                                disabled={!dirty || busy} className="border-white/10 text-white/70 h-7 text-xs">
                            Reset
                        </Button>
                        <Button size="sm" onClick={() => onChange({ deny_patterns: draft })}
                                disabled={!dirty || busy}
                                className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold h-7 text-xs"
                                data-testid="deny-save-btn">
                            {busy ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                            Save
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

// ─────────────────────────────────────────────────────
//  Tenant Routing tab
// ─────────────────────────────────────────────────────

const RoutingTab = ({ tenants, onUpdate, onShowDns, busy }) => {
    const [drafts, setDrafts] = useState({});
    const setDraft = (id, k, v) => setDrafts(s => ({ ...s, [id]: { ...(s[id] || {}), [k]: v } }));

    return (
        <div className="space-y-4">
            <div className="p-3 bg-cyan-500/[0.04] border border-cyan-500/25 rounded-lg flex items-start gap-2">
                <Globe className="w-4 h-4 text-cyan-400 mt-0.5" />
                <div className="text-xs text-cyan-400/80">
                    Each tenant gets <strong>three URL forms</strong>: subdomain (e.g. <code>fasah.falconops.ai</code>),
                    custom vanity domain (e.g. <code>monitor.fasah.com</code>), and path-prefix (<code>/t/fasah</code>).
                    Path-prefix works without DNS changes; the others require CNAMEs.
                </div>
            </div>

            {(tenants || []).map(t => {
                const draft = { ...t, ...(drafts[t.id] || {}) };
                const dirty = JSON.stringify(draft) !== JSON.stringify({ ...t, ...(drafts[t.id] || {}), ...t });
                const changed = Object.keys(drafts[t.id] || {}).length > 0;
                return (
                    <Card key={t.id} className="bg-[#0a0a0a] border-white/10" data-testid={`tenant-card-${t.id}`}>
                        <CardHeader className="py-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2 text-sm">
                                    <Server className="w-4 h-4 text-[#F5B841]" />
                                    {t.name}
                                    {!t.routing_enabled && <Badge variant="outline" className="text-[10px] border-zinc-500/30 text-zinc-400">disabled</Badge>}
                                </CardTitle>
                                <div className="flex items-center gap-2">
                                    <Switch
                                        checked={draft.routing_enabled !== false}
                                        onCheckedChange={(v) => setDraft(t.id, 'routing_enabled', v)}
                                        data-testid={`tenant-routing-toggle-${t.id}`}
                                    />
                                    <Button variant="ghost" size="sm" onClick={() => onShowDns(t.id)}
                                            className="text-cyan-400 hover:bg-cyan-500/10 text-xs"
                                            data-testid={`tenant-dns-btn-${t.id}`}>
                                        <Network className="w-3.5 h-3.5 mr-1.5" /> DNS Records
                                    </Button>
                                </div>
                            </div>
                            <CardDescription className="text-[11px]">slug · <code className="text-white/60">{t.slug || '—'}</code></CardDescription>
                        </CardHeader>
                        <CardContent className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                            <div className="space-y-1">
                                <Label className="text-xs text-white/60">Subdomain</Label>
                                <Input
                                    value={draft.subdomain || ''}
                                    onChange={(e) => setDraft(t.id, 'subdomain', e.target.value)}
                                    placeholder="fasah"
                                    className="bg-black/40 border-white/10 h-8 text-xs"
                                    data-testid={`tenant-subdomain-${t.id}`}
                                />
                                <p className="text-[10px] text-white/30 truncate">→ https://{draft.subdomain || '<sub>'}.{draft.base_domain || 'falconops.ai'}</p>
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs text-white/60">Custom Domain</Label>
                                <Input
                                    value={draft.custom_domain || ''}
                                    onChange={(e) => setDraft(t.id, 'custom_domain', e.target.value)}
                                    placeholder="monitor.fasah.com"
                                    className="bg-black/40 border-white/10 h-8 text-xs"
                                    data-testid={`tenant-customdomain-${t.id}`}
                                />
                                <p className="text-[10px] text-white/30 truncate">→ https://{draft.custom_domain || '<your-domain>'}</p>
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs text-white/60">Base Domain (for subdomain)</Label>
                                <Input
                                    value={draft.base_domain || ''}
                                    onChange={(e) => setDraft(t.id, 'base_domain', e.target.value)}
                                    placeholder="falconops.ai"
                                    className="bg-black/40 border-white/10 h-8 text-xs"
                                    data-testid={`tenant-basedomain-${t.id}`}
                                />
                                <p className="text-[10px] text-white/30 truncate">Path-prefix: /t/{t.slug || draft.subdomain || '<slug>'}</p>
                            </div>
                            <div className="lg:col-span-3 flex items-center justify-end gap-2 pt-1">
                                <Button variant="outline" size="sm" disabled={!changed || busy}
                                        onClick={() => setDrafts(s => { const c = { ...s }; delete c[t.id]; return c; })}
                                        className="border-white/10 text-white/70 h-7 text-xs">
                                    <X className="w-3 h-3 mr-1" /> Discard
                                </Button>
                                <Button size="sm" disabled={!changed || busy}
                                        onClick={() => onUpdate(t.id, drafts[t.id] || {})}
                                        className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold h-7 text-xs"
                                        data-testid={`tenant-save-${t.id}`}>
                                    {busy ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                                    Save Routing
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}

            {(!tenants || tenants.length === 0) && (
                <p className="text-center text-sm text-white/40 py-12">No tenants found.</p>
            )}
        </div>
    );
};

// ─────────────────────────────────────────────────────
//  Audit Log tab
// ─────────────────────────────────────────────────────

const AuditLogTab = ({ entries }) => (
    <Card className="bg-[#0a0a0a] border-white/10">
        <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
                <History className="w-4 h-4 text-[#F5B841]" />
                Configuration Audit Log
                <Badge variant="outline" className="text-[10px] border-white/20 text-white/60 ml-2">
                    {entries?.length || 0} entries
                </Badge>
            </CardTitle>
            <CardDescription className="text-xs">Every change to feature flags, AI prompt, deny patterns and limits.</CardDescription>
        </CardHeader>
        <CardContent>
            <ScrollArea className="h-[500px] pr-2">
                <div className="space-y-2">
                    {(!entries || entries.length === 0) && (
                        <p className="text-xs text-white/40 text-center py-8">No changes yet.</p>
                    )}
                    {(entries || []).map((e) => (
                        <div key={e.id} className="p-3 bg-white/[0.02] border border-white/5 rounded-lg" data-testid={`audit-entry-${e.id}`}>
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                    <span className="text-xs text-white">{e.changed_by}</span>
                                    <Badge variant="outline" className="text-[9px] border-white/15 text-white/50">
                                        {e.diff_count} change{e.diff_count !== 1 ? 's' : ''}
                                    </Badge>
                                </div>
                                <span className="text-[10px] text-white/30">{new Date(e.changed_at).toLocaleString()}</span>
                            </div>
                            <ul className="space-y-1 pl-4 text-[11px] text-white/60">
                                {(e.diffs || []).slice(0, 5).map((d, i) => (
                                    <li key={i} className="flex items-center gap-2">
                                        <Edit3 className="w-2.5 h-2.5 text-white/40" />
                                        <code className="text-cyan-400">{d.section}{d.key ? `.${d.key}` : ''}</code>
                                        {d.from !== undefined && <>
                                            <span className="text-white/30">{String(d.from).slice(0, 30)}</span>
                                            <span className="text-white/20">→</span>
                                            <span className="text-emerald-400">{String(d.to).slice(0, 30)}</span>
                                        </>}
                                        {d.added !== undefined && <span className="text-emerald-400">+{(d.added || []).length} added</span>}
                                        {d.removed !== undefined && <span className="text-red-400">-{(d.removed || []).length} removed</span>}
                                    </li>
                                ))}
                                {(e.diffs || []).length > 5 && (
                                    <li className="text-white/30">+ {(e.diffs.length - 5)} more…</li>
                                )}
                            </ul>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </CardContent>
    </Card>
);

// ─────────────────────────────────────────────────────
//  DNS Records modal (inline panel)
// ─────────────────────────────────────────────────────

const DnsModal = ({ data, onClose }) => {
    if (!data) return null;
    const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success('Copied'); };
    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
            <Card className="bg-[#0a0a0a] border-white/10 max-w-2xl w-full max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Network className="w-4 h-4 text-[#F5B841]" /> DNS Records — {data.tenant_name}
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Add these records at your DNS provider (Route 53 / Cloudflare / GoDaddy / etc).
                        After propagation (~5 min), the URLs below will resolve.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    {(data.records || []).map((r, i) => (
                        r.type === 'INFO' ? (
                            <div key={i} className="p-3 bg-amber-500/[0.06] border border-amber-500/30 rounded-lg text-xs text-amber-300">
                                {r.message}
                                {r.path_prefix_url && (
                                    <div className="mt-2 flex items-center gap-2">
                                        <code className="bg-black/40 px-2 py-1 rounded text-amber-200">{r.path_prefix_url}</code>
                                        <Copy className="w-3 h-3 cursor-pointer text-white/40 hover:text-white/70" onClick={() => copy(r.path_prefix_url)} />
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div key={i} className="p-3 bg-white/[0.02] border border-white/10 rounded-lg space-y-1.5 text-[12px] font-mono">
                                <div className="flex items-center gap-2">
                                    <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/30 text-[10px]">{r.type}</Badge>
                                    <span className="text-white/50 ml-auto text-[10px]">TTL {r.ttl}s</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-white/40 w-12 text-[10px]">Host</span>
                                    <code className="bg-black/40 px-2 py-1 rounded text-emerald-300 flex-1">{r.host}</code>
                                    <Copy className="w-3 h-3 cursor-pointer text-white/40 hover:text-white/70" onClick={() => copy(r.host)} />
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-white/40 w-12 text-[10px]">Value</span>
                                    <code className="bg-black/40 px-2 py-1 rounded text-white/70 flex-1">{r.value}</code>
                                    <Copy className="w-3 h-3 cursor-pointer text-white/40 hover:text-white/70" onClick={() => copy(r.value)} />
                                </div>
                                <p className="text-[10px] text-white/40 pt-1">{r.purpose}</p>
                            </div>
                        )
                    ))}

                    {data.urls && (
                        <div className="p-3 bg-emerald-500/[0.04] border border-emerald-500/25 rounded-lg space-y-1">
                            <div className="text-[10px] uppercase tracking-widest text-emerald-400/70 mb-1">Reachable URLs (after DNS propagation)</div>
                            {Object.entries(data.urls).map(([k, v]) => (
                                <div key={k} className="flex items-center gap-2 text-[11px]">
                                    <span className="text-emerald-400/60 w-32 capitalize">{k.replace(/_/g, ' ')}</span>
                                    <code className="text-emerald-300 flex-1 truncate">{v}</code>
                                    <Copy className="w-3 h-3 cursor-pointer text-white/40 hover:text-white/70" onClick={() => copy(v)} />
                                </div>
                            ))}
                        </div>
                    )}

                    {data.verify_command && (
                        <div className="p-3 bg-black/60 rounded-lg">
                            <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Verify command</div>
                            <code className="block text-[11px] text-cyan-300 font-mono break-all">{data.verify_command}</code>
                        </div>
                    )}

                    <div className="flex justify-end pt-2">
                        <Button onClick={onClose} className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold">
                            Close
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

// ─────────────────────────────────────────────────────
//  Limits + Auto-Action Allowlist tab
// ─────────────────────────────────────────────────────

const LimitsTab = ({ config, onChange, busy }) => {
    const limits = config?.limits || {};
    const [draft, setDraft] = useState({ ...limits });
    useEffect(() => { setDraft({ ...limits }); }, [JSON.stringify(limits)]);
    const dirty = JSON.stringify(draft) !== JSON.stringify(limits);

    const setField = (k, v) => setDraft({ ...draft, [k]: v });
    const allowlist = draft.auto_action_allowlist || [];

    const KNOWN_ACTIONS = [
        { kind: 'alert_ack', risk: 'low' },
        { kind: 'lower_check_interval', risk: 'low' },
        { kind: 'deduplicate_monitors', risk: 'low' },
        { kind: 'rotate_certificate', risk: 'medium' },
        { kind: 'scale_down', risk: 'medium' },
        { kind: 'scale_up', risk: 'medium' },
        { kind: 'restart_service', risk: 'high' },
        { kind: 'block_potential_threat', risk: 'high' },
    ];

    return (
        <Card className="bg-[#0a0a0a] border-white/10">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                    <Cog className="w-4 h-4 text-[#F5B841]" /> Platform Limits & Auto-Action Allowlist
                </CardTitle>
                <CardDescription className="text-xs">
                    Default check intervals, retention, response-time SLAs, and which agent-proposed actions can run without admin approval.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Default check interval (sec)</Label>
                        <Input type="number" min={10} value={draft.default_check_interval_sec || 60}
                               onChange={(e) => setField('default_check_interval_sec', Number(e.target.value))}
                               className="bg-black/40 border-white/10 h-9 text-sm"
                               data-testid="limits-interval" />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Default check timeout (sec)</Label>
                        <Input type="number" min={1} value={draft.default_check_timeout_sec || 10}
                               onChange={(e) => setField('default_check_timeout_sec', Number(e.target.value))}
                               className="bg-black/40 border-white/10 h-9 text-sm"
                               data-testid="limits-timeout" />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Default response-time SLA (ms)</Label>
                        <Input type="number" min={100} value={draft.max_response_time_ms_default || 5000}
                               onChange={(e) => setField('max_response_time_ms_default', Number(e.target.value))}
                               className="bg-black/40 border-white/10 h-9 text-sm"
                               data-testid="limits-rt-sla" />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Alert cooldown (min)</Label>
                        <Input type="number" min={0} value={draft.alert_cooldown_min || 5}
                               onChange={(e) => setField('alert_cooldown_min', Number(e.target.value))}
                               className="bg-black/40 border-white/10 h-9 text-sm"
                               data-testid="limits-cooldown" />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Max retention (days)</Label>
                        <Input type="number" min={7} value={draft.max_retention_days || 90}
                               onChange={(e) => setField('max_retention_days', Number(e.target.value))}
                               className="bg-black/40 border-white/10 h-9 text-sm"
                               data-testid="limits-retention" />
                    </div>
                </div>

                {/* Auto-Action Allowlist */}
                <div className="pt-3 border-t border-white/10">
                    <div className="flex items-center gap-2 mb-2">
                        <Zap className="w-3.5 h-3.5 text-emerald-400" />
                        <Label className="text-sm text-white">Auto-Action Allowlist</Label>
                        <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400 ml-2">
                            Actions in this list run WITHOUT admin approval
                        </Badge>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {KNOWN_ACTIONS.map(a => {
                            const checked = allowlist.includes(a.kind);
                            const disabledByRisk = a.risk === 'high';
                            return (
                                <label key={a.kind}
                                       className={`flex items-center justify-between p-2.5 rounded-lg border ${
                                           checked
                                               ? 'bg-emerald-500/[0.06] border-emerald-500/30'
                                               : 'bg-white/[0.02] border-white/5'
                                       } ${disabledByRisk ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={checked}
                                            disabled={disabledByRisk}
                                            onChange={(e) => {
                                                const next = e.target.checked
                                                    ? [...allowlist, a.kind]
                                                    : allowlist.filter(x => x !== a.kind);
                                                setField('auto_action_allowlist', next);
                                            }}
                                            data-testid={`allow-${a.kind}`}
                                        />
                                        <code className="text-xs text-white/80">{a.kind}</code>
                                    </div>
                                    <Badge className={`text-[9px] ${
                                        a.risk === 'low' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' :
                                        a.risk === 'medium' ? 'bg-amber-500/15 text-amber-300 border-amber-500/30' :
                                        'bg-red-500/15 text-red-300 border-red-500/30'}`}>
                                        {a.risk}
                                    </Badge>
                                </label>
                            );
                        })}
                    </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-1">
                    <Button variant="outline" size="sm" onClick={() => setDraft({ ...limits })}
                            disabled={!dirty || busy} className="border-white/10 text-white/70">
                        <X className="w-3.5 h-3.5 mr-1.5" /> Discard
                    </Button>
                    <Button size="sm" onClick={() => onChange({ limits: draft })}
                            disabled={!dirty || busy}
                            className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                            data-testid="limits-save-btn">
                        {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                        Save Limits
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
};

// ─────────────────────────────────────────────────────
//  Testers tab
// ─────────────────────────────────────────────────────

const TestersTab = ({ tenants, onShowDns }) => {
    const [bodyText, setBodyText] = useState('Internal Server Error: Traceback (most recent call last)...\nFile "x.py" line 42, in handler');
    const [bodyResult, setBodyResult] = useState(null);
    const [bodyBusy, setBodyBusy] = useState(false);

    const [promptText, setPromptText] = useState('Monitor https://api.example.com/health every 60s and alert on any 5xx error');
    const [promptResult, setPromptResult] = useState(null);
    const [promptBusy, setPromptBusy] = useState(false);

    const [routingResults, setRoutingResults] = useState({}); // tenantId+method → result
    const [routingBusy, setRoutingBusy] = useState(null);

    const testPattern = async () => {
        setBodyBusy(true);
        try {
            const r = await fetch(`${API}/api/admin/test/deny-patterns`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ body: bodyText }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Test failed');
            setBodyResult(d);
        } catch (e) { toast.error(e.message); } finally { setBodyBusy(false); }
    };

    const testPrompt = async () => {
        setPromptBusy(true);
        try {
            const r = await fetch(`${API}/api/admin/test/ai-prompt`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ sample_message: promptText }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Test failed');
            setPromptResult(d);
        } catch (e) { toast.error(e.message); } finally { setPromptBusy(false); }
    };

    const testRouting = async (tid, method) => {
        const key = `${tid}:${method}`;
        setRoutingBusy(key);
        try {
            const r = await fetch(`${API}/api/admin/test/tenant-routing/${tid}`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ method }),
            });
            const d = await r.json();
            setRoutingResults({ ...routingResults, [key]: d });
        } catch (e) { toast.error(e.message); } finally { setRoutingBusy(null); }
    };

    return (
        <div className="space-y-4">
            {/* Pattern Tester */}
            <Card className="bg-[#0a0a0a] border-white/10">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-sm">
                        <Shield className="w-4 h-4 text-[#F5B841]" /> Deny Pattern Tester
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Paste a response body to see exactly which deny patterns would mark a monitor as down.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                    <Textarea
                        value={bodyText} onChange={(e) => setBodyText(e.target.value)}
                        className="bg-black/60 border-white/10 text-xs font-mono min-h-[120px]"
                        placeholder='Paste a response body here...'
                        data-testid="tester-body-input"
                    />
                    <div className="flex justify-end">
                        <Button onClick={testPattern} disabled={bodyBusy || !bodyText.trim()}
                                size="sm" className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                data-testid="tester-pattern-run">
                            {bodyBusy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Activity className="w-3.5 h-3.5 mr-1.5" />}
                            Run Test
                        </Button>
                    </div>
                    {bodyResult && (
                        <div className={`p-3 rounded-lg border ${
                            bodyResult.verdict === 'PASS'
                                ? 'bg-emerald-500/[0.06] border-emerald-500/30'
                                : 'bg-red-500/[0.06] border-red-500/30'
                        }`} data-testid="tester-pattern-result">
                            <div className="flex items-center gap-2 mb-2">
                                <Badge className={bodyResult.verdict === 'PASS'
                                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                    : 'bg-red-500/20 text-red-300 border-red-500/30'}>
                                    {bodyResult.verdict}
                                </Badge>
                                <span className="text-xs text-white/70">
                                    {bodyResult.matches_count} / {bodyResult.patterns_tested} pattern(s) matched
                                </span>
                            </div>
                            {bodyResult.matches?.length > 0 && (
                                <ul className="space-y-1 mt-2">
                                    {bodyResult.matches.slice(0, 5).map((m, i) => (
                                        <li key={i} className="text-[11px] font-mono">
                                            <code className="text-red-300">{m.pattern}</code>
                                            <div className="text-white/50 ml-4 italic">…{m.context}…</div>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Prompt Tester */}
            <Card className="bg-[#0a0a0a] border-white/10">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-sm">
                        <Sparkles className="w-4 h-4 text-[#F5B841]" /> AI Prompt Tester
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Send a sample question through the AI Copilot using the currently-saved system prompt.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                    <Input value={promptText} onChange={(e) => setPromptText(e.target.value)}
                           className="bg-black/40 border-white/10 text-sm"
                           placeholder="Sample user message..."
                           data-testid="tester-prompt-input" />
                    <div className="flex justify-end">
                        <Button onClick={testPrompt} disabled={promptBusy || !promptText.trim()}
                                size="sm" className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                data-testid="tester-prompt-run">
                            {promptBusy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
                            Send to AI
                        </Button>
                    </div>
                    {promptResult && (
                        <div className="p-3 bg-cyan-500/[0.04] border border-cyan-500/25 rounded-lg" data-testid="tester-prompt-result">
                            <div className="flex items-center gap-2 mb-2">
                                <Badge className="text-[10px] bg-cyan-500/20 text-cyan-300 border-cyan-500/30">
                                    {promptResult.model} · {promptResult.provider}
                                </Badge>
                                <span className="text-[10px] text-white/40">{promptResult.system_prompt_chars} chars in prompt</span>
                            </div>
                            <pre className="text-[11px] text-white/80 whitespace-pre-wrap font-mono bg-black/40 p-3 rounded max-h-72 overflow-y-auto">
                                {promptResult.assistant_response}
                            </pre>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Routing self-test */}
            <Card className="bg-[#0a0a0a] border-white/10">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-sm">
                        <Globe className="w-4 h-4 text-[#F5B841]" /> Tenant Routing Self-Test
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Backend curls itself with the configured Host header / path-prefix to verify the tenant resolution middleware fires correctly. Works in any environment (no DNS needed).
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                    {(tenants || []).length === 0 && (
                        <p className="text-xs text-white/40 text-center py-6">No tenants configured yet.</p>
                    )}
                    {(tenants || []).map(t => (
                        <div key={t.id} className="p-3 bg-white/[0.02] border border-white/5 rounded-lg" data-testid={`routing-test-${t.id}`}>
                            <div className="flex items-center justify-between mb-2">
                                <div className="text-sm text-white">{t.name}</div>
                                <Button size="sm" variant="ghost" onClick={() => onShowDns(t.id)}
                                        className="text-cyan-400 hover:bg-cyan-500/10 text-[10px] h-6">
                                    DNS records
                                </Button>
                            </div>
                            <div className="grid grid-cols-3 gap-2">
                                {['subdomain', 'custom_domain', 'path_prefix'].map(method => {
                                    const k = `${t.id}:${method}`;
                                    const r = routingResults[k];
                                    const valid = (method === 'subdomain' && t.subdomain)
                                        || (method === 'custom_domain' && t.custom_domain)
                                        || (method === 'path_prefix' && (t.slug || t.subdomain));
                                    return (
                                        <div key={method} className="space-y-1">
                                            <Button size="sm" variant="outline"
                                                    onClick={() => testRouting(t.id, method)}
                                                    disabled={!valid || routingBusy === k}
                                                    className="w-full border-white/10 text-white/70 text-[10px] h-7 capitalize"
                                                    data-testid={`routing-test-${t.id}-${method}`}>
                                                {routingBusy === k
                                                    ? <Loader2 className="w-3 h-3 animate-spin" />
                                                    : <span>Test {method.replace('_', ' ')}</span>}
                                            </Button>
                                            {r && (
                                                <div className={`p-1.5 rounded text-[10px] ${
                                                    r.verdict === 'ok' ? 'bg-emerald-500/[0.06] border border-emerald-500/30 text-emerald-300' :
                                                    r.verdict === 'skipped' ? 'bg-zinc-500/[0.06] border border-zinc-500/30 text-zinc-300' :
                                                    'bg-red-500/[0.06] border border-red-500/30 text-red-300'
                                                }`}>
                                                    <div className="flex items-center gap-1 font-bold uppercase mb-0.5">
                                                        {r.verdict === 'ok' && <CheckCircle2 className="w-3 h-3" />}
                                                        {r.verdict !== 'ok' && <XCircle className="w-3 h-3" />}
                                                        {r.verdict}
                                                    </div>
                                                    {r.observed_slug && <div>slug: {r.observed_slug}</div>}
                                                    {r.http_status && <div>HTTP {r.http_status}</div>}
                                                    {r.reason && <div className="text-[9px] opacity-80">{r.reason}</div>}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    );
};

// ─────────────────────────────────────────────────────
//  Main page
// ─────────────────────────────────────────────────────

export default function AdminControlConsole() {
    const { user } = useAuth();
    const [config, setConfig] = useState(null);
    const [catalog, setCatalog] = useState(null);
    const [audit, setAudit] = useState([]);
    const [tenants, setTenants] = useState([]);
    const [busy, setBusy] = useState(false);
    const [dnsData, setDnsData] = useState(null);
    const [tab, setTab] = useState('modules');

    if (!user || user.role !== 'admin') return <Navigate to="/dashboard" replace />;

    const loadAll = async () => {
        try {
            const [cfg, cat, log, tens] = await Promise.all([
                fetch(`${API}/api/admin/features`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/admin/features/catalog`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/admin/features/audit-log?limit=50`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/admin/tenants/routing`, { headers: headers() }).then(r => r.json()),
            ]);
            setConfig(cfg);
            setCatalog(cat);
            setAudit(log.entries || []);
            setTenants(tens.tenants || []);
        } catch {
            toast.error('Failed to load admin config');
        }
    };

    useEffect(() => { loadAll(); }, []);

    const apply = async (updates) => {
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/admin/features`, {
                method: 'PATCH', headers: headers(), body: JSON.stringify(updates),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Update failed');
            setConfig(d);
            toast.success('Saved');
            loadAll();
        } catch (e) {
            toast.error(e.message || 'Update failed');
        } finally { setBusy(false); }
    };

    const updateTenant = async (tid, updates) => {
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/admin/tenants/${tid}/routing`, {
                method: 'PATCH', headers: headers(), body: JSON.stringify(updates),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Update failed');
            toast.success('Routing updated');
            loadAll();
        } catch (e) {
            toast.error(e.message || 'Update failed');
        } finally { setBusy(false); }
    };

    const showDns = async (tid) => {
        try {
            const r = await fetch(`${API}/api/admin/tenants/${tid}/dns-instructions`, { headers: headers() });
            setDnsData(await r.json());
        } catch { toast.error('Failed to fetch DNS instructions'); }
    };

    if (!config || !catalog) return (
        <div className="p-12 text-center text-white/40 text-sm">
            <Loader2 className="w-5 h-5 mx-auto mb-2 animate-spin" /> Loading admin console…
        </div>
    );

    return (
        <div className="space-y-5" data-testid="admin-control-console">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-gradient-to-br from-[#F5B841]/20 to-amber-500/10 border border-[#F5B841]/30 rounded-lg">
                        <Settings className="w-5 h-5 text-[#F5B841]" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-white">Admin Control Console</h1>
                        <p className="text-xs text-white/50">
                            Live-toggle modules · Edit AI prompt · Tune deny patterns · Per-tenant URL routing · Audit log
                        </p>
                    </div>
                </div>
                <Button variant="ghost" size="sm" onClick={loadAll} className="text-white/60">
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                </Button>
            </div>

            <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="bg-[#0a0a0a] border border-white/10">
                    <TabsTrigger value="modules" data-testid="tab-modules"><Cog className="w-3.5 h-3.5 mr-1.5" /> Modules</TabsTrigger>
                    <TabsTrigger value="ai" data-testid="tab-ai"><Sparkles className="w-3.5 h-3.5 mr-1.5" /> AI Copilot</TabsTrigger>
                    <TabsTrigger value="deny" data-testid="tab-deny"><Shield className="w-3.5 h-3.5 mr-1.5" /> Deny Patterns</TabsTrigger>
                    <TabsTrigger value="limits" data-testid="tab-limits"><Cog className="w-3.5 h-3.5 mr-1.5" /> Limits & Auto-Action</TabsTrigger>
                    <TabsTrigger value="routing" data-testid="tab-routing"><Globe className="w-3.5 h-3.5 mr-1.5" /> Tenant URLs</TabsTrigger>
                    <TabsTrigger value="testers" data-testid="tab-testers"><Activity className="w-3.5 h-3.5 mr-1.5" /> Testers</TabsTrigger>
                    <TabsTrigger value="audit" data-testid="tab-audit"><History className="w-3.5 h-3.5 mr-1.5" /> Audit Log</TabsTrigger>
                </TabsList>

                <TabsContent value="modules" className="mt-4">
                    <ModulesTab catalog={catalog} config={config} onChange={apply} busy={busy} />
                </TabsContent>
                <TabsContent value="ai" className="mt-4">
                    <AICopilotTab catalog={catalog} config={config} onChange={apply} busy={busy} />
                </TabsContent>
                <TabsContent value="deny" className="mt-4">
                    <DenyPatternsTab config={config} onChange={apply} busy={busy} />
                </TabsContent>
                <TabsContent value="limits" className="mt-4">
                    <LimitsTab config={config} onChange={apply} busy={busy} />
                </TabsContent>
                <TabsContent value="routing" className="mt-4">
                    <RoutingTab tenants={tenants} onUpdate={updateTenant} onShowDns={showDns} busy={busy} />
                </TabsContent>
                <TabsContent value="testers" className="mt-4">
                    <TestersTab tenants={tenants} onShowDns={showDns} />
                </TabsContent>
                <TabsContent value="audit" className="mt-4">
                    <AuditLogTab entries={audit} />
                </TabsContent>
            </Tabs>

            <DnsModal data={dnsData} onClose={() => setDnsData(null)} />
        </div>
    );
}
