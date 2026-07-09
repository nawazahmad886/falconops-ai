import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
    X, 
    Maximize2, 
    Clock, 
    AlertTriangle, 
    Bell, 
    Activity, 
    Server, 
    CheckCircle,
    XCircle,
    Zap,
    RefreshCw,
    TrendingUp,
    TrendingDown,
    Users,
    Shield,
    Cpu,
    Database,
    Globe,
} from 'lucide-react';
import { FalconLogo } from '../components/FalconLogo';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Wallboard Page Component
export const WallboardPage = () => {
    const { api } = useAuth();
    const [currentTime, setCurrentTime] = useState(new Date());
    const [stats, setStats] = useState({
        openAlerts: 0,
        criticalAlerts: 0,
        warningAlerts: 0,
        activeIncidents: 0,
        resolvedToday: 0,
        mttr: '0h 0m',
        slaCompliance: 100,
        healthyServices: 0,
        totalServices: 0,
    });
    const [recentAlerts, setRecentAlerts] = useState([]);
    const [recentIncidents, setRecentIncidents] = useState([]);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [loading, setLoading] = useState(true);

    // Auto-refresh every 5 seconds for NOC real-time monitoring
    const fetchData = useCallback(async () => {
        try {
            const [alertsRes, incidentsRes, analyticsRes] = await Promise.all([
                api.get('/alerts?status=open&limit=10'),
                api.get('/incidents?limit=5'),
                api.get('/analytics/summary'),
            ]);

            const alerts = alertsRes.data || [];
            const incidents = incidentsRes.data || [];
            const analytics = analyticsRes.data || {};

            setStats({
                openAlerts: alerts.length,
                criticalAlerts: alerts.filter(a => a.severity === 'critical').length,
                warningAlerts: alerts.filter(a => a.severity === 'warning').length,
                activeIncidents: incidents.filter(i => i.status !== 'resolved').length,
                resolvedToday: analytics.resolved_alerts || 0,
                mttr: analytics.avg_mttr || '0h 0m',
                slaCompliance: Math.round(analytics.sla_compliance || 100),
                healthyServices: analytics.healthy_services || 0,
                totalServices: analytics.total_services || 0,
            });

            setRecentAlerts(alerts.slice(0, 8));
            setRecentIncidents(incidents.slice(0, 5));
            setLoading(false);
        } catch (error) {
            console.error('Failed to fetch wallboard data:', error);
            setLoading(false);
        }
    }, [api]);

    useEffect(() => {
        fetchData();
        const dataInterval = setInterval(fetchData, 5000); // Refresh every 5 seconds for real-time NOC
        return () => clearInterval(dataInterval);
    }, [fetchData]);

    // Update clock every second
    useEffect(() => {
        const clockInterval = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(clockInterval);
    }, []);

    // Toggle fullscreen
    const toggleFullscreen = () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    };

    // Exit wallboard
    const exitWallboard = () => {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        }
        window.history.back();
    };

    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'critical': return 'bg-red-500';
            case 'warning': return 'bg-amber-500';
            case 'info': return 'bg-blue-500';
            default: return 'bg-gray-500';
        }
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'open': return 'text-red-400';
            case 'investigating': return 'text-amber-400';
            case 'resolved': return 'text-emerald-400';
            default: return 'text-white/50';
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center">
                <RefreshCw className="w-16 h-16 text-primary animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#0B0E14] text-white p-6 overflow-hidden">
            {/* Header */}
            <header className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <FalconLogo size={48} />
                    <div>
                        <h1 className="text-3xl font-bold">
                            <span className="text-[#F5B841]">FALCON</span>
                            <span className="text-white">OPS</span>
                            <span className="text-[#00E0FF] ml-2">NOC</span>
                        </h1>
                        <p className="text-white/50 text-sm">Enterprise Operations Center</p>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    {/* Live Indicator */}
                    <div className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 border border-emerald-500/30 rounded-lg">
                        <div className="w-3 h-3 bg-emerald-400 rounded-full animate-pulse" />
                        <span className="text-emerald-400 font-bold text-lg">LIVE</span>
                    </div>

                    {/* Clock */}
                    <div className="text-right">
                        <div className="text-4xl font-mono font-bold text-white">
                            {currentTime.toLocaleTimeString('en-US', { hour12: false })}
                        </div>
                        <div className="text-sm text-white/50">
                            {currentTime.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
                        </div>
                    </div>

                    {/* Controls */}
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" onClick={toggleFullscreen} className="text-white/70 hover:text-white">
                            <Maximize2 className="w-6 h-6" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={exitWallboard} className="text-white/70 hover:text-white">
                            <X className="w-6 h-6" />
                        </Button>
                    </div>
                </div>
            </header>

            {/* Main Grid */}
            <div className="grid grid-cols-12 gap-4 h-[calc(100vh-140px)]">
                {/* Left Column - Stats */}
                <div className="col-span-3 space-y-4">
                    {/* Critical Alerts */}
                    <div className={`p-6 rounded-xl border ${stats.criticalAlerts > 0 ? 'bg-red-500/20 border-red-500/50 animate-pulse' : 'bg-white/5 border-white/10'}`}>
                        <div className="flex items-center gap-3 mb-2">
                            <AlertTriangle className={`w-8 h-8 ${stats.criticalAlerts > 0 ? 'text-red-400' : 'text-white/50'}`} />
                            <span className="text-white/70 text-lg">Critical Alerts</span>
                        </div>
                        <div className={`text-6xl font-bold ${stats.criticalAlerts > 0 ? 'text-red-400' : 'text-white'}`}>
                            {stats.criticalAlerts}
                        </div>
                    </div>

                    {/* Warning Alerts */}
                    <div className="p-6 rounded-xl bg-white/5 border border-white/10">
                        <div className="flex items-center gap-3 mb-2">
                            <Bell className="w-8 h-8 text-amber-400" />
                            <span className="text-white/70 text-lg">Warning Alerts</span>
                        </div>
                        <div className="text-6xl font-bold text-amber-400">
                            {stats.warningAlerts}
                        </div>
                    </div>

                    {/* Active Incidents */}
                    <div className="p-6 rounded-xl bg-white/5 border border-white/10">
                        <div className="flex items-center gap-3 mb-2">
                            <Zap className="w-8 h-8 text-purple-400" />
                            <span className="text-white/70 text-lg">Active Incidents</span>
                        </div>
                        <div className="text-6xl font-bold text-purple-400">
                            {stats.activeIncidents}
                        </div>
                    </div>

                    {/* Resolved Today */}
                    <div className="p-6 rounded-xl bg-white/5 border border-white/10">
                        <div className="flex items-center gap-3 mb-2">
                            <CheckCircle className="w-8 h-8 text-emerald-400" />
                            <span className="text-white/70 text-lg">Resolved Today</span>
                        </div>
                        <div className="text-6xl font-bold text-emerald-400">
                            {stats.resolvedToday}
                        </div>
                    </div>
                </div>

                {/* Center Column - Alert Feed */}
                <div className="col-span-6 space-y-4">
                    {/* SLA & MTTR Bar */}
                    <div className="grid grid-cols-3 gap-4">
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center">
                            <div className="text-white/50 text-sm mb-1">SLA Compliance</div>
                            <div className={`text-4xl font-bold ${stats.slaCompliance >= 99 ? 'text-emerald-400' : stats.slaCompliance >= 95 ? 'text-amber-400' : 'text-red-400'}`}>
                                {stats.slaCompliance}%
                            </div>
                        </div>
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center">
                            <div className="text-white/50 text-sm mb-1">Avg MTTR</div>
                            <div className="text-4xl font-bold text-[#00E0FF]">{stats.mttr}</div>
                        </div>
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10 text-center">
                            <div className="text-white/50 text-sm mb-1">Service Health</div>
                            <div className="text-4xl font-bold text-emerald-400">
                                {stats.healthyServices}/{stats.totalServices}
                            </div>
                        </div>
                    </div>

                    {/* Live Alert Feed */}
                    <div className="flex-1 p-4 rounded-xl bg-white/5 border border-white/10">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold flex items-center gap-2">
                                <Activity className="w-5 h-5 text-[#00E0FF]" />
                                Live Alert Feed
                            </h2>
                            <Badge variant="outline" className="border-white/20">
                                {recentAlerts.length} alerts
                            </Badge>
                        </div>
                        <div className="space-y-2 max-h-[calc(100vh-400px)] overflow-y-auto">
                            {recentAlerts.length === 0 ? (
                                <div className="text-center py-12 text-white/30">
                                    <CheckCircle className="w-16 h-16 mx-auto mb-4" />
                                    <p className="text-xl">All Clear</p>
                                    <p className="text-sm">No active alerts</p>
                                </div>
                            ) : (
                                recentAlerts.map((alert, idx) => (
                                    <div 
                                        key={alert.id || idx}
                                        className={`flex items-center gap-4 p-4 rounded-lg bg-black/30 border-l-4 ${
                                            alert.severity === 'critical' ? 'border-red-500' :
                                            alert.severity === 'warning' ? 'border-amber-500' : 'border-blue-500'
                                        }`}
                                    >
                                        <div className={`w-3 h-3 rounded-full ${getSeverityColor(alert.severity)}`} />
                                        <div className="flex-1">
                                            <div className="font-semibold text-lg">{alert.title}</div>
                                            <div className="text-sm text-white/50">
                                                {alert.service} • {alert.host}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <Badge className={getSeverityColor(alert.severity)}>
                                                {alert.severity?.toUpperCase()}
                                            </Badge>
                                            <div className="text-xs text-white/40 mt-1">
                                                {new Date(alert.created_at).toLocaleTimeString()}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Column - Incidents & Services */}
                <div className="col-span-3 space-y-4">
                    {/* Active Incidents List */}
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10 h-1/2">
                        <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
                            <Zap className="w-5 h-5 text-purple-400" />
                            Active Incidents
                        </h2>
                        <div className="space-y-2 overflow-y-auto max-h-[calc(100%-40px)]">
                            {recentIncidents.filter(i => i.status !== 'resolved').length === 0 ? (
                                <div className="text-center py-8 text-white/30">
                                    <Shield className="w-12 h-12 mx-auto mb-2" />
                                    <p>No active incidents</p>
                                </div>
                            ) : (
                                recentIncidents.filter(i => i.status !== 'resolved').map((incident, idx) => (
                                    <div key={incident.id || idx} className="p-3 rounded-lg bg-black/30">
                                        <div className="font-medium text-sm truncate">{incident.title}</div>
                                        <div className="flex items-center justify-between mt-1">
                                            <span className="text-xs text-white/50">{incident.service}</span>
                                            <span className={`text-xs font-semibold ${getStatusColor(incident.status)}`}>
                                                {incident.status?.toUpperCase()}
                                            </span>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Quick Stats */}
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10 h-1/2">
                        <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
                            <Server className="w-5 h-5 text-[#F5B841]" />
                            Infrastructure
                        </h2>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between p-2 rounded bg-black/30">
                                <span className="flex items-center gap-2">
                                    <Cpu className="w-4 h-4 text-cyan-400" />
                                    Servers
                                </span>
                                <span className="font-mono">12 / 12</span>
                            </div>
                            <div className="flex items-center justify-between p-2 rounded bg-black/30">
                                <span className="flex items-center gap-2">
                                    <Database className="w-4 h-4 text-emerald-400" />
                                    Databases
                                </span>
                                <span className="font-mono">4 / 4</span>
                            </div>
                            <div className="flex items-center justify-between p-2 rounded bg-black/30">
                                <span className="flex items-center gap-2">
                                    <Globe className="w-4 h-4 text-blue-400" />
                                    Services
                                </span>
                                <span className="font-mono">{stats.healthyServices} / {stats.totalServices}</span>
                            </div>
                            <div className="flex items-center justify-between p-2 rounded bg-black/30">
                                <span className="flex items-center gap-2">
                                    <Users className="w-4 h-4 text-purple-400" />
                                    Team Online
                                </span>
                                <span className="font-mono">5</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <footer className="absolute bottom-2 left-0 right-0 text-center text-white/30 text-xs">
                FalconOps AI • Auto-refreshes every 5 seconds • Press ESC to exit fullscreen
            </footer>
        </div>
    );
};

export default WallboardPage;
