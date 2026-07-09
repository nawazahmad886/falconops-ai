import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Shield,
    AlertTriangle,
    Activity,
    Users,
    Search,
    RefreshCw,
    ShieldAlert,
    ShieldCheck,
    Globe,
    User,
    Lock,
    Zap,
    Target,
    Eye,
    Server,
    Clock,
    ChevronRight,
    XCircle,
    CheckCircle,
    ArrowUpRight,
    Fingerprint,
    Network,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    AreaChart, Area, PieChart, Pie, Cell, Legend,
} from 'recharts';

const API = process.env.REACT_APP_BACKEND_URL;

const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', dot: 'bg-red-500' },
    high: { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', dot: 'bg-orange-500' },
    warning: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', dot: 'bg-amber-500' },
    info: { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30', dot: 'bg-blue-500' },
};

const THREAT_ICONS = {
    brute_force: Lock,
    malicious_ip: Globe,
    impossible_travel: Globe,
    privilege_escalation: ArrowUpRight,
    data_exfiltration: Zap,
};

const PIE_COLORS = ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#6b7280'];

const TABS = [
    { id: 'overview', label: 'Overview', icon: Shield },
    { id: 'threats', label: 'Threats', icon: ShieldAlert },
    { id: 'users', label: 'User Activity', icon: Users },
    { id: 'events', label: 'Security Events', icon: Activity },
];

// ======================== SUB-COMPONENTS ========================

const StatCard = ({ icon: Icon, label, value, sub, color = 'text-white' }) => (
    <Card className="bg-[#0D1117] border-white/5">
        <CardContent className="p-5 flex items-start gap-4">
            <div className={`p-2.5 rounded-lg ${color === 'text-red-400' ? 'bg-red-500/10' : color === 'text-orange-400' ? 'bg-orange-500/10' : color === 'text-emerald-400' ? 'bg-emerald-500/10' : 'bg-white/5'}`}>
                <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <div>
                <p className="text-xs text-white/40 uppercase tracking-wider">{label}</p>
                <p className={`text-2xl font-bold mt-0.5 ${color}`}>{value}</p>
                {sub && <p className="text-xs text-white/30 mt-0.5">{sub}</p>}
            </div>
        </CardContent>
    </Card>
);

const SeverityBadge = ({ severity }) => {
    const s = SEVERITY_COLORS[severity] || SEVERITY_COLORS.info;
    return (
        <Badge className={`${s.bg} ${s.text} ${s.border} text-[10px] px-2 py-0.5 border`} data-testid={`severity-${severity}`}>
            {severity?.toUpperCase()}
        </Badge>
    );
};

// ======================== OVERVIEW TAB ========================

const OverviewTab = ({ dashboard, loading }) => {
    if (loading) return <div className="text-center py-20 text-white/40">Loading dashboard...</div>;
    if (!dashboard) return null;

    const severityData = Object.entries(dashboard.severity_breakdown || {}).map(([name, value]) => ({ name, value }));
    const threatTypeData = (dashboard.top_threat_types || []).map(t => ({ name: t.type?.replace('_', ' '), count: t.count }));

    return (
        <div className="space-y-6" data-testid="security-overview">
            {/* Stats Row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={Activity} label="Total Events" value={dashboard.total_events || 0} sub="Last 24h" />
                <StatCard icon={ShieldAlert} label="Active Threats" value={dashboard.active_threats || 0} color="text-red-400" sub={`${dashboard.critical_threats || 0} critical`} />
                <StatCard icon={AlertTriangle} label="High Severity" value={dashboard.high_threats || 0} color="text-orange-400" />
                <StatCard icon={ShieldCheck} label="Resolved" value={dashboard.total_events ? dashboard.total_events - (dashboard.active_threats || 0) : 0} color="text-emerald-400" />
            </div>

            {/* Timeline + Severity */}
            <div className="grid lg:grid-cols-3 gap-4">
                <Card className="lg:col-span-2 bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Event Timeline (24h)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-52">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={dashboard.timeline || []}>
                                    <defs>
                                        <linearGradient id="secEvGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="secThGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <XAxis dataKey="hour" tick={{ fill: '#ffffff40', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fill: '#ffffff40', fontSize: 10 }} axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                    <Area type="monotone" dataKey="events" stroke="#3b82f6" fill="url(#secEvGrad)" strokeWidth={2} name="Events" />
                                    <Area type="monotone" dataKey="threats" stroke="#ef4444" fill="url(#secThGrad)" strokeWidth={2} name="Threats" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Severity Distribution</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-52">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={severityData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value" nameKey="name" paddingAngle={2}>
                                        {severityData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                    </Pie>
                                    <Legend wrapperStyle={{ fontSize: 11, color: '#ffffff60' }} />
                                    <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Threat Types + Top IPs */}
            <div className="grid lg:grid-cols-2 gap-4">
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Threat Types</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {threatTypeData.length === 0 ? (
                            <p className="text-center text-white/30 py-8 text-sm">No threats detected</p>
                        ) : (
                            <div className="h-48">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={threatTypeData} layout="vertical">
                                        <XAxis type="number" tick={{ fill: '#ffffff40', fontSize: 10 }} axisLine={false} tickLine={false} />
                                        <YAxis type="category" dataKey="name" tick={{ fill: '#ffffff60', fontSize: 11 }} axisLine={false} tickLine={false} width={120} />
                                        <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                                        <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} barSize={18} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-white/60">Top Source IPs (Failed Auth)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {(dashboard.top_source_ips || []).length === 0 ? (
                            <p className="text-center text-white/30 py-8 text-sm">No data</p>
                        ) : (
                            <div className="space-y-2">
                                {(dashboard.top_source_ips || []).slice(0, 8).map((ip, i) => (
                                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                                        <div className="flex items-center gap-2">
                                            <Network className="w-3.5 h-3.5 text-white/30" />
                                            <span className="text-sm font-mono text-white/70">{ip.ip}</span>
                                        </div>
                                        <Badge variant="outline" className="text-[10px] text-red-400 border-red-500/30">{ip.count} attempts</Badge>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

// ======================== THREATS TAB ========================

const ThreatsTab = ({ threats, loading, onResolve }) => {
    if (loading) return <div className="text-center py-20 text-white/40">Loading threats...</div>;

    return (
        <div className="space-y-4" data-testid="security-threats">
            {threats.length === 0 ? (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="py-16 text-center">
                        <ShieldCheck className="w-12 h-12 mx-auto text-emerald-400/30 mb-3" />
                        <p className="text-white/50 text-sm">No active threats detected</p>
                        <p className="text-white/30 text-xs mt-1">Generate demo data to see threat detection in action</p>
                    </CardContent>
                </Card>
            ) : (
                threats.map((threat) => {
                    const ThreatIcon = THREAT_ICONS[threat.type] || ShieldAlert;
                    const sev = SEVERITY_COLORS[threat.severity] || SEVERITY_COLORS.info;
                    return (
                        <Card key={threat.id} className={`bg-[#0D1117] border-white/5 hover:border-white/10 transition-colors`} data-testid={`threat-${threat.id}`}>
                            <CardContent className="p-4">
                                <div className="flex items-start gap-4">
                                    <div className={`p-2.5 rounded-lg ${sev.bg} shrink-0`}>
                                        <ThreatIcon className={`w-5 h-5 ${sev.text}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-sm font-semibold text-white/90">{threat.type?.replace(/_/g, ' ').toUpperCase()}</span>
                                            <SeverityBadge severity={threat.severity} />
                                            {threat.mitre_technique && (
                                                <Badge variant="outline" className="text-[9px] text-purple-400 border-purple-500/30">{threat.mitre_technique}</Badge>
                                            )}
                                        </div>
                                        <p className="text-sm text-white/60 mb-2">{threat.message}</p>
                                        <div className="flex items-center gap-4 text-xs text-white/30">
                                            {threat.source_ip && <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> {threat.source_ip}</span>}
                                            {threat.user && <span className="flex items-center gap-1"><User className="w-3 h-3" /> {threat.user}</span>}
                                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(threat.timestamp).toLocaleString()}</span>
                                        </div>
                                    </div>
                                    <div className="flex gap-1.5 shrink-0">
                                        <Button size="sm" variant="ghost" className="text-xs text-emerald-400 hover:bg-emerald-500/10" onClick={() => onResolve(threat.id, 'resolved')} data-testid={`resolve-${threat.id}`}>
                                            <CheckCircle className="w-3.5 h-3.5 mr-1" /> Resolve
                                        </Button>
                                        <Button size="sm" variant="ghost" className="text-xs text-white/40 hover:bg-white/5" onClick={() => onResolve(threat.id, 'dismissed')} data-testid={`dismiss-${threat.id}`}>
                                            <XCircle className="w-3.5 h-3.5 mr-1" /> Dismiss
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })
            )}
        </div>
    );
};

// ======================== USER ACTIVITY TAB ========================

const UserActivityTab = ({ activity, loading }) => {
    if (loading) return <div className="text-center py-20 text-white/40">Loading activity...</div>;
    if (!activity) return null;

    return (
        <div className="space-y-6" data-testid="security-user-activity">
            {/* Suspicious Users */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-red-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" /> Suspicious Users (Failed Logins)
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {(activity.suspicious_users || []).length === 0 ? (
                        <p className="text-center text-white/30 py-6 text-sm">No suspicious login activity</p>
                    ) : (
                        <div className="space-y-2">
                            {activity.suspicious_users.map((u, i) => (
                                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5" data-testid={`suspect-user-${i}`}>
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-red-500/10">
                                            <Fingerprint className="w-4 h-4 text-red-400" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white/80">{u.user}</p>
                                            <p className="text-xs text-white/30">{u.unique_ips} unique IP{u.unique_ips !== 1 ? 's' : ''}</p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <Badge className="bg-red-500/15 text-red-400 border-red-500/30 border text-[10px]">{u.failed_logins} failed</Badge>
                                        <p className="text-[10px] text-white/20 mt-1">{new Date(u.last_attempt).toLocaleString()}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Multi-IP Users */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-amber-400 flex items-center gap-2">
                        <Globe className="w-4 h-4" /> Users from Multiple IPs
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {(activity.multi_ip_users || []).length === 0 ? (
                        <p className="text-center text-white/30 py-6 text-sm">No multi-IP login activity</p>
                    ) : (
                        <div className="space-y-2">
                            {activity.multi_ip_users.map((u, i) => (
                                <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-white/5" data-testid={`multi-ip-user-${i}`}>
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-sm font-medium text-white/80">{u.user}</span>
                                        <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30">{u.ip_count} IPs</Badge>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {u.ips.map((ip, j) => (
                                            <span key={j} className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-white/40">{ip}</span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Privileged Actions */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-purple-400 flex items-center gap-2">
                        <Lock className="w-4 h-4" /> Privileged Actions
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {(activity.privileged_actions || []).length === 0 ? (
                        <p className="text-center text-white/30 py-6 text-sm">No privileged actions recorded</p>
                    ) : (
                        <div className="space-y-1.5">
                            {activity.privileged_actions.map((ev, i) => (
                                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/5 text-sm">
                                    <SeverityBadge severity={ev.severity} />
                                    <span className="text-white/50 font-mono text-xs">{ev.user}</span>
                                    <ChevronRight className="w-3 h-3 text-white/20" />
                                    <span className="text-white/60 flex-1">{ev.action}</span>
                                    <span className="text-[10px] text-white/20">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

// ======================== EVENTS TAB ========================

const EventsTab = ({ events, total, loading, filters, setFilters }) => {
    if (loading) return <div className="text-center py-20 text-white/40">Loading events...</div>;

    return (
        <div className="space-y-4" data-testid="security-events">
            {/* Filters */}
            <div className="flex flex-wrap gap-2">
                <Input
                    placeholder="Search events..."
                    value={filters.search}
                    onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))}
                    className="w-60 bg-[#161B22] border-white/10 text-sm"
                    data-testid="security-search"
                />
                <Select value={filters.category || 'all'} onValueChange={(v) => setFilters(f => ({ ...f, category: v === 'all' ? '' : v }))}>
                    <SelectTrigger className="w-40 bg-[#161B22] border-white/10 text-xs" data-testid="filter-category">
                        <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0D1117] border-white/10">
                        <SelectItem value="all">All Categories</SelectItem>
                        <SelectItem value="authentication">Authentication</SelectItem>
                        <SelectItem value="authorization">Authorization</SelectItem>
                        <SelectItem value="network">Network</SelectItem>
                        <SelectItem value="data_access">Data Access</SelectItem>
                        <SelectItem value="application">Application</SelectItem>
                        <SelectItem value="configuration">Configuration</SelectItem>
                    </SelectContent>
                </Select>
                <Select value={filters.severity || 'all'} onValueChange={(v) => setFilters(f => ({ ...f, severity: v === 'all' ? '' : v }))}>
                    <SelectTrigger className="w-32 bg-[#161B22] border-white/10 text-xs" data-testid="filter-severity">
                        <SelectValue placeholder="Severity" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0D1117] border-white/10">
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="warning">Warning</SelectItem>
                        <SelectItem value="info">Info</SelectItem>
                    </SelectContent>
                </Select>
                <span className="text-xs text-white/30 self-center ml-2">{total} total events</span>
            </div>

            {/* Events List */}
            {(events || []).length === 0 ? (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="py-16 text-center">
                        <Activity className="w-10 h-10 mx-auto text-white/10 mb-3" />
                        <p className="text-white/40 text-sm">No security events found</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-1">
                    {events.map((ev, i) => (
                        <div key={ev.id || i} className="flex items-center gap-3 p-3 rounded-lg bg-[#0D1117] border border-white/5 hover:border-white/10 transition-colors" data-testid={`event-${i}`}>
                            <SeverityBadge severity={ev.severity} />
                            <span className="text-xs text-white/30 w-16 shrink-0">{ev.category}</span>
                            <span className="text-xs font-medium text-white/70 w-28 shrink-0">{ev.action}</span>
                            <span className="text-xs font-mono text-white/40 w-20 shrink-0">{ev.user}</span>
                            <span className="text-xs font-mono text-white/30 w-28 shrink-0">{ev.source_ip}</span>
                            <span className="text-xs text-white/50 flex-1 truncate">{ev.message}</span>
                            <span className="text-[10px] text-white/20 w-20 shrink-0 text-right">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

// ======================== MAIN PAGE ========================

export default function SecurityMonitoringPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('overview');
    const [loading, setLoading] = useState(true);
    const [dashboard, setDashboard] = useState(null);
    const [threats, setThreats] = useState([]);
    const [activity, setActivity] = useState(null);
    const [events, setEvents] = useState([]);
    const [eventsTotal, setEventsTotal] = useState(0);
    const [filters, setFilters] = useState({ search: '', category: '', severity: '' });
    const [simulating, setSimulating] = useState(false);

    const fetchDashboard = useCallback(async () => {
        try {
            const res = await api.get('/security/dashboard?hours=24');
            setDashboard(res.data);
        } catch (e) { console.error('Dashboard fetch error:', e); }
    }, [api]);

    const fetchThreats = useCallback(async () => {
        try {
            const res = await api.get('/security/threats?status=active&limit=50');
            setThreats(res.data || []);
        } catch (e) { console.error('Threats fetch error:', e); }
    }, [api]);

    const fetchActivity = useCallback(async () => {
        try {
            const res = await api.get('/security/user-activity?hours=24');
            setActivity(res.data);
        } catch (e) { console.error('Activity fetch error:', e); }
    }, [api]);

    const fetchEvents = useCallback(async () => {
        try {
            const params = new URLSearchParams({ hours: '24', limit: '100' });
            if (filters.category) params.set('category', filters.category);
            if (filters.severity) params.set('severity', filters.severity);
            if (filters.search) params.set('search', filters.search);
            const res = await api.get(`/security/events?${params}`);
            setEvents(res.data?.events || []);
            setEventsTotal(res.data?.total || 0);
        } catch (e) { console.error('Events fetch error:', e); }
    }, [api, filters]);

    const loadAll = useCallback(async () => {
        setLoading(true);
        await Promise.all([fetchDashboard(), fetchThreats(), fetchActivity(), fetchEvents()]);
        setLoading(false);
    }, [fetchDashboard, fetchThreats, fetchActivity, fetchEvents]);

    useEffect(() => { loadAll(); }, [loadAll]);

    // Debounced search
    useEffect(() => {
        const t = setTimeout(fetchEvents, 400);
        return () => clearTimeout(t);
    }, [filters, fetchEvents]);

    const handleResolve = async (id, status) => {
        try {
            await api.put(`/security/threats/${id}`, { status });
            setThreats(prev => prev.filter(t => t.id !== id));
            fetchDashboard();
        } catch (e) { console.error('Resolve error:', e); }
    };

    const handleSimulate = async () => {
        setSimulating(true);
        try {
            await api.post('/security/simulate?count=200');
            await loadAll();
        } catch (e) { console.error('Simulate error:', e); }
        setSimulating(false);
    };

    return (
        <div className="space-y-6" data-testid="security-monitoring-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="security-page-title">
                        <Shield className="w-7 h-7 text-red-400" />
                        Security Monitoring
                    </h1>
                    <p className="text-sm text-white/40 mt-1">Threat detection, user activity analysis & security event correlation</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={loadAll} disabled={loading} className="border-white/10 text-xs" data-testid="refresh-btn">
                        <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button size="sm" onClick={handleSimulate} disabled={simulating} className="bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30 text-xs" data-testid="simulate-btn">
                        <Zap className={`w-3.5 h-3.5 mr-1.5 ${simulating ? 'animate-spin' : ''}`} /> {simulating ? 'Generating...' : 'Generate Demo Data'}
                    </Button>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 bg-[#0D1117] p-1 rounded-lg border border-white/5 w-fit" data-testid="security-tabs">
                {TABS.map(t => {
                    const Icon = t.icon;
                    const active = tab === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => setTab(t.id)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-medium transition-all ${
                                active ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                            }`}
                            data-testid={`tab-${t.id}`}
                        >
                            <Icon className="w-3.5 h-3.5" /> {t.label}
                            {t.id === 'threats' && threats.length > 0 && (
                                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 text-[9px]">{threats.length}</span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Tab Content */}
            {tab === 'overview' && <OverviewTab dashboard={dashboard} loading={loading} />}
            {tab === 'threats' && <ThreatsTab threats={threats} loading={loading} onResolve={handleResolve} />}
            {tab === 'users' && <UserActivityTab activity={activity} loading={loading} />}
            {tab === 'events' && <EventsTab events={events} total={eventsTotal} loading={loading} filters={filters} setFilters={setFilters} />}
        </div>
    );
}
