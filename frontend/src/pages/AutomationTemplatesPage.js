import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Workflow, Download, Copy, ExternalLink, Search, CheckCircle2, Sparkles, BookOpen, Zap,
    Rocket, Settings, RefreshCw, AlertTriangle,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const TEMPLATE_TINT = {
    AppDynamics: 'from-amber-500/[0.08] border-amber-500/30 text-amber-300',
    Elastic:     'from-yellow-500/[0.08] border-yellow-500/30 text-yellow-300',
    PagerDuty:   'from-emerald-500/[0.08] border-emerald-500/30 text-emerald-300',
    Splunk:      'from-violet-500/[0.08] border-violet-500/30 text-violet-300',
    Datadog:     'from-fuchsia-500/[0.08] border-fuchsia-500/30 text-fuchsia-300',
};

const N8nSettingsModal = ({ open, current, onClose, onSaved }) => {
    const [form, setForm] = useState(() => ({
        base_url: current?.base_url || '',
        api_key: '',
        activate_on_import: current?.activate_on_import !== false,
        remediation_webhook_url: current?.remediation_webhook_url || '',
        auto_remediate: current?.auto_remediate === true,
    }));
    const [busy, setBusy] = useState(false);
    const [test, setTest] = useState(null);

    const runTest = async () => {
        if (!form.base_url || !form.api_key) {
            toast.error('Need both base URL and API key to test');
            return;
        }
        setBusy(true);
        setTest(null);
        try {
            const r = await fetch(`${API}/api/automation-templates/n8n/test`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify(form),
            });
            const d = await r.json();
            setTest(d);
            d.ok ? toast.success(`Connected — ${d.workflows_seen} workflows visible`)
                 : toast.error(`Connection failed: ${d.error?.slice(0, 200)}`);
        } catch (e) {
            setTest({ ok: false, error: e.message });
        } finally {
            setBusy(false);
        }
    };

    const save = async () => {
        if (!form.base_url || !form.api_key) {
            toast.error('Both fields are required');
            return;
        }
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/automation-templates/n8n/config`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify(form),
            });
            if (!r.ok) throw new Error((await r.json()).detail || 'save failed');
            toast.success('N8n config saved');
            onSaved && (await onSaved());
            onClose();
        } catch (e) {
            toast.error(e.message?.slice(0, 200) || 'Save failed');
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-lg" data-testid="n8n-settings-modal">
                <DialogHeader>
                    <DialogTitle className="text-white flex items-center gap-2">
                        <Settings className="w-4 h-4 text-violet-300" /> N8n Instance Settings
                    </DialogTitle>
                    <DialogDescription className="text-white/60 text-xs">
                        Configure once → push templates to your N8n instance with one click. Create an API key in N8n at Settings → n8n API → Create API key.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                    {current?.configured && (
                        <div className="p-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/[0.04] text-[11px] text-emerald-200 flex items-center gap-2">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Currently connected to {current.base_url} · key {current.api_key_masked}
                        </div>
                    )}
                    <div>
                        <label className="text-[11px] text-white/60">N8n base URL *</label>
                        <Input
                            value={form.base_url}
                            onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                            placeholder="https://n8n.your-company.com"
                            className="bg-black/40 border-white/10 mt-1"
                            data-testid="n8n-base-url-input"
                        />
                    </div>
                    <div>
                        <label className="text-[11px] text-white/60">API key * <span className="text-white/40">(stored server-side, never echoed back)</span></label>
                        <Input
                            type="password"
                            value={form.api_key}
                            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                            placeholder="Paste your N8n API key"
                            className="bg-black/40 border-white/10 mt-1 font-mono"
                            data-testid="n8n-api-key-input"
                        />
                    </div>
                    <label className="flex items-center gap-2 text-[12px] text-white/70 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={form.activate_on_import}
                            onChange={(e) => setForm({ ...form, activate_on_import: e.target.checked })}
                            data-testid="n8n-activate-toggle"
                        />
                        Activate workflows automatically on import
                    </label>
                    <div className="pt-2 border-t border-white/10">
                        <label className="text-[11px] text-white/60">Remediation webhook URL <span className="text-white/40">(optional — receives AI Log Analyzer remediation triggers)</span></label>
                        <Input
                            value={form.remediation_webhook_url}
                            onChange={(e) => setForm({ ...form, remediation_webhook_url: e.target.value })}
                            placeholder="https://n8n.your-company.com/webhook/falconops-remediate"
                            className="bg-black/40 border-white/10 mt-1"
                            data-testid="n8n-remediation-webhook-input"
                        />
                        <label className="flex items-center gap-2 text-[12px] text-white/70 cursor-pointer mt-2">
                            <input
                                type="checkbox"
                                checked={form.auto_remediate}
                                onChange={(e) => setForm({ ...form, auto_remediate: e.target.checked })}
                                data-testid="n8n-auto-remediate-toggle"
                            />
                            Auto-trigger for Critical/High log verdicts
                        </label>
                    </div>
                    {test && (
                        <div className={`p-2.5 rounded-lg border text-[11px] ${test.ok ? 'border-emerald-500/30 bg-emerald-500/[0.04] text-emerald-200' : 'border-red-500/30 bg-red-500/[0.04] text-red-200'}`}>
                            {test.ok ? (
                                <><CheckCircle2 className="w-3.5 h-3.5 inline mr-1" /> {test.workflows_seen} workflows visible at {test.base_url}</>
                            ) : (
                                <><AlertTriangle className="w-3.5 h-3.5 inline mr-1" /> {test.error || `HTTP ${test.status}`}</>
                            )}
                        </div>
                    )}
                </div>
                <div className="flex items-center gap-2 pt-3 border-t border-white/10">
                    <Button variant="outline" onClick={runTest} disabled={busy} className="border-white/15 text-white/80" data-testid="n8n-test-btn">
                        {busy && !test ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 mr-1.5" />}
                        Test Connection
                    </Button>
                    <div className="flex-1" />
                    <Button variant="outline" onClick={onClose} className="border-white/15 text-white/80">Cancel</Button>
                    <Button onClick={save} disabled={busy} className="bg-violet-500/[0.18] border border-violet-500/40 text-violet-200" data-testid="n8n-save-btn">
                        Save
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default function AutomationTemplatesPage() {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState(null);
    const [detail, setDetail] = useState(null);
    const [n8nCfg, setN8nCfg] = useState({ configured: false });
    const [showN8nSettings, setShowN8nSettings] = useState(false);

    useEffect(() => {
        (async () => {
            try {
                const [r1, r2] = await Promise.all([
                    fetch(`${API}/api/automation-templates/`, { headers: headers() }),
                    fetch(`${API}/api/automation-templates/n8n/config`, { headers: headers() }),
                ]);
                const d = await r1.json();
                setTemplates(d.templates || []);
                if (r2.ok) setN8nCfg(await r2.json());
            } catch {
                toast.error('Failed to load templates');
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const reloadN8nCfg = async () => {
        try {
            const r = await fetch(`${API}/api/automation-templates/n8n/config`, { headers: headers() });
            if (r.ok) setN8nCfg(await r.json());
        } catch { /* ignore */ }
    };

    const pushToN8n = async (t) => {
        if (!n8nCfg?.configured) {
            setShowN8nSettings(true);
            toast.info('Configure your N8n instance first');
            return;
        }
        const toastId = toast.loading(`Pushing ${t.name} to your N8n…`);
        try {
            const r = await fetch(`${API}/api/automation-templates/${t.id}/push-to-n8n`, {
                method: 'POST', headers: headers(),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || JSON.stringify(d));
            toast.success(
                d.activated
                    ? `${t.name} imported & activated in N8n (id ${d.workflow_id})`
                    : `${t.name} imported (id ${d.workflow_id}) — activate manually in N8n UI`,
                { id: toastId, duration: 8000, description: d.webhook_url ? `Webhook: ${d.webhook_url}` : undefined }
            );
        } catch (e) {
            toast.error(`Push failed: ${e.message?.slice(0, 200)}`, { id: toastId });
        }
    };

    const openDetail = async (t) => {
        setSelected(t);
        setDetail(null);
        try {
            const r = await fetch(`${API}/api/automation-templates/${t.id}`, { headers: headers() });
            const d = await r.json();
            setDetail(d);
        } catch {
            toast.error('Failed to load template detail');
        }
    };

    const downloadJson = async (t) => {
        try {
            const r = await fetch(`${API}/api/automation-templates/${t.id}/download`, { headers: headers() });
            if (!r.ok) throw new Error(await r.text());
            const text = await r.text();
            const blob = new Blob([text], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${t.id}.json`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success(`Downloaded ${t.name}.json`);
        } catch (e) {
            toast.error('Download failed');
        }
    };

    const copyJson = async () => {
        if (!detail?.workflow) return;
        try {
            const text = JSON.stringify(detail.workflow, null, 2);
            await navigator.clipboard.writeText(text);
            toast.success('Workflow JSON copied to clipboard');
        } catch {
            toast.error('Copy failed — use Download instead');
        }
    };

    const filtered = templates.filter((t) => {
        if (!search.trim()) return true;
        const q = search.toLowerCase();
        return (
            t.name.toLowerCase().includes(q) ||
            t.source.toLowerCase().includes(q) ||
            (t.tags || []).some((x) => x.toLowerCase().includes(q))
        );
    });

    return (
        <div className="p-6 space-y-5 max-w-7xl" data-testid="automation-templates-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Workflow className="w-6 h-6 text-violet-300" />
                        AI Automation Templates
                    </h1>
                    <p className="text-sm text-white/55 mt-1">
                        One-click N8n workflows that pipe AppDynamics, Elastic, PagerDuty, Splunk, and Datadog into FalconOps&apos; AI brain.
                    </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <div className="relative w-full md:w-72">
                        <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40" />
                        <Input
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search by source, tag, name…"
                            className="pl-8 bg-black/40 border-white/10"
                            data-testid="templates-search"
                        />
                    </div>
                    <Button
                        variant="outline"
                        onClick={() => setShowN8nSettings(true)}
                        className={`border-white/15 ${n8nCfg.configured ? 'text-emerald-300 border-emerald-500/30' : 'text-white/70'}`}
                        data-testid="n8n-settings-btn"
                    >
                        <Settings className="w-4 h-4 mr-1.5" />
                        {n8nCfg.configured ? 'N8n Connected' : 'Configure N8n'}
                    </Button>
                </div>
            </div>

            {/* Intro card */}
            <Card className="bg-gradient-to-br from-violet-500/[0.08] via-black/40 to-black/40 border-violet-500/30">
                <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                        <div className="p-2.5 rounded-lg bg-violet-500/10 border border-violet-500/30 shrink-0">
                            <Sparkles className="w-5 h-5 text-violet-300" />
                        </div>
                        <div className="space-y-1.5 flex-1">
                            <div className="text-sm font-semibold text-violet-100">How this works</div>
                            <p className="text-[13px] text-white/70 leading-relaxed">
                                Each template is a self-contained <strong>N8n workflow</strong> (Webhook → Normalize → POST to FalconOps SOC ingest).
                                Import the JSON into your N8n instance, activate it, and point your source tool at the webhook URL N8n returns.
                                Events flow into FalconOps&apos; AI pipeline within seconds.
                            </p>
                            <p className="text-[11px] text-white/40">
                                Workflows pre-fill <code className="text-white/70">FALCONOPS_URL</code> with this deployment&apos;s URL on download — zero config needed.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Grid */}
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                {loading && (
                    <div className="col-span-full text-center py-12 text-white/40 text-sm">Loading templates…</div>
                )}
                {!loading && filtered.length === 0 && (
                    <div className="col-span-full text-center py-12 text-white/40 text-sm">No templates match your search.</div>
                )}
                {filtered.map((t) => {
                    const tint = TEMPLATE_TINT[t.source] || 'from-cyan-500/[0.08] border-cyan-500/30 text-cyan-300';
                    return (
                        <Card
                            key={t.id}
                            className={`bg-gradient-to-br ${tint.split(' ')[0]} via-black/40 to-black/40 border ${tint.split(' ')[1]} cursor-pointer hover:scale-[1.01] transition-transform`}
                            onClick={() => openDetail(t)}
                            data-testid={`template-${t.id}`}
                        >
                            <CardContent className="p-5 space-y-3">
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <div className="text-sm font-bold text-white">{t.name}</div>
                                        <div className={`text-[10px] uppercase tracking-widest mt-0.5 ${tint.split(' ')[2]}`}>
                                            {t.category} · {t.source}
                                        </div>
                                    </div>
                                    <Badge className="text-[10px] bg-white/5 text-white/70 border border-white/10 shrink-0">
                                        {t.difficulty}
                                    </Badge>
                                </div>
                                <p className="text-[12px] text-white/65 leading-relaxed line-clamp-3">{t.description}</p>
                                <div className="flex items-center gap-1.5 flex-wrap">
                                    {(t.tags || []).slice(0, 4).map((tag) => (
                                        <Badge key={tag} variant="outline" className="text-[9px] border-white/10 text-white/60">
                                            {tag}
                                        </Badge>
                                    ))}
                                </div>
                                <div className="flex items-center gap-2 pt-1 flex-wrap">
                                    <Button
                                        size="sm"
                                        onClick={(e) => { e.stopPropagation(); pushToN8n(t); }}
                                        className="text-[11px] h-7 bg-violet-500/[0.18] border border-violet-500/40 text-violet-200 hover:bg-violet-500/[0.28]"
                                        data-testid={`push-${t.id}`}
                                    >
                                        <Rocket className="w-3.5 h-3.5 mr-1" /> Push to N8n
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={(e) => { e.stopPropagation(); downloadJson(t); }}
                                        className="text-[11px] h-7 border-white/15 text-white/80"
                                        data-testid={`download-${t.id}`}
                                    >
                                        <Download className="w-3.5 h-3.5 mr-1" /> JSON
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={(e) => { e.stopPropagation(); openDetail(t); }}
                                        className="text-[11px] h-7 border-white/15 text-white/80"
                                        data-testid={`detail-${t.id}`}
                                    >
                                        <BookOpen className="w-3.5 h-3.5 mr-1" /> Steps
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {/* Detail modal */}
            <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
                <DialogContent className="max-w-3xl max-h-[88vh] bg-[#0a0a0a] border-white/10 overflow-hidden flex flex-col">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-white">
                            <Workflow className="w-5 h-5 text-violet-300" />
                            {selected?.name}
                        </DialogTitle>
                        <DialogDescription className="text-white/60 text-xs">
                            {selected?.description}
                        </DialogDescription>
                    </DialogHeader>

                    {!detail && (
                        <div className="py-10 text-center text-white/50 text-sm">Loading template…</div>
                    )}

                    {detail && (
                        <Tabs defaultValue="setup" className="flex-1 overflow-hidden flex flex-col">
                            <TabsList className="bg-black/40 border border-white/10">
                                <TabsTrigger value="setup" data-testid="tab-setup">Setup Steps</TabsTrigger>
                                <TabsTrigger value="usecases" data-testid="tab-usecases">Use Cases</TabsTrigger>
                                <TabsTrigger value="json" data-testid="tab-json">N8n Workflow JSON</TabsTrigger>
                            </TabsList>

                            <TabsContent value="setup" className="flex-1 overflow-hidden mt-3">
                                <ScrollArea className="h-[55vh] pr-3">
                                    <ol className="space-y-3">
                                        {detail.setup_steps.map((s, i) => (
                                            <li key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                                <span className="w-6 h-6 rounded-full bg-violet-500/15 border border-violet-500/40 text-violet-300 text-[11px] font-bold flex items-center justify-center shrink-0">
                                                    {i + 1}
                                                </span>
                                                <span className="text-[13px] text-white/85 leading-relaxed">{s}</span>
                                            </li>
                                        ))}
                                    </ol>
                                    <div className="mt-4 p-3 rounded-lg border border-cyan-500/30 bg-cyan-500/[0.04]">
                                        <div className="text-[10px] uppercase tracking-widest text-cyan-300/80 mb-1">
                                            <Zap className="w-3 h-3 inline mr-1" /> Required Env Vars
                                        </div>
                                        <ul className="space-y-1">
                                            {(detail.env_vars || []).map((v, i) => (
                                                <li key={i} className="text-[12px] text-white/80 font-mono">{v}</li>
                                            ))}
                                        </ul>
                                    </div>
                                </ScrollArea>
                            </TabsContent>

                            <TabsContent value="usecases" className="flex-1 overflow-hidden mt-3">
                                <ScrollArea className="h-[55vh] pr-3">
                                    <ul className="space-y-2">
                                        {(detail.use_cases || []).map((u, i) => (
                                            <li key={i} className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/[0.04] border border-emerald-500/20">
                                                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                                                <span className="text-[13px] text-white/85">{u}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </ScrollArea>
                            </TabsContent>

                            <TabsContent value="json" className="flex-1 overflow-hidden mt-3">
                                <ScrollArea className="h-[55vh] pr-3">
                                    <pre className="text-[11px] text-white/85 font-mono whitespace-pre-wrap bg-black/40 p-3 rounded-lg border border-white/10">
                                        {JSON.stringify(detail.workflow, null, 2)}
                                    </pre>
                                </ScrollArea>
                            </TabsContent>
                        </Tabs>
                    )}

                    <div className="flex items-center gap-2 pt-3 border-t border-white/10 mt-3">
                        <Button onClick={() => detail && pushToN8n(detail)} disabled={!detail} className="bg-violet-500/[0.18] border border-violet-500/40 text-violet-200 hover:bg-violet-500/[0.3]" data-testid="modal-push">
                            <Rocket className="w-3.5 h-3.5 mr-1.5" /> Push to N8n
                        </Button>
                        <Button onClick={() => detail && downloadJson(detail)} disabled={!detail} variant="outline" className="border-white/15 text-white/80" data-testid="modal-download">
                            <Download className="w-3.5 h-3.5 mr-1.5" /> Download JSON
                        </Button>
                        <Button onClick={copyJson} disabled={!detail} variant="outline" className="border-white/15 text-white/80" data-testid="modal-copy">
                            <Copy className="w-3.5 h-3.5 mr-1.5" /> Copy
                        </Button>
                        <div className="flex-1" />
                        <a href="https://n8n.io" target="_blank" rel="noreferrer" className="text-[11px] text-cyan-300 hover:underline flex items-center gap-1">
                            n8n.io <ExternalLink className="w-3 h-3" />
                        </a>
                    </div>
                </DialogContent>
            </Dialog>

            <N8nSettingsModal
                key={`n8n-modal-${showN8nSettings}-${n8nCfg?.base_url || ''}`}
                open={showN8nSettings}
                current={n8nCfg}
                onClose={() => setShowN8nSettings(false)}
                onSaved={reloadN8nCfg}
            />
        </div>
    );
}
