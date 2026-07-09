import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Separator } from '../components/ui/separator';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    FileText,
    Search,
    RefreshCw,
    AlertTriangle,
    AlertCircle,
    Info,
    Filter,
    Play,
    Brain,
    MessageSquare,
    Send,
    Sparkles,
    TrendingUp,
    Clock,
    Server,
    Zap,
    Eye,
    ChevronDown,
    ChevronUp,
    Copy,
    X,
    Bot,
    User,
    Loader2,
    BarChart3,
    Activity,
    Database,
    Network,
    Cpu,
    HardDrive,
    Shield,
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';

const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', dot: 'bg-red-500' },
    error: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', dot: 'bg-red-500' },
    warning: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', dot: 'bg-yellow-500' },
    info: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', dot: 'bg-blue-500' },
};

const CATEGORY_ICONS = {
    database: Database,
    network: Network,
    memory: Cpu,
    cpu: Cpu,
    disk: HardDrive,
    authentication: Shield,
    application: Activity,
    api: Zap,
    general: FileText,
};

const PIE_COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#22c55e', '#8b5cf6'];

export const LogsPage = () => {
    const { api, user } = useAuth();
    const [activeTab, setActiveTab] = useState('logs');
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);
    
    // Logs state
    const [logs, setLogs] = useState([]);
    const [totalLogs, setTotalLogs] = useState(0);
    const [statistics, setStatistics] = useState(null);
    const [services, setServices] = useState([]);
    const [anomalies, setAnomalies] = useState([]);
    const [correlations, setCorrelations] = useState([]);
    const [aiAnalysis, setAiAnalysis] = useState(null);
    
    // Filters
    const [searchTerm, setSearchTerm] = useState('');
    const [severityFilter, setSeverityFilter] = useState('');
    const [serviceFilter, setServiceFilter] = useState('');
    const [timeRange, setTimeRange] = useState('1');
    
    // Copilot state
    const [copilotOpen, setCopilotOpen] = useState(false);
    const [copilotMessages, setCopilotMessages] = useState([]);
    const [copilotInput, setCopilotInput] = useState('');
    const [copilotLoading, setCopilotLoading] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const chatEndRef = useRef(null);
    
    // Expanded log
    const [expandedLogId, setExpandedLogId] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.append('hours', timeRange);
            params.append('limit', '200');
            if (severityFilter) params.append('severity', severityFilter);
            if (serviceFilter) params.append('service', serviceFilter);
            if (searchTerm) params.append('search', searchTerm);
            
            const [logsRes, statsRes, servicesRes] = await Promise.all([
                api.get(`/logs?${params.toString()}`),
                api.get(`/logs/statistics?hours=${timeRange}`),
                api.get(`/logs/services?hours=${timeRange}`),
            ]);
            
            setLogs(logsRes.data.logs || []);
            setTotalLogs(logsRes.data.total || 0);
            setStatistics(statsRes.data);
            setServices(servicesRes.data || []);
        } catch (error) {
            console.error('Failed to fetch logs:', error);
            toast.error('Failed to fetch logs');
        } finally {
            setLoading(false);
        }
    }, [api, timeRange, severityFilter, serviceFilter, searchTerm]);

    const fetchAnomalies = useCallback(async () => {
        try {
            const res = await api.get(`/logs/anomalies?hours=${timeRange}`);
            setAnomalies(res.data.anomalies || []);
        } catch (error) {
            console.error('Failed to fetch anomalies:', error);
        }
    }, [api, timeRange]);

    const fetchCorrelations = useCallback(async () => {
        try {
            const res = await api.post(`/logs/correlate?hours=${timeRange}&time_window=5`);
            setCorrelations(res.data.events || []);
        } catch (error) {
            console.error('Failed to fetch correlations:', error);
        }
    }, [api, timeRange]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useEffect(() => {
        if (activeTab === 'anomalies') {
            fetchAnomalies();
        } else if (activeTab === 'correlations') {
            fetchCorrelations();
        }
    }, [activeTab, fetchAnomalies, fetchCorrelations]);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [copilotMessages]);

    const handleSimulateLogs = async () => {
        try {
            const res = await api.post('/logs/simulate?count=100');
            toast.success(res.data.message);
            fetchData();
        } catch (error) {
            toast.error('Failed to simulate logs');
        }
    };

    const handleAIAnalysis = async () => {
        setAnalyzing(true);
        try {
            const params = new URLSearchParams();
            params.append('hours', timeRange);
            if (serviceFilter) params.append('service', serviceFilter);
            
            const res = await api.post(`/logs/analyze?${params.toString()}`);
            setAiAnalysis(res.data);
            toast.success('AI Analysis complete');
        } catch (error) {
            toast.error('Failed to run AI analysis');
        } finally {
            setAnalyzing(false);
        }
    };

    const handleCopilotSend = async () => {
        if (!copilotInput.trim()) return;
        
        const userMessage = copilotInput.trim();
        setCopilotInput('');
        setCopilotMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setCopilotLoading(true);
        
        try {
            const res = await api.post('/logs/copilot/chat', {
                message: userMessage,
                session_id: sessionId,
                context: { current_page: 'logs' }
            });
            
            if (!sessionId) {
                setSessionId(res.data.session_id);
            }
            
            setCopilotMessages(prev => [...prev, { role: 'assistant', content: res.data.response }]);
        } catch (error) {
            setCopilotMessages(prev => [...prev, { 
                role: 'assistant', 
                content: 'Sorry, I encountered an error. Please try again.' 
            }]);
        } finally {
            setCopilotLoading(false);
        }
    };

    const getSeverityIcon = (severity) => {
        switch (severity) {
            case 'critical':
            case 'error':
                return <AlertCircle className="w-4 h-4 text-red-400" />;
            case 'warning':
                return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
            default:
                return <Info className="w-4 h-4 text-blue-400" />;
        }
    };

    const formatTimestamp = (ts) => {
        if (!ts) return '--';
        const date = new Date(ts);
        return date.toLocaleString();
    };

    return (
        <>
            <div className="space-y-6" data-testid="logs-page">
                {/* Header */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-heading font-bold text-white uppercase tracking-wider flex items-center gap-3">
                            <FileText className="w-6 h-6 text-cyan-400" />
                            AI Logs Monitoring
                        </h1>
                        <p className="text-white/50 text-sm font-mono mt-1">
                            Intelligent log analysis, anomaly detection & AI-powered RCA
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            variant="outline"
                            onClick={fetchData}
                            disabled={loading}
                            className="border-white/10"
                            data-testid="refresh-logs-btn"
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleSimulateLogs}
                            className="border-cyan-500/30 text-cyan-400"
                            data-testid="simulate-logs-btn"
                        >
                            <Play className="w-4 h-4 mr-2" />
                            Demo Logs
                        </Button>
                        <Button
                            onClick={handleAIAnalysis}
                            disabled={analyzing}
                            className="bg-purple-500 hover:bg-purple-600 text-white"
                            data-testid="ai-analyze-btn"
                        >
                            {analyzing ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Brain className="w-4 h-4 mr-2" />
                            )}
                            AI Analyze
                        </Button>
                        <Button
                            onClick={() => setCopilotOpen(!copilotOpen)}
                            className={`${copilotOpen ? 'bg-primary text-black' : 'bg-primary/20 text-primary'}`}
                            data-testid="copilot-toggle-btn"
                        >
                            <Bot className="w-4 h-4 mr-2" />
                            AI Copilot
                        </Button>
                    </div>
                </div>

                {/* Statistics Cards */}
                {statistics && (
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardContent className="p-4">
                                <p className="text-[10px] font-mono uppercase text-white/40">Total Logs</p>
                                <p className="text-2xl font-bold text-white">{statistics.total_logs?.toLocaleString() || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardContent className="p-4">
                                <p className="text-[10px] font-mono uppercase text-white/40">Error Rate</p>
                                <p className={`text-2xl font-bold ${statistics.error_rate > 0.1 ? 'text-red-400' : 'text-green-400'}`}>
                                    {((statistics.error_rate || 0) * 100).toFixed(1)}%
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0a0a0a] border-red-500/20">
                            <CardContent className="p-4">
                                <p className="text-[10px] font-mono uppercase text-white/40">Critical</p>
                                <p className="text-2xl font-bold text-red-400">{statistics.by_severity?.critical || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0a0a0a] border-yellow-500/20">
                            <CardContent className="p-4">
                                <p className="text-[10px] font-mono uppercase text-white/40">Warnings</p>
                                <p className="text-2xl font-bold text-yellow-400">{statistics.by_severity?.warning || 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="bg-[#0a0a0a] border-blue-500/20">
                            <CardContent className="p-4">
                                <p className="text-[10px] font-mono uppercase text-white/40">Services</p>
                                <p className="text-2xl font-bold text-cyan-400">{Object.keys(statistics.by_service || {}).length}</p>
                            </CardContent>
                        </Card>
                    </div>
                )}

                {/* Filters */}
                <Card className="bg-[#0a0a0a] border-white/5">
                    <CardContent className="p-4">
                        <div className="flex flex-wrap gap-4 items-center">
                            <div className="flex items-center gap-2">
                                <Filter className="w-4 h-4 text-white/40" />
                                <span className="text-white/40 text-sm">Filters:</span>
                            </div>
                            <div className="flex-1 min-w-[200px]">
                                <Input
                                    placeholder="Search logs..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="bg-white/5 border-white/10"
                                    data-testid="log-search-input"
                                />
                            </div>
                            <Select value={severityFilter || "all"} onValueChange={(v) => setSeverityFilter(v === "all" ? "" : v)}>
                                <SelectTrigger className="w-[130px] bg-white/5 border-white/10">
                                    <SelectValue placeholder="Severity" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All</SelectItem>
                                    <SelectItem value="critical">Critical</SelectItem>
                                    <SelectItem value="warning">Warning</SelectItem>
                                    <SelectItem value="info">Info</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select value={serviceFilter || "all"} onValueChange={(v) => setServiceFilter(v === "all" ? "" : v)}>
                                <SelectTrigger className="w-[150px] bg-white/5 border-white/10">
                                    <SelectValue placeholder="Service" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Services</SelectItem>
                                    {services.map((s) => (
                                        <SelectItem key={s.service} value={s.service}>{s.service}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select value={timeRange} onValueChange={setTimeRange}>
                                <SelectTrigger className="w-[120px] bg-white/5 border-white/10">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">Last 1 hour</SelectItem>
                                    <SelectItem value="6">Last 6 hours</SelectItem>
                                    <SelectItem value="24">Last 24 hours</SelectItem>
                                    <SelectItem value="72">Last 3 days</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </CardContent>
                </Card>

                {/* Main Content */}
                <div className="grid lg:grid-cols-3 gap-6">
                    {/* Logs Panel */}
                    <div className={`${copilotOpen ? 'lg:col-span-2' : 'lg:col-span-3'}`}>
                        <Tabs value={activeTab} onValueChange={setActiveTab}>
                            <TabsList className="bg-[#0a0a0a] border border-white/10 mb-4">
                                <TabsTrigger value="logs" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                                    <FileText className="w-4 h-4 mr-2" />
                                    Logs ({totalLogs})
                                </TabsTrigger>
                                <TabsTrigger value="anomalies" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                                    <Zap className="w-4 h-4 mr-2" />
                                    Anomalies ({anomalies.length})
                                </TabsTrigger>
                                <TabsTrigger value="correlations" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                                    <TrendingUp className="w-4 h-4 mr-2" />
                                    Correlations
                                </TabsTrigger>
                                <TabsTrigger value="analysis" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                                    <Brain className="w-4 h-4 mr-2" />
                                    AI Analysis
                                </TabsTrigger>
                            </TabsList>

                            {/* Logs Tab */}
                            <TabsContent value="logs" className="space-y-2">
                                {loading ? (
                                    <div className="flex items-center justify-center py-20">
                                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                                    </div>
                                ) : logs.length === 0 ? (
                                    <Card className="bg-[#0a0a0a] border-white/5">
                                        <CardContent className="py-20 text-center">
                                            <FileText className="w-16 h-16 mx-auto text-white/20 mb-4" />
                                            <p className="text-white/50">No logs found</p>
                                            <Button onClick={handleSimulateLogs} className="mt-4 bg-cyan-500">
                                                <Play className="w-4 h-4 mr-2" />
                                                Generate Demo Logs
                                            </Button>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    <div className="space-y-1 max-h-[600px] overflow-y-auto">
                                        {logs.map((log) => {
                                            const colors = SEVERITY_COLORS[log.severity] || SEVERITY_COLORS.info;
                                            const isExpanded = expandedLogId === log.id;
                                            const CategoryIcon = CATEGORY_ICONS[log.category] || FileText;
                                            
                                            return (
                                                <motion.div
                                                    key={log.id}
                                                    initial={{ opacity: 0 }}
                                                    animate={{ opacity: 1 }}
                                                    className={`p-3 rounded-sm border ${colors.border} ${colors.bg} cursor-pointer hover:bg-white/5 transition-colors`}
                                                    onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                                                >
                                                    <div className="flex items-start gap-3">
                                                        <div className={`w-2 h-2 rounded-full mt-2 ${colors.dot}`} />
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center gap-2 flex-wrap">
                                                                <Badge variant="outline" className={`text-xs ${colors.text} ${colors.border}`}>
                                                                    {log.severity?.toUpperCase()}
                                                                </Badge>
                                                                <Badge variant="outline" className="text-xs text-white/60 border-white/20">
                                                                    <Server className="w-3 h-3 mr-1" />
                                                                    {log.service}
                                                                </Badge>
                                                                <Badge variant="outline" className="text-xs text-white/40 border-white/10">
                                                                    <CategoryIcon className="w-3 h-3 mr-1" />
                                                                    {log.category}
                                                                </Badge>
                                                                <span className="text-xs text-white/30 ml-auto">
                                                                    {formatTimestamp(log.timestamp)}
                                                                </span>
                                                            </div>
                                                            <p className={`font-mono text-sm mt-1 ${isExpanded ? 'text-white' : 'text-white/70 truncate'}`}>
                                                                {log.message}
                                                            </p>
                                                            {isExpanded && (
                                                                <div className="mt-3 pt-3 border-t border-white/10 space-y-2 text-xs">
                                                                    {log.host && (
                                                                        <div className="flex gap-2">
                                                                            <span className="text-white/40">Host:</span>
                                                                            <span className="text-white/70 font-mono">{log.host}</span>
                                                                        </div>
                                                                    )}
                                                                    {log.tags && Object.keys(log.tags).length > 0 && (
                                                                        <div className="flex gap-2 flex-wrap">
                                                                            <span className="text-white/40">Tags:</span>
                                                                            {Object.entries(log.tags).map(([k, v]) => (
                                                                                <Badge key={k} variant="outline" className="text-xs">{k}: {v}</Badge>
                                                                            ))}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                        {isExpanded ? (
                                                            <ChevronUp className="w-4 h-4 text-white/30" />
                                                        ) : (
                                                            <ChevronDown className="w-4 h-4 text-white/30" />
                                                        )}
                                                    </div>
                                                </motion.div>
                                            );
                                        })}
                                    </div>
                                )}
                            </TabsContent>

                            {/* Anomalies Tab */}
                            <TabsContent value="anomalies" className="space-y-2">
                                {anomalies.length === 0 ? (
                                    <Card className="bg-[#0a0a0a] border-white/5">
                                        <CardContent className="py-20 text-center">
                                            <Zap className="w-16 h-16 mx-auto text-green-400/30 mb-4" />
                                            <p className="text-green-400">No anomalies detected</p>
                                            <p className="text-white/40 text-sm mt-2">System is operating normally</p>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    anomalies.map((anomaly, idx) => {
                                        const colors = SEVERITY_COLORS[anomaly.severity] || SEVERITY_COLORS.warning;
                                        return (
                                            <Card key={idx} className={`bg-[#0a0a0a] ${colors.border}`}>
                                                <CardContent className="p-4">
                                                    <div className="flex items-start gap-3">
                                                        <Zap className={`w-5 h-5 ${colors.text}`} />
                                                        <div className="flex-1">
                                                            <div className="flex items-center gap-2">
                                                                <Badge variant="outline" className={`${colors.text} ${colors.border}`}>
                                                                    {anomaly.type?.replace(/_/g, ' ')}
                                                                </Badge>
                                                                <Badge variant="outline" className="text-white/60">
                                                                    {anomaly.service}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-white/80 mt-2">{anomaly.description}</p>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        );
                                    })
                                )}
                            </TabsContent>

                            {/* Correlations Tab */}
                            <TabsContent value="correlations" className="space-y-2">
                                {correlations.length === 0 ? (
                                    <Card className="bg-[#0a0a0a] border-white/5">
                                        <CardContent className="py-20 text-center">
                                            <TrendingUp className="w-16 h-16 mx-auto text-white/20 mb-4" />
                                            <p className="text-white/50">No correlated events found</p>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    correlations.map((event) => (
                                        <Card key={event.id} className="bg-[#0a0a0a] border-white/5">
                                            <CardContent className="p-4">
                                                <div className="flex items-start gap-3">
                                                    <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${
                                                        event.severity === 'critical' ? 'bg-red-500/20' : 'bg-yellow-500/20'
                                                    }`}>
                                                        <TrendingUp className={`w-5 h-5 ${
                                                            event.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'
                                                        }`} />
                                                    </div>
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <Badge variant="outline" className={
                                                                event.severity === 'critical' ? 'border-red-500/30 text-red-400' : 'border-yellow-500/30 text-yellow-400'
                                                            }>
                                                                {event.error_count} errors
                                                            </Badge>
                                                            <Badge variant="outline" className="text-white/60">
                                                                {event.primary_category}
                                                            </Badge>
                                                            <span className="text-xs text-white/40 ml-auto">
                                                                {formatTimestamp(event.time_window)}
                                                            </span>
                                                        </div>
                                                        <p className="text-white/60 text-sm mt-2">
                                                            Services: {event.services_affected?.join(', ')}
                                                        </p>
                                                        {event.sample_messages?.length > 0 && (
                                                            <div className="mt-2 p-2 bg-black/30 rounded-sm">
                                                                <p className="text-xs text-white/40 mb-1">Sample errors:</p>
                                                                {event.sample_messages.slice(0, 2).map((msg, i) => (
                                                                    <p key={i} className="text-xs text-white/60 font-mono truncate">{msg}</p>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))
                                )}
                            </TabsContent>

                            {/* AI Analysis Tab */}
                            <TabsContent value="analysis">
                                {!aiAnalysis ? (
                                    <Card className="bg-[#0a0a0a] border-white/5">
                                        <CardContent className="py-20 text-center">
                                            <Brain className="w-16 h-16 mx-auto text-purple-400/30 mb-4" />
                                            <p className="text-white/50">No AI analysis available</p>
                                            <p className="text-white/30 text-sm mt-2">Click "AI Analyze" to run analysis</p>
                                            <Button onClick={handleAIAnalysis} disabled={analyzing} className="mt-4 bg-purple-500">
                                                {analyzing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Brain className="w-4 h-4 mr-2" />}
                                                Run AI Analysis
                                            </Button>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    <Card className="bg-[#0a0a0a] border-purple-500/20">
                                        <CardHeader>
                                            <CardTitle className="text-white flex items-center gap-2">
                                                <Sparkles className="w-5 h-5 text-purple-400" />
                                                AI Analysis Results
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="flex gap-4 text-sm">
                                                <Badge variant="outline" className="text-white/60">
                                                    {aiAnalysis.logs_analyzed} logs analyzed
                                                </Badge>
                                                <Badge variant="outline" className="text-red-400 border-red-500/30">
                                                    {aiAnalysis.error_count} errors
                                                </Badge>
                                            </div>
                                            <div className="prose prose-invert max-w-none">
                                                <pre className="whitespace-pre-wrap text-sm text-white/80 bg-black/30 p-4 rounded-sm overflow-auto max-h-[400px]">
                                                    {aiAnalysis.analysis}
                                                </pre>
                                            </div>
                                            {aiAnalysis.recommendations?.length > 0 && (
                                                <div>
                                                    <h4 className="text-sm font-medium text-white mb-2">Recommendations:</h4>
                                                    <ul className="space-y-1">
                                                        {aiAnalysis.recommendations.map((rec, i) => (
                                                            <li key={i} className="text-sm text-white/70 flex gap-2">
                                                                <span className="text-purple-400">•</span>
                                                                {rec}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                )}
                            </TabsContent>
                        </Tabs>
                    </div>

                    {/* AI Copilot Panel */}
                    <AnimatePresence>
                        {copilotOpen && (
                            <motion.div
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                className="lg:col-span-1"
                            >
                                <Card className="bg-[#0a0a0a] border-primary/30 h-[700px] flex flex-col">
                                    <CardHeader className="pb-2 border-b border-white/10">
                                        <div className="flex items-center justify-between">
                                            <CardTitle className="text-white flex items-center gap-2">
                                                <Bot className="w-5 h-5 text-primary" />
                                                AI Copilot
                                            </CardTitle>
                                            <Button variant="ghost" size="sm" onClick={() => setCopilotOpen(false)}>
                                                <X className="w-4 h-4" />
                                            </Button>
                                        </div>
                                        <p className="text-xs text-white/40">Ask questions about logs, incidents, and get AI-powered insights</p>
                                    </CardHeader>
                                    <CardContent className="flex-1 flex flex-col p-0">
                                        {/* Messages */}
                                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                            {copilotMessages.length === 0 && (
                                                <div className="text-center py-8">
                                                    <Bot className="w-12 h-12 mx-auto text-primary/30 mb-4" />
                                                    <p className="text-white/50 text-sm">Hi! I'm your AI NOC assistant.</p>
                                                    <p className="text-white/30 text-xs mt-2">Ask me about logs, errors, or incidents.</p>
                                                    <div className="mt-4 space-y-2">
                                                        <Button 
                                                            variant="outline" 
                                                            size="sm" 
                                                            className="text-xs"
                                                            onClick={() => setCopilotInput("What are the critical errors in the last hour?")}
                                                        >
                                                            "What are the critical errors?"
                                                        </Button>
                                                        <Button 
                                                            variant="outline" 
                                                            size="sm" 
                                                            className="text-xs"
                                                            onClick={() => setCopilotInput("Why is the payment service having issues?")}
                                                        >
                                                            "Why is payment service slow?"
                                                        </Button>
                                                    </div>
                                                </div>
                                            )}
                                            {copilotMessages.map((msg, i) => (
                                                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                                        msg.role === 'user' ? 'bg-primary/20' : 'bg-purple-500/20'
                                                    }`}>
                                                        {msg.role === 'user' ? (
                                                            <User className="w-4 h-4 text-primary" />
                                                        ) : (
                                                            <Bot className="w-4 h-4 text-purple-400" />
                                                        )}
                                                    </div>
                                                    <div className={`max-w-[80%] p-3 rounded-sm ${
                                                        msg.role === 'user' 
                                                            ? 'bg-primary/10 border border-primary/20' 
                                                            : 'bg-purple-500/10 border border-purple-500/20'
                                                    }`}>
                                                        <p className="text-sm text-white/80 whitespace-pre-wrap">{msg.content}</p>
                                                    </div>
                                                </div>
                                            ))}
                                            {copilotLoading && (
                                                <div className="flex gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                                                        <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                                                    </div>
                                                    <div className="bg-purple-500/10 border border-purple-500/20 p-3 rounded-sm">
                                                        <p className="text-sm text-white/50">Thinking...</p>
                                                    </div>
                                                </div>
                                            )}
                                            <div ref={chatEndRef} />
                                        </div>
                                        {/* Input */}
                                        <div className="p-4 border-t border-white/10">
                                            <div className="flex gap-2">
                                                <Input
                                                    value={copilotInput}
                                                    onChange={(e) => setCopilotInput(e.target.value)}
                                                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleCopilotSend()}
                                                    placeholder="Ask about logs, errors..."
                                                    className="bg-white/5 border-white/10"
                                                    data-testid="copilot-input"
                                                />
                                                <Button 
                                                    onClick={handleCopilotSend} 
                                                    disabled={copilotLoading || !copilotInput.trim()}
                                                    className="bg-primary text-black"
                                                >
                                                    <Send className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Timeline Chart */}
                {statistics?.timeline?.length > 0 && (
                    <Card className="bg-[#0a0a0a] border-white/5">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <BarChart3 className="w-5 h-5 text-cyan-400" />
                                Log Volume Timeline
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="h-[200px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={statistics.timeline}>
                                    <defs>
                                        <linearGradient id="logGradient" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#00E0FF" stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor="#00E0FF" stopOpacity={0}/>
                                        </linearGradient>
                                        <linearGradient id="errorGradient" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                    <XAxis 
                                        dataKey="hour" 
                                        tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
                                        tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    />
                                    <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} />
                                    <Tooltip 
                                        contentStyle={{ background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.1)' }}
                                        labelFormatter={(v) => new Date(v).toLocaleString()}
                                    />
                                    <Area type="monotone" dataKey="total" stroke="#00E0FF" fill="url(#logGradient)" name="Total" />
                                    <Area type="monotone" dataKey="errors" stroke="#ef4444" fill="url(#errorGradient)" name="Errors" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                )}
            </div>
        </>
    );
};
