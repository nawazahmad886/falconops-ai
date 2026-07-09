import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Mail, Plus, Pencil, Trash2, RefreshCw, X, CheckCircle2, Send, Code, Eye,
} from 'lucide-react';
import WysiwygEditor from '../components/WysiwygEditor';

const API = process.env.REACT_APP_BACKEND_URL || '';
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const EMPTY_TMPL = {
    name: '', description: '', subject: '', body_html: '', body_text: '',
    variables: [], is_active: true,
};

const renderTemplate = (text, vars) => {
    if (!text) return '';
    let out = text;
    Object.entries(vars || {}).forEach(([k, v]) => {
        out = out.replaceAll(`{{${k}}}`, v == null ? '' : String(v));
    });
    return out;
};

const buildPreviewVars = (variables) => {
    const out = {};
    (variables || []).forEach((v) => {
        out[v] = `<${v}>`;
    });
    return out;
};

export default function AdminEmailTemplatesPage() {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);
    const [varsText, setVarsText] = useState('');
    const [tab, setTab] = useState('edit');
    const [busy, setBusy] = useState(false);
    const [testRecipient, setTestRecipient] = useState('');
    const [testBusy, setTestBusy] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/api/admin/email-templates`, { headers: authHeaders() });
            const d = await r.json();
            setTemplates(d.templates || []);
        } catch {
            toast.error('Failed to load templates');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const openEdit = (tmpl) => {
        setEditing(tmpl || { ...EMPTY_TMPL });
        setVarsText((tmpl?.variables || []).join(', '));
        setTab('edit');
    };

    const save = async () => {
        if (!editing.name.trim() || !editing.subject.trim() || !editing.body_html.trim()) {
            toast.error('Name, subject and HTML body are required');
            return;
        }
        const payload = {
            ...editing,
            variables: varsText.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean),
        };
        setBusy(true);
        try {
            const method = payload.id ? 'PUT' : 'POST';
            const url = payload.id ? `${API}/api/admin/email-templates/${payload.id}` : `${API}/api/admin/email-templates`;
            const r = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(payload) });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`Template ${payload.id ? 'updated' : 'created'}`);
            setEditing(null);
            load();
        } catch (e) {
            toast.error(`Save failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusy(false);
        }
    };

    const remove = async (tmpl) => {
        if (!window.confirm(`Delete template "${tmpl.name}"?`)) return;
        try {
            const r = await fetch(`${API}/api/admin/email-templates/${tmpl.id}`, {
                method: 'DELETE', headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Template deleted');
            load();
        } catch (e) {
            toast.error(`Delete failed: ${e.message?.slice(0, 200)}`);
        }
    };

    const sendTest = async () => {
        if (!testRecipient.trim()) { toast.error('Recipient email required'); return; }
        setTestBusy(true);
        try {
            const r = await fetch(`${API}/api/admin/email-templates/${editing.id}/send-test`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({
                    recipient: testRecipient,
                    variables: buildPreviewVars(editing.variables),
                }),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Test email sent');
        } catch (e) {
            toast.error(`Send failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setTestBusy(false);
        }
    };

    return (
        <div className="p-6 space-y-5" data-testid="admin-email-templates-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Mail className="w-6 h-6 text-cyan-400" /> Email Templates
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Edit subject + HTML body. Variables use <code className="text-cyan-300">{'{{name}}'}</code> syntax.
                    </p>
                </div>
                <Button onClick={() => openEdit(null)} data-testid="new-template-btn">
                    <Plus className="w-4 h-4 mr-1.5" /> New Template
                </Button>
            </div>

            {loading ? (
                <div className="py-10 text-center"><RefreshCw className="w-5 h-5 text-white/40 animate-spin inline" /></div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {templates.map((t) => (
                        <Card key={t.id} className="bg-black/40 border-white/10" data-testid={`template-card-${t.id}`}>
                            <CardContent className="p-4">
                                <div className="flex items-start justify-between gap-3 mb-1">
                                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                                        <span className="text-base font-semibold text-white truncate">{t.name}</span>
                                        <Badge className={`text-[10px] ${t.is_active ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30'} border`}>
                                            {t.is_active ? 'active' : 'inactive'}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                        <Button variant="ghost" size="sm" onClick={() => openEdit(t)} data-testid={`edit-template-${t.id}`}>
                                            <Pencil className="w-3.5 h-3.5" />
                                        </Button>
                                        <Button variant="ghost" size="sm" onClick={() => remove(t)} data-testid={`delete-template-${t.id}`}>
                                            <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                        </Button>
                                    </div>
                                </div>
                                <div className="text-[11px] text-white/55 mb-2">{t.description}</div>
                                <div className="text-[12px] text-white/80 font-medium truncate" title={t.subject}>
                                    📧 {t.subject}
                                </div>
                                <div className="flex items-center gap-1 flex-wrap mt-2">
                                    {(t.variables || []).slice(0, 6).map((v) => (
                                        <Badge key={v} className="text-[9px] bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">{v}</Badge>
                                    ))}
                                    {(t.variables || []).length > 6 && (
                                        <Badge className="text-[9px] bg-white/5 text-white/50 border border-white/10">
                                            +{t.variables.length - 6} more
                                        </Badge>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Edit Dialog */}
            <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
                <DialogContent className="bg-zinc-950 border-white/10 max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="template-edit-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white">{editing?.id ? `Edit ${editing.name}` : 'New Template'}</DialogTitle>
                        <DialogDescription className="text-white/50 text-xs">
                            Use <code className="text-cyan-300">{'{{variable}}'}</code> in subject + body. Define variable names in the Variables field.
                        </DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <Tabs value={tab} onValueChange={setTab}>
                            <TabsList className="bg-black/40 border border-white/10">
                                <TabsTrigger value="edit" data-testid="tab-edit"><Code className="w-3.5 h-3.5 mr-1.5" /> Edit</TabsTrigger>
                                <TabsTrigger value="preview" data-testid="tab-preview"><Eye className="w-3.5 h-3.5 mr-1.5" /> Preview</TabsTrigger>
                                {editing.id && <TabsTrigger value="test" data-testid="tab-test"><Send className="w-3.5 h-3.5 mr-1.5" /> Send test</TabsTrigger>}
                            </TabsList>

                            <TabsContent value="edit" className="space-y-3 mt-4">
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-xs text-white/70">Template name (slug)</Label>
                                        <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                                            placeholder="welcome" className="bg-black/40 border-white/10 mt-1" data-testid="template-name-input" />
                                    </div>
                                    <div className="flex items-center justify-end pt-5">
                                        <Label className="text-xs text-white/70 mr-2">Active</Label>
                                        <Switch checked={!!editing.is_active} onCheckedChange={(v) => setEditing({ ...editing, is_active: v })} data-testid="template-active-switch" />
                                    </div>
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Description (internal)</Label>
                                    <Input value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Subject</Label>
                                    <Input value={editing.subject} onChange={(e) => setEditing({ ...editing, subject: e.target.value })}
                                        placeholder="Welcome to FalconOps, {{name}}!" className="bg-black/40 border-white/10 mt-1" data-testid="template-subject-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">HTML body</Label>
                                    <div className="mt-1" data-testid="template-html-input">
                                        <WysiwygEditor
                                            value={editing.body_html}
                                            onChange={(html) => setEditing({ ...editing, body_html: html })}
                                            variables={varsText.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean)}
                                            testid="template-wysiwyg"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Plain-text body (fallback)</Label>
                                    <Textarea value={editing.body_text} onChange={(e) => setEditing({ ...editing, body_text: e.target.value })}
                                        rows={4} className="bg-black/40 border-white/10 mt-1 font-mono text-[12px]" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Variables (comma or space separated)</Label>
                                    <Input value={varsText} onChange={(e) => setVarsText(e.target.value)}
                                        placeholder="name, email, company" className="bg-black/40 border-white/10 mt-1" data-testid="template-vars-input" />
                                </div>
                            </TabsContent>

                            <TabsContent value="preview" className="mt-4">
                                <div className="rounded-lg border border-white/10 bg-white p-5" data-testid="template-preview">
                                    <div className="text-xs text-zinc-500 mb-2">
                                        <strong>Subject:</strong> {renderTemplate(editing.subject, buildPreviewVars(varsText.split(/[,\s]+/).filter(Boolean)))}
                                    </div>
                                    <div className="border-t border-zinc-200 pt-3 text-zinc-900 prose prose-sm max-w-none"
                                        dangerouslySetInnerHTML={{ __html: renderTemplate(editing.body_html, buildPreviewVars(varsText.split(/[,\s]+/).filter(Boolean))) }}
                                    />
                                </div>
                            </TabsContent>

                            <TabsContent value="test" className="space-y-3 mt-4">
                                <Label className="text-xs text-white/70">Recipient email</Label>
                                <Input type="email" value={testRecipient} onChange={(e) => setTestRecipient(e.target.value)}
                                    placeholder="you@example.com" className="bg-black/40 border-white/10 mt-1" data-testid="test-recipient-input" />
                                <Button onClick={sendTest} disabled={testBusy} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="send-test-btn">
                                    {testBusy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Send className="w-4 h-4 mr-1.5" />}
                                    Send test email
                                </Button>
                                <p className="text-[10px] text-white/50">
                                    Variables will be replaced with placeholder values <code>{'<name>'}</code>, etc. To send with real values, integrate via the API.
                                </p>
                            </TabsContent>
                        </Tabs>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEditing(null)}><X className="w-4 h-4 mr-1.5" /> Cancel</Button>
                        <Button onClick={save} disabled={busy} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="save-template-btn">
                            {busy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
