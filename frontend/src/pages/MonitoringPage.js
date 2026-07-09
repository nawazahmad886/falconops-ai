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
    DialogTrigger,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Activity,
    Server,
    Wifi,
    WifiOff,
    Clock,
    TrendingUp,
    TrendingDown,
    Plus,
    RefreshCw,
    Play,
    Pause,
    Trash2,
    Eye,
    Globe,
    Shield,
    Zap,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Target,
    BarChart3,
    Lock,
    Mail,
    Network,
    Edit,
    X,
    Calendar,
    Filter,
} from 'lucide-react';
import { TracerouteVisualizer } from '../components/TracerouteVisualizer';
import { AnimatePresence } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell } from 'recharts';
import { motion } from 'framer-motion';

const statusColors = {
    up: 'bg-green-500/20 text-green-400 border-green-500/30',
    down: 'bg-red-500/20 text-red-400 border-red-500/30',
    timeout: 'bg-red-500/20 text-red-400 border-red-500/30',
    degraded: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    pending: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    unknown: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const statusIcons = {
    up: CheckCircle2,
    down: XCircle,
    timeout: XCircle,
    degraded: AlertTriangle,
    pending: Clock,
    unknown: Clock,
};

const PIE_COLORS = ['#10B981', '#EF4444', '#F59E0B', '#6B7280'];

// Time filter options
const TIME_FILTERS = [
    { label: 'Last 5 Minutes', value: '5m', hours: 0.083 },
    { label: 'Last 15 Minutes', value: '15m', hours: 0.25 },
    { label: 'Last 1 Hour', value: '1h', hours: 1 },
    { label: 'Last 6 Hours', value: '6h', hours: 6 },
    { label: 'Last 24 Hours', value: '24h', hours: 24 },
    { label: 'Last 7 Days', value: '7d', hours: 168 },
    { label: 'Custom', value: 'custom', hours: null },
];

// Format timestamp helper
const formatTimestamp = (timestamp) => {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    });
};

const formatRelativeTime = (timestamp) => {
    if (!timestamp) return '--';
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    return `${diffDay}d ago`;
};

