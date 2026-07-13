import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Wrench, Play, History, RefreshCw, CheckCircle, AlertTriangle,
    Shield, Server, Lock, Zap, Database, Clock, ChevronRight,
    Cpu, HardDrive, UserX, Key, Trash2, RotateCcw,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend,
} from 'recharts';

const CATEGORY_ICONS = {
    compute: Cpu, security: Shield, performance: Zap, infrastructure: HardDrive,
};
const RISK_STYLES = {
    low: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    high: 'bg-red-500/15 text-red-400 border-red-500/30',
};
const PIE_COLORS = ['#22c55e', '#eab308', '#ef4444', '#3b82f6'];

export default function RemediationPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('actions');
    const [loading, setLoading] = useState(true);
    const [actions, setActions] = useState([]);
    const [historyData, setHistoryData] = useState([]);
    const [stats, setStats] = useState(null);
    const [executing, setExecuting] = useState(null);
    const [lastResult, setLastResult] = useState(null);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestCause, setSuggestCause] = useState('');

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [aRes, hRes, sRes] = await Promise.all([
                api.get('/remediation/actions'),
                api.get('/remediation/history?limit=20'),
                api.get('/remediation/stats'),
            ]);
            setActions(aRes.data || []);
            setHistoryData(hRes.data || []);
            setStats(sRes.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const executeAction = async (actionId, params = {}) => {
        setExecuting(actionId);
        setLastResult(null);
        try {
            const res = await api.post('/remediation/execute', { action_id: actionId, params, trigger: 'manual' });
            setLastResult(res.data);
            const hRes = await api.get('/remediation/history?limit=20');
            setHistoryData(hRes.data || []);
            const sRes = await api.get('/remediation/stats');
            setStats(sRes.data);
        } catch (e) { console.error(e); }
        setExecuting(null);
    };

    const getSuggestions = async (cause) => {
        try {
            const res = await api.post('/remediation/suggest', { root_cause: cause, context: {} });
            setSuggestions(res.data || []);
            setSuggestCause(cause);
        } catch (e) { console.error(e); }
    };

    const CAUSES = ['high_cpu', 'high_memory', 'disk_full', 'brute_force', 'privilege_escalation', 'data_exfiltration', 'service_down', 'connection_leak'];

    if (loading) return <div className="flex items-center justify-center h-64 text-white/40">Loading...</div>;

    return (
        <div className="space-y-6" data-testid="remediation-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="remediation-title">
                        <Wrench className="w-7 h-7 text-amber-400" /> Auto-Remediation
                    </h1>
                    <p className="text-sm text-white/40 mt-1">Automated response actions — block IPs, restart services, scale infrastructure</p>
                    <p className="text-xs text-amber-400/80 mt-0.5">Dry-run preview only — commands are resolved and logged but never run against real infrastructure</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchData} className="border-white/10 text-xs">
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                </Button>
            </div>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 text-center">
                        <p className="text-xs text-white/40">Total Executions</p><p className="text-2xl font-bold text-white mt-1">{stats.total_executions}</p>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-emerald-500/20"><CardContent className="p-4 text-center">
                        <p className="text-xs text-emerald-400">Previewed</p><p className="text-2xl font-bold text-emerald-400 mt-1">{stats.previewed}</p>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-blue-500/20"><CardContent className="p-4 text-center">
                        <p className="text-xs text-blue-400">Auto-Triggered</p><p className="text-2xl font-bold text-blue-400 mt-1">{stats.auto_triggered}</p>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-amber-500/20"><CardContent className="p-4 text-center">
                        <p className="text-xs text-amber-400">Manual</p><p className="text-2xl font-bold text-amber-400 mt-1">{stats.manual_triggered}</p>
                    </CardContent></Card>
                </div>
            )}

            {lastResult && (
                <Card className="bg-emerald-500/5 border-emerald-500/20" data-testid="remediation-result">
                    <CardContent className="p-4 flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-emerald-400" />
                        <div>
                            <p className="text-sm font-medium text-white/80">{lastResult.action_name} — {lastResult.status}</p>
                            <p className="text-xs text-white/40 font-mono">{lastResult.resolved_script}</p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Tabs */}
            <div className="flex gap-1 bg-[#0D1117] p-1 rounded-lg border border-white/5 w-fit">
                {[{ id: 'actions', label: 'Action Library', icon: Wrench }, { id: 'suggest', label: 'RCA Suggest', icon: Zap }, { id: 'history', label: 'History', icon: History }].map(t => (
                    <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60 hover:bg-white/5'}`} data-testid={`tab-${t.id}`}>
                        <t.icon className="w-3.5 h-3.5" /> {t.label}
                    </button>
                ))}
            </div>

            {/* Action Library */}
            {tab === 'actions' && (
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="action-library">
                    {actions.map(a => {
                        const Icon = CATEGORY_ICONS[a.category] || Wrench;
                        const riskStyle = RISK_STYLES[a.risk_level] || RISK_STYLES.medium;
                        return (
                            <Card key={a.id} className="bg-[#0D1117] border-white/5 hover:border-white/10 transition-colors" data-testid={`action-${a.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="p-2 rounded-lg bg-amber-500/10"><Icon className="w-5 h-5 text-amber-400" /></div>
                                        <div className="flex gap-1.5">
                                            <Badge className={`${riskStyle} border text-[9px]`}>{a.risk_level}</Badge>
                                            {a.auto_eligible && <Badge className="bg-blue-500/15 text-blue-400 border-blue-500/30 border text-[9px]">Auto</Badge>}
                                        </div>
                                    </div>
                                    <h4 className="text-sm font-semibold text-white/90 mb-1">{a.name}</h4>
                                    <p className="text-xs text-white/40 mb-2">{a.description}</p>
                                    <p className="text-[10px] font-mono text-white/20 mb-3 truncate">{a.script_preview}</p>
                                    <Button size="sm" onClick={() => executeAction(a.id, {})} disabled={!!executing} className="w-full bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30 text-xs" data-testid={`exec-${a.id}`}>
                                        {executing === a.id ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Play className="w-3.5 h-3.5 mr-1.5" />}
                                        Preview (dry-run)
                                    </Button>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* RCA Suggest */}
            {tab === 'suggest' && (
                <div className="space-y-4" data-testid="rca-suggest">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-white/60">Select Root Cause</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-2">
                                {CAUSES.map(c => (
                                    <Button key={c} size="sm" variant={suggestCause === c ? 'default' : 'outline'} onClick={() => getSuggestions(c)} className="text-xs border-white/10" data-testid={`cause-${c}`}>
                                        {c.replace(/_/g, ' ')}
                                    </Button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                    {suggestions.length > 0 && (
                        <div className="space-y-2">
                            <h3 className="text-sm text-white/60">Suggested Actions for "{suggestCause.replace(/_/g, ' ')}"</h3>
                            {suggestions.map((s, i) => (
                                <Card key={i} className="bg-[#0D1117] border-white/5" data-testid={`suggestion-${i}`}>
                                    <CardContent className="p-4 flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-white/80">{s.name}</p>
                                            <p className="text-xs text-white/40">{s.description}</p>
                                            <p className="text-[10px] font-mono text-white/20 mt-1">{s.script_preview}</p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge className={`${RISK_STYLES[s.risk_level] || ''} border text-[9px]`}>{s.risk_level}</Badge>
                                            <Button size="sm" onClick={() => executeAction(s.action_id, s.pre_filled_params || {})} disabled={!!executing} className="text-xs bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30">
                                                <Play className="w-3 h-3 mr-1" /> Preview
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* History */}
            {tab === 'history' && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="remediation-history">
                    <CardContent className="p-4">
                        {historyData.length === 0 ? (
                            <p className="text-center text-white/30 py-8 text-sm">No remediation history</p>
                        ) : (
                            <div className="space-y-1.5">
                                {historyData.map((h, i) => (
                                    <div key={h.id || i} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5" data-testid={`hist-${i}`}>
                                        <div className="flex items-center gap-3">
                                            <CheckCircle className={`w-4 h-4 ${h.status === 'previewed' ? 'text-emerald-400' : 'text-red-400'}`} />
                                            <div>
                                                <p className="text-sm font-medium text-white/70">{h.action_name}</p>
                                                <p className="text-[10px] font-mono text-white/30">{h.resolved_script}</p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <Badge variant="outline" className={`text-[10px] ${h.trigger === 'auto' ? 'text-blue-400 border-blue-500/30' : 'text-white/40 border-white/10'}`}>{h.trigger}</Badge>
                                            <p className="text-[10px] text-white/20 mt-0.5">{new Date(h.started_at).toLocaleString()}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
