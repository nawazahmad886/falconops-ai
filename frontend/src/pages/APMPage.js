import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import {
    Activity,
    RefreshCw,
    Server,
    Clock,
    AlertTriangle,
    Zap,
    Database,
    Globe,
    TrendingUp,
    Code,
    Plus,
    Copy,
    Eye,
    Filter,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts';
import { motion } from 'framer-motion';

export const APMPage = () => {
    const { api } = useAuth();
    const [dashboard, setDashboard] = useState(null);
    const [services, setServices] = useState([]);
    const [selectedService, setSelectedService] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [errors, setErrors] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showRegisterModal, setShowRegisterModal] = useState(false);
    const [newService, setNewService] = useState({ service_name: '', service_type: 'web', environment: 'production' });
    const [activeTab, setActiveTab] = useState('overview');

    const fetchDashboard = async () => {
        try {
            const [dashboardRes, servicesRes] = await Promise.all([
                api.get('/apm/dashboard'),
                api.get('/apm/services'),
            ]);
            setDashboard(dashboardRes.data);
            setServices(servicesRes.data);
        } catch (error) {
            console.error('Failed to fetch APM data:', error);
            toast.error('Failed to load APM dashboard');
        } finally {
            setLoading(false);
        }
    };

    const fetchServiceDetails = async (serviceId) => {
        try {
            const [txRes, errRes] = await Promise.all([
                api.get(`/apm/services/${serviceId}/transactions?limit=50`),
                api.get(`/apm/services/${serviceId}/errors?limit=50`),
            ]);
            setTransactions(txRes.data);
            setErrors(errRes.data);
        } catch (error) {
            console.error('Failed to fetch service details:', error);
        }
    };

    useEffect(() => {
        fetchDashboard();
        const interval = setInterval(fetchDashboard, 30000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (selectedService) {
            fetchServiceDetails(selectedService.id);
        }
    }, [selectedService]);

    const registerService = async () => {
        try {
            const res = await api.post('/apm/services', newService);
            toast.success(`Service registered! API Key: ${res.data.api_key}`);
            setShowRegisterModal(false);
            setNewService({ service_name: '', service_type: 'web', environment: 'production' });
            fetchDashboard();
        } catch (error) {
            toast.error('Failed to register service');
        }
    };

    const copyApiKey = (key) => {
        navigator.clipboard.writeText(key);
        toast.success('API key copied to clipboard');
    };

    const formatDuration = (ms) => {
        if (!ms) return '--';
        if (ms < 1000) return `${Math.round(ms)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <div className="text-center">
                        <RefreshCw className="w-10 h-10 animate-spin text-primary mx-auto mb-4" />
                        <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Loading APM Data...</p>
                    </div>
                </div>
            </>
        );
    }

    const metrics = dashboard?.overall_metrics || {};

    return (
        <>
            <div className="space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-heading font-bold text-white uppercase tracking-wider flex items-center gap-3">
                            <Activity className="w-6 h-6 text-cyan-400" />
                            Application Performance Monitoring
                        </h1>
                        <p className="text-white/50 text-sm font-mono mt-1">Real-time application insights and performance metrics</p>
                    </div>
                    <div className="flex gap-3">
                        <Button 
                            variant="outline" 
                            onClick={fetchDashboard}
                            className="border-white/10 text-white hover:bg-white/5"
                            data-testid="apm-refresh-btn"
                        >
                            <RefreshCw className="w-4 h-4 mr-2" />
                            Refresh
                        </Button>
                        <Button 
                            onClick={() => setShowRegisterModal(true)}
                            className="bg-cyan-500 hover:bg-cyan-600 text-black font-bold"
                            data-testid="register-service-btn"
                        >
                            <Plus className="w-4 h-4 mr-2" />
                            Register Service
                        </Button>
                    </div>
                </div>

                {/* Overview KPIs */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                        { label: 'Total Transactions', value: metrics.total_transactions || 0, icon: Activity, color: 'cyan' },
                        { label: 'Error Rate', value: `${metrics.error_rate || 0}%`, icon: AlertTriangle, color: metrics.error_rate > 5 ? 'red' : 'green' },
                        { label: 'Avg Response Time', value: formatDuration(metrics.avg_response_time_ms), icon: Clock, color: 'primary' },
                        { label: 'P95 Latency', value: formatDuration(metrics.p95_response_time_ms), icon: TrendingUp, color: 'yellow' },
                    ].map((stat, idx) => {
                        const Icon = stat.icon;
                        return (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                            >
                                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <p className="text-[10px] font-mono uppercase tracking-wider text-white/40 mb-2">{stat.label}</p>
                                                <p className={`font-heading font-bold text-2xl text-${stat.color}-400`} data-testid={`apm-${stat.label.toLowerCase().replace(/\s/g, '-')}`}>
                                                    {stat.value}
                                                </p>
                                            </div>
                                            <div className={`w-10 h-10 rounded-sm bg-${stat.color}-500/10 border border-${stat.color}-500/20 flex items-center justify-center`}>
                                                <Icon className={`w-5 h-5 text-${stat.color}-400`} />
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Tabs */}
                <div className="flex gap-2 border-b border-white/10 pb-2">
                    {['overview', 'services', 'errors'].map((tab) => (
                        <Button
                            key={tab}
                            variant={activeTab === tab ? 'default' : 'ghost'}
                            onClick={() => setActiveTab(tab)}
                            className={`uppercase text-xs font-mono tracking-wider ${activeTab === tab ? 'bg-cyan-500 text-black' : 'text-white/50 hover:text-white'}`}
                            data-testid={`apm-tab-${tab}`}
                        >
                            {tab}
                        </Button>
                    ))}
                </div>

                {/* Tab Content */}
                {activeTab === 'overview' && (
                    <div className="grid lg:grid-cols-2 gap-4">
                        {/* Services Performance */}
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Server className="w-4 h-4 text-primary" />
                                    Services Performance
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                {dashboard?.services?.length === 0 ? (
                                    <div className="text-center py-12 text-white/40">
                                        <Server className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                        <p className="text-sm font-medium mb-1">No services registered</p>
                                        <p className="text-xs font-mono">Register a service to start monitoring</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2 max-h-[300px] overflow-auto">
                                        {dashboard?.services?.map((svc, idx) => (
                                            <div 
                                                key={idx}
                                                onClick={() => setSelectedService(svc)}
                                                className={`flex items-center justify-between p-3 rounded-sm border cursor-pointer transition-colors ${
                                                    selectedService?.id === svc.id 
                                                        ? 'bg-cyan-500/10 border-cyan-500/30' 
                                                        : 'bg-white/5 border-white/5 hover:border-white/10'
                                                }`}
                                                data-testid={`apm-service-${svc.service_name}`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-2 h-2 rounded-full ${
                                                        svc.error_rate < 1 ? 'bg-green-400' :
                                                        svc.error_rate < 5 ? 'bg-yellow-400' :
                                                        'bg-red-400 animate-pulse'
                                                    }`} />
                                                    <div>
                                                        <span className="font-mono text-sm text-white">{svc.service_name}</span>
                                                        <p className="text-xs text-white/40">{svc.environment}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4 text-xs">
                                                    <span className="text-white/50">{svc.transaction_count} txns</span>
                                                    <span className="text-white/50">{formatDuration(svc.avg_response_time_ms)}</span>
                                                    <Badge variant="outline" className={`text-xs ${svc.error_rate < 1 ? 'border-green-500/30 text-green-400' : svc.error_rate < 5 ? 'border-yellow-500/30 text-yellow-400' : 'border-red-500/30 text-red-400'}`}>
                                                        {svc.error_rate}% errors
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Slow Transactions */}
                        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                            <CardHeader className="pb-2 border-b border-white/5">
                                <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                    <Clock className="w-4 h-4 text-yellow-400" />
                                    Slowest Transactions
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                {dashboard?.slow_transactions?.length === 0 ? (
                                    <div className="text-center py-12 text-white/40">
                                        <Zap className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                        <p className="text-sm font-medium">No slow transactions</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2 max-h-[300px] overflow-auto">
                                        {dashboard?.slow_transactions?.map((tx, idx) => (
                                            <div 
                                                key={idx}
                                                className="flex items-center justify-between p-3 rounded-sm bg-white/5 border border-white/5"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <Code className="w-4 h-4 text-white/30" />
                                                    <span className="font-mono text-sm text-white truncate max-w-[200px]">{tx.transaction_name}</span>
                                                </div>
                                                <Badge variant="outline" className="border-yellow-500/30 text-yellow-400 text-xs">
                                                    {formatDuration(tx.duration_ms)}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                )}

                {activeTab === 'services' && (
                    <div className="grid lg:grid-cols-3 gap-4">
                        {services.length === 0 ? (
                            <Card className="lg:col-span-3 bg-[#0a0a0a] border-white/5 rounded-sm">
                                <CardContent className="py-16 text-center">
                                    <Server className="w-16 h-16 mx-auto mb-4 text-white/20" />
                                    <p className="text-white/50 mb-4">No services registered yet</p>
                                    <Button onClick={() => setShowRegisterModal(true)} className="bg-cyan-500 hover:bg-cyan-600 text-black">
                                        <Plus className="w-4 h-4 mr-2" />
                                        Register Your First Service
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            services.map((svc) => (
                                <Card key={svc.id} className="bg-[#0a0a0a] border-white/5 rounded-sm">
                                    <CardHeader className="pb-2 border-b border-white/5">
                                        <div className="flex items-center justify-between">
                                            <CardTitle className="font-mono text-sm text-white">{svc.service_name}</CardTitle>
                                            <Badge variant="outline" className="text-xs border-cyan-500/30 text-cyan-400">
                                                {svc.service_type}
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="pt-4 space-y-3">
                                        <div className="flex justify-between text-sm">
                                            <span className="text-white/50">Environment</span>
                                            <span className="text-white">{svc.environment}</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="text-white/50">Status</span>
                                            <Badge variant="outline" className={`text-xs ${svc.status === 'active' ? 'border-green-500/30 text-green-400' : 'border-red-500/30 text-red-400'}`}>
                                                {svc.status}
                                            </Badge>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="text-white/50">Last Seen</span>
                                            <span className="text-white/70 text-xs">{svc.last_seen ? new Date(svc.last_seen).toLocaleString() : 'Never'}</span>
                                        </div>
                                        <div className="pt-2 border-t border-white/5">
                                            <p className="text-xs text-white/40 mb-2">API Key</p>
                                            <div className="flex items-center gap-2">
                                                <code className="flex-1 text-xs font-mono bg-black/30 px-2 py-1 rounded text-white/50 truncate">
                                                    {svc.api_key?.slice(0, 20)}...
                                                </code>
                                                <Button size="sm" variant="ghost" onClick={() => copyApiKey(svc.api_key)} className="text-white/50 hover:text-white">
                                                    <Copy className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                )}

                {activeTab === 'errors' && (
                    <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                        <CardHeader className="pb-2 border-b border-white/5">
                            <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                                <AlertTriangle className="w-4 h-4 text-red-400" />
                                Error Breakdown
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4">
                            {dashboard?.error_breakdown?.length === 0 ? (
                                <div className="text-center py-12 text-white/40">
                                    <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                    <p className="text-sm font-medium">No errors recorded</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {dashboard?.error_breakdown?.map((err, idx) => (
                                        <div 
                                            key={idx}
                                            className="flex items-center justify-between p-3 rounded-sm bg-red-500/5 border border-red-500/10"
                                        >
                                            <div className="flex items-center gap-3">
                                                <AlertTriangle className="w-4 h-4 text-red-400" />
                                                <span className="font-mono text-sm text-white">{err.error_type}</span>
                                            </div>
                                            <Badge variant="outline" className="border-red-500/30 text-red-400">
                                                {err.count} occurrences
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                )}
            </div>

            {/* Register Service Modal */}
            {showRegisterModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                    <Card className="bg-[#0a0a0a] border-white/10 w-full max-w-md">
                        <CardHeader className="border-b border-white/5">
                            <CardTitle className="font-heading text-white uppercase tracking-wider">Register New Service</CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4 space-y-4">
                            <div>
                                <label className="text-xs text-white/50 uppercase tracking-wider">Service Name</label>
                                <Input
                                    value={newService.service_name}
                                    onChange={(e) => setNewService({ ...newService, service_name: e.target.value })}
                                    placeholder="my-api-service"
                                    className="mt-1 bg-black/30 border-white/10 text-white"
                                    data-testid="apm-service-name-input"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-white/50 uppercase tracking-wider">Service Type</label>
                                <select
                                    value={newService.service_type}
                                    onChange={(e) => setNewService({ ...newService, service_type: e.target.value })}
                                    className="w-full mt-1 bg-black/30 border border-white/10 text-white rounded-md px-3 py-2"
                                    data-testid="apm-service-type-select"
                                >
                                    <option value="web">Web Service</option>
                                    <option value="api">API</option>
                                    <option value="worker">Background Worker</option>
                                    <option value="database">Database</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-white/50 uppercase tracking-wider">Environment</label>
                                <select
                                    value={newService.environment}
                                    onChange={(e) => setNewService({ ...newService, environment: e.target.value })}
                                    className="w-full mt-1 bg-black/30 border border-white/10 text-white rounded-md px-3 py-2"
                                    data-testid="apm-service-env-select"
                                >
                                    <option value="production">Production</option>
                                    <option value="staging">Staging</option>
                                    <option value="development">Development</option>
                                </select>
                            </div>
                            <div className="flex gap-3 pt-4">
                                <Button variant="outline" onClick={() => setShowRegisterModal(false)} className="flex-1 border-white/10 text-white">
                                    Cancel
                                </Button>
                                <Button onClick={registerService} className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-black font-bold" data-testid="apm-register-submit">
                                    Register
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </>
    );
};
