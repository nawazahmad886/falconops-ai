import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    Play, 
    Pause, 
    RefreshCw, 
    Bell, 
    AlertTriangle, 
    Server, 
    Cpu, 
    HardDrive, 
    Activity,
    Brain,
    CheckCircle,
    XCircle,
    Clock,
    Zap,
    TrendingUp,
    TrendingDown,
} from 'lucide-react';
import { Button } from './ui/button';

// Simulated services
const SERVICES = ['payment-api', 'user-service', 'order-service', 'inventory-api', 'auth-gateway', 'notification-svc'];
const ALERT_TYPES = ['CPU High', 'Memory Warning', 'Disk Space Low', 'Response Time', 'Error Rate', 'Connection Pool'];
const SEVERITIES = ['critical', 'warning', 'info'];

// Generate random metrics
const generateMetrics = () => ({
    cpu: Math.floor(Math.random() * 40) + 30,
    memory: Math.floor(Math.random() * 35) + 40,
    disk: Math.floor(Math.random() * 30) + 50,
    network: Math.floor(Math.random() * 100) + 50,
});

// Generate random alert
const generateAlert = (id) => ({
    id,
    title: `${ALERT_TYPES[Math.floor(Math.random() * ALERT_TYPES.length)]} on ${SERVICES[Math.floor(Math.random() * SERVICES.length)]}`,
    severity: SEVERITIES[Math.floor(Math.random() * SEVERITIES.length)],
    service: SERVICES[Math.floor(Math.random() * SERVICES.length)],
    timestamp: new Date().toISOString(),
    isNew: true,
});

// Generate AI analysis
const generateAIAnalysis = () => {
    const analyses = [
        { title: 'Memory leak detected in payment-api', confidence: 94, suggestion: 'Restart pod and investigate heap dump' },
        { title: 'Database connection pool exhaustion', confidence: 89, suggestion: 'Increase pool size or optimize queries' },
        { title: 'Cascading failure from auth-gateway', confidence: 91, suggestion: 'Check upstream dependencies' },
        { title: 'CPU saturation due to inefficient loop', confidence: 87, suggestion: 'Review recent deployments' },
        { title: 'Network latency spike from load balancer', confidence: 92, suggestion: 'Check health check configurations' },
    ];
    return analyses[Math.floor(Math.random() * analyses.length)];
};

