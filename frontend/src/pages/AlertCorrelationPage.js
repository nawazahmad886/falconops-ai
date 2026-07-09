import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    GitMerge, RefreshCw, AlertTriangle, BarChart3, Settings,
    Activity, Eye, Shield, Target, Clock, CheckCircle, Hash,
} from 'lucide-react';

const SEV_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};

export default function AlertCorrelationPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('groups');
    const [data, setData] = useState(null);
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [configForm, setConfigForm] = useState({ correlation_window_min: 30, similarity_threshold: 0.35, max_group_size: 20 });

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [aRes, cRes] = await Promise.all([api.get('/correlation/analyze?hours=24'), api.get('/correlation/config')]);
            setData(aRes.data);
            setConfig(cRes.data);
            setConfigForm(cRes.data || configForm);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const saveConfig = useCallback(async () => {
        setSaving(true);
        try { await api.put('/correlation/config', configForm); await fetchData(); } catch (e) { console.error(e); }
        setSaving(false);
    }, [api, configForm, fetchData]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const tabs = [{ id: 'groups', label: 'Correlation Groups', icon: GitMerge }, { id: 'config', label: 'Configuration', icon: Settings }];

    return (
        <div className="space-y-6" data-testid="alert-correlation-page">
            <div className="flex items-center justify-between">
                <div><h1 className="text-2xl font-bold text-white flex items-center gap-3"><div className="p-2 rounded-lg bg-amber-500/15"><GitMerge className="w-6 h-6 text-amber-400" /></div>Alert Correlation</h1><p className="text-sm text-white/50 mt-1">NLP-powered alert grouping & noise reduction</p></div>
                <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
            </div>

            {data && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-blue-500/15"><AlertTriangle className="w-4 h-4 text-blue-400" /></div><div><p className="text-xs text-white/50">Total Alerts</p><p className="text-lg font-bold text-white" data-testid="total-alerts">{data.total_alerts}</p></div></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-amber-500/15"><GitMerge className="w-4 h-4 text-amber-400" /></div><div><p className="text-xs text-white/50">Groups</p><p className="text-lg font-bold text-amber-400">{data.correlation_groups}</p></div></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-emerald-500/15"><Activity className="w-4 h-4 text-emerald-400" /></div><div><p className="text-xs text-white/50">Noise Reduction</p><p className="text-lg font-bold text-emerald-400">{data.noise_reduction_pct}%</p></div></CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3"><div className="p-2 rounded-lg bg-cyan-500/15"><Hash className="w-4 h-4 text-cyan-400" /></div><div><p className="text-xs text-white/50">Avg Group Size</p><p className="text-lg font-bold text-white">{data.total_alerts && data.correlation_groups ? (data.total_alerts / data.correlation_groups).toFixed(1) : 0}</p></div></CardContent></Card>
                </div>
            )}

            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (<Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}><Icon className="w-3 h-3 mr-1" /> {t.label}</Button>); })}
            </div>

            {tab === 'groups' && data?.groups && (
                <div className="space-y-3" data-testid="correlation-groups">
                    {data.groups.map((g, i) => {
                        const sevStyle = SEV_STYLES[g.severity] || SEV_STYLES.info;
                        return (
                            <Card key={g.id} className="bg-[#0D1117] border-white/5" data-testid={`group-${i}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <Badge className={`text-[9px] ${sevStyle}`}>{g.severity}</Badge>
                                            <span className="text-sm font-semibold text-white">{g.primary?.service || 'Multi-service'}</span>
                                            <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{g.alert_count} alerts</Badge>
                                        </div>
                                        <div className="flex gap-1">{g.sources?.map(s => <Badge key={s} variant="outline" className="text-[8px] text-white/30 border-white/10">{s}</Badge>)}</div>
                                    </div>
                                    <p className="text-xs text-white/60 mb-2">{g.primary?.message}</p>
                                    <div className="flex flex-wrap gap-1 mb-2">{g.top_keywords?.slice(0, 6).map(k => <span key={k} className="text-[9px] bg-white/5 text-white/40 px-1.5 py-0.5 rounded">{k}</span>)}</div>
                                    {g.correlated?.length > 0 && (
                                        <div className="mt-2 pt-2 border-t border-white/5 space-y-1">
                                            <p className="text-[10px] text-white/30">Correlated alerts:</p>
                                            {g.correlated.slice(0, 5).map((c, j) => (
                                                <div key={j} className="flex items-center gap-2 text-[10px]">
                                                    <Badge variant="outline" className="text-[8px] text-amber-400 border-amber-500/30">{c.similarity}%</Badge>
                                                    <span className="text-white/50 truncate">{c.message}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {tab === 'config' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Settings className="w-4 h-4 text-white/60" /> Correlation Settings</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div><Label className="text-xs text-white/60">Time Window (min)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={configForm.correlation_window_min} onChange={e => setConfigForm(p => ({ ...p, correlation_window_min: parseInt(e.target.value) || 30 }))} data-testid="window-input" /></div>
                            <div><Label className="text-xs text-white/60">Similarity Threshold (0-1)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" step="0.05" value={configForm.similarity_threshold} onChange={e => setConfigForm(p => ({ ...p, similarity_threshold: parseFloat(e.target.value) || 0.35 }))} data-testid="threshold-input" /></div>
                            <div><Label className="text-xs text-white/60">Max Group Size</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={configForm.max_group_size} onChange={e => setConfigForm(p => ({ ...p, max_group_size: parseInt(e.target.value) || 20 }))} /></div>
                        </div>
                        <Button onClick={saveConfig} disabled={saving} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="save-config-btn"><CheckCircle className="w-3 h-3 mr-1" /> Save</Button>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