export const MonitoringPage = () => {
    const { api, user } = useAuth();
    const [dashboard, setDashboard] = useState(null);
    const [monitors, setMonitors] = useState([]);
    const [loading, setLoading] = useState(true);
    const [schedulerRunning, setSchedulerRunning] = useState(false);
    const [showAddDialog, setShowAddDialog] = useState(false);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [showDetailsDialog, setShowDetailsDialog] = useState(false);
    const [selectedMonitor, setSelectedMonitor] = useState(null);
    const [monitorResults, setMonitorResults] = useState([]);
    const [showTraceroute, setShowTraceroute] = useState(false);
    const [traceMonitor, setTraceMonitor] = useState(null);
    const [currentTime, setCurrentTime] = useState(new Date());
    const [timeFilter, setTimeFilter] = useState('24h');
    const [customStartDate, setCustomStartDate] = useState('');
    const [customEndDate, setCustomEndDate] = useState('');
    const [showCustomDatePicker, setShowCustomDatePicker] = useState(false);
    
    const emptyMonitor = {
        name: '',
        target: '',
        monitor_type: 'ping',
        interval_seconds: 60,
        timeout_seconds: 5,
        port: 443,
        expected_status_code: 200,
        environment: 'production',
        sla_uptime_percent: 99.9,
        sla_max_latency_ms: 300,
        enabled: true,
        notification_email: '',
    };
    
    const [newMonitor, setNewMonitor] = useState(emptyMonitor);
    const [editMonitor, setEditMonitor] = useState(null);

    const isAdmin = user?.role === 'admin';

    // Update current time every second
    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const fetchData = async () => {
        try {
            const [dashboardRes, monitorsRes, schedulerRes] = await Promise.all([
                api.get('/monitors/dashboard'),
                api.get('/monitors'),
                api.get('/monitors/status/health'),
            ]);
            setDashboard(dashboardRes.data);
            setMonitors(monitorsRes.data);
            setSchedulerRunning(schedulerRes.data.monitoring_scheduler_running);
        } catch (error) {
            console.error('Failed to fetch monitoring data:', error);
            toast.error('Failed to load monitoring data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, []);

    const getTimeFilterHours = () => {
        const filter = TIME_FILTERS.find(f => f.value === timeFilter);
        return filter?.hours || 24;
    };

    const handleAddMonitor = async () => {
        try {
            if (!newMonitor.name.trim()) {
                toast.error('Monitor name is required');
                return;
            }
            if (!newMonitor.target.trim()) {
                toast.error('Target URL/IP is required');
                return;
            }
            
            const monitorData = { ...newMonitor };
            if (!monitorData.notification_email) {
                delete monitorData.notification_email;
            }
            await api.post('/monitors', monitorData);
            toast.success('Monitor created successfully');
            setShowAddDialog(false);
            setNewMonitor(emptyMonitor);
            fetchData();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to create monitor');
        }
    };

    const handleEditMonitor = async () => {
        try {
            if (!editMonitor.name.trim()) {
                toast.error('Monitor name is required');
                return;
            }
            if (!editMonitor.target.trim()) {
                toast.error('Target URL/IP is required');
                return;
            }
            
            const monitorData = { ...editMonitor };
            delete monitorData.id;
            delete monitorData.status;
            delete monitorData.last_check;
            delete monitorData.last_latency_ms;
            delete monitorData.uptime_percent_24h;
            delete monitorData.created_at;
            delete monitorData.created_by;
            
            if (!monitorData.notification_email) {
                delete monitorData.notification_email;
            }
            
            await api.put(`/monitors/${editMonitor.id}`, monitorData);
            toast.success('Monitor updated successfully');
            setShowEditDialog(false);
            setEditMonitor(null);
            fetchData();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to update monitor');
        }
    };

    const handleDeleteMonitor = async (monitorId) => {
        if (!window.confirm('Are you sure you want to delete this monitor?')) return;
        try {
            await api.delete(`/monitors/${monitorId}`);
            toast.success('Monitor deleted');
            fetchData();
        } catch (error) {
            toast.error('Failed to delete monitor');
        }
    };

    const handleToggleMonitor = async (monitor) => {
        try {
            const updateData = { ...monitor, enabled: !monitor.enabled };
            delete updateData.id;
            delete updateData.status;
            delete updateData.last_check;
            delete updateData.last_latency_ms;
            delete updateData.uptime_percent_24h;
            delete updateData.created_at;
            delete updateData.created_by;
            
            await api.put(`/monitors/${monitor.id}`, updateData);
            toast.success(monitor.enabled ? 'Monitor paused' : 'Monitor enabled');
            fetchData();
        } catch (error) {
            toast.error('Failed to toggle monitor');
        }
    };

    const handleRunCheck = async (monitorId) => {
        try {
            const result = await api.post(`/monitors/${monitorId}/check`);
            toast.success(`Check completed: ${result.data.result.status}`);
            fetchData();
        } catch (error) {
            toast.error('Failed to run check');
        }
    };

    const handleViewDetails = async (monitor) => {
        setSelectedMonitor(monitor);
        setShowDetailsDialog(true);
        try {
            const hours = getTimeFilterHours();
            const res = await api.get(`/monitors/${monitor.id}/results?hours=${Math.ceil(hours)}`);
            setMonitorResults(res.data);
        } catch (error) {
            toast.error('Failed to load results');
        }
    };

    const handleOpenEdit = (monitor) => {
        setEditMonitor({ ...monitor });
        setShowEditDialog(true);
    };

    const handleOpenTraceroute = (monitor) => {
        setTraceMonitor(monitor);
        setShowTraceroute(true);
    };

    const handleCloseTraceroute = () => {
        setShowTraceroute(false);
        setTraceMonitor(null);
    };

    const handleTimeFilterChange = (value) => {
        setTimeFilter(value);
        if (value === 'custom') {
            setShowCustomDatePicker(true);
        } else {
            setShowCustomDatePicker(false);
        }
    };

    const pieData = dashboard ? [
        { name: 'Up', value: dashboard.monitors_up, color: '#10B981' },
        { name: 'Down', value: dashboard.monitors_down, color: '#EF4444' },
        { name: 'Degraded', value: dashboard.monitors_degraded, color: '#F59E0B' },
        { name: 'Unknown', value: dashboard.total_monitors - dashboard.monitors_up - dashboard.monitors_down - dashboard.monitors_degraded, color: '#6B7280' },
    ].filter(d => d.value > 0) : [];

    // Monitor Form Component (reused for Add and Edit)
    const MonitorForm = ({ monitor, setMonitor, onSubmit, submitLabel }) => (
        <div className="space-y-4 mt-4">
            <div className="space-y-2">
                <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Name *</Label>
                <Input
                    value={monitor.name}
                    onChange={(e) => setMonitor({ ...monitor, name: e.target.value })}
                    placeholder="e.g., Production API"
                    className="bg-black/50 border-white/10 rounded-sm text-white"
                    data-testid="monitor-name-input"
                />
            </div>
            <div className="space-y-2">
                <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Target (IP/Hostname/URL) *</Label>
                <Input
                    value={monitor.target}
                    onChange={(e) => setMonitor({ ...monitor, target: e.target.value })}
                    placeholder="e.g., google.com or https://api.example.com"
                    className="bg-black/50 border-white/10 rounded-sm text-white"
                    data-testid="monitor-target-input"
                />
            </div>
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Type</Label>
                    <Select value={monitor.monitor_type} onValueChange={(v) => setMonitor({ ...monitor, monitor_type: v })}>
                        <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0a0a0a] border-white/10">
                            <SelectItem value="ping">Ping (ICMP)</SelectItem>
                            <SelectItem value="http">HTTP/HTTPS</SelectItem>
                            <SelectItem value="tcp">TCP Port</SelectItem>
                            <SelectItem value="ssl">SSL Certificate</SelectItem>
                            <SelectItem value="dns">DNS Resolution</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Environment</Label>
                    <Select value={monitor.environment} onValueChange={(v) => setMonitor({ ...monitor, environment: v })}>
                        <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0a0a0a] border-white/10">
                            <SelectItem value="production">Production</SelectItem>
                            <SelectItem value="staging">Staging</SelectItem>
                            <SelectItem value="development">Development</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Interval (seconds)</Label>
                    <Input
                        type="number"
                        value={monitor.interval_seconds}
                        onChange={(e) => setMonitor({ ...monitor, interval_seconds: parseInt(e.target.value) || 60 })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Timeout (seconds)</Label>
                    <Input
                        type="number"
                        value={monitor.timeout_seconds}
                        onChange={(e) => setMonitor({ ...monitor, timeout_seconds: parseInt(e.target.value) || 5 })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
            </div>
            {(monitor.monitor_type === 'tcp' || monitor.monitor_type === 'ssl') && (
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Port</Label>
                    <Input
                        type="number"
                        value={monitor.port}
                        onChange={(e) => setMonitor({ ...monitor, port: parseInt(e.target.value) })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
            )}
            {monitor.monitor_type === 'http' && (
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Expected Status Code</Label>
                    <Input
                        type="number"
                        value={monitor.expected_status_code}
                        onChange={(e) => setMonitor({ ...monitor, expected_status_code: parseInt(e.target.value) || 200 })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
            )}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">SLA Uptime %</Label>
                    <Input
                        type="number"
                        step="0.1"
                        value={monitor.sla_uptime_percent}
                        onChange={(e) => setMonitor({ ...monitor, sla_uptime_percent: parseFloat(e.target.value) })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
                <div className="space-y-2">
                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Max Latency (ms)</Label>
                    <Input
                        type="number"
                        value={monitor.sla_max_latency_ms}
                        onChange={(e) => setMonitor({ ...monitor, sla_max_latency_ms: parseFloat(e.target.value) })}
                        className="bg-black/50 border-white/10 rounded-sm text-white"
                    />
                </div>
            </div>
            <div className="space-y-2">
                <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Alert Email (Optional)</Label>
                <Input
                    type="email"
                    value={monitor.notification_email || ''}
                    onChange={(e) => setMonitor({ ...monitor, notification_email: e.target.value })}
                    placeholder="alerts@yourcompany.com"
                    className="bg-black/50 border-white/10 rounded-sm text-white"
                />
                <p className="text-[10px] text-white/40 font-mono">Receive email notifications on SLA breaches</p>
            </div>
            <Button onClick={onSubmit} className="w-full bg-primary text-black hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm" data-testid="monitor-submit-btn">
                {submitLabel}
            </Button>
        </div>
    );

    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <div className="text-center">
                        <RefreshCw className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
                        <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Loading Monitoring...</p>
                    </div>
                </div>
            </>
        );
    }

    return (
        <>
            <div className="space-y-6" data-testid="monitoring-page">
                {/* Global Timestamp Header */}
                <div className="flex items-center justify-between bg-[#0a0a0a] border border-white/5 rounded-sm p-3">
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <Clock className="w-4 h-4 text-cyan-400" />
                            <span className="font-mono text-sm text-white/70">Current Time:</span>
                            <span className="font-mono text-sm text-white" data-testid="current-timestamp">
                                {currentTime.toLocaleString('en-US', {
                                    year: 'numeric',
                                    month: 'short',
                                    day: '2-digit',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                    second: '2-digit',
                                    hour12: false,
                                })} UTC
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <Filter className="w-4 h-4 text-white/50" />
                        <Select value={timeFilter} onValueChange={handleTimeFilterChange}>
                            <SelectTrigger className="w-[180px] bg-black/50 border-white/10 rounded-sm text-white text-xs" data-testid="time-filter-select">
                                <SelectValue placeholder="Select time range" />
                            </SelectTrigger>
                            <SelectContent className="bg-[#0a0a0a] border-white/10">
                                {TIME_FILTERS.map((filter) => (
                                    <SelectItem key={filter.value} value={filter.value}>
                                        {filter.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {showCustomDatePicker && (
                            <div className="flex items-center gap-2">
                                <Input
                                    type="datetime-local"
                                    value={customStartDate}
                                    onChange={(e) => setCustomStartDate(e.target.value)}
                                    className="bg-black/50 border-white/10 rounded-sm text-white text-xs w-[180px]"
                                    data-testid="custom-start-date"
                                />
                                <span className="text-white/50">to</span>
                                <Input
                                    type="datetime-local"
                                    value={customEndDate}
                                    onChange={(e) => setCustomEndDate(e.target.value)}
                                    className="bg-black/50 border-white/10 rounded-sm text-white text-xs w-[180px]"
                                    data-testid="custom-end-date"
                                />
                            </div>
                        )}
                    </div>
                </div>

                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white flex items-center gap-3">
                                <Activity className="w-7 h-7 text-cyan-400" />
                                Uptime Monitoring
                            </h1>
                            <Badge className={schedulerRunning ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}>
                                {schedulerRunning ? 'LIVE' : 'PAUSED'}
                            </Badge>
                        </div>
                        <p className="text-white/50 text-sm font-mono">Enterprise availability & SLA monitoring</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={fetchData}
                            variant="outline"
                            size="sm"
                            className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm font-medium"
                            data-testid="refresh-btn"
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Refresh
                        </Button>
                        {isAdmin && (
                            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                                <DialogTrigger asChild>
                                    <Button className="bg-primary text-black hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm" data-testid="add-monitor-btn">
                                        <Plus className="w-4 h-4 mr-2" />
                                        Add Monitor
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-md max-h-[90vh] overflow-y-auto">
                                    <DialogHeader>
                                        <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white">Add New Monitor</DialogTitle>
                                    </DialogHeader>
                                    <MonitorForm 
                                        monitor={newMonitor} 
                                        setMonitor={setNewMonitor} 
                                        onSubmit={handleAddMonitor}
                                        submitLabel="Create Monitor"
                                    />
                                </DialogContent>
                            </Dialog>
                        )}
                    </div>
                </div>

                {/* Stats Overview */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                        { label: 'TOTAL MONITORS', value: dashboard?.total_monitors || 0, icon: Server, color: 'cyan' },
                        { label: 'OVERALL UPTIME', value: `${dashboard?.overall_uptime_percent || 100}%`, icon: TrendingUp, color: 'green' },
                        { label: 'SLA COMPLIANCE', value: `${dashboard?.sla_compliance_percent || 100}%`, icon: Target, color: 'primary' },
                        { label: 'ACTIVE OUTAGES', value: dashboard?.active_outages || 0, icon: AlertTriangle, color: 'red' },
                    ].map((stat, idx) => {
                        const Icon = stat.icon;
                        const colorClasses = {
                            cyan: { bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', text: 'text-cyan-400' },
                            green: { bg: 'bg-green-500/10', border: 'border-green-500/20', text: 'text-green-400' },
                            primary: { bg: 'bg-primary/10', border: 'border-primary/20', text: 'text-primary' },
                            red: { bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400' },
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
                                                <p className={`font-heading font-bold text-3xl ${colorClasses.text}`}>{stat.value}</p>
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
                    {/* Latency Trend */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="lg:col-span-2"
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <BarChart3 className="w-4 h-4 text-cyan-400" />
                                    Latency Trend ({TIME_FILTERS.find(f => f.value === timeFilter)?.label || '24h'})
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="h-[200px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={dashboard?.latency_trend || []}>
                                            <defs>
                                                <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3} />
                                                    <stop offset="95%" stopColor="#00F0FF" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                            <XAxis dataKey="hour" stroke="rgba(255,255,255,0.3)" fontSize={10} fontFamily="JetBrains Mono" />
                                            <YAxis stroke="rgba(255,255,255,0.3)" fontSize={10} fontFamily="JetBrains Mono" unit="ms" />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: '#0a0a0a',
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '2px',
                                                    fontFamily: 'JetBrains Mono',
                                                    fontSize: '12px'
                                                }}
                                            />
                                            <Area type="monotone" dataKey="avg_latency" stroke="#00F0FF" strokeWidth={2} fill="url(#colorLatency)" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Status Distribution */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.25 }}
                    >
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm h-full">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Activity className="w-4 h-4 text-primary" />
                                    Status Distribution
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="h-[180px]">
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
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: '#0a0a0a',
                                                    border: '1px solid rgba(255,255,255,0.1)',
                                                    borderRadius: '2px'
                                                }}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
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
                    </motion.div>
                </div>

                {/* Monitors Grid */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                        <CardHeader className="pb-2 border-b border-white/5">
                            <div className="flex items-center justify-between">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Server className="w-4 h-4 text-primary" />
                                    Monitored Hosts ({monitors.length})
                                </CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent className="pt-4">
                            {monitors.length === 0 ? (
                                <div className="text-center py-12 text-white/40">
                                    <Server className="w-16 h-16 mx-auto mb-4 opacity-30" />
                                    <p className="text-lg font-heading font-bold uppercase tracking-wider mb-2">No monitors configured</p>
                                    <p className="text-sm font-mono mb-4">Add your first monitor to start tracking uptime</p>
                                    {isAdmin && (
                                        <Button onClick={() => setShowAddDialog(true)} className="bg-primary text-black hover:bg-primary/90">
                                            <Plus className="w-4 h-4 mr-2" />
                                            Add Monitor
                                        </Button>
                                    )}
                                </div>
                            ) : (
                                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {monitors.map((monitor) => {
                                        const StatusIcon = statusIcons[monitor.status] || Clock;
                                        return (
                                            <div
                                                key={monitor.id}
                                                className={`p-4 rounded-sm border transition-colors ${
                                                    monitor.status === 'up' ? 'bg-green-500/5 border-green-500/20' :
                                                    monitor.status === 'down' || monitor.status === 'timeout' ? 'bg-red-500/5 border-red-500/20' :
                                                    monitor.status === 'degraded' ? 'bg-yellow-500/5 border-yellow-500/20' :
                                                    'bg-white/5 border-white/10'
                                                }`}
                                                data-testid={`monitor-card-${monitor.id}`}
                                            >
                                                <div className="flex items-start justify-between mb-3">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-3 h-3 rounded-full ${
                                                            monitor.status === 'up' ? 'bg-green-400' :
                                                            monitor.status === 'down' || monitor.status === 'timeout' ? 'bg-red-400 animate-pulse' :
                                                            monitor.status === 'degraded' ? 'bg-yellow-400' :
                                                            'bg-gray-400'
                                                        }`} />
                                                        <span className="font-medium text-white">{monitor.name}</span>
                                                    </div>
                                                    <Badge className={`${statusColors[monitor.status]} text-[10px] uppercase rounded-sm border`}>
                                                        {monitor.status}
                                                    </Badge>
                                                </div>
                                                <div className="space-y-2 text-xs text-white/50 font-mono">
                                                    <div className="flex items-center gap-2">
                                                        <Globe className="w-3 h-3" />
                                                        <span className="truncate">{monitor.target}</span>
                                                    </div>
                                                    <div className="flex items-center justify-between">
                                                        <span className="uppercase">{monitor.monitor_type}</span>
                                                        <span>{monitor.environment}</span>
                                                    </div>
                                                    {monitor.last_latency_ms && (
                                                        <div className="flex items-center gap-2">
                                                            <Clock className="w-3 h-3" />
                                                            <span>{monitor.last_latency_ms}ms</span>
                                                        </div>
                                                    )}
                                                    <div className="flex items-center gap-2 text-white/30">
                                                        <Calendar className="w-3 h-3" />
                                                        <span>Last check: {formatRelativeTime(monitor.last_check)}</span>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2 mt-4 pt-3 border-t border-white/5">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleViewDetails(monitor)}
                                                        className="flex-1 border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 rounded-sm text-xs"
                                                        data-testid={`view-details-${monitor.id}`}
                                                    >
                                                        <Eye className="w-3 h-3 mr-1" />
                                                        Details
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleOpenTraceroute(monitor)}
                                                        className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10 rounded-sm text-xs"
                                                        data-testid={`traceroute-${monitor.id}`}
                                                    >
                                                        <Network className="w-3 h-3" />
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => handleRunCheck(monitor.id)}
                                                        className="border-green-500/30 text-green-400 hover:bg-green-500/10 rounded-sm text-xs"
                                                    >
                                                        <Play className="w-3 h-3" />
                                                    </Button>
                                                    {isAdmin && (
                                                        <>
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                onClick={() => handleOpenEdit(monitor)}
                                                                className="border-blue-500/30 text-blue-400 hover:bg-blue-500/10 rounded-sm text-xs"
                                                                data-testid={`edit-monitor-${monitor.id}`}
                                                            >
                                                                <Edit className="w-3 h-3" />
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                onClick={() => handleToggleMonitor(monitor)}
                                                                className={`border-white/20 rounded-sm text-xs ${monitor.enabled ? 'text-yellow-400' : 'text-green-400'}`}
                                                            >
                                                                {monitor.enabled ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                onClick={() => handleDeleteMonitor(monitor.id)}
                                                                className="border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-sm text-xs"
                                                                data-testid={`delete-monitor-${monitor.id}`}
                                                            >
                                                                <Trash2 className="w-3 h-3" />
                                                            </Button>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Edit Monitor Dialog */}
                <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-md max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white">Edit Monitor</DialogTitle>
                        </DialogHeader>
                        {editMonitor && (
                            <MonitorForm 
                                monitor={editMonitor} 
                                setMonitor={setEditMonitor} 
                                onSubmit={handleEditMonitor}
                                submitLabel="Update Monitor"
                            />
                        )}
                    </DialogContent>
                </Dialog>

                {/* Monitor Details Dialog */}
                <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-2xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-2">
                                <Eye className="w-5 h-5 text-cyan-400" />
                                Monitor Details
                            </DialogTitle>
                        </DialogHeader>
                        {selectedMonitor && (
                            <div className="space-y-6 mt-4">
                                {/* Status Header */}
                                <div className="flex items-center justify-between p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-4 h-4 rounded-full ${
                                            selectedMonitor.status === 'up' ? 'bg-green-400' :
                                            selectedMonitor.status === 'down' || selectedMonitor.status === 'timeout' ? 'bg-red-400 animate-pulse' :
                                            'bg-yellow-400'
                                        }`} />
                                        <div>
                                            <h3 className="font-bold text-white">{selectedMonitor.name}</h3>
                                            <p className="text-sm text-white/50 font-mono">{selectedMonitor.target}</p>
                                        </div>
                                    </div>
                                    <Badge className={`${statusColors[selectedMonitor.status]} text-sm uppercase`}>
                                        {selectedMonitor.status}
                                    </Badge>
                                </div>

                                {/* Details Grid */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Type</p>
                                        <p className="text-white font-mono">{selectedMonitor.monitor_type.toUpperCase()}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Environment</p>
                                        <p className="text-white font-mono">{selectedMonitor.environment}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Last Latency</p>
                                        <p className="text-cyan-400 font-mono">{selectedMonitor.last_latency_ms || '--'}ms</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Last Check</p>
                                        <p className="text-white font-mono text-xs">{formatTimestamp(selectedMonitor.last_check)}</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">SLA Target</p>
                                        <p className="text-white font-mono">{selectedMonitor.sla_uptime_percent}%</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Max Latency</p>
                                        <p className="text-white font-mono">{selectedMonitor.sla_max_latency_ms}ms</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Interval</p>
                                        <p className="text-white font-mono">{selectedMonitor.interval_seconds}s</p>
                                    </div>
                                    <div className="p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Timeout</p>
                                        <p className="text-white font-mono">{selectedMonitor.timeout_seconds}s</p>
                                    </div>
                                    <div className="col-span-2 p-3 bg-white/5 rounded-sm">
                                        <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Created At</p>
                                        <p className="text-white font-mono text-xs">{formatTimestamp(selectedMonitor.created_at)}</p>
                                    </div>
                                    {selectedMonitor.notification_email && (
                                        <div className="col-span-2 p-3 bg-white/5 rounded-sm">
                                            <p className="text-[10px] text-white/40 uppercase tracking-wider font-mono mb-1">Alert Email</p>
                                            <p className="text-white font-mono">{selectedMonitor.notification_email}</p>
                                        </div>
                                    )}
                                </div>

                                {/* Recent Results */}
                                <div>
                                    <h4 className="font-heading text-sm font-bold uppercase tracking-wider text-white mb-3 flex items-center gap-2">
                                        <BarChart3 className="w-4 h-4 text-cyan-400" />
                                        Recent Check Results ({monitorResults.length})
                                    </h4>
                                    {monitorResults.length > 0 ? (
                                        <div className="max-h-[200px] overflow-y-auto space-y-2">
                                            {monitorResults.slice(0, 20).map((result, idx) => (
                                                <div 
                                                    key={idx}
                                                    className={`flex items-center justify-between p-2 rounded-sm text-xs ${
                                                        result.status === 'up' ? 'bg-green-500/10 border border-green-500/20' :
                                                        'bg-red-500/10 border border-red-500/20'
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-2">
                                                        {result.status === 'up' ? 
                                                            <CheckCircle2 className="w-3 h-3 text-green-400" /> :
                                                            <XCircle className="w-3 h-3 text-red-400" />
                                                        }
                                                        <span className={result.status === 'up' ? 'text-green-400' : 'text-red-400'}>
                                                            {result.status.toUpperCase()}
                                                        </span>
                                                    </div>
                                                    <span className="text-white/50 font-mono">{result.latency_ms ? `${result.latency_ms}ms` : '--'}</span>
                                                    <span className="text-white/30 font-mono">{formatTimestamp(result.created_at)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-white/40 text-sm">No results available</p>
                                    )}
                                </div>

                                {/* Actions */}
                                <div className="flex gap-3 pt-4 border-t border-white/10">
                                    <Button
                                        onClick={() => handleRunCheck(selectedMonitor.id)}
                                        className="flex-1 bg-cyan-500 text-black hover:bg-cyan-600"
                                    >
                                        <Play className="w-4 h-4 mr-2" />
                                        Run Check Now
                                    </Button>
                                    <Button
                                        onClick={() => handleOpenTraceroute(selectedMonitor)}
                                        variant="outline"
                                        className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
                                    >
                                        <Network className="w-4 h-4 mr-2" />
                                        Traceroute
                                    </Button>
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Traceroute Modal */}
                <AnimatePresence>
                    {showTraceroute && traceMonitor && (
                        <TracerouteVisualizer
                            monitorId={traceMonitor.id}
                            monitorName={traceMonitor.name}
                            target={traceMonitor.target}
                            api={api}
                            onClose={handleCloseTraceroute}
                            isModal={true}
                        />
                    )}
                </AnimatePresence>
            </div>
        </>
    );
};