export const InteractiveDemo = () => {
    const [isRunning, setIsRunning] = useState(false);
    const [metrics, setMetrics] = useState(generateMetrics());
    const [alerts, setAlerts] = useState([]);
    const [incidents, setIncidents] = useState(0);
    const [correlatedAlerts, setCorrelatedAlerts] = useState(0);
    const [aiAnalysis, setAiAnalysis] = useState(null);
    const [showAIPopup, setShowAIPopup] = useState(false);
    const [alertCounter, setAlertCounter] = useState(0);

    // Generate new alert
    const addAlert = useCallback(() => {
        const newAlert = generateAlert(alertCounter);
        setAlertCounter(prev => prev + 1);
        setAlerts(prev => [newAlert, ...prev.slice(0, 4)]);
        
        // Random chance to trigger AI analysis
        if (Math.random() > 0.6) {
            setTimeout(() => {
                setAiAnalysis(generateAIAnalysis());
                setShowAIPopup(true);
                setIncidents(prev => prev + 1);
                setCorrelatedAlerts(prev => prev + Math.floor(Math.random() * 3) + 1);
                setTimeout(() => setShowAIPopup(false), 4000);
            }, 1000);
        }
    }, [alertCounter]);

    // Update metrics periodically
    useEffect(() => {
        if (!isRunning) return;

        const metricsInterval = setInterval(() => {
            setMetrics(prev => ({
                cpu: Math.max(20, Math.min(95, prev.cpu + (Math.random() - 0.5) * 15)),
                memory: Math.max(30, Math.min(90, prev.memory + (Math.random() - 0.5) * 10)),
                disk: Math.max(40, Math.min(95, prev.disk + (Math.random() - 0.3) * 5)),
                network: Math.max(10, Math.min(200, prev.network + (Math.random() - 0.5) * 30)),
            }));
        }, 1500);

        const alertInterval = setInterval(() => {
            if (Math.random() > 0.4) {
                addAlert();
            }
        }, 2500);

        return () => {
            clearInterval(metricsInterval);
            clearInterval(alertInterval);
        };
    }, [isRunning, addAlert]);

    // Mark alerts as not new after animation
    useEffect(() => {
        const timeout = setTimeout(() => {
            setAlerts(prev => prev.map(a => ({ ...a, isNew: false })));
        }, 500);
        return () => clearTimeout(timeout);
    }, [alerts]);

    const handleReset = () => {
        setAlerts([]);
        setIncidents(0);
        setCorrelatedAlerts(0);
        setMetrics(generateMetrics());
        setAiAnalysis(null);
        setShowAIPopup(false);
    };

    const severityColors = {
        critical: 'bg-red-500/20 text-red-400 border-red-500/30',
        warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        info: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    };

    const severityDots = {
        critical: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-cyan-500',
    };

    return (
        <div className="relative">
            {/* Control Bar */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <Button
                        onClick={() => setIsRunning(!isRunning)}
                        className={`${isRunning ? 'bg-red-500 hover:bg-red-600' : 'bg-emerald-500 hover:bg-emerald-600'} text-white font-bold uppercase tracking-wider rounded-sm px-6`}
                        data-testid="demo-toggle-btn"
                    >
                        {isRunning ? (
                            <>
                                <Pause className="w-4 h-4 mr-2" />
                                Stop Demo
                            </>
                        ) : (
                            <>
                                <Play className="w-4 h-4 mr-2" />
                                Start Demo
                            </>
                        )}
                    </Button>
                    <Button
                        onClick={handleReset}
                        variant="outline"
                        className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm"
                        data-testid="demo-reset-btn"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Reset
                    </Button>
                </div>
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-white/30'}`} />
                    <span className={`text-xs font-mono uppercase tracking-wider ${isRunning ? 'text-emerald-400' : 'text-white/50'}`}>
                        {isRunning ? 'Live Simulation' : 'Paused'}
                    </span>
                </div>
            </div>

            {/* Demo Dashboard Grid */}
            <div className="grid grid-cols-12 gap-4">
                {/* Metrics Panel */}
                <div className="col-span-12 lg:col-span-4 space-y-4">
                    <div className="p-4 bg-black/60 backdrop-blur-xl border border-white/10 rounded-sm">
                        <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 mb-4 flex items-center gap-2">
                            <Server className="w-4 h-4" />
                            System Metrics
                        </h3>
                        <div className="space-y-4">
                            {/* CPU */}
                            <div>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-white/60 flex items-center gap-2">
                                        <Cpu className="w-3 h-3" /> CPU
                                    </span>
                                    <span className={`text-sm font-mono font-bold ${metrics.cpu > 80 ? 'text-red-400' : metrics.cpu > 60 ? 'text-yellow-400' : 'text-emerald-400'}`}>
                                        {Math.round(metrics.cpu)}%
                                    </span>
                                </div>
                                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                    <motion.div 
                                        className={`h-full rounded-full ${metrics.cpu > 80 ? 'bg-red-500' : metrics.cpu > 60 ? 'bg-yellow-500' : 'bg-emerald-500'}`}
                                        animate={{ width: `${metrics.cpu}%` }}
                                        transition={{ duration: 0.5 }}
                                    />
                                </div>
                            </div>
                            {/* Memory */}
                            <div>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-white/60 flex items-center gap-2">
                                        <Activity className="w-3 h-3" /> Memory
                                    </span>
                                    <span className={`text-sm font-mono font-bold ${metrics.memory > 80 ? 'text-red-400' : metrics.memory > 60 ? 'text-yellow-400' : 'text-cyan-400'}`}>
                                        {Math.round(metrics.memory)}%
                                    </span>
                                </div>
                                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                    <motion.div 
                                        className={`h-full rounded-full ${metrics.memory > 80 ? 'bg-red-500' : metrics.memory > 60 ? 'bg-yellow-500' : 'bg-cyan-500'}`}
                                        animate={{ width: `${metrics.memory}%` }}
                                        transition={{ duration: 0.5 }}
                                    />
                                </div>
                            </div>
                            {/* Disk */}
                            <div>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-white/60 flex items-center gap-2">
                                        <HardDrive className="w-3 h-3" /> Disk
                                    </span>
                                    <span className={`text-sm font-mono font-bold ${metrics.disk > 85 ? 'text-red-400' : metrics.disk > 70 ? 'text-yellow-400' : 'text-primary'}`}>
                                        {Math.round(metrics.disk)}%
                                    </span>
                                </div>
                                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                    <motion.div 
                                        className={`h-full rounded-full ${metrics.disk > 85 ? 'bg-red-500' : metrics.disk > 70 ? 'bg-yellow-500' : 'bg-primary'}`}
                                        animate={{ width: `${metrics.disk}%` }}
                                        transition={{ duration: 0.5 }}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Stats Cards */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 bg-black/60 backdrop-blur-xl border border-white/10 rounded-sm">
                            <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Incidents</p>
                            <p className="text-2xl font-heading font-bold text-yellow-400">{incidents}</p>
                        </div>
                        <div className="p-3 bg-black/60 backdrop-blur-xl border border-white/10 rounded-sm">
                            <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Correlated</p>
                            <p className="text-2xl font-heading font-bold text-cyan-400">{correlatedAlerts}</p>
                        </div>
                    </div>
                </div>

                {/* Alerts Panel */}
                <div className="col-span-12 lg:col-span-5 p-4 bg-black/60 backdrop-blur-xl border border-white/10 rounded-sm">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-white/50 mb-4 flex items-center gap-2">
                        <Bell className="w-4 h-4" />
                        Live Alert Stream
                        {alerts.length > 0 && (
                            <span className="ml-auto px-2 py-0.5 bg-red-500/20 text-red-400 text-[10px] rounded-sm">
                                {alerts.length} Active
                            </span>
                        )}
                    </h3>
                    <div className="space-y-2 min-h-[200px]">
                        <AnimatePresence mode="popLayout">
                            {alerts.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-[200px] text-white/30">
                                    <Bell className="w-8 h-8 mb-2 opacity-50" />
                                    <p className="text-xs font-mono">Start the demo to see live alerts</p>
                                </div>
                            ) : (
                                alerts.map((alert) => (
                                    <motion.div
                                        key={alert.id}
                                        initial={{ opacity: 0, x: -20, scale: 0.95 }}
                                        animate={{ opacity: 1, x: 0, scale: 1 }}
                                        exit={{ opacity: 0, x: 20, scale: 0.95 }}
                                        transition={{ duration: 0.3 }}
                                        className={`flex items-center gap-3 p-3 rounded-sm border ${severityColors[alert.severity]} ${alert.isNew ? 'ring-1 ring-white/20' : ''}`}
                                    >
                                        <div className={`w-2 h-2 rounded-full ${severityDots[alert.severity]} ${alert.severity === 'critical' ? 'animate-pulse' : ''}`} />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-white truncate">{alert.title}</p>
                                            <p className="text-[10px] text-white/50 font-mono">{alert.service}</p>
                                        </div>
                                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-sm ${severityColors[alert.severity]}`}>
                                            {alert.severity}
                                        </span>
                                    </motion.div>
                                ))
                            )}
                        </AnimatePresence>
                    </div>
                </div>

                {/* AI Analysis Panel */}
                <div className="col-span-12 lg:col-span-3 p-4 bg-black/60 backdrop-blur-xl border border-cyan-500/20 rounded-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl" />
                    <h3 className="text-xs font-mono uppercase tracking-wider text-cyan-400 mb-4 flex items-center gap-2 relative">
                        <Brain className="w-4 h-4" />
                        AI Copilot
                    </h3>
                    
                    <AnimatePresence mode="wait">
                        {showAIPopup && aiAnalysis ? (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="relative space-y-3"
                            >
                                <div className="flex items-center gap-2 text-cyan-400">
                                    <Zap className="w-4 h-4" />
                                    <span className="text-xs font-mono uppercase">Analysis Complete</span>
                                </div>
                                <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-sm">
                                    <p className="text-sm text-white font-medium mb-2">{aiAnalysis.title}</p>
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                            <motion.div 
                                                className="h-full bg-cyan-400 rounded-full"
                                                initial={{ width: 0 }}
                                                animate={{ width: `${aiAnalysis.confidence}%` }}
                                                transition={{ duration: 1 }}
                                            />
                                        </div>
                                        <span className="text-xs font-mono text-cyan-400">{aiAnalysis.confidence}%</span>
                                    </div>
                                    <p className="text-xs text-white/60">
                                        <span className="text-cyan-400">Suggestion:</span> {aiAnalysis.suggestion}
                                    </p>
                                </div>
                            </motion.div>
                        ) : (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex flex-col items-center justify-center h-[180px] text-white/30 relative"
                            >
                                <Brain className="w-10 h-10 mb-3 opacity-30" />
                                <p className="text-xs font-mono text-center">
                                    {isRunning ? 'Analyzing patterns...' : 'Start demo for AI analysis'}
                                </p>
                                {isRunning && (
                                    <div className="mt-3 flex items-center gap-1">
                                        <motion.div 
                                            animate={{ opacity: [0.3, 1, 0.3] }}
                                            transition={{ duration: 1.5, repeat: Infinity }}
                                            className="w-1.5 h-1.5 bg-cyan-400 rounded-full"
                                        />
                                        <motion.div 
                                            animate={{ opacity: [0.3, 1, 0.3] }}
                                            transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
                                            className="w-1.5 h-1.5 bg-cyan-400 rounded-full"
                                        />
                                        <motion.div 
                                            animate={{ opacity: [0.3, 1, 0.3] }}
                                            transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
                                            className="w-1.5 h-1.5 bg-cyan-400 rounded-full"
                                        />
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Bottom Stats */}
            <div className="mt-4 grid grid-cols-4 gap-3">
                <div className="p-3 bg-black/40 backdrop-blur border border-white/5 rounded-sm flex items-center gap-3">
                    <div className="w-8 h-8 rounded-sm bg-emerald-500/10 flex items-center justify-center">
                        <TrendingDown className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/40 uppercase">Noise Reduced</p>
                        <p className="text-lg font-bold text-emerald-400">-73%</p>
                    </div>
                </div>
                <div className="p-3 bg-black/40 backdrop-blur border border-white/5 rounded-sm flex items-center gap-3">
                    <div className="w-8 h-8 rounded-sm bg-cyan-500/10 flex items-center justify-center">
                        <Clock className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/40 uppercase">Avg MTTR</p>
                        <p className="text-lg font-bold text-cyan-400">14m</p>
                    </div>
                </div>
                <div className="p-3 bg-black/40 backdrop-blur border border-white/5 rounded-sm flex items-center gap-3">
                    <div className="w-8 h-8 rounded-sm bg-primary/10 flex items-center justify-center">
                        <CheckCircle className="w-4 h-4 text-primary" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/40 uppercase">SLA Compliance</p>
                        <p className="text-lg font-bold text-primary">99.2%</p>
                    </div>
                </div>
                <div className="p-3 bg-black/40 backdrop-blur border border-white/5 rounded-sm flex items-center gap-3">
                    <div className="w-8 h-8 rounded-sm bg-purple-500/10 flex items-center justify-center">
                        <Brain className="w-4 h-4 text-purple-400" />
                    </div>
                    <div>
                        <p className="text-[10px] text-white/40 uppercase">AI Confidence</p>
                        <p className="text-lg font-bold text-purple-400">94%</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default InteractiveDemo;
