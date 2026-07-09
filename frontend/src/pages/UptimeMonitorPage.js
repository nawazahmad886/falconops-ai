import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Globe, RefreshCw, Plus, Trash2, CheckCircle, XCircle,
    Clock, Activity, Zap, Eye, BarChart3, Play, Pause,
    ArrowUpCircle, ArrowDownCircle, TrendingUp, Bell,
    Map, Settings, AlertTriangle, Webhook, Mail, X,
} from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
    BarChart, Bar,
} from 'recharts';

const STATUS_STYLES = {
    up: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', icon: ArrowUpCircle },
    down: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', icon: ArrowDownCircle },
    pending: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', icon: Clock },
};

export default function UptimeMonitorPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('monitors');
    const [monitors, setMonitors] = useState([]);
    const [stats, setStats] = useState(null);
    const [regions, setRegions] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAdd, setShowAdd] = useState(false);
    const [checking, setChecking] = useState(null);
    const [selectedMonitor, setSelectedMonitor] = useState(null);
    const [history, setHistory] = useState([]);
    const [timeseries, setTimeseries] = useState(null);
    const [tsHours, setTsHours] = useState(24);
    const [regionStats, setRegionStats] = useState([]);
    const [editingMonitor, setEditingMonitor] = useState(null);
    const [form, setForm] = useState({
        name: '', url: '', interval: '60', method: 'GET', expected_status: '200', timeout: '10',
        regions: ['us-east'], consecutive_failures: '3', alert_channels: [],
    });
    const [channelForm, setChannelForm] = useState({ type: 'webhook', url: '', address: '', webhook_url: '' });

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [mRes, sRes, rRes, aRes] = await Promise.all([
                api.get('/uptime/monitors'),
                api.get('/uptime/stats'),
                api.get('/uptime/regions'),
                api.get('/uptime/alerts?limit=30'),
            ]);
            setMonitors(mRes.data || []);
            setStats(sRes.data);
            setRegions(rRes.data || []);
            setAlerts(aRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchHistory = useCallback(async (monitorId) => {
        try {
            const [hRes, rRes, tsRes] = await Promise.all([
                api.get(`/uptime/monitors/${monitorId}/history?hours=${tsHours}&limit=200`),
                api.get(`/uptime/monitors/${monitorId}/regions?hours=${tsHours}`),
                api.get(`/uptime/monitors/${monitorId}/timeseries?hours=${tsHours}`),
            ]);
            setHistory(hRes.data || []);
            setRegionStats(rRes.data || []);
            setTimeseries(tsRes.data);
        } catch (e) { console.error(e); }
    }, [api, tsHours]);

    const addMonitor = useCallback(async () => {
        try {
            await api.post('/uptime/monitors', {
                ...form,
                interval: parseInt(form.interval),
                expected_status: parseInt(form.expected_status),
                timeout: parseInt(form.timeout),
                consecutive_failures: parseInt(form.consecutive_failures),
            });
            setShowAdd(false);
            setForm({ name: '', url: '', interval: '60', method: 'GET', expected_status: '200', timeout: '10', regions: ['us-east'], consecutive_failures: '3', alert_channels: [] });
            await fetchData();
        } catch (e) { console.error(e); }
    }, [api, form, fetchData]);

    const deleteMonitor = useCallback(async (id) => { try { await api.delete(`/uptime/monitors/${id}`); setSelectedMonitor(null); await fetchData(); } catch (e) { console.error(e); } }, [api, fetchData]);
    const checkNow = useCallback(async (id) => { setChecking(id); try { await api.post(`/uptime/monitors/${id}/check`); await fetchData(); if (selectedMonitor === id) await fetchHistory(id); } catch (e) { console.error(e); } setChecking(null); }, [api, fetchData, fetchHistory, selectedMonitor]);
    const toggleMonitor = useCallback(async (id) => { try { await api.post(`/uptime/monitors/${id}/toggle`); await fetchData(); } catch (e) { console.error(e); } }, [api, fetchData]);

    const updateMonitor = useCallback(async (id, updates) => {
        try { await api.put(`/uptime/monitors/${id}`, updates); setEditingMonitor(null); await fetchData(); } catch (e) { console.error(e); }
    }, [api, fetchData]);

    const addChannel = () => {
        const ch = {};
        if (channelForm.type === 'webhook') ch.type = 'webhook'; ch.url = channelForm.url;
        if (channelForm.type === 'email') { ch.type = 'email'; ch.address = channelForm.address; }
        if (channelForm.type === 'slack') { ch.type = 'slack'; ch.webhook_url = channelForm.webhook_url; }
        setForm(p => ({ ...p, alert_channels: [...p.alert_channels, { type: channelForm.type, ...ch }] }));
        setChannelForm({ type: 'webhook', url: '', address: '', webhook_url: '' });
    };

    const removeChannel = (i) => setForm(p => ({ ...p, alert_channels: p.alert_channels.filter((_, idx) => idx !== i) }));
    const toggleRegion = (regionId) => setForm(p => ({ ...p, regions: p.regions.includes(regionId) ? p.regions.filter(r => r !== regionId) : [...p.regions, regionId] }));

    useEffect(() => { fetchData(); const i = setInterval(fetchData, 30000); return () => clearInterval(i); }, [fetchData]);
    useEffect(() => { if (selectedMonitor) fetchHistory(selectedMonitor); }, [selectedMonitor, fetchHistory, tsHours]);

    const chartData = (timeseries?.series || []).map(s => ({
        time: new Date(s.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        response_time: s.avg_response_time_ms,
        max_response_time: s.max_response_time_ms,
        uptime: s.uptime_pct,
        success: s.success, fail: s.fail, reason: s.failure_reasons?.[0] || '',
    }));
    const tabs = [
        { id: 'monitors', label: 'Monitors', icon: Globe },
        { id: 'alerts', label: 'Alert History', icon: Bell },
        { id: 'regions', label: 'Regions', icon: Map },
    ];

    return (
        <div className="space-y-6" data-testid="uptime-monitor-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><Globe className="w-6 h-6 text-emerald-400" /></div>
                        Uptime Monitor
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Multi-region URL monitoring with alerts & response tracking</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs" data-testid="refresh-uptime-btn">
                        <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => setShowAdd(!showAdd)} className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs" data-testid="add-monitor-btn">
                        <Plus className="w-3 h-3 mr-1" /> Add Monitor
                    </Button>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                    { label: 'Total', value: stats?.total_monitors ?? 0, icon: BarChart3, color: 'blue' },
                    { label: 'Up', value: stats?.up ?? 0, icon: ArrowUpCircle, color: 'emerald' },
                    { label: 'Down', value: stats?.down ?? 0, icon: ArrowDownCircle, color: 'red' },
                    { label: 'Avg Uptime', value: `${stats?.avg_uptime_pct ?? 0}%`, icon: TrendingUp, color: 'cyan' },
                    { label: 'Checks (24h)', value: stats?.total_checks_period ?? 0, icon: Activity, color: 'amber' },
                ].map(s => (
                    <Card key={s.label} className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className={`p-2 rounded-lg bg-${s.color}-500/15`}><s.icon className={`w-4 h-4 text-${s.color}-400`} /></div>
                        <div><p className="text-xs text-white/50">{s.label}</p><p className={`text-lg font-bold ${s.color === 'red' && stats?.down > 0 ? 'text-red-400' : 'text-white'}`}>{s.value}</p></div>
                    </CardContent></Card>
                ))}
            </div>

            {/* Add Monitor Form */}
            {showAdd && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="add-monitor-form">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Plus className="w-4 h-4 text-emerald-400" /> New Monitor</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="My Website" data-testid="monitor-name-input" /></div>
                            <div className="md:col-span-2"><Label className="text-xs text-white/60">URL</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.url} onChange={e => setForm(p => ({ ...p, url: e.target.value }))} placeholder="https://example.com" data-testid="monitor-url-input" /></div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            <div><Label className="text-xs text-white/60">Interval (s)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.interval} onChange={e => setForm(p => ({ ...p, interval: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Method</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.method} onChange={e => setForm(p => ({ ...p, method: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Expected Status</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.expected_status} onChange={e => setForm(p => ({ ...p, expected_status: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Timeout (s)</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.timeout} onChange={e => setForm(p => ({ ...p, timeout: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Fail Threshold</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.consecutive_failures} onChange={e => setForm(p => ({ ...p, consecutive_failures: e.target.value }))} /></div>
                        </div>

                        {/* Region Selection */}
                        <div>
                            <Label className="text-xs text-white/60 mb-2 block">Check Regions</Label>
                            <div className="flex flex-wrap gap-2">
                                {regions.map(r => (
                                    <Button key={r.id} variant="outline" size="sm"
                                        onClick={() => toggleRegion(r.id)}
                                        className={`text-[10px] ${form.regions.includes(r.id) ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'text-white/40 border-white/10'}`}
                                        data-testid={`region-${r.id}`}>
                                        <Map className="w-3 h-3 mr-1" /> {r.name}
                                    </Button>
                                ))}
                            </div>
                        </div>

                        {/* Alert Channels */}
                        <div>
                            <Label className="text-xs text-white/60 mb-2 block">Alert Channels (notify on failure)</Label>
                            {form.alert_channels.map((ch, i) => (
                                <div key={i} className="flex items-center gap-2 mb-1">
                                    <Badge variant="outline" className="text-[10px] text-white/50 border-white/10">{ch.type}</Badge>
                                    <span className="text-[10px] text-white/40 truncate">{ch.url || ch.address || ch.webhook_url}</span>
                                    <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => removeChannel(i)}><X className="w-3 h-3 text-red-400" /></Button>
                                </div>
                            ))}
                            <div className="flex gap-2 mt-2">
                                <select className="bg-[#161B22] border border-white/10 rounded text-xs text-white/60 px-2 py-1" value={channelForm.type} onChange={e => setChannelForm(p => ({ ...p, type: e.target.value }))}>
                                    <option value="webhook">Webhook</option>
                                    <option value="email">Email</option>
                                    <option value="slack">Slack</option>
                                    <option value="whatsapp">WhatsApp</option>
                                </select>
                                {channelForm.type === 'webhook' && <Input className="bg-[#161B22] border-white/10 text-xs flex-1" placeholder="https://hooks.example.com/..." value={channelForm.url} onChange={e => setChannelForm(p => ({ ...p, url: e.target.value }))} data-testid="channel-url-input" />}
                                {channelForm.type === 'email' && <Input className="bg-[#161B22] border-white/10 text-xs flex-1" placeholder="alert@example.com" value={channelForm.address} onChange={e => setChannelForm(p => ({ ...p, address: e.target.value }))} />}
                                {channelForm.type === 'slack' && <Input className="bg-[#161B22] border-white/10 text-xs flex-1" placeholder="https://hooks.slack.com/..." value={channelForm.webhook_url} onChange={e => setChannelForm(p => ({ ...p, webhook_url: e.target.value }))} />}
                                {channelForm.type === 'whatsapp' && <Input className="bg-[#161B22] border-white/10 text-xs flex-1" placeholder="+966XXXXXXXXX" value={channelForm.to_number || ''} onChange={e => setChannelForm(p => ({ ...p, to_number: e.target.value }))} data-testid="whatsapp-number-input" />}
                                <Button variant="outline" size="sm" className="border-white/10 text-xs" onClick={addChannel} data-testid="add-channel-btn"><Plus className="w-3 h-3" /></Button>
                            </div>
                        </div>

                        <Button onClick={addMonitor} disabled={!form.name || !form.url} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="submit-monitor-btn"><CheckCircle className="w-3 h-3 mr-1" /> Create Monitor</Button>
                    </CardContent>
                </Card>
            )}

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {/* Monitors Tab */}
            {tab === 'monitors' && (
                <div className="grid grid-cols-1 gap-3">
                    {monitors.length === 0 && !loading && (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-8 text-center text-white/40"><Globe className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No monitors yet.</p></CardContent></Card>
                    )}
                    {monitors.map(mon => {
                        const st = STATUS_STYLES[mon.status] || STATUS_STYLES.pending;
                        const StIcon = st.icon;
                        const isSelected = selectedMonitor === mon.id;
                        return (
                            <Card key={mon.id} className={`bg-[#0D1117] border-white/5 transition-all cursor-pointer hover:border-white/15 ${isSelected ? 'ring-1 ring-emerald-500/30' : ''}`}
                                onClick={() => setSelectedMonitor(isSelected ? null : mon.id)} data-testid={`monitor-card-${mon.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <div className={`p-2 rounded-lg ${st.bg}`}><StIcon className={`w-5 h-5 ${st.text}`} /></div>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <h3 className="text-sm font-semibold text-white">{mon.name}</h3>
                                                    <Badge className={`text-[9px] ${st.bg} ${st.text} ${st.border}`}>{mon.status}</Badge>
                                                    {mon.alert_active && <Badge className="text-[9px] bg-red-500/15 text-red-400 border-red-500/30"><Bell className="w-2.5 h-2.5 mr-0.5" /> Alerting</Badge>}
                                                    {!mon.enabled && <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">Disabled</Badge>}
                                                </div>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <p className="text-[10px] text-white/40 font-mono truncate max-w-xs">{mon.url}</p>
                                                    {mon.regions?.map(r => <Badge key={r} variant="outline" className="text-[8px] text-white/30 border-white/10">{r}</Badge>)}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4">
                                            <div className="text-right hidden md:block"><p className="text-xs text-white/50">Response</p><p className="text-sm font-bold text-white">{mon.last_response_time != null ? `${mon.last_response_time}ms` : '—'}</p></div>
                                            <div className="text-right hidden md:block"><p className="text-xs text-white/50">Uptime</p><p className={`text-sm font-bold ${mon.uptime_pct >= 99 ? 'text-emerald-400' : mon.uptime_pct >= 95 ? 'text-amber-400' : 'text-red-400'}`}>{mon.uptime_pct}%</p></div>
                                            <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => checkNow(mon.id)} disabled={checking === mon.id} data-testid={`check-now-${mon.id}`}>
                                                    {checking === mon.id ? <RefreshCw className="w-3 h-3 animate-spin text-white/50" /> : <Play className="w-3 h-3 text-white/50" />}
                                                </Button>
                                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => toggleMonitor(mon.id)}>
                                                    {mon.enabled ? <Pause className="w-3 h-3 text-amber-400" /> : <Play className="w-3 h-3 text-emerald-400" />}
                                                </Button>
                                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteMonitor(mon.id)} data-testid={`delete-${mon.id}`}>
                                                    <Trash2 className="w-3 h-3 text-red-400" />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                    {isSelected && (
                                        <div className="mt-4 pt-4 border-t border-white/5 space-y-3">
                                            <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-xs">
                                                <div><span className="text-white/40">Method:</span> <span className="text-white/70">{mon.method}</span></div>
                                                <div><span className="text-white/40">Interval:</span> <span className="text-white/70">{mon.interval}s</span></div>
                                                <div><span className="text-white/40">Expected:</span> <span className="text-white/70">{mon.expected_status}</span></div>
                                                <div><span className="text-white/40">Checks:</span> <span className="text-white/70">{mon.total_checks}</span></div>
                                                <div><span className="text-white/40">Fail Threshold:</span> <span className="text-white/70">{mon.consecutive_failures}</span></div>
                                                <div><span className="text-white/40">Alert Channels:</span> <span className="text-white/70">{mon.alert_channels?.length || 0}</span></div>
                                            </div>

                                            {/* Advanced status strip — assertions, SSL, last failure */}
                                            <div className="flex flex-wrap items-center gap-2 text-[11px]" data-testid={`mon-status-strip-${mon.id}`}>
                                                <Badge variant="outline" className="border-cyan-500/20 text-cyan-400 text-[10px]">
                                                    {mon.assertions?.length || 0} assertions
                                                </Badge>
                                                {mon.max_response_time_ms && (
                                                    <Badge variant="outline" className="border-purple-500/20 text-purple-400 text-[10px]">
                                                        SLA ≤ {mon.max_response_time_ms}ms
                                                    </Badge>
                                                )}
                                                {mon.last_ssl_days_remaining !== null && mon.last_ssl_days_remaining !== undefined && (
                                                    <Badge variant="outline" className={`text-[10px] ${
                                                        mon.last_ssl_days_remaining < 14
                                                            ? 'border-red-500/30 text-red-400'
                                                            : 'border-emerald-500/20 text-emerald-400'
                                                    }`}>
                                                        SSL: {mon.last_ssl_days_remaining}d left
                                                    </Badge>
                                                )}
                                                {mon.last_failure_reason && mon.status === 'down' && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-500/10 border border-red-500/25 text-red-400">
                                                        <AlertTriangle className="w-2.5 h-2.5" />
                                                        {mon.last_failure_reason}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Time range selector */}
                                            <div className="flex items-center justify-between pt-1">
                                                <p className="text-xs text-white/50">Historical metrics</p>
                                                <div className="flex items-center gap-1 p-1 bg-black/30 rounded-lg border border-white/5">
                                                    {[1, 6, 24, 72, 168].map(h => (
                                                        <button
                                                            key={h}
                                                            onClick={(e) => { e.stopPropagation(); setTsHours(h); }}
                                                            data-testid={`ts-range-${h < 24 ? `${h}h` : h === 168 ? '7d' : `${h / 24}d`}`}
                                                            className={`px-2 py-0.5 text-[10px] font-mono rounded transition ${
                                                                tsHours === h
                                                                    ? 'bg-[#F5B841]/20 text-[#F5B841] border border-[#F5B841]/40'
                                                                    : 'text-white/40 hover:text-white/70'
                                                            }`}
                                                        >
                                                            {h < 24 ? `${h}h` : h === 168 ? '7d' : `${h / 24}d`}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* Summary mini-cards */}
                                            {timeseries?.summary && (
                                                <div className="grid grid-cols-4 gap-2 text-[11px]">
                                                    <div className="p-2 bg-black/30 rounded">
                                                        <div className="text-white/40">Total</div>
                                                        <div className="text-white font-semibold">{timeseries.summary.total_checks}</div>
                                                    </div>
                                                    <div className="p-2 bg-emerald-500/[0.06] border border-emerald-500/20 rounded">
                                                        <div className="text-emerald-400/70">Success</div>
                                                        <div className="text-emerald-400 font-semibold">{timeseries.summary.successful}</div>
                                                    </div>
                                                    <div className="p-2 bg-red-500/[0.06] border border-red-500/20 rounded">
                                                        <div className="text-red-400/70">Failed</div>
                                                        <div className="text-red-400 font-semibold">{timeseries.summary.failed}</div>
                                                    </div>
                                                    <div className="p-2 bg-cyan-500/[0.06] border border-cyan-500/20 rounded">
                                                        <div className="text-cyan-400/70">Uptime %</div>
                                                        <div className="text-cyan-400 font-semibold">{timeseries.summary.uptime_pct}%</div>
                                                    </div>
                                                </div>
                                            )}

                                            {/* Region Stats */}
                                            {regionStats.length > 0 && (
                                                <div>
                                                    <p className="text-xs text-white/50 mb-2">Per-Region Latency (avg)</p>
                                                    <ResponsiveContainer width="100%" height={120}>
                                                        <BarChart data={regionStats}>
                                                            <XAxis dataKey="region" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} axisLine={false} />
                                                            <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} axisLine={false} unit="ms" />
                                                            <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff', fontSize: 11 }} />
                                                            <Bar dataKey="avg_response_ms" fill="#22c55e" radius={[4, 4, 0, 0]} />
                                                        </BarChart>
                                                    </ResponsiveContainer>
                                                </div>
                                            )}
                                            {chartData.length > 0 && (
                                                <div>
                                                    <p className="text-xs text-white/50 mb-2">
                                                        Response Time · bucketed {timeseries?.bucket_minutes || 15}m
                                                    </p>
                                                    <ResponsiveContainer width="100%" height={140}>
                                                        <AreaChart data={chartData}>
                                                            <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} axisLine={false} />
                                                            <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 9 }} axisLine={false} unit="ms" />
                                                            <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff', fontSize: 11 }}
                                                                formatter={(v, name) => [v, name === 'response_time' ? 'Avg ms' : 'Max ms']} />
                                                            <Area type="monotone" dataKey="max_response_time" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.08} strokeWidth={1} />
                                                            <Area type="monotone" dataKey="response_time" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} strokeWidth={1.5} />
                                                        </AreaChart>
                                                    </ResponsiveContainer>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Alert History Tab */}
            {tab === 'alerts' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Bell className="w-4 h-4 text-red-400" /> Alert History <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{alerts.length}</Badge></CardTitle></CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[500px] overflow-y-auto divide-y divide-white/5" data-testid="alert-list">
                            {alerts.length === 0 ? (
                                <div className="p-8 text-center text-white/40"><Bell className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No alerts fired yet. Configure alert channels on your monitors.</p></div>
                            ) : alerts.map((a, i) => (
                                <div key={a.id || i} className="flex items-start gap-3 p-3 hover:bg-white/[0.02]" data-testid={`alert-${i}`}>
                                    <div className={`p-1.5 rounded ${a.alert_type === 'down' ? 'bg-red-500/10' : 'bg-emerald-500/10'}`}>
                                        {a.alert_type === 'down' ? <ArrowDownCircle className="w-3.5 h-3.5 text-red-400" /> : <ArrowUpCircle className="w-3.5 h-3.5 text-emerald-400" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-white/80">{a.monitor_name}</span>
                                            <Badge className={a.alert_type === 'down' ? 'text-[9px] bg-red-500/15 text-red-400 border-red-500/30' : 'text-[9px] bg-emerald-500/15 text-emerald-400 border-emerald-500/30'}>{a.alert_type}</Badge>
                                        </div>
                                        <p className="text-[10px] text-white/40 truncate">{a.url}</p>
                                        {a.channels_notified?.length > 0 && <div className="flex gap-1 mt-1">{a.channels_notified.map((ch, j) => <Badge key={j} variant="outline" className="text-[8px] text-white/30 border-white/10">{ch.type}: {ch.status}</Badge>)}</div>}
                                    </div>
                                    <span className="text-[10px] text-white/25 whitespace-nowrap">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Regions Tab */}
            {tab === 'regions' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {regions.map(r => (
                        <Card key={r.id} className="bg-[#0D1117] border-white/5" data-testid={`region-card-${r.id}`}>
                            <CardContent className="p-4">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className="p-2 rounded-lg bg-cyan-500/10"><Map className="w-4 h-4 text-cyan-400" /></div>
                                    <div><h3 className="text-sm font-semibold text-white">{r.name}</h3><p className="text-[10px] text-white/40">{r.id}</p></div>
                                </div>
                                <p className="text-xs text-white/50">Latency offset: +{r.latency_offset}ms</p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
