import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Globe, Plus, Trash2, Play, RefreshCw, CheckCircle, XCircle, Clock,
    Pencil, Eye, ArrowLeft, Shield, Key, Sparkles, AlertTriangle,
    ArrowUpRight, ArrowDownRight, Wifi, WifiOff, Lock, BarChart3,
    ChevronRight, ExternalLink,
} from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, BarChart, Bar,
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const getAuth = () => ({ Authorization: `Bearer ${localStorage.getItem('falconToken')}` });

// ─── Uptime Bar ───
const UptimeBar = ({ checks }) => {
    if (!checks || checks.length === 0) return <div className="h-6 bg-[#1a1a2e] rounded text-center text-[9px] text-slate-600 leading-6">No data</div>;
    const recent = checks.slice(-60);
    return (
        <div className="flex gap-[1px] h-6 items-end" data-testid="uptime-bar">
            {recent.map((c, i) => (
                <div key={i} className={`flex-1 rounded-sm min-w-[2px] ${c.is_up ? 'bg-emerald-500' : 'bg-red-500'}`}
                    style={{ height: `${Math.min(100, Math.max(20, (c.response_time_ms || 100) / 10))}%` }}
                    title={`${c.is_up ? 'UP' : 'DOWN'} - ${c.response_time_ms}ms`} />
            ))}
        </div>
    );
};

