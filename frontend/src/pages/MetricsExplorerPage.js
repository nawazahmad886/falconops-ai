import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    LineChart, Line, AreaChart, Area, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
    Activity, TrendingUp, AlertTriangle, Search, RefreshCw,
    Clock, Server, Database, Cpu, HardDrive, Network, Zap,
    ChevronDown, ChevronRight, Filter, Download, Play,
    BarChart2, PieChart, ArrowUpRight, ArrowDownRight, Minus
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTimeRangeParams } from '../hooks/useTimeRangeParams';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Aggregation options
const AGGREGATIONS = [
    { label: 'Average', value: 'avg' },
    { label: 'Sum', value: 'sum' },
    { label: 'Min', value: 'min' },
    { label: 'Max', value: 'max' },
    { label: 'P50', value: 'p50' },
    { label: 'P95', value: 'p95' },
    { label: 'P99', value: 'p99' },
];

// Bucket options
const BUCKETS = [
    { label: '1 minute', value: '1m' },
    { label: '5 minutes', value: '5m' },
    { label: '15 minutes', value: '15m' },
    { label: '1 hour', value: '1h' },
    { label: '6 hours', value: '6h' },
    { label: '1 day', value: '1d' },
];

const MetricsExplorerPage = () => {
    const { token } = useAuth();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    // Query state
    const [selectedMetric, setSelectedMetric] = useState('');
    const { hours, startTime } = useTimeRangeParams();
    const [aggregation, setAggregation] = useState('avg');
    const [bucket, setBucket] = useState('5m');
    const [hostFilter, setHostFilter] = useState('');
    const [serviceFilter, setServiceFilter] = useState('');
    
    // Data state
    const [catalog, setCatalog] = useState(null);
    const [queryResult, setQueryResult] = useState(null);
    const [topMetrics, setTopMetrics] = useState([]);
    const [anomalies, setAnomalies] = useState([]);
    const [stats, setStats] = useState(null);
    
    // UI state
    const [activeTab, setActiveTab] = useState('explorer');
    const [expandedCategories, setExpandedCategories] = useState({});
    const [chartType, setChartType] = useState('line');
    
    const getAuthHeaders = useCallback(() => ({
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    }), [token]);
    
    // Fetch catalog
    const fetchCatalog = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/metrics/v2/catalog`, {
                headers: getAuthHeaders()
            });
            if (response.ok) {
                const data = await response.json();
                setCatalog(data);
            }
        } catch (err) {
            console.error('Catalog fetch error:', err);
        }
    }, [getAuthHeaders]);
    
    // Fetch stats
    const fetchStats = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/metrics/v2/stats`, {
                headers: getAuthHeaders()
            });
            if (response.ok) {
                const data = await response.json();
                setStats(data);
            }
        } catch (err) {
            console.error('Stats fetch error:', err);
        }
    }, [getAuthHeaders]);
    
    // Fetch anomalies
    const fetchAnomalies = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/api/metrics/v2/anomalies?limit=20`, {
                headers: getAuthHeaders()
            });
            if (response.ok) {
                const data = await response.json();
                setAnomalies(data.anomalies || []);
            }
        } catch (err) {
            console.error('Anomalies fetch error:', err);
        }
    }, [getAuthHeaders]);
    
    // Query metric
    const queryMetric = useCallback(async () => {
        if (!selectedMetric) return;
        
        setLoading(true);
        setError(null);
        
        try {
            let url = `${API_URL}/api/metrics/v2/query?metric_name=${encodeURIComponent(selectedMetric)}&start_time=${startTime}&aggregation=${aggregation}&bucket=${bucket}`;
            
            if (hostFilter) url += `&host=${encodeURIComponent(hostFilter)}`;
            if (serviceFilter) url += `&service=${encodeURIComponent(serviceFilter)}`;
            
            const response = await fetch(url, { headers: getAuthHeaders() });
            
            if (response.ok) {
                const data = await response.json();
                setQueryResult(data);
                
                // Also fetch top metrics for this metric
                fetchTopMetrics(selectedMetric);
            } else {
                setError('Failed to query metrics');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [selectedMetric, startTime, aggregation, bucket, hostFilter, serviceFilter, getAuthHeaders]);
    
    // Fetch top metrics
    const fetchTopMetrics = async (metricName) => {
        try {
            const response = await fetch(
                `${API_URL}/api/metrics/v2/top?metric_name=${encodeURIComponent(metricName)}&group_by=host&limit=10`,
                { headers: getAuthHeaders() }
            );
            if (response.ok) {
                const data = await response.json();
                setTopMetrics(data.results || []);
            }
        } catch (err) {
            console.error('Top metrics fetch error:', err);
        }
    };
    
    // Initial load
    useEffect(() => {
        fetchCatalog();
        fetchStats();
        fetchAnomalies();
        
        const interval = setInterval(() => {
            fetchStats();
            fetchAnomalies();
        }, 30000);
        
        return () => clearInterval(interval);
    }, [fetchCatalog, fetchStats, fetchAnomalies]);
    
    // Toggle category expansion
    const toggleCategory = (category) => {
        setExpandedCategories(prev => ({
            ...prev,
            [category]: !prev[category]
        }));
    };
    
    // Select metric from catalog
    const selectMetricFromCatalog = (metricName) => {
        setSelectedMetric(metricName);
    };
    
    // Format timestamp for chart
    const formatChartTime = (timestamp) => {
        const date = new Date(timestamp);
        if (hours > 24) {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    };
    
    // Get severity color
    const getSeverityColor = (severity) => {
        const colors = {
            critical: 'bg-red-500',
            high: 'bg-orange-500',
            medium: 'bg-yellow-500',
            low: 'bg-blue-500',
            normal: 'bg-green-500'
        };
        return colors[severity] || 'bg-gray-500';
    };
    
    // Get metric icon
    const getMetricIcon = (category) => {
        const icons = {
            infrastructure: <Server className="w-4 h-4" />,
            application: <Activity className="w-4 h-4" />,
            database: <Database className="w-4 h-4" />,
            kubernetes: <Zap className="w-4 h-4" />,
            custom: <BarChart2 className="w-4 h-4" />
        };
        return icons[category] || <Activity className="w-4 h-4" />;
    };
    
    // Render chart
    const renderChart = () => {
        if (!queryResult || !queryResult.series || queryResult.series.length === 0) {
            return (
                <div className="h-80 flex items-center justify-center text-white/50">
                    <div className="text-center">
                        <BarChart2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>No data to display</p>
                        <p className="text-sm">Select a metric and click Query</p>
                    </div>
                </div>
            );
        }
        
        const chartData = queryResult.series.map(s => ({
            timestamp: formatChartTime(s.timestamp),
            value: s.value,
            count: s.count
        }));
        
        if (chartType === 'area') {
            return (
                <ResponsiveContainer width="100%" height={320}>
                    <AreaChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="timestamp" stroke="#888" tick={{ fill: '#888' }} />
                        <YAxis stroke="#888" tick={{ fill: '#888' }} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                            labelStyle={{ color: '#fff' }}
                        />
                        <Area 
                            type="monotone" 
                            dataKey="value" 
                            stroke="#F5B841" 
                            fill="#F5B841" 
                            fillOpacity={0.3}
                            name={selectedMetric}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            );
        }
        
        if (chartType === 'bar') {
            return (
                <ResponsiveContainer width="100%" height={320}>
                    <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                        <XAxis dataKey="timestamp" stroke="#888" tick={{ fill: '#888' }} />
                        <YAxis stroke="#888" tick={{ fill: '#888' }} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                            labelStyle={{ color: '#fff' }}
                        />
                        <Bar dataKey="value" fill="#F5B841" name={selectedMetric} />
                    </BarChart>
                </ResponsiveContainer>
            );
        }
        
        return (
            <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="timestamp" stroke="#888" tick={{ fill: '#888' }} />
                    <YAxis stroke="#888" tick={{ fill: '#888' }} />
                    <Tooltip 
                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                        labelStyle={{ color: '#fff' }}
                    />
                    <Legend />
                    <Line 
                        type="monotone" 
                        dataKey="value" 
                        stroke="#F5B841" 
                        strokeWidth={2}
                        dot={false}
                        name={selectedMetric}
                    />
                </LineChart>
            </ResponsiveContainer>
        );
    };
    
    return (
        <div className="space-y-6" data-testid="metrics-explorer-page">
            {/* Header with Stats */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Activity className="w-7 h-7 text-[#F5B841]" />
                        Metrics Explorer
                    </h1>
                    <p className="text-white/60 mt-1">
                        Query, visualize, and analyze time-series metrics
                    </p>
                </div>
                <Button
                    variant="outline"
                    onClick={() => { fetchCatalog(); fetchStats(); fetchAnomalies(); }}
                    className="border-white/20"
                    data-testid="refresh-metrics-btn"
                >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                </Button>
            </div>
            
            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-white/50 text-sm">Total Data Points</p>
                                    <p className="text-2xl font-bold text-white">
                                        {stats.total_data_points?.toLocaleString() || 0}
                                    </p>
                                </div>
                                <Database className="w-8 h-8 text-blue-400" />
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-white/50 text-sm">Metrics/Hour</p>
                                    <p className="text-2xl font-bold text-white">
                                        {stats.metrics_per_hour?.toLocaleString() || 0}
                                    </p>
                                </div>
                                <TrendingUp className="w-8 h-8 text-emerald-400" />
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-white/50 text-sm">Unique Metrics</p>
                                    <p className="text-2xl font-bold text-white">
                                        {stats.unique_metrics || 0}
                                    </p>
                                </div>
                                <BarChart2 className="w-8 h-8 text-purple-400" />
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-white/50 text-sm">Anomalies/Hour</p>
                                    <p className="text-2xl font-bold text-white">
                                        {stats.anomalies_per_hour || 0}
                                    </p>
                                </div>
                                <AlertTriangle className="w-8 h-8 text-red-400" />
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
            
            {/* Main Content */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList className="bg-white/5">
                    <TabsTrigger value="explorer" data-testid="explorer-tab">
                        <Search className="w-4 h-4 mr-2" />
                        Explorer
                    </TabsTrigger>
                    <TabsTrigger value="catalog" data-testid="catalog-tab">
                        <Database className="w-4 h-4 mr-2" />
                        Catalog
                    </TabsTrigger>
                    <TabsTrigger value="anomalies" data-testid="anomalies-tab">
                        <AlertTriangle className="w-4 h-4 mr-2" />
                        Anomalies ({anomalies.length})
                    </TabsTrigger>
                </TabsList>
                
                {/* Explorer Tab */}
                <TabsContent value="explorer" className="space-y-4">
                    {/* Query Builder */}
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardHeader className="pb-3">
                            <CardTitle className="text-white text-lg">Query Builder</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
                                <div className="md:col-span-2">
                                    <label className="text-sm text-white/60 mb-1 block">Metric Name</label>
                                    <Input
                                        placeholder="e.g., cpu_usage"
                                        value={selectedMetric}
                                        onChange={(e) => setSelectedMetric(e.target.value)}
                                        className="bg-white/5 border-white/10 text-white"
                                        data-testid="metric-name-input"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-white/60 mb-1 block">Time Range</label>
                                    <div className="h-10 flex items-center px-3 bg-white/5 border border-white/10 rounded-md text-white/70 text-sm" data-testid="active-time-range">
                                        <Clock className="w-3.5 h-3.5 mr-2 text-white/40" />
                                        Last {hours}h <span className="text-white/30 ml-1 text-xs">(header)</span>
                                    </div>
                                </div>
                                <div>
                                    <label className="text-sm text-white/60 mb-1 block">Aggregation</label>
                                    <Select value={aggregation} onValueChange={setAggregation}>
                                        <SelectTrigger className="bg-white/5 border-white/10 text-white">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {AGGREGATIONS.map(a => (
                                                <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <label className="text-sm text-white/60 mb-1 block">Bucket</label>
                                    <Select value={bucket} onValueChange={setBucket}>
                                        <SelectTrigger className="bg-white/5 border-white/10 text-white">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {BUCKETS.map(b => (
                                                <SelectItem key={b.value} value={b.value}>{b.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-end">
                                    <Button
                                        onClick={queryMetric}
                                        disabled={!selectedMetric || loading}
                                        className="w-full bg-[#F5B841] hover:bg-[#F5B841]/90 text-black"
                                        data-testid="query-btn"
                                    >
                                        {loading ? (
                                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                        ) : (
                                            <Play className="w-4 h-4 mr-2" />
                                        )}
                                        Query
                                    </Button>
                                </div>
                            </div>
                            
                            {/* Filters */}
                            <div className="flex gap-4 pt-2 border-t border-white/10">
                                <div className="flex-1">
                                    <label className="text-sm text-white/60 mb-1 block">Host Filter</label>
                                    <Input
                                        placeholder="Filter by host"
                                        value={hostFilter}
                                        onChange={(e) => setHostFilter(e.target.value)}
                                        className="bg-white/5 border-white/10 text-white"
                                    />
                                </div>
                                <div className="flex-1">
                                    <label className="text-sm text-white/60 mb-1 block">Service Filter</label>
                                    <Input
                                        placeholder="Filter by service"
                                        value={serviceFilter}
                                        onChange={(e) => setServiceFilter(e.target.value)}
                                        className="bg-white/5 border-white/10 text-white"
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    
                    {/* Chart */}
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-white text-lg">
                                        {selectedMetric || 'Select a Metric'}
                                    </CardTitle>
                                    {queryResult && (
                                        <CardDescription>
                                            {queryResult.data_points} data points • {aggregation.toUpperCase()} aggregation • {bucket} buckets
                                        </CardDescription>
                                    )}
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        variant={chartType === 'line' ? 'default' : 'ghost'}
                                        size="sm"
                                        onClick={() => setChartType('line')}
                                        className={chartType === 'line' ? 'bg-[#F5B841] text-black' : ''}
                                    >
                                        Line
                                    </Button>
                                    <Button
                                        variant={chartType === 'area' ? 'default' : 'ghost'}
                                        size="sm"
                                        onClick={() => setChartType('area')}
                                        className={chartType === 'area' ? 'bg-[#F5B841] text-black' : ''}
                                    >
                                        Area
                                    </Button>
                                    <Button
                                        variant={chartType === 'bar' ? 'default' : 'ghost'}
                                        size="sm"
                                        onClick={() => setChartType('bar')}
                                        className={chartType === 'bar' ? 'bg-[#F5B841] text-black' : ''}
                                    >
                                        Bar
                                    </Button>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {error && (
                                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg mb-4 text-red-400">
                                    {error}
                                </div>
                            )}
                            {renderChart()}
                        </CardContent>
                    </Card>
                    
                    {/* Top Metrics */}
                    {topMetrics.length > 0 && (
                        <Card className="bg-[#0a0a0a] border-white/10">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-white text-lg">Top by Host</CardTitle>
                                <CardDescription>Highest {selectedMetric} values by host</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {topMetrics.map((m, idx) => (
                                        <div 
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                                        >
                                            <div className="flex items-center gap-3">
                                                <span className="text-white/50 w-6">{idx + 1}.</span>
                                                <Server className="w-4 h-4 text-blue-400" />
                                                <span className="text-white">{m.host}</span>
                                            </div>
                                            <div className="flex items-center gap-4 text-sm">
                                                <span className="text-white/60">avg: <span className="text-white">{m.avg}</span></span>
                                                <span className="text-white/60">max: <span className="text-red-400">{m.max}</span></span>
                                                <span className="text-white/60">min: <span className="text-emerald-400">{m.min}</span></span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>
                
                {/* Catalog Tab */}
                <TabsContent value="catalog" className="space-y-4">
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardHeader>
                            <CardTitle className="text-white">Metrics Catalog</CardTitle>
                            <CardDescription>
                                Browse all available metrics organized by category
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {catalog && Object.entries(catalog.metrics || {}).map(([category, metrics]) => (
                                <div key={category} className="mb-4">
                                    <button
                                        onClick={() => toggleCategory(category)}
                                        className="flex items-center gap-2 w-full p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                                    >
                                        {expandedCategories[category] ? (
                                            <ChevronDown className="w-4 h-4 text-white/50" />
                                        ) : (
                                            <ChevronRight className="w-4 h-4 text-white/50" />
                                        )}
                                        {getMetricIcon(category)}
                                        <span className="text-white font-medium capitalize">{category}</span>
                                        <Badge variant="outline" className="ml-auto">
                                            {metrics.length} metrics
                                        </Badge>
                                    </button>
                                    
                                    {expandedCategories[category] && metrics.length > 0 && (
                                        <div className="mt-2 ml-6 space-y-1">
                                            {metrics.map((m, idx) => (
                                                <button
                                                    key={idx}
                                                    onClick={() => {
                                                        selectMetricFromCatalog(m.name);
                                                        setActiveTab('explorer');
                                                    }}
                                                    className="flex items-center justify-between w-full p-2 rounded hover:bg-white/5 transition-colors text-left"
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <Activity className="w-3 h-3 text-[#F5B841]" />
                                                        <span className="text-white/80 text-sm">{m.name}</span>
                                                        {m.unit && (
                                                            <span className="text-white/40 text-xs">({m.unit})</span>
                                                        )}
                                                    </div>
                                                    <span className="text-white/40 text-xs">
                                                        {m.count?.toLocaleString()} pts
                                                    </span>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                    
                                    {expandedCategories[category] && metrics.length === 0 && (
                                        <div className="mt-2 ml-6 p-3 text-white/50 text-sm">
                                            No metrics in this category yet
                                        </div>
                                    )}
                                </div>
                            ))}
                            
                            {!catalog && (
                                <div className="text-center py-8 text-white/50">
                                    <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p>Loading catalog...</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
                
                {/* Anomalies Tab */}
                <TabsContent value="anomalies" className="space-y-4">
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <AlertTriangle className="w-5 h-5 text-red-400" />
                                Detected Anomalies
                            </CardTitle>
                            <CardDescription>
                                Metrics with unusual behavior detected by statistical analysis
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {anomalies.length > 0 ? (
                                <div className="space-y-3">
                                    {anomalies.map((a, idx) => (
                                        <div 
                                            key={idx}
                                            className="p-4 bg-white/5 rounded-lg border-l-4 border-l-red-500"
                                        >
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <span className="text-white font-medium">{a.name}</span>
                                                        <Badge className={`${getSeverityColor(a.anomaly?.severity)} text-white`}>
                                                            {a.anomaly?.severity || 'unknown'}
                                                        </Badge>
                                                    </div>
                                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                                        <div>
                                                            <span className="text-white/50">Value:</span>
                                                            <span className="text-white ml-2">{a.value?.toFixed(2)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-white/50">Z-Score:</span>
                                                            <span className="text-red-400 ml-2">{a.anomaly?.z_score}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-white/50">Baseline:</span>
                                                            <span className="text-white ml-2">{a.anomaly?.baseline_mean?.toFixed(2)}</span>
                                                        </div>
                                                        <div>
                                                            <span className="text-white/50">Host:</span>
                                                            <span className="text-white ml-2">{a.tags?.host || 'N/A'}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="text-right text-sm text-white/50">
                                                    <Clock className="w-3 h-3 inline mr-1" />
                                                    {new Date(a.timestamp).toLocaleString()}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-white/50">
                                    <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p>No anomalies detected in the last 24 hours</p>
                                    <p className="text-sm mt-1">The system is operating normally</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default MetricsExplorerPage;
