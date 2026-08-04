import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
    AlertTriangle,
    Bell,
    CheckCircle2,
    Clock,
    TrendingDown,
    Activity,
    Server,
    RefreshCw,
    ArrowRight,
    Zap,
    Brain,
    Shield,
    Target,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Area, AreaChart } from 'recharts';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LiveAlertFeed } from '../components/LiveAlertFeed';
import { OnboardingChecklist } from '../components/OnboardingChecklist';
import { useTimeRangeParams } from '../hooks/useTimeRangeParams';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

const severityColors = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
};

const healthColors = {
    healthy: 'text-green-400',
    warning: 'text-yellow-400',
    degraded: 'text-yellow-400',
    critical: 'text-red-400',
};

const healthBg = {
    healthy: 'bg-green-500/10 border-green-500/20',
    warning: 'bg-yellow-500/10 border-yellow-500/20',
    degraded: 'bg-yellow-500/10 border-yellow-500/20',
    critical: 'bg-red-500/10 border-red-500/20',
};

export const DashboardPage = () => {
    const { api } = useAuth();
    const [analytics, setAnalytics] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [incidents, setIncidents] = useState([]);
    const [services, setServices] = useState([]);
    const [loading, setLoading] = useState(true);

    const { hours } = useTimeRangeParams();

    const fetchData = async () => {
        try {
            const days = Math.ceil(hours / 24) || 7;
            const [analyticsRes, alertsRes, incidentsRes, servicesRes] = await Promise.all([
                api.get(`/analytics/dashboard?days=${days}`),
                api.get('/alerts?limit=5'),
                api.get('/incidents?limit=5'),
                api.get('/services'),
            ]);
            setAnalytics(analyticsRes.data);
            setAlerts(alertsRes.data);
            setIncidents(incidentsRes.data);
            setServices(servicesRes.data);
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
            toast.error('Failed to load dashboard data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hours]);

    useAutoRefresh(fetchData);

    const formatMTTR = (seconds) => {
        if (!seconds) return '--';
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${Math.round(seconds / 3600)}h`;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-[60vh]">
                <div className="text-center">
                    <RefreshCw className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
                    <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Loading Intelligence...</p>
                </div>
            </div>
        );
    }

    const statCards = [
        {
            label: 'OPEN ALERTS',
            value: analytics?.open_alerts || 0,
            icon: Bell,
            color: 'red',
            testId: 'open-alerts-count',
        },
        {
            label: 'INCIDENTS',
            value: analytics?.open_incidents || 0,
            icon: AlertTriangle,
            color: 'yellow',
            testId: 'open-incidents-count',
        },
        {
            label: 'AVG MTTR',
            value: formatMTTR(analytics?.avg_mttr_seconds),
            icon: Clock,
            color: 'cyan',
            testId: 'avg-mttr',
        },
        {
            label: 'SLA COMPLIANCE',
            value: `${analytics?.sla_compliance || 100}%`,
            icon: Target,
            color: 'green',
            testId: 'sla-compliance',
        },
    ];

    const colorMap = {
        red: { bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400', icon: 'text-red-400' },
        yellow: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', text: 'text-yellow-400', icon: 'text-yellow-400' },
        cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', text: 'text-cyan-400', icon: 'text-cyan-400' },
        green: { bg: 'bg-green-500/10', border: 'border-green-500/20', text: 'text-green-400', icon: 'text-green-400' },
    };

    return (
        <>
            <div className="space-y-6" data-testid="dashboard-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white">
                                Command Center
                            </h1>
                            <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-sm">
                                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                                <span className="text-xs text-green-400 font-mono uppercase">Live</span>
                            </div>
                        </div>
                        <p className="text-white/50 text-sm font-mono">Real-time NOC intelligence overview</p>
                    </div>
                    <Button 
                        onClick={fetchData} 
                        variant="outline" 
                        size="sm" 
                        data-testid="refresh-btn"
                        className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm font-medium"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Refresh
                    </Button>
                </div>

                <OnboardingChecklist />

                {/* Stats Grid - Bento Style */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {statCards.map((stat, idx) => {
                        const Icon = stat.icon;
                        const colors = colorMap[stat.color];
                        return (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                            >
                                <Card className={`bg-[#0a0a0a] border-white/5 hover:border-white/10 transition-colors rounded-sm`}>
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <p className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">{stat.label}</p>
                                                <p className={`font-heading font-bold text-3xl ${colors.text}`} data-testid={stat.testId}>
                                                    {stat.value}
                                                </p>
                                            </div>
                                            <div className={`w-10 h-10 rounded-sm ${colors.bg} ${colors.border} border flex items-center justify-center`}>
                                                <Icon className={`w-5 h-5 ${colors.icon}`} />
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Charts Row */}
                <div className="grid lg:grid-cols-2 gap-4">
                    {/* Incidents Trend */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.2 }}
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Activity className="w-4 h-4 text-cyan-400" />
                                    Incidents Trend (7 Days)
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="h-[200px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={analytics?.incidents_trend || []}>
                                            <defs>
                                                <linearGradient id="colorIncidents" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3}/>
                                                    <stop offset="95%" stopColor="#00F0FF" stopOpacity={0}/>
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                            <XAxis 
                                                dataKey="date" 
                                                stroke="rgba(255,255,255,0.3)" 
                                                fontSize={10}
                                                fontFamily="JetBrains Mono"
                                                tickFormatter={(val) => val?.slice(5) || ''}
                                            />
                                            <YAxis stroke="rgba(255,255,255,0.3)" fontSize={10} fontFamily="JetBrains Mono" />
                                            <Tooltip 
                                                contentStyle={{ 
                                                    backgroundColor: '#0a0a0a', 
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '2px',
                                                    fontFamily: 'JetBrains Mono',
                                                    fontSize: '12px'
                                                }}
                                            />
                                            <Area 
                                                type="monotone" 
                                                dataKey="count" 
                                                stroke="#00F0FF" 
                                                strokeWidth={2}
                                                fill="url(#colorIncidents)"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Alerts by Severity */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.25 }}
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Zap className="w-4 h-4 text-yellow-400" />
                                    Alerts by Severity
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="h-[200px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart 
                                            data={Object.entries(analytics?.alerts_by_severity || {}).map(([name, value]) => ({ name, value }))}
                                            layout="vertical"
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                            <XAxis type="number" stroke="rgba(255,255,255,0.3)" fontSize={10} fontFamily="JetBrains Mono" />
                                            <YAxis dataKey="name" type="category" stroke="rgba(255,255,255,0.3)" fontSize={10} fontFamily="JetBrains Mono" width={70} />
                                            <Tooltip 
                                                contentStyle={{ 
                                                    backgroundColor: '#0a0a0a', 
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '2px',
                                                    fontFamily: 'JetBrains Mono',
                                                    fontSize: '12px'
                                                }}
                                            />
                                            <Bar 
                                                dataKey="value" 
                                                fill="#D4AF37"
                                                radius={[0, 2, 2, 0]}
                                            />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                </div>

                {/* Live Alert Feed */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.25 }}
                >
                    <LiveAlertFeed maxAlerts={10} />
                </motion.div>

                {/* Services & Recent Activity */}
                <div className="grid lg:grid-cols-2 gap-4">
                    {/* Service Health */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.3 }}
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm h-full">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                        <Server className="w-4 h-4 text-primary" />
                                        Service Health
                                    </CardTitle>
                                    <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300 font-mono uppercase tracking-wider">
                                        View All
                                    </Link>
                                </div>
                            </CardHeader>
                            <CardContent className="pt-4">
                                {services.length === 0 ? (
                                    <div className="text-center py-12 text-white/40">
                                        <Server className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                        <p className="text-sm font-medium mb-1">No services detected</p>
                                        <p className="text-xs font-mono">Send alerts via webhook to populate</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {services.slice(0, 5).map((service, idx) => (
                                            <div 
                                                key={idx} 
                                                className={`flex items-center justify-between p-3 rounded-sm ${healthBg[service.health]} border`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-2 h-2 rounded-full ${
                                                        service.health === 'healthy' ? 'bg-green-400' :
                                                        service.health === 'critical' ? 'bg-red-400 animate-pulse' :
                                                        'bg-yellow-400'
                                                    }`} />
                                                    <span className="font-mono text-sm text-white">{service.name}</span>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <span className="text-xs text-white/50 font-mono">
                                                        {service.open_alerts} open
                                                    </span>
                                                    <Badge variant="outline" className={`${healthColors[service.health]} border-current text-xs uppercase rounded-sm`}>
                                                        {service.health}
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Recent Incidents */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.35 }}
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm h-full">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                        <Brain className="w-4 h-4 text-cyan-400" />
                                        AI-Analyzed Incidents
                                    </CardTitle>
                                    <Link to="/incidents" className="text-xs text-cyan-400 hover:text-cyan-300 font-mono uppercase tracking-wider">
                                        View All
                                    </Link>
                                </div>
                            </CardHeader>
                            <CardContent className="pt-4">
                                {incidents.length === 0 ? (
                                    <div className="text-center py-12 text-white/40">
                                        <CheckCircle2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                        <p className="text-sm font-medium mb-1">No incidents</p>
                                        <p className="text-xs font-mono">All systems operational</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {incidents.slice(0, 5).map((incident) => (
                                            <Link 
                                                key={incident.id} 
                                                to={`/incidents`}
                                                className="flex items-start justify-between p-3 rounded-sm bg-white/5 border border-white/5 hover:border-cyan-500/30 transition-colors"
                                            >
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium text-white truncate">{incident.title}</p>
                                                    <div className="flex items-center gap-2 mt-1">
                                                        <span className="text-xs text-white/50 font-mono">{incident.service}</span>
                                                        <span className="text-white/30">•</span>
                                                        <span className="text-xs text-white/50 font-mono">{incident.alert_count} alerts</span>
                                                        {incident.ai_analysis && (
                                                            <>
                                                                <span className="text-white/30">•</span>
                                                                <span className="text-xs text-cyan-400 font-mono flex items-center gap-1">
                                                                    <Brain className="w-3 h-3" /> AI
                                                                </span>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>
                                                <Badge className={`${severityColors[incident.severity]} text-xs uppercase rounded-sm border`}>
                                                    {incident.severity}
                                                </Badge>
                                            </Link>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>
                </div>

                {/* Recent Alerts */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: 0.4 }}
                >
                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                        <CardHeader className="pb-2 border-b border-white/5">
                            <div className="flex items-center justify-between">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Bell className="w-4 h-4 text-red-400" />
                                    Recent Alerts
                                </CardTitle>
                                <Link to="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300 font-mono uppercase tracking-wider flex items-center gap-1">
                                    View All <ArrowRight className="w-3 h-3" />
                                </Link>
                            </div>
                        </CardHeader>
                        <CardContent className="pt-4">
                            {alerts.length === 0 ? (
                                <div className="text-center py-12 text-white/40">
                                    <Bell className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                    <p className="text-sm font-medium mb-1">No alerts yet</p>
                                    <p className="text-xs font-mono">Configure webhooks to receive alerts</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {alerts.map((alert) => (
                                        <div 
                                            key={alert.id}
                                            className="flex items-center justify-between p-3 rounded-sm bg-white/5 border border-white/5"
                                        >
                                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                                <div className={`w-2 h-2 rounded-full shrink-0 ${
                                                    alert.severity === 'critical' ? 'bg-red-500 animate-pulse' :
                                                    alert.severity === 'warning' ? 'bg-yellow-500' :
                                                    'bg-cyan-500'
                                                }`} />
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium text-white truncate">{alert.title}</p>
                                                    <p className="text-xs text-white/50 font-mono">
                                                        {alert.source} • {alert.service}
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <Badge variant="outline" className="text-xs text-white/50 border-white/20 rounded-sm uppercase">
                                                    {alert.status}
                                                </Badge>
                                                <Badge className={`${severityColors[alert.severity]} text-xs uppercase rounded-sm border`}>
                                                    {alert.severity}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>
            </div>
        </>
    );
};
