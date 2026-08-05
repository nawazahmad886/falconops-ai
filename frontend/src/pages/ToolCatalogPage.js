import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Plus, FlaskConical, Ban, CheckCircle2, Wrench } from 'lucide-react';

const RISK_STYLE = { SAFE: 'text-emerald-300 border-emerald-500/30', GUARDED: 'text-amber-300 border-amber-500/30', DESTRUCTIVE: 'text-red-300 border-red-500/30' };

export const ToolCatalogPage = () => {
    const { api } = useAuth();
    const [tools, setTools] = useState([]);
    const [bindingKinds, setBindingKinds] = useState([]);
    const [showCreate, setShowCreate] = useState(false);
    const [draft, setDraft] = useState({ name: '', description: '', category: 'Observability', risk_tier: 'SAFE', binding: { kind: 'troubleshooting_command', ref: '', static_params: {} }, timeout_seconds: 30 });
    const [testingId, setTestingId] = useState(null);
    const [testResult, setTestResult] = useState(null);

    const load = useCallback(async () => {
        const [toolsRes, kindsRes] = await Promise.all([api.get('/v1/tools'), api.get('/v1/tools/binding-kinds')]);
        setTools(toolsRes.data.tools || []);
        setBindingKinds(kindsRes.data.binding_kinds || []);
    }, [api]);

    useEffect(() => { load(); }, [load]);

    const createTool = async () => {
        try {
            await api.post('/v1/tools', { payload: draft });
            toast.success('Tool created');
            setShowCreate(false);
            load();
        } catch (e) { toast.error(e?.response?.data?.detail || 'Create failed'); }
    };

    const toggleStatus = async (tool) => {
        const path = tool.status === 'active' ? 'disable' : 'enable';
        await api.post(`/v1/tools/${tool.tool_id}/${path}`);
        load();
    };

    const runTest = async (toolId) => {
        setTestingId(toolId);
        try {
            const res = await api.post(`/v1/tools/${toolId}/test`, { input: {} });
            setTestResult({ toolId, ...res.data });
        } catch (e) { toast.error('Test failed'); }
        finally { setTestingId(null); }
    };

    const selectedKind = bindingKinds.find((k) => k.kind === draft.binding.kind);

    return (
        <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-white flex items-center gap-2"><Wrench className="w-4 h-4" />Tool Catalog</h1>
                <Button size="sm" onClick={() => setShowCreate(true)}><Plus className="w-3.5 h-3.5 mr-1" />New Tool</Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tools.map((t) => (
                    <Card key={t.tool_id} className="bg-white/5 border-white/10">
                        <CardContent className="p-4 space-y-2">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold text-white">{t.name}</span>
                                <div className="flex gap-1">
                                    <Badge variant="outline" className={`text-[10px] ${RISK_STYLE[t.risk_tier]}`}>{t.risk_tier}</Badge>
                                    <Badge variant="outline" className="text-[10px]">{t.status}</Badge>
                                </div>
                            </div>
                            <p className="text-xs text-white/50">{t.description}</p>
                            <div className="text-[10px] text-white/40 font-mono">{t.binding.kind}:{t.binding.ref || '(n/a)'}</div>
                            <div className="flex gap-1.5">
                                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => runTest(t.tool_id)} disabled={testingId === t.tool_id}>
                                    <FlaskConical className="w-3 h-3 mr-1" />{testingId === t.tool_id ? 'Testing…' : 'Test'}
                                </Button>
                                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => toggleStatus(t)}>
                                    {t.status === 'active' ? <><Ban className="w-3 h-3 mr-1" />Disable</> : <><CheckCircle2 className="w-3 h-3 mr-1" />Enable</>}
                                </Button>
                            </div>
                            {testResult?.toolId === t.tool_id && (
                                <pre className="text-[10px] bg-black/30 rounded p-2 overflow-x-auto text-white/60">{JSON.stringify(testResult, null, 2)}</pre>
                            )}
                        </CardContent>
                    </Card>
                ))}
                {tools.length === 0 && <div className="text-white/40 text-sm">No tools yet.</div>}
            </div>

            {showCreate && (
                <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
                    <div className="bg-[#0D1117] border border-white/10 rounded-lg p-4 w-[480px] space-y-3" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-sm font-semibold text-white">New Tool</h3>
                        <div><Label className="text-xs">Name</Label><Input className="bg-muted/30" value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} /></div>
                        <div><Label className="text-xs">Description</Label><Input className="bg-muted/30" value={draft.description} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} /></div>
                        <div><Label className="text-xs">Binding Kind</Label>
                            <Select value={draft.binding.kind} onValueChange={(v) => setDraft((d) => ({ ...d, binding: { ...d.binding, kind: v } }))}>
                                <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                                <SelectContent>{bindingKinds.map((k) => <SelectItem key={k.kind} value={k.kind}>{k.label}</SelectItem>)}</SelectContent>
                            </Select>
                            {selectedKind && <p className="text-[10px] text-white/40 mt-1">{selectedKind.description}</p>}
                        </div>
                        <div><Label className="text-xs">Ref ({selectedKind?.ref_hint})</Label>
                            <Input className="bg-muted/30" value={draft.binding.ref} onChange={(e) => setDraft((d) => ({ ...d, binding: { ...d.binding, ref: e.target.value } }))} /></div>
                        <div><Label className="text-xs">Risk Tier</Label>
                            <Select value={draft.risk_tier} onValueChange={(v) => setDraft((d) => ({ ...d, risk_tier: v }))}>
                                <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                                <SelectContent>{['SAFE', 'GUARDED', 'DESTRUCTIVE'].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                            </Select>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                            <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
                            <Button size="sm" onClick={createTool}>Create</Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ToolCatalogPage;
