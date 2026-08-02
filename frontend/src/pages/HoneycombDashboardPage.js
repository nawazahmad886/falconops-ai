import React, { useState, useEffect, useMemo, useCallback } from 'react';
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
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    Hexagon,
    Plus,
    RefreshCw,
    Play,
    Pause,
    Settings,
    Globe,
    Server,
    Wifi,
    Lock,
    Clock,
    TrendingUp,
    TrendingDown,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Activity,
    Eye,
    Maximize2,
    Minimize2,
    Zap,
    Brain,
    BarChart3,
    LineChart,
    Database,
    Cloud,
    Cpu,
    HardDrive,
    Network,
    Shield,
    Target,
    Layers,
    GitBranch,
    ArrowRight,
    ChevronRight,
    X,
    Info,
    Edit,
    Trash2,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { LineChart as RechartsLine, Line, ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts';
import { TracerouteVisualizer } from '../components/TracerouteVisualizer';
import { useTimeRangeParams } from '../hooks/useTimeRangeParams';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

// Calculate health score from uptime and latency
const calculateHealthScore = (monitor) => {
    const uptime = monitor.uptime_percent_24h || 100;
    const latency = monitor.last_latency_ms || 0;
    const slaLatency = monitor.sla_max_latency_ms || 300;
    
    let score = uptime;
    if (latency > slaLatency) {
        score -= Math.min(20, (latency - slaLatency) / slaLatency * 20);
    }
    return Math.max(0, Math.round(score));
};

// Get health status from score
const getHealthStatus = (score) => {
    if (score >= 99) return { status: 'healthy', color: 'green', label: 'Healthy' };
    if (score >= 95) return { status: 'warning', color: 'yellow', label: 'Warning' };
    if (score >= 80) return { status: 'degraded', color: 'orange', label: 'Degraded' };
    return { status: 'critical', color: 'red', label: 'Critical' };
};

// Sparkline component for mini charts
const Sparkline = ({ data, color, height = 30 }) => {
    const chartData = data.slice(-20).map((d, i) => ({
        value: d.latency_ms || 0,
        status: d.status === 'up' ? 1 : 0,
    }));

    return (
        <ResponsiveContainer width="100%" height={height}>
            <AreaChart data={chartData}>
                <defs>
                    <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={color} stopOpacity={0.4}/>
                        <stop offset="95%" stopColor={color} stopOpacity={0}/>
                    </linearGradient>
                </defs>
                <Area 
                    type="monotone" 
                    dataKey="value" 
                    stroke={color} 
                    strokeWidth={1.5}
                    fill={`url(#spark-${color})`}
                />
            </AreaChart>
        </ResponsiveContainer>
    );
};

// Advanced Hexagon Tile
const AdvancedHexTile = ({ monitor, results, onClick, index, isSelected, viewMode }) => {
    const healthScore = calculateHealthScore(monitor);
    const health = getHealthStatus(healthScore);
    
    const colorMap = {
        green: {
            bg: 'from-emerald-500/20 via-emerald-600/10 to-emerald-700/5',
            border: 'border-emerald-500/40',
            glow: '0 0 30px rgba(16, 185, 129, 0.3)',
            text: '#10B981',
            pulse: false,
        },
        yellow: {
            bg: 'from-amber-500/20 via-amber-600/10 to-amber-700/5',
            border: 'border-amber-500/40',
            glow: '0 0 30px rgba(245, 158, 11, 0.3)',
            text: '#F59E0B',
            pulse: false,
        },
        orange: {
            bg: 'from-orange-500/20 via-orange-600/10 to-orange-700/5',
            border: 'border-orange-500/40',
            glow: '0 0 30px rgba(249, 115, 22, 0.3)',
            text: '#F97316',
            pulse: true,
        },
        red: {
            bg: 'from-red-500/25 via-red-600/15 to-red-700/5',
            border: 'border-red-500/50',
            glow: '0 0 40px rgba(239, 68, 68, 0.4)',
            text: '#EF4444',
            pulse: true,
        },
    };

    const colors = colorMap[health.color] || colorMap.green;
    
    const typeIcons = {
        ping: Wifi,
        http: Globe,
        tcp: Server,
        ssl: Lock,
    };
    const TypeIcon = typeIcons[monitor.monitor_type] || Activity;

    // Compact view
    if (viewMode === 'compact') {
        return (
            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.02 }}
                onClick={() => onClick(monitor)}
                className={`
                    w-16 h-16 cursor-pointer transition-all duration-200
                    hover:scale-110 hover:z-10 relative
                    ${colors.pulse ? 'animate-pulse' : ''}
                `}
                style={{
                    clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
                }}
            >
                <div className={`w-full h-full bg-gradient-to-b ${colors.bg} border ${colors.border} flex items-center justify-center`}
                    style={{ clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }}>
                    <div className="text-center">
                        <TypeIcon className="w-5 h-5 mx-auto" style={{ color: colors.text }} />
                        <p className="text-[8px] font-bold mt-1" style={{ color: colors.text }}>{healthScore}</p>
                    </div>
                </div>
            </motion.div>
        );
    }

    // Full view
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ delay: index * 0.03, duration: 0.4, type: 'spring' }}
            className="relative"
            style={{ width: '160px', height: '185px' }}
        >
            <div
                onClick={() => onClick(monitor)}
                className={`
                    cursor-pointer transition-all duration-300 transform 
                    hover:scale-105 hover:z-20
                    ${isSelected ? 'scale-110 z-30' : ''}
                `}
                style={{ boxShadow: isSelected ? colors.glow : 'none' }}
            >
                {/* Hexagon Shape */}
                <div
                    className={`
                        relative w-[150px] h-[173px] mx-auto
                        bg-gradient-to-b ${colors.bg}
                        border-2 ${colors.border}
                        backdrop-blur-sm
                        transition-all duration-300
                    `}
                    style={{
                        clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
                    }}
                >
                    {/* Problem indicator */}
                    {health.color === 'red' && (
                        <div className="absolute top-2 right-4 z-10">
                            <div className="w-4 h-4 bg-red-500 rounded-full animate-ping absolute" />
                            <div className="w-4 h-4 bg-red-500 rounded-full flex items-center justify-center relative">
                                <AlertTriangle className="w-2.5 h-2.5 text-white" />
                            </div>
                        </div>
                    )}

                    {/* Content */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-3">
                        {/* Health Score Circle */}
                        <div 
                            className="w-14 h-14 rounded-full flex items-center justify-center mb-2 relative"
                            style={{ 
                                background: `conic-gradient(${colors.text} ${healthScore}%, transparent ${healthScore}%)`,
                                padding: '3px'
                            }}
                        >
                            <div className="w-full h-full rounded-full bg-black/60 flex flex-col items-center justify-center">
                                <span className="font-heading font-bold text-lg" style={{ color: colors.text }}>
                                    {healthScore}
                                </span>
                            </div>
                        </div>

                        {/* Monitor Name */}
                        <p className="text-white text-xs font-medium text-center truncate w-full px-1 leading-tight">
                            {monitor.name}
                        </p>

                        {/* Mini Sparkline */}
                        {results && results.length > 0 && (
                            <div className="w-full h-6 mt-1 px-2">
                                <Sparkline data={results} color={colors.text} height={24} />
                            </div>
                        )}

                        {/* Type & Latency */}
                        <div className="flex items-center gap-2 mt-1">
                            <TypeIcon className="w-3 h-3 text-white/50" />
                            <span className="text-[10px] font-mono text-white/60">
                                {monitor.last_latency_ms ? `${monitor.last_latency_ms}ms` : '--'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

// Environment Group Header
const EnvironmentGroup = ({ environment, monitors, children }) => {
    const healthyCount = monitors.filter(m => calculateHealthScore(m) >= 99).length;
    const totalCount = monitors.length;
    
    return (
        <div className="mb-8">
            <div className="flex items-center gap-3 mb-4 px-2">
                <div className={`w-3 h-3 rounded-full ${
                    healthyCount === totalCount ? 'bg-green-400' :
                    healthyCount > totalCount / 2 ? 'bg-yellow-400' : 'bg-red-400'
                }`} />
                <h3 className="font-heading font-bold text-sm uppercase tracking-wider text-white/80">
                    {environment}
                </h3>
                <Badge className="bg-white/10 text-white/60 text-[10px]">
                    {healthyCount}/{totalCount} healthy
                </Badge>
            </div>
            {children}
        </div>
    );
};

// Side Panel for detailed view
const DetailPanel = ({ monitor, results, onClose, onRunCheck, onRunTrace }) => {
    if (!monitor) return null;

    const healthScore = calculateHealthScore(monitor);
    const health = getHealthStatus(healthScore);
    
    const recentResults = results?.slice(0, 50) || [];
    const avgLatency = recentResults.length > 0 
        ? Math.round(recentResults.filter(r => r.latency_ms).reduce((a, b) => a + (b.latency_ms || 0), 0) / recentResults.filter(r => r.latency_ms).length)
        : 0;
    const upCount = recentResults.filter(r => r.status === 'up').length;
    const uptimeRecent = recentResults.length > 0 ? Math.round((upCount / recentResults.length) * 100) : 100;

    const chartData = recentResults.slice(0, 30).reverse().map((r, i) => ({
        time: i,
        latency: r.latency_ms || 0,
        status: r.status === 'up' ? 100 : 0,
    }));

    return (
        <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            className="fixed right-0 top-0 h-full w-[400px] bg-[#0a0a0a] border-l border-white/10 z-50 overflow-y-auto"
        >
            {/* Header */}
            <div className="sticky top-0 bg-[#0a0a0a] border-b border-white/10 p-4">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                            health.color === 'green' ? 'bg-green-500/20' :
                            health.color === 'yellow' ? 'bg-yellow-500/20' :
                            health.color === 'orange' ? 'bg-orange-500/20' : 'bg-red-500/20'
                        }`}>
                            <span className={`font-heading font-bold text-xl ${
                                health.color === 'green' ? 'text-green-400' :
                                health.color === 'yellow' ? 'text-yellow-400' :
                                health.color === 'orange' ? 'text-orange-400' : 'text-red-400'
                            }`}>{healthScore}</span>
                        </div>
                        <div>
                            <h2 className="font-heading font-bold text-lg text-white">{monitor.name}</h2>
                            <p className="text-xs text-white/50 font-mono">{monitor.target}</p>
                        </div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={onClose} className="text-white/50 hover:text-white">
                        <X className="w-5 h-5" />
                    </Button>
                </div>

                {/* Status Badge */}
                <div className={`p-3 rounded-sm ${
                    health.color === 'green' ? 'bg-green-500/10 border border-green-500/30' :
                    health.color === 'yellow' ? 'bg-yellow-500/10 border border-yellow-500/30' :
                    health.color === 'orange' ? 'bg-orange-500/10 border border-orange-500/30' :
                    'bg-red-500/10 border border-red-500/30'
                }`}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {health.color === 'green' && <CheckCircle2 className="w-5 h-5 text-green-400" />}
                            {health.color === 'yellow' && <AlertTriangle className="w-5 h-5 text-yellow-400" />}
                            {health.color === 'orange' && <AlertTriangle className="w-5 h-5 text-orange-400" />}
                            {health.color === 'red' && <XCircle className="w-5 h-5 text-red-400" />}
                            <span className={`font-bold uppercase text-sm ${
                                health.color === 'green' ? 'text-green-400' :
                                health.color === 'yellow' ? 'text-yellow-400' :
                                health.color === 'orange' ? 'text-orange-400' : 'text-red-400'
                            }`}>{health.label}</span>
                        </div>
                        <Badge className="bg-white/10 text-white/70 uppercase text-xs">
                            {monitor.monitor_type}
                        </Badge>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="overview" className="p-4">
                <TabsList className="w-full bg-white/5 p-1 rounded-sm">
                    <TabsTrigger value="overview" className="flex-1 text-xs uppercase data-[state=active]:bg-primary data-[state=active]:text-black">
                        Overview
                    </TabsTrigger>
                    <TabsTrigger value="metrics" className="flex-1 text-xs uppercase data-[state=active]:bg-primary data-[state=active]:text-black">
                        Metrics
                    </TabsTrigger>
                    <TabsTrigger value="history" className="flex-1 text-xs uppercase data-[state=active]:bg-primary data-[state=active]:text-black">
                        History
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="mt-4 space-y-4">
                    {/* Key Metrics */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <div className="flex items-center gap-2 mb-1">
                                <TrendingUp className="w-4 h-4 text-green-400" />
                                <span className="text-[10px] text-white/40 uppercase">Uptime (24h)</span>
                            </div>
                            <p className={`font-heading font-bold text-xl ${
                                (monitor.uptime_percent_24h || 100) >= 99.9 ? 'text-green-400' :
                                (monitor.uptime_percent_24h || 100) >= 99 ? 'text-yellow-400' : 'text-red-400'
                            }`}>
                                {monitor.uptime_percent_24h || 100}%
                            </p>
                        </div>
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <div className="flex items-center gap-2 mb-1">
                                <Clock className="w-4 h-4 text-cyan-400" />
                                <span className="text-[10px] text-white/40 uppercase">Avg Latency</span>
                            </div>
                            <p className="font-heading font-bold text-xl text-cyan-400">
                                {avgLatency}ms
                            </p>
                        </div>
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <div className="flex items-center gap-2 mb-1">
                                <Target className="w-4 h-4 text-primary" />
                                <span className="text-[10px] text-white/40 uppercase">SLA Target</span>
                            </div>
                            <p className="font-heading font-bold text-xl text-primary">
                                {monitor.sla_uptime_percent}%
                            </p>
                        </div>
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <div className="flex items-center gap-2 mb-1">
                                <Activity className="w-4 h-4 text-purple-400" />
                                <span className="text-[10px] text-white/40 uppercase">Checks</span>
                            </div>
                            <p className="font-heading font-bold text-xl text-purple-400">
                                {recentResults.length}
                            </p>
                        </div>
                    </div>

                    {/* Latency Chart */}
                    <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                        <h4 className="text-xs text-white/40 uppercase mb-3">Response Time Trend</h4>
                        <div className="h-[120px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chartData}>
                                    <defs>
                                        <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#00F0FF" stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor="#00F0FF" stopOpacity={0}/>
                                        </linearGradient>
                                    </defs>
                                    <Tooltip 
                                        contentStyle={{ 
                                            backgroundColor: '#0a0a0a', 
                                            border: '1px solid rgba(255,255,255,0.1)',
                                            borderRadius: '4px',
                                            fontSize: '12px'
                                        }}
                                        labelFormatter={() => ''}
                                        formatter={(value) => [`${value}ms`, 'Latency']}
                                    />
                                    <Area 
                                        type="monotone" 
                                        dataKey="latency" 
                                        stroke="#00F0FF" 
                                        strokeWidth={2}
                                        fill="url(#latencyGradient)"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Configuration */}
                    <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                        <h4 className="text-xs text-white/40 uppercase mb-3">Configuration</h4>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span className="text-white/50">Environment</span>
                                <span className="text-white uppercase">{monitor.environment}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/50">Check Interval</span>
                                <span className="text-white">{monitor.interval_seconds}s</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/50">Timeout</span>
                                <span className="text-white">{monitor.timeout_seconds}s</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-white/50">Max Latency SLA</span>
                                <span className="text-white">{monitor.sla_max_latency_ms}ms</span>
                            </div>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                        <Button 
                            onClick={() => onRunCheck(monitor.id)}
                            className="flex-1 bg-cyan-500 text-black hover:bg-cyan-400 font-bold uppercase"
                        >
                            <Play className="w-4 h-4 mr-2" />
                            Run Check
                        </Button>
                        <Button 
                            onClick={() => onRunTrace(monitor)}
                            variant="outline"
                            className="flex-1 border-purple-500/50 text-purple-400 hover:bg-purple-500/10 font-bold uppercase"
                        >
                            <Network className="w-4 h-4 mr-2" />
                            Trace Path
                        </Button>
                    </div>
                </TabsContent>

                <TabsContent value="metrics" className="mt-4 space-y-4">
                    {/* Status Distribution */}
                    <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                        <h4 className="text-xs text-white/40 uppercase mb-3">Status Distribution (Last 50)</h4>
                        <div className="flex gap-1 flex-wrap">
                            {recentResults.map((r, i) => (
                                <div
                                    key={i}
                                    className={`w-4 h-4 rounded-sm ${
                                        r.status === 'up' ? 'bg-green-500/60' :
                                        r.status === 'timeout' ? 'bg-yellow-500/60' : 'bg-red-500/60'
                                    }`}
                                    title={`${r.status} - ${r.latency_ms || 0}ms`}
                                />
                            ))}
                        </div>
                        <div className="flex gap-4 mt-3 text-xs text-white/50">
                            <span className="flex items-center gap-1">
                                <div className="w-3 h-3 bg-green-500/60 rounded-sm" /> Up: {upCount}
                            </span>
                            <span className="flex items-center gap-1">
                                <div className="w-3 h-3 bg-red-500/60 rounded-sm" /> Down: {recentResults.length - upCount}
                            </span>
                        </div>
                    </div>

                    {/* Percentile Latencies */}
                    <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                        <h4 className="text-xs text-white/40 uppercase mb-3">Latency Percentiles</h4>
                        {(() => {
                            const latencies = recentResults.filter(r => r.latency_ms).map(r => r.latency_ms).sort((a, b) => a - b);
                            if (latencies.length === 0) return <p className="text-white/30 text-sm">No data</p>;
                            const p50 = latencies[Math.floor(latencies.length * 0.5)] || 0;
                            const p90 = latencies[Math.floor(latencies.length * 0.9)] || 0;
                            const p99 = latencies[Math.floor(latencies.length * 0.99)] || 0;
                            return (
                                <div className="space-y-2">
                                    <div className="flex justify-between items-center">
                                        <span className="text-white/50 text-sm">P50</span>
                                        <div className="flex-1 mx-4 h-2 bg-white/10 rounded-full overflow-hidden">
                                            <div className="h-full bg-green-500" style={{ width: `${Math.min(100, p50 / 5)}%` }} />
                                        </div>
                                        <span className="text-white font-mono text-sm">{p50}ms</span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-white/50 text-sm">P90</span>
                                        <div className="flex-1 mx-4 h-2 bg-white/10 rounded-full overflow-hidden">
                                            <div className="h-full bg-yellow-500" style={{ width: `${Math.min(100, p90 / 5)}%` }} />
                                        </div>
                                        <span className="text-white font-mono text-sm">{p90}ms</span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                        <span className="text-white/50 text-sm">P99</span>
                                        <div className="flex-1 mx-4 h-2 bg-white/10 rounded-full overflow-hidden">
                                            <div className="h-full bg-red-500" style={{ width: `${Math.min(100, p99 / 5)}%` }} />
                                        </div>
                                        <span className="text-white font-mono text-sm">{p99}ms</span>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                </TabsContent>

                <TabsContent value="history" className="mt-4">
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                        {recentResults.slice(0, 20).map((r, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-white/5 rounded-sm">
                                <div className="flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${
                                        r.status === 'up' ? 'bg-green-400' : 'bg-red-400'
                                    }`} />
                                    <span className={`text-xs font-mono uppercase ${
                                        r.status === 'up' ? 'text-green-400' : 'text-red-400'
                                    }`}>{r.status}</span>
                                </div>
                                <span className="text-xs text-white/50 font-mono">
                                    {r.latency_ms ? `${r.latency_ms}ms` : '--'}
                                </span>
                                <span className="text-xs text-white/30">
                                    {new Date(r.created_at).toLocaleTimeString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </TabsContent>
            </Tabs>
        </motion.div>
    );
};

// Main Component
export const HoneycombDashboardPage = () => {
    const { api } = useAuth();
    const [monitors, setMonitors] = useState([]);
    const [monitorResults, setMonitorResults] = useState({});
    const [loading, setLoading] = useState(true);
    const [selectedMonitor, setSelectedMonitor] = useState(null);
    const [showPanel, setShowPanel] = useState(false);
    const [viewMode, setViewMode] = useState('full'); // full, compact
    const [groupBy, setGroupBy] = useState('none'); // none, environment, type
    const [filter, setFilter] = useState('all');
    const [schedulerRunning, setSchedulerRunning] = useState(false);
    const [fullscreen, setFullscreen] = useState(false);
    const [showAddDialog, setShowAddDialog] = useState(false);
    const [showTraceroute, setShowTraceroute] = useState(false);
    const [traceMonitor, setTraceMonitor] = useState(null);

    const { hours } = useTimeRangeParams();

    // Edit monitor state
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [editMonitor, setEditMonitor] = useState(null);
    
    const [newMonitor, setNewMonitor] = useState({
        name: '',
        target: '',
        monitor_type: 'http',
        environment: 'production',
        sla_uptime_percent: 99.9,
        sla_max_latency_ms: 300,
    });

    const fetchData = useCallback(async () => {
        try {
            const [monitorsRes, schedulerRes] = await Promise.all([
                api.get('/monitors'),
                api.get('/monitors/status/health'),
            ]);
            setMonitors(monitorsRes.data);
            setSchedulerRunning(schedulerRes.data.monitoring_scheduler_running);

            // Fetch results for each monitor
            const resultsPromises = monitorsRes.data.map(m =>
                api.get(`/monitors/${m.id}/results?hours=${hours}&limit=50`).then(res => ({ id: m.id, results: res.data })).catch(() => ({ id: m.id, results: [] }))
            );
            const resultsData = await Promise.all(resultsPromises);
            const resultsMap = {};
            resultsData.forEach(r => { resultsMap[r.id] = r.results; });
            setMonitorResults(resultsMap);
        } catch (error) {
            console.error('Failed to load data:', error);
            toast.error('Failed to load data');
        } finally {
            setLoading(false);
        }
    }, [api, hours]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    useAutoRefresh(fetchData);

    const handleSelectMonitor = async (monitor) => {
        setSelectedMonitor(monitor);
        setShowPanel(true);
    };

    const handleRunCheck = async (monitorId) => {
        try {
            const result = await api.post(`/monitors/${monitorId}/check`);
            toast.success(`Status: ${result.data.result.status.toUpperCase()}`);
            fetchData();
        } catch (error) {
            toast.error('Check failed');
        }
    };

    const handleOpenTraceroute = (monitor) => {
        setTraceMonitor(monitor);
        setShowTraceroute(true);
    };

    const handleCloseTraceroute = () => {
        setShowTraceroute(false);
        setTraceMonitor(null);
    };

    const handleAddMonitor = async () => {
        try {
            await api.post('/monitors', { ...newMonitor, enabled: true });
            toast.success('Monitor added');
            setShowAddDialog(false);
            fetchData();
        } catch (error) {
            toast.error('Failed to add');
        }
    };

    // Filter and group monitors
    const processedMonitors = useMemo(() => {
        let filtered = monitors.filter(m => {
            if (filter === 'all') return true;
            if (filter === 'healthy') return calculateHealthScore(m) >= 99;
            if (filter === 'warning') return calculateHealthScore(m) >= 80 && calculateHealthScore(m) < 99;
            if (filter === 'critical') return calculateHealthScore(m) < 80;
            if (filter === 'ping') return m.monitor_type === 'ping';
            if (filter === 'http') return m.monitor_type === 'http';
            if (filter === 'ssl') return m.monitor_type === 'ssl';
            return true;
        });

        if (groupBy === 'none') return { ungrouped: filtered };

        const groups = {};
        filtered.forEach(m => {
            const key = groupBy === 'environment' ? m.environment : m.monitor_type;
            if (!groups[key]) groups[key] = [];
            groups[key].push(m);
        });
        return groups;
    }, [monitors, filter, groupBy]);

    // Stats
    const stats = useMemo(() => {
        const scores = monitors.map(m => calculateHealthScore(m));
        return {
            total: monitors.length,
            healthy: scores.filter(s => s >= 99).length,
            warning: scores.filter(s => s >= 80 && s < 99).length,
            critical: scores.filter(s => s < 80).length,
            avgScore: scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 100,
        };
    }, [monitors]);

    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <div className="text-center">
                        <div className="relative w-20 h-20 mx-auto mb-4">
                            <Hexagon className="w-20 h-20 text-primary/30 animate-pulse" />
                            <RefreshCw className="w-8 h-8 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-spin" />
                        </div>
                        <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Initializing Honeycomb...</p>
                    </div>
                </div>
            </>
        );
    }

    const content = (
        <div className={`space-y-6 ${fullscreen ? 'p-6' : ''}`} data-testid="honeycomb-dashboard">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-3 mb-1">
                        <Hexagon className="w-8 h-8 text-primary" />
                        <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white">
                            Service Topology
                        </h1>
                        <Badge className={`${schedulerRunning ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'} border`}>
                            {schedulerRunning ? 'LIVE' : 'PAUSED'}
                        </Badge>
                    </div>
                    <p className="text-white/50 text-sm font-mono">Real-time health topology • Dynatrace-style monitoring</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    {/* View Mode */}
                    <div className="flex bg-white/5 rounded-sm p-1">
                        <Button
                            size="sm"
                            variant={viewMode === 'full' ? 'default' : 'ghost'}
                            onClick={() => setViewMode('full')}
                            className={`text-xs ${viewMode === 'full' ? 'bg-primary text-black' : 'text-white/60'}`}
                        >
                            <Maximize2 className="w-3 h-3 mr-1" /> Full
                        </Button>
                        <Button
                            size="sm"
                            variant={viewMode === 'compact' ? 'default' : 'ghost'}
                            onClick={() => setViewMode('compact')}
                            className={`text-xs ${viewMode === 'compact' ? 'bg-primary text-black' : 'text-white/60'}`}
                        >
                            <Minimize2 className="w-3 h-3 mr-1" /> Compact
                        </Button>
                    </div>

                    {/* Group By */}
                    <Select value={groupBy} onValueChange={setGroupBy}>
                        <SelectTrigger className="w-[140px] bg-white/5 border-white/10 text-white text-xs">
                            <Layers className="w-3 h-3 mr-2" />
                            <SelectValue placeholder="Group by" />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0a0a0a] border-white/10">
                            <SelectItem value="none">No Grouping</SelectItem>
                            <SelectItem value="environment">Environment</SelectItem>
                            <SelectItem value="type">Type</SelectItem>
                        </SelectContent>
                    </Select>

                    <Button onClick={fetchData} variant="outline" size="sm" className="border-white/20 text-white">
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>

                    <Button onClick={() => setFullscreen(!fullscreen)} variant="outline" size="sm" className="border-white/20 text-white">
                        {fullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                    </Button>

                    <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                        <DialogTrigger asChild>
                            <Button className="bg-primary text-black font-bold uppercase">
                                <Plus className="w-4 h-4 mr-1" /> Add
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0a0a0a] border-white/10">
                            <DialogHeader>
                                <DialogTitle className="font-heading text-white uppercase">Add Service Monitor</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 mt-4">
                                <Input
                                    placeholder="Service Name"
                                    value={newMonitor.name}
                                    onChange={(e) => setNewMonitor({ ...newMonitor, name: e.target.value })}
                                    className="bg-black/50 border-white/10 text-white"
                                />
                                <Input
                                    placeholder="URL or Hostname"
                                    value={newMonitor.target}
                                    onChange={(e) => setNewMonitor({ ...newMonitor, target: e.target.value })}
                                    className="bg-black/50 border-white/10 text-white"
                                />
                                <div className="grid grid-cols-2 gap-4">
                                    <Select value={newMonitor.monitor_type} onValueChange={(v) => setNewMonitor({ ...newMonitor, monitor_type: v })}>
                                        <SelectTrigger className="bg-black/50 border-white/10 text-white">
                                            <SelectValue placeholder="Type" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0a0a0a] border-white/10">
                                            <SelectItem value="http">HTTP/HTTPS</SelectItem>
                                            <SelectItem value="ping">Ping</SelectItem>
                                            <SelectItem value="ssl">SSL Cert</SelectItem>
                                            <SelectItem value="tcp">TCP Port</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Select value={newMonitor.environment} onValueChange={(v) => setNewMonitor({ ...newMonitor, environment: v })}>
                                        <SelectTrigger className="bg-black/50 border-white/10 text-white">
                                            <SelectValue placeholder="Environment" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-[#0a0a0a] border-white/10">
                                            <SelectItem value="production">Production</SelectItem>
                                            <SelectItem value="staging">Staging</SelectItem>
                                            <SelectItem value="development">Development</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <Button onClick={handleAddMonitor} className="w-full bg-primary text-black font-bold uppercase">
                                    Add Monitor
                                </Button>
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* Health Summary */}
            <div className="grid grid-cols-5 gap-4">
                <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20 rounded-sm">
                    <CardContent className="p-4 text-center">
                        <p className="font-heading font-bold text-4xl text-primary">{stats.avgScore}</p>
                        <p className="text-[10px] text-white/50 uppercase mt-1">Health Score</p>
                    </CardContent>
                </Card>
                <Card className="bg-white/5 border-white/10 rounded-sm cursor-pointer hover:border-white/30" onClick={() => setFilter('all')}>
                    <CardContent className="p-4 text-center">
                        <p className="font-heading font-bold text-3xl text-white">{stats.total}</p>
                        <p className="text-[10px] text-white/50 uppercase mt-1">Total</p>
                    </CardContent>
                </Card>
                <Card className="bg-green-500/5 border-green-500/20 rounded-sm cursor-pointer hover:border-green-500/40" onClick={() => setFilter('healthy')}>
                    <CardContent className="p-4 text-center">
                        <p className="font-heading font-bold text-3xl text-green-400">{stats.healthy}</p>
                        <p className="text-[10px] text-white/50 uppercase mt-1">Healthy</p>
                    </CardContent>
                </Card>
                <Card className="bg-yellow-500/5 border-yellow-500/20 rounded-sm cursor-pointer hover:border-yellow-500/40" onClick={() => setFilter('warning')}>
                    <CardContent className="p-4 text-center">
                        <p className="font-heading font-bold text-3xl text-yellow-400">{stats.warning}</p>
                        <p className="text-[10px] text-white/50 uppercase mt-1">Warning</p>
                    </CardContent>
                </Card>
                <Card className="bg-red-500/5 border-red-500/20 rounded-sm cursor-pointer hover:border-red-500/40" onClick={() => setFilter('critical')}>
                    <CardContent className="p-4 text-center">
                        <p className="font-heading font-bold text-3xl text-red-400">{stats.critical}</p>
                        <p className="text-[10px] text-white/50 uppercase mt-1">Critical</p>
                    </CardContent>
                </Card>
            </div>

            {/* Type Filters */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-white/40 text-xs font-mono mr-2">FILTER:</span>
                {[
                    { key: 'all', icon: Hexagon, label: 'All' },
                    { key: 'ping', icon: Wifi, label: 'Ping' },
                    { key: 'http', icon: Globe, label: 'HTTP' },
                    { key: 'ssl', icon: Lock, label: 'SSL' },
                    { key: 'dns', icon: Database, label: 'DNS' },
                ].map(f => (
                    <Button
                        key={f.key}
                        size="sm"
                        variant={filter === f.key ? 'default' : 'outline'}
                        onClick={() => setFilter(f.key)}
                        className={`text-xs uppercase rounded-sm ${
                            filter === f.key ? 'bg-primary text-black' : 'border-white/20 text-white/60'
                        }`}
                    >
                        <f.icon className="w-3 h-3 mr-1" />
                        {f.label}
                    </Button>
                ))}
            </div>

            {/* Honeycomb Grid */}
            <Card className="bg-[#0a0a0a]/50 border-white/5 rounded-sm backdrop-blur-sm">
                <CardContent className="p-6 min-h-[400px]">
                    {Object.keys(processedMonitors).length === 0 || 
                     Object.values(processedMonitors).every(arr => arr.length === 0) ? (
                        <div className="text-center py-20">
                            <Hexagon className="w-24 h-24 mx-auto mb-4 text-white/10" />
                            <p className="text-white/40 font-heading text-lg uppercase mb-2">No Services Found</p>
                            <p className="text-white/30 text-sm mb-4">
                                {filter !== 'all' ? 'Try changing filters' : 'Add your first service to monitor'}
                            </p>
                            <Button onClick={() => setShowAddDialog(true)} className="bg-primary text-black">
                                <Plus className="w-4 h-4 mr-2" /> Add Service
                            </Button>
                        </div>
                    ) : (
                        Object.entries(processedMonitors).map(([group, groupMonitors]) => (
                            groupBy === 'none' ? (
                                <div key="ungrouped" className="flex flex-wrap justify-center gap-4 py-4">
                                    {groupMonitors.map((monitor, idx) => (
                                        <AdvancedHexTile
                                            key={monitor.id}
                                            monitor={monitor}
                                            results={monitorResults[monitor.id]}
                                            onClick={handleSelectMonitor}
                                            index={idx}
                                            isSelected={selectedMonitor?.id === monitor.id}
                                            viewMode={viewMode}
                                        />
                                    ))}
                                </div>
                            ) : (
                                <EnvironmentGroup key={group} environment={group} monitors={groupMonitors}>
                                    <div className="flex flex-wrap gap-4">
                                        {groupMonitors.map((monitor, idx) => (
                                            <AdvancedHexTile
                                                key={monitor.id}
                                                monitor={monitor}
                                                results={monitorResults[monitor.id]}
                                                onClick={handleSelectMonitor}
                                                index={idx}
                                                isSelected={selectedMonitor?.id === monitor.id}
                                                viewMode={viewMode}
                                            />
                                        ))}
                                    </div>
                                </EnvironmentGroup>
                            )
                        ))
                    )}
                </CardContent>
            </Card>

            {/* Legend */}
            <div className="flex items-center justify-center gap-8 text-xs text-white/40">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gradient-to-b from-emerald-500/40 to-emerald-600/20" />
                    <span>Healthy (99%+)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gradient-to-b from-amber-500/40 to-amber-600/20" />
                    <span>Warning (95-99%)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gradient-to-b from-orange-500/40 to-orange-600/20" />
                    <span>Degraded (80-95%)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-gradient-to-b from-red-500/40 to-red-600/20 animate-pulse" />
                    <span>Critical (&lt;80%)</span>
                </div>
            </div>

            {/* Detail Panel */}
            <AnimatePresence>
                {showPanel && selectedMonitor && (
                    <DetailPanel
                        monitor={selectedMonitor}
                        results={monitorResults[selectedMonitor.id]}
                        onClose={() => { setShowPanel(false); setSelectedMonitor(null); }}
                        onRunCheck={handleRunCheck}
                        onRunTrace={handleOpenTraceroute}
                    />
                )}
            </AnimatePresence>

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
    );

    if (fullscreen) {
        return (
            <div className="fixed inset-0 bg-[#050505] z-50 overflow-y-auto">
                {content}
            </div>
        );
    }

    return <>{content}</>;
};
