import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Fingerprint, Users, AlertTriangle, Shield, RefreshCw, ChevronRight, 
    Clock, Globe, Lock, Zap, Server, Eye, Activity, Target,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend, RadarChart, Radar, PolarGrid,
    PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

const RISK_COLORS = {
    critical: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', fill: '#ef4444' },
    high: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', fill: '#f97316' },
    medium: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', fill: '#eab308' },
    low: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30', fill: '#22c55e' },
};

const PIE_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e'];

export default function UEBAPage() {
    const { api } = useAuth();
    const [loading, setLoading] = useState(true);
    const [summary, setSummary] = useState(null);
    const [profiles, setProfiles] = useState([]);
    const [selectedUser, setSelectedUser] = useState(null);
    const [userDetail, setUserDetail] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [sumRes, profRes] = await Promise.all([
                api.get('/security/ueba/summary?hours=168'),
                api.get('/security/ueba/profiles?hours=168'),
            ]);
            setSummary(sumRes.data);
            setProfiles(profRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const viewUser = async (username) => {
        setSelectedUser(username);
        try {
            const res = await api.get(`/security/ueba/user/${username}?hours=168`);
            setUserDetail(res.data);
        } catch (e) { console.error(e); }
    };

    if (loading) return <div className="flex items-center justify-center h-64 text-white/40">Loading UEBA data...</div>;

    return (
        <div className="space-y-6" data-testid="ueba-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="ueba-title">
                        <Fingerprint className="w-7 h-7 text-purple-400" />
                        User Behavior Analytics
                    </h1>
                    <p className="text-sm text-white/40 mt-1">Behavioral profiling, anomaly detection & risk scoring</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchData} className="border-white/10 text-xs" data-testid="ueba-refresh">
                    <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardContent className="p-4 text-center">
                            <p className="text-xs text-white/40">Total Users</p>
                            <p className="text-2xl font-bold text-white mt-1">{summary.total_users}</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0D1117] border-red-500/20">
                        <CardContent className="p-4 text-center">
                            <p className="text-xs text-red-400">Critical Risk</p>
                            <p className="text-2xl font-bold text-red-400 mt-1">{summary.critical_count}</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0D1117] border-orange-500/20">
                        <CardContent className="p-4 text-center">
                            <p className="text-xs text-orange-400">High Risk</p>
                            <p className="text-2xl font-bold text-orange-400 mt-1">{summary.high_count}</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0D1117] border-amber-500/20">
                        <CardContent className="p-4 text-center">
                            <p className="text-xs text-amber-400">Medium Risk</p>
                            <p className="text-2xl font-bold text-amber-400 mt-1">{summary.medium_count}</p>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0D1117] border-emerald-500/20">
                        <CardContent className="p-4 text-center">
                            <p className="text-xs text-emerald-400">Low Risk</p>
                            <p className="text-2xl font-bold text-emerald-400 mt-1">{summary.low_count}</p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Charts Row */}
            <div className="grid lg:grid-cols-3 gap-4">
                {/* Risk Distribution */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Risk Distribution</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-52">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={summary?.risk_distribution || []} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="count" nameKey="level" paddingAngle={2}>
                                        {(summary?.risk_distribution || []).map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                    </Pie>
                                    <Legend wrapperStyle={{ fontSize: 11, color: '#ffffff60' }} />
                                    <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                {/* Top Risk Factors */}
                <Card className="lg:col-span-2 bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Top Risk Factors</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-52">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={summary?.top_risk_factors?.slice(0, 6) || []} layout="vertical">
                                    <XAxis type="number" tick={{ fill: '#ffffff40', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <YAxis type="category" dataKey="factor" tick={{ fill: '#ffffff60', fontSize: 10 }} axisLine={false} tickLine={false} width={180} />
                                    <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                    <Bar dataKey="count" fill="#a855f7" radius={[0, 4, 4, 0]} barSize={16} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* User Profiles + Detail */}
            <div className="grid lg:grid-cols-5 gap-4">
                {/* User List */}
                <div className="lg:col-span-2 space-y-2">
                    <h3 className="text-sm font-medium text-white/60 mb-3">User Risk Profiles</h3>
                    {profiles.map((p, i) => {
                        const rc = RISK_COLORS[p.risk_level] || RISK_COLORS.low;
                        const active = selectedUser === p.user;
                        return (
                            <div
                                key={p.user}
                                onClick={() => viewUser(p.user)}
                                className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all ${
                                    active ? 'bg-white/5 border-purple-500/40' : 'bg-[#0D1117] border-white/5 hover:border-white/10'
                                }`}
                                data-testid={`user-profile-${i}`}
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${rc.bg} ${rc.text}`}>
                                        {p.risk_score}
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-white/80 truncate">{p.user}</p>
                                        <p className="text-[10px] text-white/30">{p.total_events} events | {p.unique_ips} IPs</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge className={`${rc.bg} ${rc.text} ${rc.border} border text-[9px] px-1.5`}>{p.risk_level}</Badge>
                                    <ChevronRight className="w-3.5 h-3.5 text-white/20" />
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* User Detail */}
                <div className="lg:col-span-3 space-y-4">
                    {userDetail ? (
                        <>
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium text-white/60 flex items-center gap-2">
                                        <Eye className="w-4 h-4" /> {userDetail.user} - Activity Timeline
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="h-40">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={userDetail.hourly_distribution || []}>
                                                <XAxis dataKey="hour" tick={{ fill: '#ffffff30', fontSize: 8 }} axisLine={false} tickLine={false} interval={2} />
                                                <YAxis tick={{ fill: '#ffffff30', fontSize: 10 }} axisLine={false} tickLine={false} />
                                                <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                                <Bar dataKey="count" fill="#a855f7" radius={[2, 2, 0, 0]} barSize={12} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Action Breakdown */}
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium text-white/60">Action Breakdown</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-wrap gap-2">
                                        {(userDetail.action_breakdown || []).map((a, i) => (
                                            <div key={i} className="px-3 py-1.5 rounded-md bg-white/[0.03] border border-white/5">
                                                <span className="text-xs text-white/50">{a.action}</span>
                                                <span className="text-xs font-bold text-white/80 ml-2">{a.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Recent Events */}
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium text-white/60">Recent Events ({userDetail.total_events} total)</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-1 max-h-60 overflow-y-auto">
                                        {(userDetail.events || []).slice(0, 15).map((ev, i) => (
                                            <div key={i} className="flex items-center gap-2 p-2 rounded bg-white/[0.02] text-xs">
                                                <Badge className={`text-[9px] px-1.5 ${ev.severity === 'critical' ? 'bg-red-500/15 text-red-400' : ev.severity === 'high' ? 'bg-orange-500/15 text-orange-400' : 'bg-white/5 text-white/40'}`}>{ev.severity}</Badge>
                                                <span className="text-white/50 w-20">{ev.action}</span>
                                                <span className="text-white/30 font-mono w-24">{ev.source_ip}</span>
                                                <span className="text-white/40 flex-1 truncate">{ev.message}</span>
                                                <span className="text-white/20 w-16">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardContent className="py-20 text-center">
                                <Fingerprint className="w-10 h-10 mx-auto text-purple-400/20 mb-3" />
                                <p className="text-white/40 text-sm">Select a user to view behavior details</p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
