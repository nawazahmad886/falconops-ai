import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    BarChart3,
    TrendingUp,
    TrendingDown,
    Target,
    Clock,
    AlertTriangle,
    CheckCircle,
    XCircle,
    Download,
    FileText,
    Brain,
    RefreshCw,
    Calendar,
    Users,
    Activity,
    Zap,
    Server,
    Shield,
} from 'lucide-react';
import { motion } from 'framer-motion';
import {
    LineChart,
    Line,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    Area,
    AreaChart,
} from 'recharts';

const COLORS = ['#D4AF37', '#00F0FF', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

export const ExecutiveReportsPage = () => {
    const { api } = useAuth();
    const [activeTab, setActiveTab] = useState('executive');
    const [loading, setLoading] = useState(true);
    const [executiveData, setExecutiveData] = useState(null);
    const [slaData, setSlaData] = useState(null);
    const [incidentData, setIncidentData] = useState(null);
    const [teamData, setTeamData] = useState(null);
    const [dateRange, setDateRange] = useState({ start: '', end: '' });
    const [exporting, setExporting] = useState(false);

    // Set default date range (last 7 days)
    useEffect(() => {
        const end = new Date().toISOString().split('T')[0];
        const start = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        setDateRange({ start, end });
    }, []);

    const fetchExecutiveReport = async () => {
        setLoading(true);
        try {
            const res = await api.get(`/reports/executive?start_date=${dateRange.start}&end_date=${dateRange.end}&include_ai_summary=true`);
            setExecutiveData(res.data);
        } catch (error) {
            toast.error('Failed to fetch executive report');
        } finally {
            setLoading(false);
        }
    };

    const fetchSLAReport = async () => {
        try {
            const res = await api.get(`/reports/sla?start_date=${dateRange.start}&end_date=${dateRange.end}`);
            setSlaData(res.data);
        } catch (error) {
            toast.error('Failed to fetch SLA report');
        }
    };

    const fetchIncidentReport = async () => {
        try {
            const res = await api.get(`/reports/incidents?start_date=${dateRange.start}&end_date=${dateRange.end}`);
            setIncidentData(res.data);
        } catch (error) {
            toast.error('Failed to fetch incident report');
        }
    };

    const fetchTeamReport = async () => {
        try {
            const res = await api.get(`/reports/team-performance?start_date=${dateRange.start}&end_date=${dateRange.end}`);
            setTeamData(res.data);
        } catch (error) {
            toast.error('Failed to fetch team report');
        }
    };

    useEffect(() => {
        if (dateRange.start && dateRange.end) {
            fetchExecutiveReport();
            fetchSLAReport();
            fetchIncidentReport();
            fetchTeamReport();
        }
    }, [dateRange]);

    const handleExport = async (format) => {
        setExporting(true);
        try {
            const response = await api.get(`/reports/export/${format}?report_type=${activeTab}&start_date=${dateRange.start}&end_date=${dateRange.end}`, {
                responseType: 'blob'
            });
            
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `falconops_${activeTab}_report.${format === 'pdf' ? 'pdf' : 'xlsx'}`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            toast.success(`Report exported as ${format.toUpperCase()}`);
        } catch (error) {
            toast.error('Export failed');
        } finally {
            setExporting(false);
        }
    };

    const KPICard = ({ title, value, icon: Icon, trend, trendValue, color = 'primary' }) => (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`p-5 bg-gradient-to-br from-${color === 'primary' ? 'primary' : color}-500/10 to-transparent border border-${color === 'primary' ? 'primary' : color}-500/20 rounded-sm`}
        >
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-white/50 text-xs uppercase tracking-wider font-mono mb-1">{title}</p>
                    <p className={`font-heading font-bold text-3xl text-${color === 'primary' ? 'primary' : color}-400`}>{value}</p>
                    {trend && (
                        <div className={`flex items-center gap-1 mt-2 text-xs ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}>
                            {trend === 'up' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{trendValue}</span>
                        </div>
                    )}
                </div>
                <div className={`p-3 bg-${color === 'primary' ? 'primary' : color}-500/20 rounded-sm`}>
                    <Icon className={`w-6 h-6 text-${color === 'primary' ? 'primary' : color}-400`} />
                </div>
            </div>
        </motion.div>
    );

    return (
        <>
            <div className="space-y-6" data-testid="executive-reports-page">
                {/* Header */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div>
                        <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white flex items-center gap-3">
                            <BarChart3 className="w-8 h-8 text-primary" />
                            Enterprise Reports
                        </h1>
                        <p className="text-white/50 text-sm font-mono mt-1">AI-Powered Analytics & Executive Insights</p>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* Date Range */}
                        <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-sm px-3 py-2">
                            <Calendar className="w-4 h-4 text-white/40" />
                            <input
                                type="date"
                                value={dateRange.start}
                                onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                                className="bg-transparent text-white text-sm border-none outline-none"
                            />
                            <span className="text-white/30">to</span>
                            <input
                                type="date"
                                value={dateRange.end}
                                onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                                className="bg-transparent text-white text-sm border-none outline-none"
                            />
                        </div>
                        
                        {/* Export Buttons */}
                        <Button
                            onClick={() => handleExport('pdf')}
                            disabled={exporting}
                            variant="outline"
                            size="sm"
                            className="border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-sm"
                        >
                            <Download className="w-4 h-4 mr-2" />
                            PDF
                        </Button>
                        <Button
                            onClick={() => handleExport('excel')}
                            disabled={exporting}
                            variant="outline"
                            size="sm"
                            className="border-green-500/30 text-green-400 hover:bg-green-500/10 rounded-sm"
                        >
                            <Download className="w-4 h-4 mr-2" />
                            Excel
                        </Button>
                        <Button
                            onClick={fetchExecutiveReport}
                            variant="outline"
                            size="sm"
                            className="border-white/20 hover:bg-white/5 text-white rounded-sm"
                        >
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>

                {/* Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                    <TabsList className="bg-white/5 border border-white/10 p-1 rounded-sm">
                        <TabsTrigger value="executive" className="data-[state=active]:bg-primary data-[state=active]:text-black rounded-sm">
                            <BarChart3 className="w-4 h-4 mr-2" />
                            Executive
                        </TabsTrigger>
                        <TabsTrigger value="sla" className="data-[state=active]:bg-primary data-[state=active]:text-black rounded-sm">
                            <Target className="w-4 h-4 mr-2" />
                            SLA & Availability
                        </TabsTrigger>
                        <TabsTrigger value="incidents" className="data-[state=active]:bg-primary data-[state=active]:text-black rounded-sm">
                            <AlertTriangle className="w-4 h-4 mr-2" />
                            Incidents
                        </TabsTrigger>
                        <TabsTrigger value="teams" className="data-[state=active]:bg-primary data-[state=active]:text-black rounded-sm">
                            <Users className="w-4 h-4 mr-2" />
                            Team Performance
                        </TabsTrigger>
                    </TabsList>

                    {/* Executive Dashboard Tab */}
                    <TabsContent value="executive" className="space-y-6">
                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <RefreshCw className="w-10 h-10 animate-spin text-primary" />
                            </div>
                        ) : executiveData && (
                            <>
                                {/* KPI Cards */}
                                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                                    <KPICard
                                        title="Total Incidents"
                                        value={executiveData.kpis?.total_incidents || 0}
                                        icon={AlertTriangle}
                                        color="yellow"
                                    />
                                    <KPICard
                                        title="Resolution Rate"
                                        value={`${executiveData.kpis?.resolution_rate || 0}%`}
                                        icon={CheckCircle}
                                        color="green"
                                    />
                                    <KPICard
                                        title="Avg MTTR"
                                        value={`${executiveData.kpis?.avg_mttr_minutes || 0}m`}
                                        icon={Clock}
                                        color="cyan"
                                    />
                                    <KPICard
                                        title="SLA Compliance"
                                        value={`${executiveData.sla_summary?.sla_compliance || 0}%`}
                                        icon={Target}
                                        color="primary"
                                    />
                                    <KPICard
                                        title="Availability"
                                        value={`${executiveData.sla_summary?.overall_availability || 0}%`}
                                        icon={Activity}
                                        color="green"
                                    />
                                </div>

                                {/* AI Executive Summary */}
                                {executiveData.ai_summary && (
                                    <Card className="bg-gradient-to-r from-primary/10 via-cyan-500/5 to-transparent border-primary/30 rounded-sm">
                                        <CardHeader className="pb-2">
                                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-primary">
                                                <Brain className="w-5 h-5" />
                                                AI Executive Summary
                                                <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 text-[10px]">GPT-5.2</Badge>
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="prose prose-invert prose-sm max-w-none">
                                                <p className="text-white/80 whitespace-pre-wrap leading-relaxed">{executiveData.ai_summary}</p>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}

                                {/* Charts Row */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Incident Trend */}
                                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                        <CardHeader className="pb-2 border-b border-white/5">
                                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                                <TrendingUp className="w-4 h-4 text-cyan-400" />
                                                Incident Trend
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-4">
                                            <ResponsiveContainer width="100%" height={250}>
                                                <AreaChart data={executiveData.incident_trends || []}>
                                                    <defs>
                                                        <linearGradient id="incidentGradient" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3}/>
                                                            <stop offset="95%" stopColor="#00F0FF" stopOpacity={0}/>
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                                    <XAxis dataKey="date" stroke="#666" fontSize={10} />
                                                    <YAxis stroke="#666" fontSize={10} />
                                                    <Tooltip
                                                        contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                                                        labelStyle={{ color: '#fff' }}
                                                    />
                                                    <Area type="monotone" dataKey="count" stroke="#00F0FF" fill="url(#incidentGradient)" />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>

                                    {/* Category Breakdown */}
                                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                        <CardHeader className="pb-2 border-b border-white/5">
                                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                                <Zap className="w-4 h-4 text-primary" />
                                                Top Categories
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-4">
                                            <ResponsiveContainer width="100%" height={250}>
                                                <BarChart data={(executiveData.category_breakdown || []).slice(0, 6)} layout="vertical">
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                                    <XAxis type="number" stroke="#666" fontSize={10} />
                                                    <YAxis dataKey="category" type="category" stroke="#666" fontSize={10} width={100} />
                                                    <Tooltip
                                                        contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                                                    />
                                                    <Bar dataKey="count" fill="#D4AF37" radius={[0, 4, 4, 0]} />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Team Performance */}
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                            <Users className="w-4 h-4 text-primary" />
                                            Team Workload Distribution
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="pt-4">
                                        <div className="space-y-3">
                                            {(executiveData.team_performance || []).slice(0, 5).map((team, idx) => (
                                                <div key={idx} className="flex items-center gap-4">
                                                    <div className="w-32 text-white text-sm truncate">{team.team}</div>
                                                    <div className="flex-1 bg-white/5 rounded-full h-6 overflow-hidden">
                                                        <div
                                                            className="h-full bg-gradient-to-r from-primary to-cyan-500 rounded-full flex items-center justify-end pr-2"
                                                            style={{ width: `${Math.min(team.incident_count * 10, 100)}%` }}
                                                        >
                                                            <span className="text-[10px] text-black font-bold">{team.incident_count}</span>
                                                        </div>
                                                    </div>
                                                    <div className="w-20 text-right">
                                                        <span className="text-cyan-400 text-sm font-mono">{team.avg_mttr_minutes}m</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </>
                        )}
                    </TabsContent>

                    {/* SLA & Availability Tab */}
                    <TabsContent value="sla" className="space-y-6">
                        {slaData && (
                            <>
                                {/* SLA KPIs */}
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                    <KPICard
                                        title="Overall Availability"
                                        value={`${slaData.summary?.overall_availability || 0}%`}
                                        icon={Activity}
                                        color="green"
                                    />
                                    <KPICard
                                        title="SLA Compliance"
                                        value={`${slaData.summary?.sla_compliance || 0}%`}
                                        icon={Target}
                                        color="primary"
                                    />
                                    <KPICard
                                        title="Total Services"
                                        value={slaData.summary?.total_services || 0}
                                        icon={Server}
                                        color="cyan"
                                    />
                                    <KPICard
                                        title="Downtime Events"
                                        value={slaData.summary?.total_downtime_events || 0}
                                        icon={XCircle}
                                        color="red"
                                    />
                                </div>

                                {/* Availability Trend */}
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                            <TrendingUp className="w-4 h-4 text-green-400" />
                                            Availability Trend
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="pt-4">
                                        <ResponsiveContainer width="100%" height={300}>
                                            <LineChart data={slaData.availability_trend || []}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                                <XAxis dataKey="date" stroke="#666" fontSize={10} />
                                                <YAxis domain={[95, 100]} stroke="#666" fontSize={10} />
                                                <Tooltip
                                                    contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                                                />
                                                <Line type="monotone" dataKey="availability" stroke="#10B981" strokeWidth={2} dot={{ fill: '#10B981' }} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>

                                {/* Service SLA Table */}
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                            <Shield className="w-4 h-4 text-primary" />
                                            Service SLA Status
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="pt-4">
                                        <div className="overflow-x-auto">
                                            <table className="w-full">
                                                <thead>
                                                    <tr className="text-left text-white/50 text-xs uppercase border-b border-white/10">
                                                        <th className="pb-3 font-mono">Service</th>
                                                        <th className="pb-3 font-mono">Type</th>
                                                        <th className="pb-3 font-mono">Availability</th>
                                                        <th className="pb-3 font-mono">SLA Target</th>
                                                        <th className="pb-3 font-mono">Latency</th>
                                                        <th className="pb-3 font-mono">Status</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {(slaData.service_breakdown || []).map((svc, idx) => (
                                                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                                                            <td className="py-3 text-white">{svc.service_name}</td>
                                                            <td className="py-3 text-white/60 text-xs uppercase">{svc.type}</td>
                                                            <td className={`py-3 font-mono ${svc.availability_percent >= svc.sla_target ? 'text-green-400' : 'text-red-400'}`}>
                                                                {svc.availability_percent}%
                                                            </td>
                                                            <td className="py-3 text-white/60 font-mono">{svc.sla_target}%</td>
                                                            <td className="py-3 text-cyan-400 font-mono">{svc.avg_latency_ms}ms</td>
                                                            <td className="py-3">
                                                                <Badge className={`text-[10px] ${svc.sla_met ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                                                    {svc.sla_met ? 'MET' : 'BREACHED'}
                                                                </Badge>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </>
                        )}
                    </TabsContent>

                    {/* Incidents Tab */}
                    <TabsContent value="incidents" className="space-y-6">
                        {incidentData && (
                            <>
                                {/* Incident KPIs */}
                                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                                    <KPICard
                                        title="Total Incidents"
                                        value={incidentData.summary?.total_incidents || 0}
                                        icon={AlertTriangle}
                                        color="yellow"
                                    />
                                    <KPICard
                                        title="Resolved"
                                        value={incidentData.summary?.resolved_incidents || 0}
                                        icon={CheckCircle}
                                        color="green"
                                    />
                                    <KPICard
                                        title="Open"
                                        value={incidentData.summary?.open_incidents || 0}
                                        icon={XCircle}
                                        color="red"
                                    />
                                    <KPICard
                                        title="Critical"
                                        value={incidentData.summary?.critical_incidents || 0}
                                        icon={Zap}
                                        color="red"
                                    />
                                    <KPICard
                                        title="Avg MTTR"
                                        value={`${incidentData.mttr_stats?.average_minutes || 0}m`}
                                        icon={Clock}
                                        color="cyan"
                                    />
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Severity Breakdown */}
                                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                        <CardHeader className="pb-2 border-b border-white/5">
                                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                                                Severity Distribution
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-4">
                                            <ResponsiveContainer width="100%" height={250}>
                                                <PieChart>
                                                    <Pie
                                                        data={incidentData.severity_breakdown || []}
                                                        dataKey="count"
                                                        nameKey="severity"
                                                        cx="50%"
                                                        cy="50%"
                                                        innerRadius={60}
                                                        outerRadius={100}
                                                        paddingAngle={5}
                                                    >
                                                        {(incidentData.severity_breakdown || []).map((entry, index) => (
                                                            <Cell key={`cell-${index}`} fill={entry.severity === 'critical' ? '#EF4444' : entry.severity === 'warning' ? '#F59E0B' : '#10B981'} />
                                                        ))}
                                                    </Pie>
                                                    <Tooltip
                                                        contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                                                    />
                                                    <Legend />
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>

                                    {/* Hourly Distribution */}
                                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                        <CardHeader className="pb-2 border-b border-white/5">
                                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                                <Clock className="w-4 h-4 text-cyan-400" />
                                                Hourly Distribution
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="pt-4">
                                            <ResponsiveContainer width="100%" height={250}>
                                                <BarChart data={incidentData.hourly_distribution || []}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                                                    <XAxis dataKey="hour" stroke="#666" fontSize={10} />
                                                    <YAxis stroke="#666" fontSize={10} />
                                                    <Tooltip
                                                        contentStyle={{ background: '#1a1a1a', border: '1px solid #333', borderRadius: '4px' }}
                                                    />
                                                    <Bar dataKey="count" fill="#00F0FF" radius={[4, 4, 0, 0]} />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Recent Incidents */}
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                            <FileText className="w-4 h-4 text-primary" />
                                            Recent Incidents with AI Analysis
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="pt-4">
                                        <div className="space-y-3">
                                            {(incidentData.recent_incidents || []).map((incident, idx) => (
                                                <div key={idx} className="p-4 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="flex items-start justify-between">
                                                        <div>
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <h4 className="text-white font-medium">{incident.title}</h4>
                                                                <Badge className={`text-[10px] ${incident.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                                                                    {incident.severity}
                                                                </Badge>
                                                                <Badge className={`text-[10px] ${incident.status === 'resolved' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                                                                    {incident.status}
                                                                </Badge>
                                                                {incident.has_ai_analysis && (
                                                                    <Badge className="bg-cyan-500/20 text-cyan-400 text-[10px]">
                                                                        <Brain className="w-3 h-3 mr-1" />
                                                                        AI
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                            {incident.root_cause && (
                                                                <p className="text-white/60 text-sm mt-2">{incident.root_cause.substring(0, 200)}...</p>
                                                            )}
                                                        </div>
                                                        <div className="text-right text-xs text-white/40 font-mono">
                                                            {incident.mttr_minutes && <p>MTTR: {incident.mttr_minutes}m</p>}
                                                            <p>{new Date(incident.created_at).toLocaleDateString()}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </>
                        )}
                    </TabsContent>

                    {/* Team Performance Tab */}
                    <TabsContent value="teams" className="space-y-6">
                        {teamData && (
                            <>
                                {/* Team KPIs */}
                                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                                    <KPICard
                                        title="Active Teams"
                                        value={teamData.summary?.total_teams || 0}
                                        icon={Users}
                                        color="primary"
                                    />
                                    <KPICard
                                        title="Total Incidents"
                                        value={teamData.summary?.total_incidents || 0}
                                        icon={AlertTriangle}
                                        color="yellow"
                                    />
                                    <KPICard
                                        title="Overall Resolution Rate"
                                        value={`${teamData.summary?.overall_resolution_rate || 0}%`}
                                        icon={CheckCircle}
                                        color="green"
                                    />
                                </div>

                                {/* Team Performance Table */}
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                            <Users className="w-4 h-4 text-primary" />
                                            Team Performance Breakdown
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="pt-4">
                                        <div className="overflow-x-auto">
                                            <table className="w-full">
                                                <thead>
                                                    <tr className="text-left text-white/50 text-xs uppercase border-b border-white/10">
                                                        <th className="pb-3 font-mono">Team</th>
                                                        <th className="pb-3 font-mono">Incidents</th>
                                                        <th className="pb-3 font-mono">Resolved</th>
                                                        <th className="pb-3 font-mono">Open</th>
                                                        <th className="pb-3 font-mono">Critical</th>
                                                        <th className="pb-3 font-mono">Resolution Rate</th>
                                                        <th className="pb-3 font-mono">Avg MTTR</th>
                                                        <th className="pb-3 font-mono">Workload</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {(teamData.team_breakdown || []).map((team, idx) => (
                                                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                                                            <td className="py-3 text-white font-medium">{team.team}</td>
                                                            <td className="py-3 text-white/80">{team.total_incidents}</td>
                                                            <td className="py-3 text-green-400">{team.resolved}</td>
                                                            <td className="py-3 text-yellow-400">{team.open}</td>
                                                            <td className="py-3 text-red-400">{team.critical}</td>
                                                            <td className={`py-3 font-mono ${team.resolution_rate >= 90 ? 'text-green-400' : team.resolution_rate >= 70 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                                {team.resolution_rate}%
                                                            </td>
                                                            <td className="py-3 text-cyan-400 font-mono">{team.avg_mttr_minutes}m</td>
                                                            <td className="py-3">
                                                                <div className="flex items-center gap-2">
                                                                    <div className="w-20 bg-white/10 rounded-full h-2 overflow-hidden">
                                                                        <div
                                                                            className="h-full bg-primary rounded-full"
                                                                            style={{ width: `${team.workload_percentage}%` }}
                                                                        />
                                                                    </div>
                                                                    <span className="text-white/60 text-xs">{team.workload_percentage}%</span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            </>
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </>
    );
};

export default ExecutiveReportsPage;
