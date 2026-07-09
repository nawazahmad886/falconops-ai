import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Shield, RefreshCw, CheckCircle, XCircle, TrendingUp,
    AlertTriangle, Clock, BarChart3, Target, Activity, Eye,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

const COMPLIANCE_STYLES = {
    true: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', label: 'Compliant' },
    false: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', label: 'Breached' },
};

export default function SLADashboardPage() {
    const { api } = useAuth();
    const [overview, setOverview] = useState(null);
    const [selectedMonitor, setSelectedMonitor] = useState(null);
    const [monitorSLA, setMonitorSLA] = useState(null);
    const [incidents, setIncidents] = useState([]);
    const [months, setMonths] = useState('3');
    const [loading, setLoading] = useState(true);
    const [settingTarget, setSettingTarget] = useState(false);

    const fetchOverview = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get(`/sla/overview?months=${months}`);
            setOverview(res.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api, months]);

    const fetchMonitorSLA = useCallback(async (monitorId) => {
        try {
            const [sRes, iRes] = await Promise.all([
                api.get(`/sla/monitor/${monitorId}?months=${months}`),
                api.get(`/sla/incidents/${monitorId}?days=90`),
            ]);
            setMonitorSLA(sRes.data);
            setIncidents(iRes.data || []);
        } catch (e) { console.error(e); }
    }, [api, months]);

    const setSLATarget = useCallback(async (monitorId, target) => {
        setSettingTarget(true);
        try {
            await api.post('/sla/target', { monitor_id: monitorId, target });
            await fetchOverview();
            if (selectedMonitor === monitorId) await fetchMonitorSLA(monitorId);
        } catch (e) { console.error(e); }
        setSettingTarget(false);
    }, [api, fetchOverview, fetchMonitorSLA, selectedMonitor]);

    useEffect(() => { fetchOverview(); }, [fetchOverview]);
    useEffect(() => { if (selectedMonitor) fetchMonitorSLA(selectedMonitor); }, [selectedMonitor, fetchMonitorSLA]);

    const monthlyChart = monitorSLA?.monthly?.map(m => ({
        name: m.month_label?.split(' ')[0]?.slice(0, 3) || m.month,
        uptime: m.uptime_pct,
        target: m.target_pct,
        breached: m.breached,
    })) || [];

    return (
        <div className="space-y-6" data-testid="sla-dashboard-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><Shield className="w-6 h-6 text-emerald-400" /></div>
                        SLA Dashboard
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Service Level Agreement compliance tracking</p>
                </div>
                <div className="flex gap-2 items-center">
                    <Select value={months} onValueChange={setMonths}>
                        <SelectTrigger className="w-32 bg-white/5 border-white/10 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-[#0D1117] border-white/10">
                            <SelectItem value="1">1 Month</SelectItem>
                            <SelectItem value="3">3 Months</SelectItem>
                            <SelectItem value="6">6 Months</SelectItem>
                            <SelectItem value="12">12 Months</SelectItem>
                        </SelectContent>
                    </Select>
                    <Button variant="outline" size="sm" onClick={fetchOverview} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
                </div>
            </div>

            {/* Overview Stats */}
            {overview && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><BarChart3 className="w-4 h-4 text-blue-400" /></div>
                        <div><p className="text-xs text-white/50">Monitors</p><p className="text-lg font-bold text-white">{overview.total_monitors}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><CheckCircle className="w-4 h-4 text-emerald-400" /></div>
                        <div><p className="text-xs text-white/50">Compliant</p><p className="text-lg font-bold text-emerald-400">{overview.compliant}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><XCircle className="w-4 h-4 text-red-400" /></div>
                        <div><p className="text-xs text-white/50">Breached</p><p className="text-lg font-bold text-red-400">{overview.breached}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/15"><TrendingUp className="w-4 h-4 text-cyan-400" /></div>
                        <div><p className="text-xs text-white/50">Compliance Rate</p><p className="text-lg font-bold text-cyan-400">{overview.compliance_rate}%</p></div>
                    </CardContent></Card>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Monitor List */}
                <div className="space-y-3">
                    <h2 className="text-sm font-semibold text-white/60">Monitor SLA Status</h2>
                    {overview?.monitors?.map(mon => {
                        const cs = COMPLIANCE_STYLES[mon.compliant];
                        return (
                            <Card key={mon.monitor_id} className={`bg-[#0D1117] border-white/5 cursor-pointer transition-all hover:border-white/15 ${selectedMonitor === mon.monitor_id ? 'ring-1 ring-emerald-500/30' : ''}`}
                                onClick={() => setSelectedMonitor(mon.monitor_id)} data-testid={`sla-monitor-${mon.monitor_id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <h3 className="text-sm font-semibold text-white truncate">{mon.name}</h3>
                                        <Badge className={`text-[9px] ${cs.bg} ${cs.text} ${cs.border}`}>{cs.label}</Badge>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className={`text-xl font-bold ${mon.uptime_pct >= mon.sla_target ? 'text-emerald-400' : 'text-red-400'}`}>{mon.uptime_pct}%</p>
                                            <p className="text-[10px] text-white/30">Target: {mon.sla_target}%</p>
                                        </div>
                                        <div className="w-16 h-16">
                                            <div className="relative w-full h-full">
                                                <svg viewBox="0 0 36 36" className="w-full h-full">
                                                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                                                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                                        fill="none" stroke={mon.compliant ? '#22c55e' : '#ef4444'} strokeWidth="3"
                                                        strokeDasharray={`${mon.uptime_pct}, 100`} strokeLinecap="round" />
                                                </svg>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                    {(!overview?.monitors || overview.monitors.length === 0) && (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-6 text-center text-white/40 text-xs">No monitors with SLA tracking</CardContent></Card>
                    )}
                </div>

                {/* Detail Panel */}
                <div className="lg:col-span-2 space-y-4">
                    {monitorSLA ? (
                        <>
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-3 border-b border-white/5">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-base flex items-center gap-2"><Target className="w-4 h-4 text-emerald-400" /> {monitorSLA.monitor_name}</CardTitle>
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-white/40">SLA Target:</span>
                                            <Select value={String(monitorSLA.sla_target)} onValueChange={v => setSLATarget(monitorSLA.monitor_id, v)} disabled={settingTarget}>
                                                <SelectTrigger className="w-32 bg-white/5 border-white/10 text-xs h-7"><SelectValue /></SelectTrigger>
                                                <SelectContent className="bg-[#0D1117] border-white/10">
                                                    {overview?.targets_available?.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-4">
                                    <div className="flex items-center gap-6 mb-4">
                                        <div>
                                            <p className="text-xs text-white/50">Overall Uptime</p>
                                            <p className={`text-3xl font-bold ${monitorSLA.overall_compliant ? 'text-emerald-400' : 'text-red-400'}`}>{monitorSLA.overall_uptime_pct}%</p>
                                        </div>
                                        <Badge className={monitorSLA.overall_compliant ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30'}>
                                            {monitorSLA.overall_compliant ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                                            {monitorSLA.overall_compliant ? 'SLA Met' : 'SLA Breached'}
                                        </Badge>
                                        {monitorSLA.months_breached > 0 && <span className="text-xs text-red-400">{monitorSLA.months_breached} month(s) breached</span>}
                                    </div>
                                    {monthlyChart.length > 0 && (
                                        <ResponsiveContainer width="100%" height={200}>
                                            <BarChart data={monthlyChart}>
                                                <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                                <YAxis domain={[99, 100]} tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                                <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff', fontSize: 11 }} />
                                                <Bar dataKey="uptime" radius={[4, 4, 0, 0]}>
                                                    {monthlyChart.map((entry, i) => <Cell key={i} fill={entry.breached ? '#ef4444' : '#22c55e'} />)}
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    )}
                                </CardContent>
                            </Card>

                            {/* Monthly Breakdown */}
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Clock className="w-4 h-4 text-white/60" /> Monthly Breakdown</CardTitle></CardHeader>
                                <CardContent className="p-0 divide-y divide-white/5">
                                    {monitorSLA.monthly?.map((m, i) => (
                                        <div key={m.month} className="p-3 hover:bg-white/[0.02]" data-testid={`sla-month-${i}`}>
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-1 rounded ${m.breached ? 'bg-red-500/10' : 'bg-emerald-500/10'}`}>
                                                        {m.breached ? <XCircle className="w-3.5 h-3.5 text-red-400" /> : <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />}
                                                    </div>
                                                    <div>
                                                        <p className="text-sm text-white/80">{m.month_label}</p>
                                                        <p className="text-[10px] text-white/30">{m.total_checks} checks | {m.failures} failures</p>
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <p className={`text-sm font-bold ${m.breached ? 'text-red-400' : 'text-emerald-400'}`}>{m.uptime_pct}%</p>
                                                    <p className="text-[10px] text-white/30">Budget: {m.remaining_budget_min}min left</p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>

                            {/* Incidents */}
                            {incidents.length > 0 && (
                                <Card className="bg-[#0D1117] border-white/5">
                                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-red-400" /> Incident Timeline</CardTitle></CardHeader>
                                    <CardContent className="p-0 divide-y divide-white/5">
                                        {incidents.map((inc, i) => (
                                            <div key={i} className="p-3 flex items-center justify-between" data-testid={`incident-${i}`}>
                                                <div className="flex items-center gap-3">
                                                    <div className="p-1 rounded bg-red-500/10"><AlertTriangle className="w-3.5 h-3.5 text-red-400" /></div>
                                                    <div>
                                                        <p className="text-xs text-white/70">Downtime: {inc.start ? new Date(inc.start).toLocaleString() : ''}</p>
                                                        <p className="text-[10px] text-white/30">{inc.end === 'ongoing' ? 'Ongoing' : `Recovered: ${inc.end ? new Date(inc.end).toLocaleTimeString() : ''}`}</p>
                                                    </div>
                                                </div>
                                                <Badge className={inc.end === 'ongoing' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'}>
                                                    {inc.duration_min != null ? `${inc.duration_min}min` : 'Ongoing'}
                                                </Badge>
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-12 text-center text-white/40">
                            <Shield className="w-10 h-10 mx-auto mb-3 opacity-30" /><p>Select a monitor to view SLA details</p>
                        </CardContent></Card>
                    )}
                </div>
            </div>
        </div>
    );
}
