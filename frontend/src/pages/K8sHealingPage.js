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
    Container, RefreshCw, Play, CheckCircle, XCircle, Clock,
    AlertTriangle, Shield, Settings, Terminal, Eye, BarChart3,
    Wrench, Server, Zap,
} from 'lucide-react';

const RISK_STYLES = {
    low: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    high: 'bg-red-500/15 text-red-400 border-red-500/30',
};
const STATUS_STYLES = {
    executed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    pending_approval: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    rejected: 'bg-red-500/15 text-red-400 border-red-500/30',
};

export default function K8sHealingPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('playbooks');
    const [playbooks, setPlaybooks] = useState([]);
    const [executions, setExecutions] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [executing, setExecuting] = useState(false);
    const [selectedPlaybook, setSelectedPlaybook] = useState('');
    const [params, setParams] = useState({});
    const [generatedCmds, setGeneratedCmds] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [pRes, eRes, sRes] = await Promise.all([
                api.get('/k8s/playbooks'), api.get('/k8s/executions?limit=20'), api.get('/k8s/stats'),
            ]);
            setPlaybooks(pRes.data || []);
            setExecutions(eRes.data || []);
            setStats(sRes.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const generatePreview = useCallback(async () => {
        if (!selectedPlaybook) return;
        try {
            const res = await api.post('/k8s/generate', { playbook_id: selectedPlaybook, params });
            setGeneratedCmds(res.data);
        } catch (e) { console.error(e); }
    }, [api, selectedPlaybook, params]);

    const executePlaybook = useCallback(async () => {
        if (!selectedPlaybook) return;
        setExecuting(true);
        try {
            await api.post('/k8s/execute', { playbook_id: selectedPlaybook, params, auto_approve: false });
            await fetchData();
            setGeneratedCmds(null);
        } catch (e) { console.error(e); }
        setExecuting(false);
    }, [api, selectedPlaybook, params, fetchData]);

    const approveExec = useCallback(async (id) => { try { await api.post(`/k8s/executions/${id}/approve`); await fetchData(); } catch (e) { console.error(e); } }, [api, fetchData]);
    const rejectExec = useCallback(async (id) => { try { await api.post(`/k8s/executions/${id}/reject`); await fetchData(); } catch (e) { console.error(e); } }, [api, fetchData]);

    useEffect(() => { fetchData(); }, [fetchData]);
    useEffect(() => { if (selectedPlaybook) generatePreview(); }, [selectedPlaybook, generatePreview]);

    const tabs = [
        { id: 'playbooks', label: 'Playbooks', icon: Wrench },
        { id: 'executions', label: 'Executions', icon: Terminal },
    ];

    const paramFields = {
        restart_pod: [{ key: 'pod_name', label: 'Pod Name' }, { key: 'namespace', label: 'Namespace', def: 'default' }, { key: 'app_label', label: 'App Label' }],
        scale_deployment: [{ key: 'deployment', label: 'Deployment' }, { key: 'replicas', label: 'Replicas', def: '3' }, { key: 'namespace', label: 'Namespace', def: 'default' }],
        rollback_deployment: [{ key: 'deployment', label: 'Deployment' }, { key: 'namespace', label: 'Namespace', def: 'default' }],
        drain_node: [{ key: 'node_name', label: 'Node Name' }],
        restart_deployment: [{ key: 'deployment', label: 'Deployment' }, { key: 'namespace', label: 'Namespace', def: 'default' }],
        hpa_adjust: [{ key: 'hpa_name', label: 'HPA Name' }, { key: 'namespace', label: 'Namespace', def: 'default' }, { key: 'min_replicas', label: 'Min Replicas', def: '2' }, { key: 'max_replicas', label: 'Max Replicas', def: '10' }],
    };

    return (
        <div className="space-y-6" data-testid="k8s-healing-page">
            <div className="flex items-center justify-between">
                <div><h1 className="text-2xl font-bold text-white flex items-center gap-3"><div className="p-2 rounded-lg bg-cyan-500/15"><Container className="w-6 h-6 text-cyan-400" /></div>K8s Auto-Healing</h1><p className="text-sm text-white/50 mt-1">Kubernetes remediation playbooks with approval workflow</p></div>
                <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
            </div>

            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Total</p><p className="text-lg font-bold text-white">{stats.total}</p></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Pending</p><p className="text-lg font-bold text-amber-400" data-testid="pending-count">{stats.pending_approval}</p></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Executed</p><p className="text-lg font-bold text-emerald-400">{stats.executed}</p></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4"><p className="text-xs text-white/50">Rejected</p><p className="text-lg font-bold text-red-400">{stats.rejected}</p></CardContent></Card>
                </div>
            )}

            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (<Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}><Icon className="w-3 h-3 mr-1" /> {t.label}</Button>); })}
            </div>

            {tab === 'playbooks' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="space-y-3">
                        {playbooks.map(pb => {
                            const riskStyle = RISK_STYLES[pb.risk_level] || RISK_STYLES.low;
                            return (
                                <Card key={pb.id} className={`bg-[#0D1117] border-white/5 cursor-pointer transition-all hover:border-white/15 ${selectedPlaybook === pb.id ? 'ring-1 ring-cyan-500/30' : ''}`}
                                    onClick={() => { setSelectedPlaybook(pb.id); setParams({}); setGeneratedCmds(null); }} data-testid={`playbook-${pb.id}`}>
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-1">
                                            <h3 className="text-sm font-semibold text-white">{pb.name}</h3>
                                            <div className="flex gap-1">
                                                <Badge className={`text-[9px] ${riskStyle}`}>{pb.risk_level}</Badge>
                                                {pb.auto_approve && <Badge variant="outline" className="text-[8px] text-emerald-400 border-emerald-500/30">Auto</Badge>}
                                            </div>
                                        </div>
                                        <p className="text-[10px] text-white/40">{pb.description}</p>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>

                    <div>
                        {selectedPlaybook ? (
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Terminal className="w-4 h-4 text-cyan-400" /> Execute: {playbooks.find(p => p.id === selectedPlaybook)?.name}</CardTitle></CardHeader>
                                <CardContent className="p-4 space-y-3">
                                    <div className="grid grid-cols-1 gap-2">
                                        {(paramFields[selectedPlaybook] || []).map(f => (
                                            <div key={f.key}><Label className="text-xs text-white/60">{f.label}</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={params[f.key] || f.def || ''} onChange={e => setParams(p => ({ ...p, [f.key]: e.target.value }))} data-testid={`param-${f.key}`} /></div>
                                        ))}
                                    </div>
                                    {generatedCmds && (
                                        <div className="mt-3">
                                            <p className="text-xs text-white/50 mb-1">Generated Commands:</p>
                                            <pre className="bg-[#161B22] border border-white/5 rounded p-3 text-[10px] text-emerald-400/70 font-mono overflow-x-auto" data-testid="generated-cmds">{generatedCmds.commands?.join('\n')}</pre>
                                        </div>
                                    )}
                                    <Button onClick={executePlaybook} disabled={executing} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="execute-btn">
                                        {executing ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />} Execute
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-12 text-center text-white/40"><Container className="w-8 h-8 mx-auto mb-3 opacity-30" /><p>Select a playbook</p></CardContent></Card>
                        )}
                    </div>
                </div>
            )}

            {tab === 'executions' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Terminal className="w-4 h-4 text-white/60" /> Execution Log</CardTitle></CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[500px] overflow-y-auto divide-y divide-white/5" data-testid="execution-list">
                            {executions.length === 0 ? (
                                <div className="p-8 text-center text-white/40"><Terminal className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No executions yet</p></div>
                            ) : executions.map((ex, i) => {
                                const stStyle = STATUS_STYLES[ex.status] || STATUS_STYLES.pending_approval;
                                const riskStyle = RISK_STYLES[ex.risk_level] || RISK_STYLES.low;
                                return (
                                    <div key={ex.id} className="p-3 hover:bg-white/[0.02]" data-testid={`execution-${i}`}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2">
                                                <Badge className={`text-[9px] ${stStyle}`}>{ex.status}</Badge>
                                                <Badge className={`text-[9px] ${riskStyle}`}>{ex.risk_level}</Badge>
                                                <span className="text-sm text-white/80">{ex.playbook_name}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {ex.status === 'pending_approval' && (
                                                    <>
                                                        <Button size="sm" variant="outline" onClick={() => approveExec(ex.id)} className="text-[10px] border-emerald-500/30 text-emerald-400 h-6" data-testid={`approve-${ex.id}`}><CheckCircle className="w-3 h-3 mr-0.5" /> Approve</Button>
                                                        <Button size="sm" variant="outline" onClick={() => rejectExec(ex.id)} className="text-[10px] border-red-500/30 text-red-400 h-6" data-testid={`reject-${ex.id}`}><XCircle className="w-3 h-3 mr-0.5" /> Reject</Button>
                                                    </>
                                                )}
                                                <span className="text-[10px] text-white/25">{ex.created_at ? new Date(ex.created_at).toLocaleString() : ''}</span>
                                            </div>
                                        </div>
                                        <pre className="text-[9px] text-white/30 font-mono truncate">{ex.commands?.join(' && ')}</pre>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