// ─── Status Dot ───
const StatusDot = ({ isUp, size = 'md' }) => {
    const s = size === 'lg' ? 'w-3 h-3' : 'w-2 h-2';
    if (isUp === null || isUp === undefined) return <div className={`${s} rounded-full bg-slate-500`} />;
    return <div className={`${s} rounded-full ${isUp ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />;
};

const CHECK_TYPE_CONFIG = {
    http: { label: 'HTTP', icon: Globe, color: '#00E0FF', desc: 'Simple HTTP check' },
    login: { label: 'Login', icon: Lock, color: '#10B981', desc: 'Login with credentials' },
    login_otp: { label: 'Login + OTP', icon: Key, color: '#8B5CF6', desc: 'Login with TOTP verification' },
};

const EMPTY_FORM = {
    name: '', url: '', check_type: 'http', interval: 300, timeout: 30,
    expected_status: 200, expected_text: '', auth_config: {}, enabled: true, tags: [],
};

// ═══════════════════════════════════════
//  FLEET OVERVIEW
// ═══════════════════════════════════════

const FleetView = ({ monitors, summary, onSelect, onRefresh, onSeed, loading }) => {
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState(EMPTY_FORM);

    const handleCreate = async () => {
        if (!form.name || !form.url) { toast.error('Name and URL required'); return; }
        try {
            const res = await fetch(`${API_URL}/api/synthetic/monitors`, {
                method: 'POST', headers: { ...getAuth(), 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            });
            if (!res.ok) throw new Error('Failed');
            toast.success('Monitor created');
            setShowForm(false); setForm(EMPTY_FORM); onRefresh();
        } catch (e) { toast.error(e.message); }
    };

    if (loading) return (
        <div className="flex items-center justify-center py-20"><RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" /></div>
    );

    return (
        <div className="space-y-6" data-testid="synthetic-fleet">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Synthetic Monitoring</h1>
                    <p className="text-sm text-slate-500 mt-0.5">URL health checks with login & OTP validation</p>
                </div>
                <div className="flex items-center gap-2">
                    {monitors.length === 0 && (
                        <Button variant="outline" size="sm" onClick={onSeed} className="border-cyan-500/30 text-cyan-400 h-8 text-xs" data-testid="seed-btn">
                            <Sparkles className="w-3 h-3 mr-1" /> Seed Demo
                        </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={onRefresh} className="text-white/50 h-8">
                        <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 h-8 text-xs" onClick={() => setShowForm(true)} data-testid="create-monitor-btn">
                        <Plus className="w-3.5 h-3.5 mr-1" /> New Monitor
                    </Button>
                </div>
            </div>

            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="summary-strip">
                <SummaryCard label="Total" value={summary.total} icon={Globe} color="#00E0FF" />
                <SummaryCard label="Up" value={summary.up} icon={CheckCircle} color="#10B981" />
                <SummaryCard label="Down" value={summary.down} icon={XCircle} color="#EF4444" />
                <SummaryCard label="Pending" value={summary.pending} icon={Clock} color="#F59E0B" />
                <SummaryCard label="Availability" value={`${summary.availability_avg || 0}%`} icon={BarChart3} color="#8B5CF6" />
            </div>

            {/* Monitor Cards */}
            {monitors.length === 0 ? (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardContent className="text-center py-16">
                        <Globe className="w-12 h-12 text-white/10 mx-auto mb-4" />
                        <p className="text-white/40 text-sm">No synthetic monitors configured</p>
                        <div className="flex gap-2 justify-center mt-4">
                            <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-400 text-xs" onClick={onSeed}>
                                <Sparkles className="w-3 h-3 mr-1" /> Load Demo Data
                            </Button>
                            <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 text-xs" onClick={() => setShowForm(true)}>
                                <Plus className="w-3 h-3 mr-1" /> Create Monitor
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {monitors.map(m => {
                        const typeConfig = CHECK_TYPE_CONFIG[m.check_type] || CHECK_TYPE_CONFIG.http;
                        const TypeIcon = typeConfig.icon;
                        return (
                            <Card key={m.id} className="bg-[#121826] border-[#2D3748]/50 hover:border-white/10 cursor-pointer transition-all group"
                                onClick={() => onSelect(m.id)} data-testid={`monitor-${m.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-4">
                                        <StatusDot isUp={m.is_up} size="lg" />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <h3 className="text-sm font-semibold text-white group-hover:text-cyan-400 transition-colors">{m.name}</h3>
                                                <Badge className="text-[8px] border-0 font-mono" style={{ backgroundColor: `${typeConfig.color}15`, color: typeConfig.color }}>
                                                    <TypeIcon className="w-2.5 h-2.5 mr-0.5" />{typeConfig.label}
                                                </Badge>
                                                {m.tags?.map(t => <Badge key={t} className="text-[8px] bg-white/5 text-slate-500 border-0">{t}</Badge>)}
                                            </div>
                                            <p className="text-[11px] text-slate-500 font-mono mt-0.5 truncate">{m.url}</p>
                                        </div>
                                        <div className="flex items-center gap-6 text-right flex-shrink-0">
                                            <div>
                                                <p className="text-[9px] text-slate-500 font-mono">RESPONSE</p>
                                                <p className="text-sm font-bold text-white font-mono">{m.last_response_time ? `${Math.round(m.last_response_time)}ms` : '-'}</p>
                                            </div>
                                            <div>
                                                <p className="text-[9px] text-slate-500 font-mono">UPTIME 24H</p>
                                                <p className={`text-sm font-bold font-mono ${(m.availability_24h || 0) >= 99 ? 'text-emerald-400' : (m.availability_24h || 0) >= 95 ? 'text-amber-400' : 'text-red-400'}`}>
                                                    {m.availability_24h != null ? `${m.availability_24h}%` : '-'}
                                                </p>
                                            </div>
                                            <div>
                                                <p className="text-[9px] text-slate-500 font-mono">INTERVAL</p>
                                                <p className="text-sm text-white/60 font-mono">{m.interval < 60 ? `${m.interval}s` : `${Math.round(m.interval / 60)}m`}</p>
                                            </div>
                                            <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-cyan-400" />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Create Dialog */}
            <CreateMonitorDialog show={showForm} onClose={() => setShowForm(false)} form={form} setForm={setForm} onSave={handleCreate} />
        </div>
    );
};

// ═══════════════════════════════════════
//  MONITOR DETAIL
// ═══════════════════════════════════════

const MonitorDetail = ({ monitorId, onBack }) => {
    const [monitor, setMonitor] = useState(null);
    const [results, setResults] = useState([]);
    const [timeseries, setTimeseries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [checking, setChecking] = useState(false);

    const fetchAll = useCallback(async () => {
        try {
            const headers = getAuth();
            const [mRes, rRes, tRes] = await Promise.all([
                fetch(`${API_URL}/api/synthetic/monitors/${monitorId}`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/synthetic/monitors/${monitorId}/results?limit=100`, { headers }).then(r => r.json()),
                fetch(`${API_URL}/api/synthetic/monitors/${monitorId}/timeseries?hours=24`, { headers }).then(r => r.json()),
            ]);
            setMonitor(mRes);
            setResults(rRes.results || []);
            setTimeseries(tRes.timeseries || []);
        } catch (e) { toast.error('Failed to load monitor'); }
        finally { setLoading(false); }
    }, [monitorId]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const runCheck = async () => {
        setChecking(true);
        try {
            const res = await fetch(`${API_URL}/api/synthetic/monitors/${monitorId}/check`, { method: 'POST', headers: getAuth() });
            const data = await res.json();
            toast.success(`Check: ${data.status} (${data.response_time_ms}ms)`);
            fetchAll();
        } catch (e) { toast.error('Check failed'); }
        finally { setChecking(false); }
    };

    if (loading || !monitor) return (
        <div className="flex items-center justify-center py-20"><RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" /></div>
    );

    const typeConfig = CHECK_TYPE_CONFIG[monitor.check_type] || CHECK_TYPE_CONFIG.http;
    const TypeIcon = typeConfig.icon;
    const chartData = timeseries.map(t => ({
        time: new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        rt: t.response_time_ms || 0,
        up: t.is_up ? 1 : 0,
    }));

    return (
        <div className="space-y-4" data-testid="monitor-detail">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onBack} className="text-white/50 h-8 px-2" data-testid="back-btn">
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <StatusDot isUp={monitor.is_up} size="lg" />
                    <div>
                        <h1 className="text-lg font-bold text-white">{monitor.name}</h1>
                        <div className="flex items-center gap-2">
                            <Badge className="text-[9px] border-0 font-mono" style={{ backgroundColor: `${typeConfig.color}15`, color: typeConfig.color }}>
                                <TypeIcon className="w-2.5 h-2.5 mr-0.5" />{typeConfig.label}
                            </Badge>
                            <span className="text-[10px] text-slate-500 font-mono">{monitor.url}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={runCheck} disabled={checking}
                        className="border-cyan-500/30 text-cyan-400 h-8 text-xs" data-testid="run-check-btn">
                        {checking ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Play className="w-3 h-3 mr-1" />}
                        Run Check
                    </Button>
                    <Button variant="ghost" size="sm" onClick={fetchAll} className="text-white/50 h-8"><RefreshCw className="w-3.5 h-3.5" /></Button>
                </div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <SummaryCard label="Status" value={monitor.is_up ? 'UP' : 'DOWN'} icon={monitor.is_up ? CheckCircle : XCircle} color={monitor.is_up ? '#10B981' : '#EF4444'} />
                <SummaryCard label="Response Time" value={`${Math.round(monitor.last_response_time || 0)}ms`} icon={Clock} color="#00E0FF" />
                <SummaryCard label="Uptime 24h" value={`${monitor.availability_24h || 0}%`} icon={BarChart3} color="#8B5CF6" />
                <SummaryCard label="Checks 24h" value={monitor.total_checks_24h || 0} icon={Eye} color="#F59E0B" />
                <SummaryCard label="Interval" value={monitor.interval < 60 ? `${monitor.interval}s` : `${Math.round(monitor.interval / 60)}m`} icon={RefreshCw} color="#64748B" />
            </div>

            {/* Response Time Chart */}
            {chartData.length > 0 && (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardHeader className="pb-1 pt-3 px-4">
                        <CardTitle className="text-xs text-slate-500 font-mono uppercase tracking-wider">Response Time (24h)</CardTitle>
                    </CardHeader>
                    <CardContent className="px-3 pb-3">
                        <ResponsiveContainer width="100%" height={180}>
                            <AreaChart data={chartData}>
                                <defs>
                                    <linearGradient id="rtGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#00E0FF" stopOpacity={0.2} />
                                        <stop offset="100%" stopColor="#00E0FF" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <XAxis dataKey="time" tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                                <YAxis tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} width={45} />
                                <Tooltip contentStyle={{ background: '#121826', border: '1px solid #2D3748', borderRadius: 8, fontSize: 11 }}
                                    formatter={(v) => [`${Math.round(v)}ms`, 'Response Time']} />
                                <Area type="monotone" dataKey="rt" stroke="#00E0FF" strokeWidth={2} fill="url(#rtGrad)" dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            )}

            {/* Check History */}
            <Card className="bg-[#121826] border-[#2D3748]/50" data-testid="check-history">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-white flex items-center gap-2">
                        <Clock className="w-4 h-4 text-amber-400" /> Check History
                        <Badge className="text-[9px] bg-white/5 text-slate-500 border-0">{results.length} checks</Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs font-mono">
                            <thead>
                                <tr className="border-b border-[#2D3748]/50 text-slate-500">
                                    <th className="text-left py-2 px-2">Status</th>
                                    <th className="text-left py-2 px-2">Type</th>
                                    <th className="text-right py-2 px-2">Response</th>
                                    <th className="text-left py-2 px-2">Steps</th>
                                    <th className="text-right py-2 px-2">Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.slice(0, 30).map((r, i) => (
                                    <tr key={r.id || i} className="border-b border-[#2D3748]/20 hover:bg-white/[0.02]">
                                        <td className="py-2 px-2">
                                            {r.is_up ? (
                                                <span className="flex items-center gap-1 text-emerald-400"><CheckCircle className="w-3 h-3" /> UP</span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-red-400"><XCircle className="w-3 h-3" /> DOWN</span>
                                            )}
                                        </td>
                                        <td className="py-2 px-2 text-slate-400">{r.check_type}</td>
                                        <td className="py-2 px-2 text-right text-white">{Math.round(r.response_time_ms)}ms</td>
                                        <td className="py-2 px-2">
                                            <div className="flex gap-0.5">
                                                {(r.steps || []).map((s, j) => (
                                                    <div key={j} className={`w-4 h-4 rounded-sm flex items-center justify-center text-[8px] ${s.status === 'pass' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}
                                                        title={`${s.step}: ${s.status}`}>
                                                        {s.status === 'pass' ? '✓' : '✗'}
                                                    </div>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="py-2 px-2 text-right text-slate-500">{r.timestamp ? new Date(r.timestamp).toLocaleString() : '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>

            {/* Auth Config Info */}
            {monitor.check_type !== 'http' && (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <Lock className="w-4 h-4 text-purple-400" /> Authentication Config
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                            <div>
                                <Label className="text-[10px] text-slate-500">Login URL</Label>
                                <p className="text-white/60 font-mono">{monitor.auth_config?.login_url || monitor.url}</p>
                            </div>
                            <div>
                                <Label className="text-[10px] text-slate-500">Username</Label>
                                <p className="text-white/60 font-mono">{monitor.auth_config?.username || '-'}</p>
                            </div>
                            {monitor.check_type === 'login_otp' && (
                                <div>
                                    <Label className="text-[10px] text-slate-500">OTP Type</Label>
                                    <p className="text-white/60 font-mono">TOTP (Time-based)</p>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

// ─── Summary Card ───
const SummaryCard = ({ label, value, icon: Icon, color }) => (
    <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 flex items-center gap-3">
        <div className="p-2 rounded-lg" style={{ backgroundColor: `${color}15` }}>
            <Icon className="w-4 h-4" style={{ color }} />
        </div>
        <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">{label}</p>
            <span className="text-lg font-bold text-white font-mono">{value ?? 0}</span>
        </div>
    </div>
);

// ─── Create Monitor Dialog ───
const CreateMonitorDialog = ({ show, onClose, form, setForm, onSave }) => (
    <Dialog open={show} onOpenChange={(open) => { if (!open) onClose(); }}>
        <DialogContent className="bg-[#0d1117] border-[#2D3748]/50 max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="monitor-form-dialog">
            <DialogHeader>
                <DialogTitle className="text-white flex items-center gap-2">
                    <Globe className="w-5 h-5 text-cyan-400" /> New Synthetic Monitor
                </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                        <Label className="text-[10px] text-slate-500 uppercase">Name</Label>
                        <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                            placeholder="e.g. Production API" className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="monitor-name-input" />
                    </div>
                    <div className="space-y-1.5">
                        <Label className="text-[10px] text-slate-500 uppercase">Check Type</Label>
                        <Select value={form.check_type} onValueChange={v => setForm({ ...form, check_type: v })}>
                            <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm" data-testid="check-type-select">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                <SelectItem value="http">HTTP Check</SelectItem>
                                <SelectItem value="login">Login Check</SelectItem>
                                <SelectItem value="login_otp">Login + OTP Check</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label className="text-[10px] text-slate-500 uppercase">URL</Label>
                    <Input value={form.url} onChange={e => setForm({ ...form, url: e.target.value })}
                        placeholder="https://example.com/health" className="bg-white/5 border-[#2D3748] h-9 text-sm font-mono" data-testid="monitor-url-input" />
                </div>

                <div className="grid grid-cols-3 gap-3">
                    <div className="space-y-1.5">
                        <Label className="text-[10px] text-slate-500 uppercase">Interval (sec)</Label>
                        <Select value={String(form.interval)} onValueChange={v => setForm({ ...form, interval: parseInt(v) })}>
                            <SelectTrigger className="bg-white/5 border-[#2D3748] h-9 text-sm"><SelectValue /></SelectTrigger>
                            <SelectContent className="bg-[#0d1117] border-[#2D3748]">
                                <SelectItem value="30">30 seconds</SelectItem>
                                <SelectItem value="60">1 minute</SelectItem>
                                <SelectItem value="120">2 minutes</SelectItem>
                                <SelectItem value="300">5 minutes</SelectItem>
                                <SelectItem value="600">10 minutes</SelectItem>
                                <SelectItem value="900">15 minutes</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-1.5">
                        <Label className="text-[10px] text-slate-500 uppercase">Expected Status</Label>
                        <Input type="number" value={form.expected_status} onChange={e => setForm({ ...form, expected_status: parseInt(e.target.value) || 200 })}
                            className="bg-white/5 border-[#2D3748] h-9 text-sm" />
                    </div>
                    <div className="space-y-1.5">
                        <Label className="text-[10px] text-slate-500 uppercase">Timeout (sec)</Label>
                        <Input type="number" value={form.timeout} onChange={e => setForm({ ...form, timeout: parseInt(e.target.value) || 30 })}
                            className="bg-white/5 border-[#2D3748] h-9 text-sm" />
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label className="text-[10px] text-slate-500 uppercase">Expected Text (optional)</Label>
                    <Input value={form.expected_text} onChange={e => setForm({ ...form, expected_text: e.target.value })}
                        placeholder="Text that must appear in response" className="bg-white/5 border-[#2D3748] h-9 text-sm" />
                </div>

                {/* Login Config */}
                {(form.check_type === 'login' || form.check_type === 'login_otp') && (
                    <div className="space-y-3 p-3 rounded-lg bg-white/[0.02] border border-[#2D3748]/30">
                        <p className="text-xs text-slate-500 font-mono uppercase tracking-wider flex items-center gap-1"><Lock className="w-3 h-3" /> Login Configuration</p>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500">Login URL</Label>
                                <Input value={form.auth_config.login_url || ''} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, login_url: e.target.value } })}
                                    placeholder="Login page URL" className="bg-white/5 border-[#2D3748] h-8 text-xs" data-testid="login-url-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500">Success Text</Label>
                                <Input value={form.auth_config.success_text || ''} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, success_text: e.target.value } })}
                                    placeholder="Text on success page" className="bg-white/5 border-[#2D3748] h-8 text-xs" />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500">Username</Label>
                                <Input value={form.auth_config.username || ''} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, username: e.target.value } })}
                                    className="bg-white/5 border-[#2D3748] h-8 text-xs" data-testid="auth-username-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-[10px] text-slate-500">Password</Label>
                                <Input type="password" value={form.auth_config.password || ''} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, password: e.target.value } })}
                                    className="bg-white/5 border-[#2D3748] h-8 text-xs" data-testid="auth-password-input" />
                            </div>
                        </div>

                        {form.check_type === 'login_otp' && (
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <Label className="text-[10px] text-slate-500">TOTP Secret Key</Label>
                                    <Input value={form.auth_config.otp_secret || ''} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, otp_secret: e.target.value } })}
                                        placeholder="Base32 secret (e.g. JBSWY3DPEHPK3PXP)" className="bg-white/5 border-[#2D3748] h-8 text-xs font-mono" data-testid="otp-secret-input" />
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="text-[10px] text-slate-500">OTP Field Name</Label>
                                    <Input value={form.auth_config.otp_field || 'otp'} onChange={e => setForm({ ...form, auth_config: { ...form.auth_config, otp_field: e.target.value } })}
                                        className="bg-white/5 border-[#2D3748] h-8 text-xs" />
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
            <DialogFooter>
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={onSave} data-testid="save-monitor-btn">Create Monitor</Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
);


// ═══════════════════════════════════════
//  MAIN PAGE
// ═══════════════════════════════════════

export const SyntheticMonitoringPage = () => {
    const [monitors, setMonitors] = useState([]);
    const [summary, setSummary] = useState({});
    const [selectedMonitor, setSelectedMonitor] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchAll = useCallback(async () => {
        try {
            setLoading(true);
            const res = await fetch(`${API_URL}/api/synthetic/dashboard`, { headers: getAuth() });
            const data = await res.json();
            setMonitors(data.monitors || []);
            setSummary(data.summary || {});
        } catch (e) { toast.error('Failed to load monitors'); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const handleSeed = async () => {
        try {
            await fetch(`${API_URL}/api/synthetic/seed`, { method: 'POST', headers: getAuth() });
            toast.success('Demo data seeded');
            fetchAll();
        } catch (e) { toast.error('Seed failed'); }
    };

    if (selectedMonitor) {
        return <MonitorDetail monitorId={selectedMonitor} onBack={() => { setSelectedMonitor(null); fetchAll(); }} />;
    }

    return <FleetView monitors={monitors} summary={summary} onSelect={setSelectedMonitor} onRefresh={fetchAll} onSeed={handleSeed} loading={loading} />;
};

export default SyntheticMonitoringPage;
