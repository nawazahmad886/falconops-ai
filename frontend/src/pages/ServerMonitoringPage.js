import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Server,
    Cpu,
    HardDrive,
    Activity,
    RefreshCw,
    Eye,
    Trash2,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Wifi,
    WifiOff,
    Clock,
    TrendingUp,
    Plus,
    Play,
    Settings,
    Terminal,
    Database,
    Globe,
    Zap,
    BarChart3,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell } from 'recharts';
import { motion } from 'framer-motion';
import { formatRelativeTime } from '../components/TimeFilter';
import { useTimeRangeParams } from '../hooks/useTimeRangeParams';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

const statusColors = {
    online: 'bg-green-500/20 text-green-400 border-green-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const statusIcons = {
    online: CheckCircle2,
    warning: AlertTriangle,
    critical: XCircle,
    offline: WifiOff,
};

const PIE_COLORS = ['#10B981', '#F59E0B', '#EF4444', '#6B7280'];

export const ServerMonitoringPage = () => {
    const { api, user } = useAuth();
    const [dashboard, setDashboard] = useState(null);
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedServer, setSelectedServer] = useState(null);
    const [serverMetrics, setServerMetrics] = useState([]);
    const [showDetailsDialog, setShowDetailsDialog] = useState(false);
    const [showRulesDialog, setShowRulesDialog] = useState(false);
    const [alertRules, setAlertRules] = useState([]);

    const { hours } = useTimeRangeParams();

    // New rule state
    const [newRule, setNewRule] = useState({
        name: '',
        metric: 'cpu',
        operator: 'gt',
        threshold: 80,
        severity: 'warning',
    });

    const isAdmin = user?.role === 'admin';

    const fetchData = async () => {
        try {
            const [dashboardRes, rulesRes] = await Promise.all([
                api.get('/servers/dashboard'),
                api.get('/servers/rules/alerts'),
            ]);
            setDashboard(dashboardRes.data);
            setServers(dashboardRes.data.servers || []);
            setAlertRules(rulesRes.data || []);
        } catch (error) {
            console.error('Failed to fetch server data:', error);
            toast.error('Failed to load server monitoring data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useAutoRefresh(fetchData);

    // Fetches once when the details dialog opens, using whatever the global
    // time range is at that moment — does not reactively refetch if the
    // global range changes while the dialog stays open (bigger UX change,
    // left for a future pass).
    const handleViewDetails = async (server) => {
        setSelectedServer(server);
        setShowDetailsDialog(true);
        try {
            const res = await api.get(`/servers/${server.id}/metrics?hours=${hours}`);
            setServerMetrics(res.data);
        } catch (error) {
            toast.error('Failed to load server metrics');
        }
    };

    const handleDeleteServer = async (serverId) => {
        if (!window.confirm('Are you sure you want to delete this server?')) return;
        try {
            await api.delete(`/servers/${serverId}`);
            toast.success('Server deleted');
            fetchData();
        } catch (error) {
            toast.error('Failed to delete server');
        }
    };

    const handleSimulateMetrics = async () => {
        try {
            await api.post('/servers/simulate');
            toast.success('Server metrics simulated');
            fetchData();
        } catch (error) {
            toast.error('Failed to simulate metrics');
        }
    };

    const handleCreateRule = async () => {
        try {
            if (!newRule.name.trim()) {
                toast.error('Rule name is required');
                return;
            }
            await api.post('/servers/rules/alerts', newRule);
            toast.success('Alert rule created');
            setNewRule({ name: '', metric: 'cpu', operator: 'gt', threshold: 80, severity: 'warning' });
            const res = await api.get('/servers/rules/alerts');
            setAlertRules(res.data || []);
        } catch (error) {
            toast.error('Failed to create rule');
        }
    };

    const handleDeleteRule = async (ruleId) => {
        try {
            await api.delete(`/servers/rules/alerts/${ruleId}`);
            toast.success('Rule deleted');
            const res = await api.get('/servers/rules/alerts');
            setAlertRules(res.data || []);
        } catch (error) {
            toast.error('Failed to delete rule');
        }
    };

    const formatUptime = (seconds) => {
        if (!seconds) return '--';
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        if (days > 0) return `${days}d ${hours}h`;
        return `${hours}h`;
    };

    const getHealthColor = (value, type) => {
        if (value === null || value === undefined) return 'text-gray-400';
        if (type === 'cpu' || type === 'memory') {
            if (value > 90) return 'text-red-400';
            if (value > 75) return 'text-yellow-400';
            return 'text-green-400';
        }
        if (type === 'disk') {
            if (value > 90) return 'text-red-400';
            if (value > 80) return 'text-yellow-400';
            return 'text-green-400';
        }
        return 'text-white';
    };

    const pieData = dashboard ? [
        { name: 'Online', value: dashboard.online_servers, color: '#10B981' },
        { name: 'Warning', value: dashboard.warning_servers, color: '#F59E0B' },
        { name: 'Critical', value: dashboard.critical_servers, color: '#EF4444' },
        { name: 'Offline', value: dashboard.offline_servers, color: '#6B7280' },
    ].filter(d => d.value > 0) : [];

    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <div className="text-center">
                        <RefreshCw className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
                        <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Loading Server Monitoring...</p>
                    </div>
                </div>
            </>
        );
    }

    return (
        <>
            <div className="space-y-6" data-testid="server-monitoring-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white flex items-center gap-3">
                                <Server className="w-7 h-7 text-cyan-400" />
                                Server Monitoring
                            </h1>
                            <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                                {dashboard?.online_servers || 0} ONLINE
                            </Badge>
                        </div>
                        <p className="text-white/50 text-sm font-mono">Real-time infrastructure health monitoring</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={fetchData}
                            variant="outline"
                            size="sm"
                            className="border-white/20 hover:bg-white/5 text-white"
                            data-testid="refresh-btn"
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Refresh
                        </Button>
                        {isAdmin && (
                            <>
                                <Button
                                    onClick={() => setShowRulesDialog(true)}
                                    variant="outline"
                                    className="border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
                                    data-testid="alert-rules-btn"
                                >
                                    <Settings className="w-4 h-4 mr-2" />
                                    Alert Rules
                                </Button>
                                <Button
                                    onClick={handleSimulateMetrics}
                                    className="bg-purple-500 hover:bg-purple-600 text-white"
                                    data-testid="simulate-btn"
                                >
                                    <Play className="w-4 h-4 mr-2" />
                                    Simulate
                                </Button>
                            </>
                        )}
                    </div>
                </div>

                {/* Stats Overview */}
                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    {[
                        { label: 'TOTAL SERVERS', value: dashboard?.total_servers || 0, icon: Server, color: 'cyan' },
                        { label: 'ONLINE', value: dashboard?.online_servers || 0, icon: CheckCircle2, color: 'green' },
                        { label: 'AVG CPU', value: `${dashboard?.avg_cpu || 0}%`, icon: Cpu, color: 'primary' },
                        { label: 'AVG MEMORY', value: `${dashboard?.avg_memory || 0}%`, icon: Activity, color: 'blue' },
                        { label: 'AVG DISK', value: `${dashboard?.avg_disk || 0}%`, icon: HardDrive, color: 'yellow' },
                    ].map((stat, idx) => {
                        const Icon = stat.icon;
                        const colorClasses = {
                            cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', text: 'text-cyan-400' },
                            green: { bg: 'bg-green-500/10', border: 'border-green-500/20', text: 'text-green-400' },
                            primary: { bg: 'bg-primary/10', border: 'border-primary/20', text: 'text-primary' },
                            blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400' },
                            yellow: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/20', text: 'text-yellow-400' },
                        }[stat.color];
                        return (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: idx * 0.05 }}
                            >
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <p className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">{stat.label}</p>
                                                <p className={`font-heading font-bold text-2xl ${colorClasses.text}`}>{stat.value}</p>
                                            </div>
                                            <div className={`w-10 h-10 rounded-sm ${colorClasses.bg} ${colorClasses.border} border flex items-center justify-center`}>
                                                <Icon className={`w-5 h-5 ${colorClasses.text}`} />
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Charts Row */}
                <div className="grid lg:grid-cols-3 gap-4">
                    {/* Server Status Distribution */}
                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                        <CardHeader className="pb-2 border-b border-white/5">
                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                <Activity className="w-4 h-4 text-primary" />
                                Status Distribution
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4">
                            <div className="h-[180px]">
                                {pieData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={pieData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={40}
                                                outerRadius={70}
                                                paddingAngle={2}
                                                dataKey="value"
                                            >
                                                {pieData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid rgba(255,255,255,0.1)' }} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-white/40">
                                        <p>No servers registered</p>
                                    </div>
                                )}
                            </div>
                            <div className="flex justify-center gap-4 mt-2">
                                {pieData.map((item, idx) => (
                                    <div key={idx} className="flex items-center gap-1">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                                        <span className="text-[10px] text-white/50 font-mono uppercase">{item.name}: {item.value}</span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Resource Usage Overview */}
                    <Card className="lg:col-span-2 bg-[#0a0a0a] border-white/5 rounded-sm">
                        <CardHeader className="pb-2 border-b border-white/5">
                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                <BarChart3 className="w-4 h-4 text-cyan-400" />
                                Resource Usage by Server
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4">
                            <div className="space-y-3 max-h-[200px] overflow-auto">
                                {servers.slice(0, 5).map((server, idx) => (
                                    <div key={idx} className="flex items-center gap-4 p-2 bg-white/5 rounded-sm">
                                        <div className={`w-2 h-2 rounded-full ${
                                            server.status === 'online' ? 'bg-green-400' :
                                            server.status === 'warning' ? 'bg-yellow-400' :
                                            server.status === 'critical' ? 'bg-red-400 animate-pulse' :
                                            'bg-gray-400'
                                        }`} />
                                        <span className="font-mono text-sm text-white w-32 truncate">{server.hostname}</span>
                                        <div className="flex-1 flex items-center gap-4">
                                            <div className="flex items-center gap-2 w-24">
                                                <Cpu className="w-3 h-3 text-cyan-400" />
                                                <div className="flex-1 bg-white/10 rounded-full h-2">
                                                    <div 
                                                        className={`h-full rounded-full ${
                                                            (server.cpu_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.cpu_usage || 0) > 75 ? 'bg-yellow-400' :
                                                            'bg-cyan-400'
                                                        }`}
                                                        style={{ width: `${server.cpu_usage || 0}%` }}
                                                    />
                                                </div>
                                                <span className={`text-xs font-mono ${getHealthColor(server.cpu_usage, 'cpu')}`}>
                                                    {server.cpu_usage?.toFixed(0) || '--'}%
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 w-24">
                                                <Activity className="w-3 h-3 text-blue-400" />
                                                <div className="flex-1 bg-white/10 rounded-full h-2">
                                                    <div 
                                                        className={`h-full rounded-full ${
                                                            (server.memory_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.memory_usage || 0) > 75 ? 'bg-yellow-400' :
                                                            'bg-blue-400'
                                                        }`}
                                                        style={{ width: `${server.memory_usage || 0}%` }}
                                                    />
                                                </div>
                                                <span className={`text-xs font-mono ${getHealthColor(server.memory_usage, 'memory')}`}>
                                                    {server.memory_usage?.toFixed(0) || '--'}%
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 w-24">
                                                <HardDrive className="w-3 h-3 text-yellow-400" />
                                                <div className="flex-1 bg-white/10 rounded-full h-2">
                                                    <div 
                                                        className={`h-full rounded-full ${
                                                            (server.disk_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.disk_usage || 0) > 80 ? 'bg-yellow-400' :
                                                            'bg-yellow-400'
                                                        }`}
                                                        style={{ width: `${server.disk_usage || 0}%` }}
                                                    />
                                                </div>
                                                <span className={`text-xs font-mono ${getHealthColor(server.disk_usage, 'disk')}`}>
                                                    {server.disk_usage?.toFixed(0) || '--'}%
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                                {servers.length === 0 && (
                                    <div className="text-center py-8 text-white/40">
                                        <Server className="w-10 h-10 mx-auto mb-2 opacity-30" />
                                        <p className="text-sm">No servers registered. Click "Simulate" to add demo servers.</p>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Server Grid */}
                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                    <CardHeader className="pb-2 border-b border-white/5">
                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                            <Terminal className="w-4 h-4 text-primary" />
                            Registered Servers ({servers.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4">
                        {servers.length === 0 ? (
                            <div className="text-center py-12 text-white/40">
                                <Server className="w-16 h-16 mx-auto mb-4 opacity-30" />
                                <p className="text-lg font-heading font-bold uppercase tracking-wider mb-2">No servers registered</p>
                                <p className="text-sm font-mono mb-4">Register servers using the agent or simulate demo data</p>
                                {isAdmin && (
                                    <Button onClick={handleSimulateMetrics} className="bg-purple-500 hover:bg-purple-600">
                                        <Play className="w-4 h-4 mr-2" />
                                        Simulate Demo Servers
                                    </Button>
                                )}
                            </div>
                        ) : (
                            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {servers.map((server) => {
                                    const StatusIcon = statusIcons[server.status] || Clock;
                                    return (
                                        <motion.div
                                            key={server.id}
                                            initial={{ opacity: 0, scale: 0.95 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className={`p-4 rounded-sm border transition-all ${
                                                server.status === 'online' ? 'bg-green-500/5 border-green-500/20' :
                                                server.status === 'warning' ? 'bg-yellow-500/5 border-yellow-500/20' :
                                                server.status === 'critical' ? 'bg-red-500/5 border-red-500/20' :
                                                'bg-gray-500/5 border-gray-500/20'
                                            }`}
                                            data-testid={`server-card-${server.id}`}
                                        >
                                            <div className="flex items-start justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-3 h-3 rounded-full ${
                                                        server.status === 'online' ? 'bg-green-400' :
                                                        server.status === 'warning' ? 'bg-yellow-400' :
                                                        server.status === 'critical' ? 'bg-red-400 animate-pulse' :
                                                        'bg-gray-400'
                                                    }`} />
                                                    <span className="font-medium text-white">{server.hostname}</span>
                                                </div>
                                                <Badge className={`${statusColors[server.status]} text-[10px] uppercase rounded-sm border`}>
                                                    {server.status}
                                                </Badge>
                                            </div>
                                            
                                            <div className="space-y-2 text-xs text-white/50 font-mono mb-4">
                                                <div className="flex items-center gap-2">
                                                    <Globe className="w-3 h-3" />
                                                    <span>{server.ip_address}</span>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span>{server.os_type} {server.os_version}</span>
                                                </div>
                                                <div className="flex items-center gap-2 text-white/30">
                                                    <Clock className="w-3 h-3" />
                                                    <span>Last seen: {formatRelativeTime(server.last_seen)}</span>
                                                </div>
                                            </div>
                                            
                                            {/* Resource Meters */}
                                            <div className="space-y-2 mb-4">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <Cpu className="w-3 h-3 text-cyan-400" />
                                                        <span className="text-xs text-white/50">CPU</span>
                                                    </div>
                                                    <span className={`text-xs font-mono ${getHealthColor(server.cpu_usage, 'cpu')}`}>
                                                        {server.cpu_usage?.toFixed(1) || '--'}%
                                                    </span>
                                                </div>
                                                <div className="w-full bg-white/10 rounded-full h-1.5">
                                                    <div 
                                                        className={`h-full rounded-full transition-all ${
                                                            (server.cpu_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.cpu_usage || 0) > 75 ? 'bg-yellow-400' :
                                                            'bg-cyan-400'
                                                        }`}
                                                        style={{ width: `${server.cpu_usage || 0}%` }}
                                                    />
                                                </div>
                                                
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <Activity className="w-3 h-3 text-blue-400" />
                                                        <span className="text-xs text-white/50">Memory</span>
                                                    </div>
                                                    <span className={`text-xs font-mono ${getHealthColor(server.memory_usage, 'memory')}`}>
                                                        {server.memory_usage?.toFixed(1) || '--'}%
                                                    </span>
                                                </div>
                                                <div className="w-full bg-white/10 rounded-full h-1.5">
                                                    <div 
                                                        className={`h-full rounded-full transition-all ${
                                                            (server.memory_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.memory_usage || 0) > 75 ? 'bg-yellow-400' :
                                                            'bg-blue-400'
                                                        }`}
                                                        style={{ width: `${server.memory_usage || 0}%` }}
                                                    />
                                                </div>
                                                
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <HardDrive className="w-3 h-3 text-yellow-400" />
                                                        <span className="text-xs text-white/50">Disk</span>
                                                    </div>
                                                    <span className={`text-xs font-mono ${getHealthColor(server.disk_usage, 'disk')}`}>
                                                        {server.disk_usage?.toFixed(1) || '--'}%
                                                    </span>
                                                </div>
                                                <div className="w-full bg-white/10 rounded-full h-1.5">
                                                    <div 
                                                        className={`h-full rounded-full transition-all ${
                                                            (server.disk_usage || 0) > 90 ? 'bg-red-400' :
                                                            (server.disk_usage || 0) > 80 ? 'bg-yellow-400' :
                                                            'bg-yellow-400'
                                                        }`}
                                                        style={{ width: `${server.disk_usage || 0}%` }}
                                                    />
                                                </div>
                                            </div>
                                            
                                            {/* Actions */}
                                            <div className="flex items-center gap-2 pt-3 border-t border-white/5">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => handleViewDetails(server)}
                                                    className="flex-1 border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 rounded-sm text-xs"
                                                    data-testid={`server-details-${server.id}`}
                                                >
                                                    <Eye className="w-3 h-3 mr-1" />
                                                    Details
                                                </Button>
                                                {isAdmin && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleDeleteServer(server.id)}
                                                        className="border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-sm text-xs"
                                                        data-testid={`server-delete-${server.id}`}
                                                    >
                                                        <Trash2 className="w-3 h-3" />
                                                    </Button>
                                                )}
                                            </div>
                                        </motion.div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Server Details Dialog */}
                <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-3xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-2">
                                <Server className="w-5 h-5 text-cyan-400" />
                                Server Details
                            </DialogTitle>
                        </DialogHeader>
                        {selectedServer && (
                            <div className="space-y-6 mt-4">
                                {/* Server Info */}
                                <div className="flex items-center justify-between p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-4 h-4 rounded-full ${
                                            selectedServer.status === 'online' ? 'bg-green-400' :
                                            selectedServer.status === 'warning' ? 'bg-yellow-400' :
                                            selectedServer.status === 'critical' ? 'bg-red-400 animate-pulse' :
                                            'bg-gray-400'
                                        }`} />
                                        <div>
                                            <h3 className="font-bold text-white">{selectedServer.hostname}</h3>
                                            <p className="text-sm text-white/50 font-mono">{selectedServer.ip_address}</p>
                                        </div>
                                    </div>
                                    <Badge className={`${statusColors[selectedServer.status]} text-sm uppercase`}>
                                        {selectedServer.status}
                                    </Badge>
                                </div>

                                {/* System Info */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">OS</p>
                                        <p className="text-white font-mono text-sm">{selectedServer.os_type} {selectedServer.os_version}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Agent Version</p>
                                        <p className="text-white font-mono text-sm">{selectedServer.agent_version || 'N/A'}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Uptime</p>
                                        <p className="text-white font-mono text-sm">{formatUptime(selectedServer.uptime_seconds)}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Processes</p>
                                        <p className="text-white font-mono text-sm">{selectedServer.process_count || 'N/A'}</p>
                                    </div>
                                </div>

                                {/* Current Metrics */}
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="p-4 bg-cyan-500/10 border border-cyan-500/20 rounded-sm text-center">
                                        <Cpu className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono">CPU</p>
                                        <p className={`text-2xl font-bold ${getHealthColor(selectedServer.cpu_usage, 'cpu')}`}>
                                            {selectedServer.cpu_usage?.toFixed(1) || '--'}%
                                        </p>
                                    </div>
                                    <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-sm text-center">
                                        <Activity className="w-6 h-6 text-blue-400 mx-auto mb-2" />
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono">Memory</p>
                                        <p className={`text-2xl font-bold ${getHealthColor(selectedServer.memory_usage, 'memory')}`}>
                                            {selectedServer.memory_usage?.toFixed(1) || '--'}%
                                        </p>
                                    </div>
                                    <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-sm text-center">
                                        <HardDrive className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono">Disk</p>
                                        <p className={`text-2xl font-bold ${getHealthColor(selectedServer.disk_usage, 'disk')}`}>
                                            {selectedServer.disk_usage?.toFixed(1) || '--'}%
                                        </p>
                                    </div>
                                </div>

                                {/* Metrics Chart */}
                                <div>
                                    <h4 className="font-heading text-sm font-bold uppercase tracking-wider text-white mb-3 flex items-center gap-2">
                                        <TrendingUp className="w-4 h-4 text-cyan-400" />
                                        Resource History (last {hours}h)
                                    </h4>
                                    {serverMetrics.length > 0 ? (
                                        <div className="h-[200px]">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <AreaChart data={serverMetrics.slice(0, 50).reverse()}>
                                                    <defs>
                                                        <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor="#00F0FF" stopOpacity={0} />
                                                        </linearGradient>
                                                        <linearGradient id="colorMem" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                                    <XAxis dataKey="timestamp" stroke="rgba(255,255,255,0.3)" fontSize={10} tickFormatter={(t) => new Date(t).toLocaleTimeString()} />
                                                    <YAxis stroke="rgba(255,255,255,0.3)" fontSize={10} domain={[0, 100]} unit="%" />
                                                    <Tooltip contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid rgba(255,255,255,0.1)' }} />
                                                    <Area type="monotone" dataKey="cpu_percent" name="CPU" stroke="#00F0FF" fill="url(#colorCpu)" />
                                                    <Area type="monotone" dataKey="memory_percent" name="Memory" stroke="#3B82F6" fill="url(#colorMem)" />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        </div>
                                    ) : (
                                        <div className="h-[200px] flex items-center justify-center text-white/40">
                                            No metrics data available
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Alert Rules Dialog */}
                <Dialog open={showRulesDialog} onOpenChange={setShowRulesDialog}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-lg">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-2">
                                <Settings className="w-5 h-5 text-yellow-400" />
                                Server Alert Rules
                            </DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 mt-4">
                            {/* Create New Rule */}
                            <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                                <h4 className="font-mono text-xs uppercase tracking-wider text-white/50 mb-3">Create New Rule</h4>
                                <div className="space-y-3">
                                    <Input
                                        placeholder="Rule name (e.g., High CPU Alert)"
                                        value={newRule.name}
                                        onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                                        className="bg-black/50 border-white/10 text-white"
                                    />
                                    <div className="grid grid-cols-3 gap-2">
                                        <Select value={newRule.metric} onValueChange={(v) => setNewRule({ ...newRule, metric: v })}>
                                            <SelectTrigger className="bg-black/50 border-white/10 text-white">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                <SelectItem value="cpu">CPU</SelectItem>
                                                <SelectItem value="memory">Memory</SelectItem>
                                                <SelectItem value="disk">Disk</SelectItem>
                                                <SelectItem value="load">Load Avg</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <Select value={newRule.operator} onValueChange={(v) => setNewRule({ ...newRule, operator: v })}>
                                            <SelectTrigger className="bg-black/50 border-white/10 text-white">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                <SelectItem value="gt">&gt; Greater Than</SelectItem>
                                                <SelectItem value="lt">&lt; Less Than</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <Input
                                            type="number"
                                            placeholder="Threshold"
                                            value={newRule.threshold}
                                            onChange={(e) => setNewRule({ ...newRule, threshold: parseFloat(e.target.value) })}
                                            className="bg-black/50 border-white/10 text-white"
                                        />
                                    </div>
                                    <div className="flex gap-2">
                                        <Select value={newRule.severity} onValueChange={(v) => setNewRule({ ...newRule, severity: v })}>
                                            <SelectTrigger className="bg-black/50 border-white/10 text-white flex-1">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                <SelectItem value="warning">Warning</SelectItem>
                                                <SelectItem value="critical">Critical</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <Button onClick={handleCreateRule} className="bg-yellow-500 hover:bg-yellow-600 text-black">
                                            <Plus className="w-4 h-4 mr-1" />
                                            Create
                                        </Button>
                                    </div>
                                </div>
                            </div>

                            {/* Existing Rules */}
                            <div>
                                <h4 className="font-mono text-xs uppercase tracking-wider text-white/50 mb-3">Existing Rules ({alertRules.length})</h4>
                                {alertRules.length === 0 ? (
                                    <p className="text-white/40 text-sm text-center py-4">No alert rules configured</p>
                                ) : (
                                    <div className="space-y-2 max-h-[200px] overflow-auto">
                                        {alertRules.map((rule) => (
                                            <div key={rule.id} className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10">
                                                <div>
                                                    <p className="text-white font-medium text-sm">{rule.name}</p>
                                                    <p className="text-white/50 font-mono text-xs">
                                                        {rule.metric.toUpperCase()} {rule.operator === 'gt' ? '>' : '<'} {rule.threshold}%
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge className={rule.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}>
                                                        {rule.severity}
                                                    </Badge>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleDeleteRule(rule.id)}
                                                        className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                                                    >
                                                        <Trash2 className="w-3 h-3" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>
        </>
    );
};
