import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    AlertTriangle, Bell, CheckCircle2, XCircle, Clock,
    ArrowUp, Filter, RefreshCw, ChevronRight, Shield,
    Zap, Eye, TrendingUp, Server
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SEVERITY_CONFIG = {
    critical: { color: 'bg-red-500/20 text-red-400 border-red-500/30', dot: 'bg-red-500', icon: XCircle },
    high: { color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', dot: 'bg-orange-500', icon: AlertTriangle },
    medium: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', dot: 'bg-amber-500', icon: Zap },
    low: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', dot: 'bg-blue-500', icon: Eye },
    info: { color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', dot: 'bg-slate-500', icon: Bell },
};

const STATUS_CONFIG = {
    triggered: { color: 'bg-red-500/20 text-red-400', label: 'Triggered' },
    acknowledged: { color: 'bg-amber-500/20 text-amber-400', label: 'Acknowledged' },
    resolved: { color: 'bg-emerald-500/20 text-emerald-400', label: 'Resolved' },
    closed: { color: 'bg-slate-500/20 text-slate-400', label: 'Closed' },
};

export const AlertEnginePage = () => {
    const { token } = useAuth();
    const [alerts, setAlerts] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('all');
    const [severityFilter, setSeverityFilter] = useState('all');
    const [activeTab, setActiveTab] = useState('active');
    const [total, setTotal] = useState(0);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/alert-engine/stats`, { headers: headers() });
            if (res.ok) setStats(await res.json());
        } catch (e) { console.error('Stats error:', e); }
    }, [headers]);

    const fetchAlerts = useCallback(async () => {
        setLoading(true);
        try {
            let url = `${API_URL}/api/alert-engine`;
            const params = new URLSearchParams();
            if (activeTab === 'active') {
                url = `${API_URL}/api/alert-engine/active`;
            } else {
                if (statusFilter !== 'all') params.set('status', statusFilter);
                if (severityFilter !== 'all') params.set('severity', severityFilter);
                params.set('limit', '100');
                url += `?${params.toString()}`;
            }
            const res = await fetch(url, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setAlerts(data.alerts || []);
                setTotal(data.total || 0);
            }
        } catch (e) { console.error('Fetch error:', e); }
        setLoading(false);
    }, [headers, activeTab, statusFilter, severityFilter]);

    useEffect(() => { fetchStats(); fetchAlerts(); }, [fetchStats, fetchAlerts]);

    const handleAction = async (alertId, action) => {
        try {
            const res = await fetch(`${API_URL}/api/alert-engine/${alertId}/${action}`, {
                method: 'POST', headers: headers(), body: JSON.stringify({})
            });
            if (res.ok) {
                toast.success(`Alert ${action}d successfully`);
                fetchAlerts();
                fetchStats();
            } else {
                toast.error(`Failed to ${action} alert`);
            }
        } catch (e) { toast.error(`Error: ${e.message}`); }
    };

    const seedAlerts = async () => {
        try {
            const res = await fetch(`${API_URL}/api/seed/alerts`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                toast.success(data.message);
                fetchAlerts();
                fetchStats();
            }
        } catch (e) { toast.error(`Seed error: ${e.message}`); }
    };

    const StatCard = ({ label, value, icon: Icon, color, subtext }) => (
        <Card data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`} className="bg-[#0A0A0A] border-[#1F1F1F]">
            <CardContent className="p-4">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">{label}</p>
                        <p className="text-2xl font-bold text-white mt-1 font-[JetBrains_Mono]">{value}</p>
                        {subtext && <p className="text-xs text-[#A3A3A3] mt-1">{subtext}</p>}
                    </div>
                    <div className={`p-2 rounded-lg ${color}`}>
                        <Icon className="h-5 w-5" />
                    </div>
                </div>
            </CardContent>
        </Card>
    );

    return (
        <div data-testid="alert-engine-page" className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white font-[Barlow_Condensed] uppercase tracking-wide">
                        Alert Engine
                    </h1>
                    <p className="text-sm text-[#A3A3A3]">Enterprise alert lifecycle management</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button data-testid="seed-alerts-btn" variant="outline" size="sm" onClick={seedAlerts}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white hover:border-[#D4AF37]">
                        <Zap className="h-4 w-4 mr-1" /> Seed Demo
                    </Button>
                    <Button data-testid="refresh-alerts-btn" variant="outline" size="sm" onClick={() => { fetchAlerts(); fetchStats(); }}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                        <RefreshCw className="h-4 w-4 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Stats Row */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Active Alerts" value={stats.active_alerts || 0}
                        icon={Bell} color="bg-red-500/10 text-red-400" />
                    <StatCard label="Critical" value={stats.by_severity?.critical || 0}
                        icon={XCircle} color="bg-red-500/10 text-red-400" />
                    <StatCard label="High" value={stats.by_severity?.high || 0}
                        icon={AlertTriangle} color="bg-orange-500/10 text-orange-400" />
                    <StatCard label="Avg MTTR" value={stats.avg_mttr_minutes ? `${stats.avg_mttr_minutes}m` : 'N/A'}
                        icon={Clock} color="bg-cyan-500/10 text-cyan-400" subtext="Mean Time to Resolve" />
                </div>
            )}

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="flex items-center justify-between">
                    <TabsList className="bg-[#0A0A0A] border border-[#1F1F1F]">
                        <TabsTrigger data-testid="tab-active" value="active" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">Active</TabsTrigger>
                        <TabsTrigger data-testid="tab-all" value="all" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">All Alerts</TabsTrigger>
                        <TabsTrigger data-testid="tab-resolved" value="resolved" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">Resolved</TabsTrigger>
                    </TabsList>
                    {activeTab !== 'active' && (
                        <div className="flex items-center gap-2">
                            <Select value={severityFilter} onValueChange={setSeverityFilter}>
                                <SelectTrigger data-testid="severity-filter" className="w-[140px] bg-[#0A0A0A] border-[#1F1F1F] text-white">
                                    <Filter className="h-3 w-3 mr-1" /><SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0A0A0A] border-[#1F1F1F]">
                                    <SelectItem value="all">All Severity</SelectItem>
                                    <SelectItem value="critical">Critical</SelectItem>
                                    <SelectItem value="high">High</SelectItem>
                                    <SelectItem value="medium">Medium</SelectItem>
                                    <SelectItem value="low">Low</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                </div>

                <TabsContent value="active" className="mt-4">
                    <AlertList alerts={alerts} loading={loading} onAction={handleAction} showActions />
                </TabsContent>
                <TabsContent value="all" className="mt-4">
                    <AlertList alerts={alerts} loading={loading} onAction={handleAction} showActions />
                </TabsContent>
                <TabsContent value="resolved" className="mt-4">
                    <AlertList alerts={alerts.filter(a => a.status === 'resolved')} loading={loading} />
                </TabsContent>
            </Tabs>

            <p className="text-xs text-[#525252]">Showing {alerts.length} of {total} alerts</p>
        </div>
    );
};

const AlertList = ({ alerts, loading, onAction, showActions }) => {
    if (loading) return (
        <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-6 w-6 text-[#A3A3A3] animate-spin" />
        </div>
    );
    if (!alerts.length) return (
        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
            <CardContent className="py-12 text-center">
                <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                <p className="text-white font-medium">All Clear</p>
                <p className="text-sm text-[#A3A3A3]">No alerts to display</p>
            </CardContent>
        </Card>
    );

    return (
        <div className="space-y-2">
            {alerts.map(alert => {
                const sev = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.info;
                const status = STATUS_CONFIG[alert.status] || STATUS_CONFIG.triggered;
                const SevIcon = sev.icon;
                return (
                    <Card key={alert.id} data-testid={`alert-card-${alert.id}`}
                        className="bg-[#0A0A0A] border-[#1F1F1F] hover:border-[#2A2A2A] transition-colors">
                        <CardContent className="p-4">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex items-start gap-3 flex-1 min-w-0">
                                    <div className={`p-1.5 rounded ${sev.color} mt-0.5`}>
                                        <SevIcon className="h-4 w-4" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-medium text-white truncate">{alert.title}</span>
                                            <Badge className={`text-[10px] ${sev.color} border`}>{alert.severity}</Badge>
                                            <Badge className={`text-[10px] ${status.color}`}>{status.label}</Badge>
                                            {alert.occurrence_count > 1 && (
                                                <Badge className="text-[10px] bg-[#1F1F1F] text-[#A3A3A3]">
                                                    x{alert.occurrence_count}
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-xs text-[#A3A3A3] mt-1 truncate">{alert.description}</p>
                                        <div className="flex items-center gap-3 mt-2 text-[10px] text-[#525252]">
                                            <span className="flex items-center gap-1">
                                                <Server className="h-3 w-3" /> {alert.entity_name}
                                            </span>
                                            {alert.metric_name && (
                                                <span className="font-[JetBrains_Mono]">
                                                    {alert.metric_name}: {alert.metric_value}
                                                </span>
                                            )}
                                            <span className="flex items-center gap-1">
                                                <Clock className="h-3 w-3" />
                                                {new Date(alert.created_at).toLocaleString()}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                {showActions && alert.status === 'triggered' && (
                                    <div className="flex items-center gap-1 shrink-0">
                                        <Button data-testid={`ack-btn-${alert.id}`} size="sm" variant="outline"
                                            onClick={() => onAction(alert.id, 'acknowledge')}
                                            className="text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10 h-7 px-2">
                                            Ack
                                        </Button>
                                        <Button data-testid={`resolve-btn-${alert.id}`} size="sm" variant="outline"
                                            onClick={() => onAction(alert.id, 'resolve')}
                                            className="text-xs border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 h-7 px-2">
                                            Resolve
                                        </Button>
                                    </div>
                                )}
                                {showActions && alert.status === 'acknowledged' && (
                                    <Button data-testid={`resolve-btn-${alert.id}`} size="sm" variant="outline"
                                        onClick={() => onAction(alert.id, 'resolve')}
                                        className="text-xs border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 h-7 px-2">
                                        Resolve
                                    </Button>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
};

export default AlertEnginePage;
