import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import {
    Server, Cpu, HardDrive, Database, Activity, AlertTriangle, Shield,
    Clock, RefreshCw, Zap, Brain, Target, Network, CheckCircle2,
    XCircle, TrendingUp, TrendingDown, Minus, Eye, ArrowUp, BarChart2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RISK_COLORS = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-amber-400',
    low: 'text-blue-400',
    minimal: 'text-emerald-400',
};

export const NOCDashboardPage = () => {
    const { token } = useAuth();
    const [activeTab, setActiveTab] = useState('noc');
    const [data, setData] = useState({
        systemRisk: null,
        alertStats: null,
        incidentStats: null,
        activeAlerts: [],
        activeIncidents: [],
        serverDashboard: null,
        anomalyScan: null,
        capacityAlerts: [],
        topology: [],
    });
    const [loading, setLoading] = useState(true);
    const [autoRefresh, setAutoRefresh] = useState(true);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        const h = headers();
        const fetches = [
            fetch(`${API_URL}/api/impact/system-risk`, { headers: h }).then(r => r.ok ? r.json() : null),
            fetch(`${API_URL}/api/alert-engine/stats`, { headers: h }).then(r => r.ok ? r.json() : null),
            fetch(`${API_URL}/api/incident-engine/stats`, { headers: h }).then(r => r.ok ? r.json() : null),
            fetch(`${API_URL}/api/alert-engine/active`, { headers: h }).then(r => r.ok ? r.json() : { alerts: [] }),
            fetch(`${API_URL}/api/incident-engine/active`, { headers: h }).then(r => r.ok ? r.json() : { incidents: [] }),
            fetch(`${API_URL}/api/servers/dashboard`, { headers: h }).then(r => r.ok ? r.json() : null),
            fetch(`${API_URL}/api/capacity/alerts?threshold=85&horizon=24h`, { headers: h }).then(r => r.ok ? r.json() : { alerts: [] }),
        ];

        try {
            const [systemRisk, alertStats, incidentStats, activeAlerts, activeIncidents, serverDashboard, capacityAlerts] = await Promise.all(fetches);
            setData({
                systemRisk,
                alertStats,
                incidentStats,
                activeAlerts: activeAlerts?.alerts || [],
                activeIncidents: activeIncidents?.incidents || [],
                serverDashboard,
                capacityAlerts: capacityAlerts?.alerts || [],
                topology: [],
            });
        } catch (e) {
            console.error('Dashboard fetch error:', e);
        }
        setLoading(false);
    }, [headers]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    useEffect(() => {
        if (!autoRefresh) return;
        const interval = setInterval(fetchAll, 30000);
        return () => clearInterval(interval);
    }, [autoRefresh, fetchAll]);

    const { systemRisk, alertStats, incidentStats, activeAlerts, activeIncidents, serverDashboard, capacityAlerts } = data;

    return (
        <div data-testid="noc-dashboard-page" className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white font-[Barlow_Condensed] uppercase tracking-wide flex items-center gap-2">
                        <Eye className="h-6 w-6 text-[#D4AF37]" /> Enterprise NOC Dashboard
                    </h1>
                    <p className="text-sm text-[#A3A3A3]">Real-time operational overview</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button data-testid="toggle-refresh" variant="outline" size="sm"
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        className={`border-[#1F1F1F] ${autoRefresh ? 'text-emerald-400 border-emerald-500/30' : 'text-[#A3A3A3]'}`}>
                        <RefreshCw className={`h-4 w-4 mr-1 ${autoRefresh ? 'animate-spin' : ''}`} />
                        {autoRefresh ? 'Live' : 'Paused'}
                    </Button>
                    <Button data-testid="refresh-noc" variant="outline" size="sm" onClick={fetchAll}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-[#0A0A0A] border border-[#1F1F1F]">
                    <TabsTrigger data-testid="tab-noc" value="noc" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        NOC Overview
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-infra" value="infra" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        Infrastructure
                    </TabsTrigger>
                    <TabsTrigger data-testid="tab-app" value="app" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">
                        Application
                    </TabsTrigger>
                </TabsList>

                {/* NOC Overview */}
                <TabsContent value="noc" className="mt-4 space-y-4">
                    {/* Risk + Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                        <RiskScoreCard risk={systemRisk} />
                        <MetricCard label="Active Alerts" value={alertStats?.active_alerts || 0}
                            icon={AlertTriangle} color="text-red-400" />
                        <MetricCard label="Critical" value={alertStats?.by_severity?.critical || 0}
                            icon={XCircle} color="text-red-400" />
                        <MetricCard label="Incidents" value={incidentStats?.active_incidents || 0}
                            icon={Shield} color="text-amber-400" />
                        <MetricCard label="MTTR" value={alertStats?.avg_mttr_minutes ? `${alertStats.avg_mttr_minutes}m` : 'N/A'}
                            icon={Clock} color="text-cyan-400" />
                        <MetricCard label="Capacity Warnings" value={capacityAlerts.length}
                            icon={TrendingUp} color="text-orange-400" />
                    </div>

                    {/* Two columns: Alerts + Incidents */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* Active Alerts */}
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider flex items-center justify-between">
                                    <span>Active Alerts ({activeAlerts.length})</span>
                                    <AlertTriangle className="h-4 w-4 text-red-400" />
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-1 max-h-[300px] overflow-y-auto">
                                {activeAlerts.length === 0 ? (
                                    <div className="py-6 text-center">
                                        <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                                        <p className="text-xs text-[#A3A3A3]">No active alerts</p>
                                    </div>
                                ) : activeAlerts.slice(0, 15).map(a => (
                                    <div key={a.id} data-testid={`noc-alert-${a.id}`}
                                        className="flex items-center justify-between p-2 rounded bg-[#121212] border border-[#1F1F1F]">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${a.severity === 'critical' ? 'bg-red-500' : a.severity === 'high' ? 'bg-orange-500' : 'bg-amber-500'}`} />
                                            <span className="text-xs text-white truncate">{a.title}</span>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <Badge className={`text-[9px] ${a.severity === 'critical' ? 'bg-red-500/20 text-red-400' : a.severity === 'high' ? 'bg-orange-500/20 text-orange-400' : 'bg-amber-500/20 text-amber-400'}`}>
                                                {a.severity}
                                            </Badge>
                                            <Badge className="text-[9px] bg-[#1F1F1F] text-[#525252]">{a.status}</Badge>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Active Incidents */}
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider flex items-center justify-between">
                                    <span>Active Incidents ({activeIncidents.length})</span>
                                    <Shield className="h-4 w-4 text-amber-400" />
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-1 max-h-[300px] overflow-y-auto">
                                {activeIncidents.length === 0 ? (
                                    <div className="py-6 text-center">
                                        <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                                        <p className="text-xs text-[#A3A3A3]">No active incidents</p>
                                    </div>
                                ) : activeIncidents.slice(0, 10).map(inc => (
                                    <div key={inc.id} data-testid={`noc-incident-${inc.id}`}
                                        className="flex items-center justify-between p-2 rounded bg-[#121212] border border-[#1F1F1F]">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${inc.severity === 'sev1' ? 'bg-red-500' : inc.severity === 'sev2' ? 'bg-orange-500' : 'bg-amber-500'}`} />
                                            <span className="text-xs text-white truncate">{inc.title}</span>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <Badge className="text-[9px] bg-[#1F1F1F] text-[#A3A3A3]">{inc.alert_count} alerts</Badge>
                                            <Badge className="text-[9px] bg-amber-500/20 text-amber-400">{inc.severity?.toUpperCase()}</Badge>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Severity Breakdown */}
                    {alertStats?.by_severity && (
                        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                                    Alert Severity Distribution
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-end gap-3 h-[120px]">
                                    {['critical', 'high', 'medium', 'low'].map(sev => {
                                        const count = alertStats.by_severity[sev] || 0;
                                        const maxCount = Math.max(...Object.values(alertStats.by_severity), 1);
                                        const height = Math.max(8, (count / maxCount) * 100);
                                        const colors = { critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-amber-500', low: 'bg-blue-500' };
                                        return (
                                            <div key={sev} className="flex-1 flex flex-col items-center gap-1">
                                                <span className="text-xs font-[JetBrains_Mono] text-white">{count}</span>
                                                <div className={`w-full rounded-t ${colors[sev]}`} style={{ height: `${height}%` }} />
                                                <span className="text-[10px] text-[#525252] uppercase font-[Barlow_Condensed]">{sev}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Infrastructure Tab */}
                <TabsContent value="infra" className="mt-4 space-y-4">
                    <InfrastructureDashboard serverDashboard={serverDashboard} capacityAlerts={capacityAlerts} />
                </TabsContent>

                {/* Application Tab */}
                <TabsContent value="app" className="mt-4 space-y-4">
                    <ApplicationDashboard alertStats={alertStats} incidentStats={incidentStats}
                        activeAlerts={activeAlerts} token={token} />
                </TabsContent>
            </Tabs>
        </div>
    );
};

// ======================== SUB COMPONENTS ========================

const RiskScoreCard = ({ risk }) => {
    if (!risk) return <MetricCard label="System Risk" value="--" icon={Target} color="text-[#A3A3A3]" />;
    const color = RISK_COLORS[risk.risk_level] || 'text-white';
    return (
        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
            <CardContent className="p-3 text-center">
                <p className="text-[10px] text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">System Risk</p>
                <p className={`text-3xl font-bold font-[JetBrains_Mono] ${color}`}>{risk.risk_score}</p>
                <Badge className={`text-[10px] ${color} bg-transparent`}>{risk.risk_level?.toUpperCase()}</Badge>
            </CardContent>
        </Card>
    );
};

const MetricCard = ({ label, value, icon: Icon, color = 'text-white' }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
        <CardContent className="p-3 text-center">
            <p className="text-[10px] text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">{label}</p>
            <p className={`text-2xl font-bold font-[JetBrains_Mono] mt-1 ${color}`}>{value}</p>
            <Icon className="h-3.5 w-3.5 text-[#525252] mx-auto mt-1" />
        </CardContent>
    </Card>
);

// ======================== INFRASTRUCTURE DASHBOARD ========================

const InfrastructureDashboard = ({ serverDashboard, capacityAlerts }) => {
    const servers = serverDashboard?.servers || [];
    const stats = serverDashboard || {};

    return (
        <div className="space-y-4">
            {/* Server Fleet Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <MetricCard label="Total Servers" value={stats.total_servers || 0} icon={Server} />
                <MetricCard label="Online" value={stats.online_count || servers.filter(s => s.status === 'online').length} icon={CheckCircle2} color="text-emerald-400" />
                <MetricCard label="Warning" value={stats.warning_count || servers.filter(s => s.status === 'warning').length} icon={AlertTriangle} color="text-amber-400" />
                <MetricCard label="Critical" value={stats.critical_count || servers.filter(s => s.status === 'critical').length} icon={XCircle} color="text-red-400" />
                <MetricCard label="Offline" value={stats.offline_count || servers.filter(s => s.status === 'offline').length} icon={Minus} color="text-[#525252]" />
            </div>

            {/* Server Grid */}
            <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                        Server Fleet ({servers.length})
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {servers.length === 0 ? (
                        <div className="py-8 text-center">
                            <Server className="h-10 w-10 text-[#525252] mx-auto mb-2" />
                            <p className="text-sm text-[#A3A3A3]">No servers registered</p>
                            <p className="text-xs text-[#525252]">Deploy the FalconOps agent to start monitoring</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {servers.map(srv => (
                                <ServerCard key={srv.id || srv.hostname} server={srv} />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Capacity Warnings */}
            {capacityAlerts.length > 0 && (
                <Card className="bg-[#0A0A0A] border-orange-500/20">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-orange-400 font-[Barlow_Condensed] uppercase tracking-wider flex items-center gap-2">
                            <TrendingUp className="h-4 w-4" /> Capacity Warnings ({capacityAlerts.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-1">
                        {capacityAlerts.map((alert, i) => (
                            <div key={i} className="flex items-center justify-between p-2 rounded bg-[#121212] border border-[#1F1F1F]">
                                <div className="flex items-center gap-2">
                                    <ArrowUp className="h-3 w-3 text-orange-400" />
                                    <span className="text-xs text-white">{alert.metric} on {alert.host}</span>
                                </div>
                                <div className="flex items-center gap-3 text-[10px]">
                                    <span className="text-[#A3A3A3]">Current: <span className="text-white font-[JetBrains_Mono]">{alert.current_value}%</span></span>
                                    <span className="text-[#A3A3A3]">Predicted: <span className="text-orange-400 font-[JetBrains_Mono]">{alert.predicted_value}%</span></span>
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

const ServerCard = ({ server }) => {
    const statusColors = {
        online: 'border-emerald-500/30 bg-emerald-500/5',
        warning: 'border-amber-500/30 bg-amber-500/5',
        critical: 'border-red-500/30 bg-red-500/5',
        offline: 'border-[#1F1F1F] bg-[#121212]',
    };
    const dotColors = {
        online: 'bg-emerald-500',
        warning: 'bg-amber-500',
        critical: 'bg-red-500',
        offline: 'bg-[#525252]',
    };
    const metrics = server.latest_metrics || server;

    return (
        <div data-testid={`server-card-${server.hostname}`}
            className={`p-3 rounded-lg border ${statusColors[server.status] || statusColors.offline}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${dotColors[server.status] || dotColors.offline}`} />
                    <span className="text-sm font-medium text-white">{server.hostname}</span>
                </div>
                <Badge className="text-[9px] bg-[#1F1F1F] text-[#A3A3A3]">{server.os_type || 'linux'}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-2">
                <ResourceBar label="CPU" value={metrics.cpu_percent || 0} />
                <ResourceBar label="MEM" value={metrics.memory_percent || 0} />
                <ResourceBar label="DISK" value={metrics.disk_percent || 0} />
            </div>
        </div>
    );
};

const ResourceBar = ({ label, value }) => {
    const color = value > 90 ? 'bg-red-500' : value > 75 ? 'bg-amber-500' : 'bg-emerald-500';
    return (
        <div>
            <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-[#525252] font-[Barlow_Condensed] uppercase">{label}</span>
                <span className="text-[9px] text-white font-[JetBrains_Mono]">{Math.round(value)}%</span>
            </div>
            <div className="h-1.5 bg-[#1F1F1F] rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${Math.min(value, 100)}%` }} />
            </div>
        </div>
    );
};

// ======================== APPLICATION DASHBOARD ========================

const ApplicationDashboard = ({ alertStats, incidentStats, activeAlerts, token }) => {
    const [serviceHealth, setServiceHealth] = useState([]);

    useEffect(() => {
        const fetchServices = async () => {
            try {
                const res = await fetch(`${API_URL}/api/analytics/services-health`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json();
                    setServiceHealth(data.services || []);
                }
            } catch (e) { console.error(e); }
        };
        if (token) fetchServices();
    }, [token]);

    // Group alerts by service
    const serviceAlertMap = {};
    (activeAlerts || []).forEach(a => {
        const svc = a.entity_name || a.tags?.service || 'unknown';
        serviceAlertMap[svc] = (serviceAlertMap[svc] || 0) + 1;
    });

    const topServices = Object.entries(serviceAlertMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([name, count]) => ({ name, alerts: count }));

    return (
        <div className="space-y-4">
            {/* Service Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Active Services" value={serviceHealth.length || Object.keys(serviceAlertMap).length}
                    icon={Activity} color="text-cyan-400" />
                <MetricCard label="Degraded" value={serviceHealth.filter(s => s.status === 'degraded').length || 0}
                    icon={AlertTriangle} color="text-amber-400" />
                <MetricCard label="Down" value={serviceHealth.filter(s => s.status === 'down').length || 0}
                    icon={XCircle} color="text-red-400" />
                <MetricCard label="Avg MTTR" value={incidentStats?.avg_mttr_minutes ? `${Math.round(incidentStats.avg_mttr_minutes)}m` : 'N/A'}
                    icon={Clock} color="text-cyan-400" />
            </div>

            {/* Top alerting services */}
            <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                        Top Alerting Services
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {topServices.length === 0 ? (
                        <div className="py-6 text-center">
                            <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                            <p className="text-xs text-[#A3A3A3]">All services healthy</p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {topServices.map(svc => {
                                const maxAlerts = Math.max(...topServices.map(s => s.alerts), 1);
                                const width = (svc.alerts / maxAlerts) * 100;
                                return (
                                    <div key={svc.name} className="flex items-center gap-3">
                                        <span className="text-xs text-[#A3A3A3] w-[150px] truncate">{svc.name}</span>
                                        <div className="flex-1 h-4 bg-[#121212] rounded overflow-hidden">
                                            <div className="h-full bg-gradient-to-r from-red-500/60 to-red-500/20 rounded" style={{ width: `${width}%` }} />
                                        </div>
                                        <span className="text-xs font-[JetBrains_Mono] text-white w-8 text-right">{svc.alerts}</span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Service Health Grid */}
            {serviceHealth.length > 0 && (
                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                            Service Health Map
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-8 gap-2">
                            {serviceHealth.map(svc => {
                                const colors = {
                                    healthy: 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400',
                                    degraded: 'bg-amber-500/20 border-amber-500/30 text-amber-400',
                                    down: 'bg-red-500/20 border-red-500/30 text-red-400',
                                };
                                return (
                                    <div key={svc.name} className={`p-2 rounded border text-center ${colors[svc.status] || colors.healthy}`}>
                                        <p className="text-[10px] truncate font-medium">{svc.name}</p>
                                        <p className="text-[9px] opacity-70">{svc.alert_count || 0} alerts</p>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Incident Severity */}
            {incidentStats?.by_severity && (
                <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-[#A3A3A3] font-[Barlow_Condensed] uppercase tracking-wider">
                            Incident Severity Distribution
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-5 gap-3">
                            {['sev1', 'sev2', 'sev3', 'sev4', 'sev5'].map(sev => {
                                const count = incidentStats.by_severity[sev] || 0;
                                const colors = { sev1: 'text-red-400', sev2: 'text-orange-400', sev3: 'text-amber-400', sev4: 'text-blue-400', sev5: 'text-slate-400' };
                                return (
                                    <div key={sev} className="text-center p-2 bg-[#121212] rounded border border-[#1F1F1F]">
                                        <p className={`text-lg font-bold font-[JetBrains_Mono] ${colors[sev]}`}>{count}</p>
                                        <p className="text-[10px] text-[#525252] uppercase font-[Barlow_Condensed]">{sev.toUpperCase()}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default NOCDashboardPage;
