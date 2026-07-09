import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
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
    DialogDescription,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Bell,
    Search,
    Filter,
    CheckCircle,
    XCircle,
    RefreshCw,
    Clock,
    Send,
    Mail,
    MessageSquare,
    Eye,
    AlertTriangle,
    Brain,
    Server,
    Activity,
    ExternalLink,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import AIOpsDiagnosePanel from '../components/AIOpsDiagnosePanel';

const severityColors = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
};

const statusColors = {
    open: 'border-red-500/50 text-red-400',
    acknowledged: 'border-yellow-500/50 text-yellow-400',
    resolved: 'border-green-500/50 text-green-400',
};

export const AlertsPage = () => {
    const { api } = useAuth();
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedAlert, setSelectedAlert] = useState(null);
    const [alertDetails, setAlertDetails] = useState(null);
    const [showDetailModal, setShowDetailModal] = useState(false);
    const [showNotifyModal, setShowNotifyModal] = useState(false);
    const [notifyChannel, setNotifyChannel] = useState('email');
    const [notifyRecipient, setNotifyRecipient] = useState('');
    const [notifyMessage, setNotifyMessage] = useState('');
    const [sendingNotification, setSendingNotification] = useState(false);
    const [notificationSettings, setNotificationSettings] = useState(null);
    const [diagnoseService, setDiagnoseService] = useState(null);
    const [filters, setFilters] = useState({
        status: '',
        severity: '',
        service: '',
        search: '',
    });

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filters.status) params.append('status', filters.status);
            if (filters.severity) params.append('severity', filters.severity);
            if (filters.service) params.append('service', filters.service);
            
            const alertsRes = await api.get(`/alerts?${params.toString()}&limit=100`);
            setAlerts(alertsRes.data);
            
            // Try to fetch notification settings, but don't fail if not available
            try {
                const settingsRes = await api.get('/settings/notifications');
                setNotificationSettings(settingsRes.data);
            } catch (settingsError) {
                // Notification settings not configured, use defaults
                setNotificationSettings({ email_enabled: true, teams_enabled: false });
            }
        } catch (error) {
            console.error('Failed to fetch alerts:', error);
            toast.error('Failed to fetch alerts');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
    }, [filters.status, filters.severity, filters.service]);

    const handleViewDetails = async (alert) => {
        setSelectedAlert(alert);
        setShowDetailModal(true);
        try {
            const res = await api.get(`/alerts/${alert.id}`);
            setAlertDetails(res.data);
        } catch (error) {
            toast.error('Failed to load alert details');
        }
    };

    const handleAcknowledge = async (alertId) => {
        try {
            await api.patch(`/alerts/${alertId}/acknowledge`);
            toast.success('Alert acknowledged');
            fetchAlerts();
            if (alertDetails?.alert?.id === alertId) {
                setAlertDetails(prev => ({
                    ...prev,
                    alert: { ...prev.alert, status: 'acknowledged' }
                }));
            }
        } catch (error) {
            toast.error('Failed to acknowledge alert');
        }
    };

    const handleResolve = async (alertId) => {
        try {
            await api.patch(`/alerts/${alertId}/resolve`);
            toast.success('Alert resolved');
            fetchAlerts();
            if (alertDetails?.alert?.id === alertId) {
                setAlertDetails(prev => ({
                    ...prev,
                    alert: { ...prev.alert, status: 'resolved' }
                }));
            }
        } catch (error) {
            toast.error('Failed to resolve alert');
        }
    };

    const handleOpenNotifyModal = (channel) => {
        setNotifyChannel(channel);
        setNotifyRecipient('');
        setNotifyMessage('');
        setShowNotifyModal(true);
    };

    const handleSendNotification = async () => {
        if (!selectedAlert) return;
        
        setSendingNotification(true);
        try {
            await api.post(`/alerts/${selectedAlert.id}/notify`, {
                channel: notifyChannel,
                recipient: notifyRecipient || undefined,
                message: notifyMessage || undefined
            });
            toast.success(`Alert sent to ${notifyChannel === 'email' ? 'Email' : 'Teams'}`);
            setShowNotifyModal(false);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to send notification');
        } finally {
            setSendingNotification(false);
        }
    };

    const filteredAlerts = alerts.filter(alert => {
        if (filters.search) {
            const search = filters.search.toLowerCase();
            return (
                alert.title?.toLowerCase().includes(search) ||
                alert.service?.toLowerCase().includes(search) ||
                alert.source?.toLowerCase().includes(search)
            );
        }
        return true;
    });

    const formatDate = (dateStr) => {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    // Count alerts by status
    const openCount = alerts.filter(a => a.status === 'open').length;
    const ackCount = alerts.filter(a => a.status === 'acknowledged').length;
    const resolvedCount = alerts.filter(a => a.status === 'resolved').length;

    return (
        <>
            <div className="space-y-6" data-testid="alerts-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white flex items-center gap-3">
                                <Bell className="w-7 h-7 text-red-400" />
                                Alert Console
                            </h1>
                        </div>
                        <p className="text-white/50 text-sm font-mono">Monitor, investigate, and respond to alerts</p>
                    </div>
                    <Button 
                        onClick={fetchAlerts} 
                        variant="outline" 
                        size="sm" 
                        data-testid="refresh-alerts-btn"
                        className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm font-medium"
                    >
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4">
                    {[
                        { label: 'Open', count: openCount, color: 'red', pulse: true },
                        { label: 'Acknowledged', count: ackCount, color: 'yellow', pulse: false },
                        { label: 'Resolved', count: resolvedCount, color: 'green', pulse: false },
                    ].map((stat, idx) => (
                        <motion.div
                            key={idx}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.05 }}
                        >
                            <Card className={`bg-${stat.color}-500/5 border-${stat.color}-500/20 rounded-sm`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-[10px] font-mono uppercase tracking-wider text-white/40">{stat.label}</p>
                                            <p className={`font-heading font-bold text-2xl text-${stat.color}-400`}>{stat.count}</p>
                                        </div>
                                        <div className={`w-3 h-3 rounded-full bg-${stat.color}-500 ${stat.pulse ? 'animate-pulse' : ''}`} />
                                    </div>
                                </CardContent>
                            </Card>
                        </motion.div>
                    ))}
                </div>

                {/* Filters */}
                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                    <CardContent className="p-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                            <div className="relative lg:col-span-2">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                                <Input
                                    placeholder="Search alerts..."
                                    value={filters.search}
                                    onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                                    className="pl-9 bg-black/50 border-white/10 focus:border-primary/50 rounded-sm text-white placeholder:text-white/30"
                                    data-testid="search-alerts"
                                />
                            </div>
                            <Select
                                value={filters.status || "all"}
                                onValueChange={(value) => setFilters({ ...filters, status: value === "all" ? "" : value })}
                            >
                                <SelectTrigger data-testid="filter-status" className="bg-black/50 border-white/10 rounded-sm text-white">
                                    <SelectValue placeholder="Status" />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0a0a0a] border-white/10 rounded-sm">
                                    <SelectItem value="all">All Status</SelectItem>
                                    <SelectItem value="open">Open</SelectItem>
                                    <SelectItem value="acknowledged">Acknowledged</SelectItem>
                                    <SelectItem value="resolved">Resolved</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select
                                value={filters.severity || "all"}
                                onValueChange={(value) => setFilters({ ...filters, severity: value === "all" ? "" : value })}
                            >
                                <SelectTrigger data-testid="filter-severity" className="bg-black/50 border-white/10 rounded-sm text-white">
                                    <SelectValue placeholder="Severity" />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0a0a0a] border-white/10 rounded-sm">
                                    <SelectItem value="all">All Severity</SelectItem>
                                    <SelectItem value="critical">Critical</SelectItem>
                                    <SelectItem value="warning">Warning</SelectItem>
                                    <SelectItem value="info">Info</SelectItem>
                                </SelectContent>
                            </Select>
                            <Button
                                variant="outline"
                                onClick={() => setFilters({ status: '', severity: '', service: '', search: '' })}
                                data-testid="clear-filters"
                                className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm font-medium"
                            >
                                <Filter className="w-4 h-4 mr-2" />
                                Clear
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Alerts List */}
                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm overflow-hidden">
                    <CardContent className="p-0">
                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <div className="text-center">
                                    <RefreshCw className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
                                    <p className="text-white/50 font-mono text-sm uppercase tracking-wider">Loading alerts...</p>
                                </div>
                            </div>
                        ) : filteredAlerts.length === 0 ? (
                            <div className="text-center py-20 text-white/40">
                                <Bell className="w-16 h-16 mx-auto mb-4 opacity-30" />
                                <p className="text-lg font-heading font-bold uppercase tracking-wider mb-2">No alerts found</p>
                                <p className="text-sm font-mono">Alerts will appear here when received via webhook</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-white/5">
                                <AnimatePresence>
                                    {filteredAlerts.map((alert, idx) => (
                                        <motion.div
                                            key={alert.id}
                                            initial={{ opacity: 0, x: -20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: 20 }}
                                            transition={{ delay: idx * 0.02 }}
                                            className={`p-4 hover:bg-white/5 transition-colors cursor-pointer ${
                                                alert.status === 'open' && alert.severity === 'critical' ? 'bg-red-500/5' : ''
                                            }`}
                                            onClick={() => handleViewDetails(alert)}
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Status Indicator */}
                                                <div className={`w-3 h-3 rounded-full mt-1.5 shrink-0 ${
                                                    alert.severity === 'critical' ? 'bg-red-500 animate-pulse' :
                                                    alert.severity === 'warning' ? 'bg-yellow-500' :
                                                    'bg-cyan-500'
                                                }`} />
                                                
                                                {/* Main Content */}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-start justify-between gap-4">
                                                        <div className="min-w-0">
                                                            <p className="font-medium text-white truncate">{alert.title}</p>
                                                            <p className="text-xs text-white/40 truncate font-mono mt-1">
                                                                {alert.description}
                                                            </p>
                                                        </div>
                                                        <div className="flex items-center gap-2 shrink-0">
                                                            <Badge className={`${severityColors[alert.severity]} text-xs uppercase rounded-sm border`}>
                                                                {alert.severity}
                                                            </Badge>
                                                            <Badge variant="outline" className={`${statusColors[alert.status]} text-xs uppercase rounded-sm`}>
                                                                {alert.status}
                                                            </Badge>
                                                        </div>
                                                    </div>
                                                    
                                                    {/* Meta Info */}
                                                    <div className="flex items-center gap-4 mt-3 text-xs text-white/40 font-mono">
                                                        <span className="flex items-center gap-1">
                                                            <Server className="w-3 h-3" />
                                                            {alert.service}
                                                        </span>
                                                        <span>{alert.source}</span>
                                                        <span className="flex items-center gap-1">
                                                            <Clock className="w-3 h-3" />
                                                            {formatDate(alert.created_at)}
                                                        </span>
                                                    </div>
                                                </div>
                                                
                                                {/* Quick Actions */}
                                                <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                                                    {alert.service && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setDiagnoseService(alert.service)}
                                                            className="text-violet-300 hover:bg-violet-500/10 border border-violet-500/30 rounded-sm text-[11px] h-7 px-2"
                                                            title={`AI Diagnose ${alert.service}`}
                                                            data-testid={`diagnose-alert-${alert.id}`}
                                                        >
                                                            <Brain className="w-3.5 h-3.5 mr-1" />
                                                            Diagnose
                                                        </Button>
                                                    )}
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => handleViewDetails(alert)}
                                                        className="text-cyan-400 hover:bg-cyan-500/10 rounded-sm"
                                                    >
                                                        <Eye className="w-4 h-4" />
                                                    </Button>
                                                    {alert.status === 'open' && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleAcknowledge(alert.id)}
                                                            className="text-yellow-400 hover:bg-yellow-500/10 rounded-sm"
                                                        >
                                                            <CheckCircle className="w-4 h-4" />
                                                        </Button>
                                                    )}
                                                    {alert.status !== 'resolved' && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => handleResolve(alert.id)}
                                                            className="text-green-400 hover:bg-green-500/10 rounded-sm"
                                                        >
                                                            <XCircle className="w-4 h-4" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* AI Diagnose Panel (renders when user clicks Diagnose on any alert) */}
                {diagnoseService && (
                    <div className="mt-4">
                        <AIOpsDiagnosePanel
                            service={diagnoseService}
                            hours={24}
                            onClose={() => setDiagnoseService(null)}
                        />
                    </div>
                )}

                {/* Alert Detail Modal */}
                <Dialog open={showDetailModal} onOpenChange={setShowDetailModal}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-2xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-3">
                                <AlertTriangle className={`w-6 h-6 ${
                                    selectedAlert?.severity === 'critical' ? 'text-red-400' :
                                    selectedAlert?.severity === 'warning' ? 'text-yellow-400' :
                                    'text-cyan-400'
                                }`} />
                                Alert Details
                            </DialogTitle>
                            <DialogDescription className="text-white/50 font-mono">
                                Investigate and respond to this alert
                            </DialogDescription>
                        </DialogHeader>
                        
                        {alertDetails ? (
                            <div className="space-y-6 mt-4">
                                {/* Alert Info */}
                                <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <h3 className="font-medium text-white text-lg">{alertDetails.alert?.title}</h3>
                                            <p className="text-sm text-white/50 mt-1">{alertDetails.alert?.description}</p>
                                        </div>
                                        <div className="flex gap-2">
                                            <Badge className={`${severityColors[alertDetails.alert?.severity]} border`}>
                                                {alertDetails.alert?.severity?.toUpperCase()}
                                            </Badge>
                                            <Badge variant="outline" className={statusColors[alertDetails.alert?.status]}>
                                                {alertDetails.alert?.status?.toUpperCase()}
                                            </Badge>
                                        </div>
                                    </div>
                                    
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                        <div>
                                            <p className="text-white/40 font-mono text-xs uppercase mb-1">Service</p>
                                            <p className="text-white">{alertDetails.alert?.service}</p>
                                        </div>
                                        <div>
                                            <p className="text-white/40 font-mono text-xs uppercase mb-1">Source</p>
                                            <p className="text-white">{alertDetails.alert?.source}</p>
                                        </div>
                                        <div>
                                            <p className="text-white/40 font-mono text-xs uppercase mb-1">Host</p>
                                            <p className="text-white">{alertDetails.alert?.host || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <p className="text-white/40 font-mono text-xs uppercase mb-1">Created</p>
                                            <p className="text-white">{formatDate(alertDetails.alert?.created_at)}</p>
                                        </div>
                                    </div>
                                </div>

                                {/* AI Analysis (if incident has it) */}
                                {alertDetails.incident?.ai_analysis && (
                                    <div className="p-4 bg-cyan-500/5 rounded-sm border border-cyan-500/20">
                                        <div className="flex items-center gap-2 mb-3">
                                            <Brain className="w-5 h-5 text-cyan-400" />
                                            <h4 className="font-heading font-bold text-sm uppercase tracking-wider text-cyan-400">AI Analysis</h4>
                                        </div>
                                        <div className="text-sm text-white/80 space-y-2">
                                            {typeof alertDetails.incident.ai_analysis === 'object' ? (
                                                <>
                                                    <p><strong>Root Cause:</strong> {alertDetails.incident.ai_analysis.root_cause}</p>
                                                    <p><strong>Impact:</strong> {alertDetails.incident.ai_analysis.impact}</p>
                                                    <p><strong>Recommendation:</strong> {alertDetails.incident.ai_analysis.recommendation}</p>
                                                    {alertDetails.incident.ai_analysis.confidence && (
                                                        <p><strong>Confidence:</strong> {alertDetails.incident.ai_analysis.confidence}%</p>
                                                    )}
                                                </>
                                            ) : (
                                                <p>{JSON.stringify(alertDetails.incident.ai_analysis)}</p>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Monitor Info (if from monitoring) */}
                                {alertDetails.monitor && (
                                    <div className="p-4 bg-primary/5 rounded-sm border border-primary/20">
                                        <div className="flex items-center gap-2 mb-3">
                                            <Activity className="w-5 h-5 text-primary" />
                                            <h4 className="font-heading font-bold text-sm uppercase tracking-wider text-primary">Monitor Details</h4>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4 text-sm">
                                            <div>
                                                <p className="text-white/40 font-mono text-xs uppercase mb-1">Target</p>
                                                <p className="text-white">{alertDetails.monitor.target}</p>
                                            </div>
                                            <div>
                                                <p className="text-white/40 font-mono text-xs uppercase mb-1">Type</p>
                                                <p className="text-white uppercase">{alertDetails.monitor.monitor_type}</p>
                                            </div>
                                            <div>
                                                <p className="text-white/40 font-mono text-xs uppercase mb-1">SLA Uptime</p>
                                                <p className="text-white">{alertDetails.monitor.sla_uptime_percent}%</p>
                                            </div>
                                            <div>
                                                <p className="text-white/40 font-mono text-xs uppercase mb-1">Max Latency</p>
                                                <p className="text-white">{alertDetails.monitor.sla_max_latency_ms}ms</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Actions */}
                                <div className="flex flex-col gap-3">
                                    <p className="text-white/40 font-mono text-xs uppercase">NOC Actions</p>
                                    <div className="grid grid-cols-2 gap-3">
                                        {alertDetails.alert?.status === 'open' && (
                                            <Button
                                                onClick={() => handleAcknowledge(alertDetails.alert.id)}
                                                className="bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 border border-yellow-500/30 rounded-sm"
                                            >
                                                <CheckCircle className="w-4 h-4 mr-2" />
                                                Acknowledge
                                            </Button>
                                        )}
                                        {alertDetails.alert?.status !== 'resolved' && (
                                            <Button
                                                onClick={() => handleResolve(alertDetails.alert.id)}
                                                className="bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30 rounded-sm"
                                            >
                                                <XCircle className="w-4 h-4 mr-2" />
                                                Resolve
                                            </Button>
                                        )}
                                        <Button
                                            onClick={() => handleOpenNotifyModal('email')}
                                            className="bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-sm"
                                        >
                                            <Mail className="w-4 h-4 mr-2" />
                                            Send Email
                                        </Button>
                                        <Button
                                            onClick={() => handleOpenNotifyModal('teams')}
                                            className="bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border border-purple-500/30 rounded-sm"
                                        >
                                            <MessageSquare className="w-4 h-4 mr-2" />
                                            Send to Teams
                                        </Button>
                                    </div>
                                </div>

                                {/* Notification History */}
                                {alertDetails.alert?.notifications && alertDetails.alert.notifications.length > 0 && (
                                    <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                                        <h4 className="font-heading font-bold text-sm uppercase tracking-wider text-white/60 mb-3">Notification History</h4>
                                        <div className="space-y-2">
                                            {alertDetails.alert.notifications.map((n, idx) => (
                                                <div key={idx} className="flex items-center gap-3 text-xs text-white/50 font-mono">
                                                    {n.channel === 'email' ? <Mail className="w-3 h-3" /> : <MessageSquare className="w-3 h-3" />}
                                                    <span>{n.channel.toUpperCase()}</span>
                                                    {n.recipient && <span>to {n.recipient}</span>}
                                                    <span>• {formatDate(n.sent_at)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex items-center justify-center py-12">
                                <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                            </div>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Send Notification Modal */}
                <Dialog open={showNotifyModal} onOpenChange={setShowNotifyModal}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-md">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-3">
                                {notifyChannel === 'email' ? (
                                    <Mail className="w-6 h-6 text-cyan-400" />
                                ) : (
                                    <MessageSquare className="w-6 h-6 text-purple-400" />
                                )}
                                Send to {notifyChannel === 'email' ? 'Email' : 'Teams'}
                            </DialogTitle>
                        </DialogHeader>
                        
                        <div className="space-y-4 mt-4">
                            {notifyChannel === 'email' ? (
                                <div className="space-y-2">
                                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Recipient Email</Label>
                                    <Input
                                        type="email"
                                        value={notifyRecipient}
                                        onChange={(e) => setNotifyRecipient(e.target.value)}
                                        placeholder={notificationSettings?.default_email || "noc@company.com"}
                                        className="bg-black/50 border-white/10 rounded-sm text-white"
                                    />
                                    <p className="text-[10px] text-white/40 font-mono">
                                        Leave empty to use default: {notificationSettings?.default_email || 'Not configured'}
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Teams Webhook URL (Optional)</Label>
                                    <Input
                                        value={notifyRecipient}
                                        onChange={(e) => setNotifyRecipient(e.target.value)}
                                        placeholder="https://outlook.office.com/webhook/..."
                                        className="bg-black/50 border-white/10 rounded-sm text-white"
                                    />
                                    <p className="text-[10px] text-white/40 font-mono">
                                        Leave empty to use default webhook {notificationSettings?.teams_webhook_configured ? '(configured)' : '(not configured)'}
                                    </p>
                                </div>
                            )}
                            
                            <div className="space-y-2">
                                <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Additional Message (Optional)</Label>
                                <Textarea
                                    value={notifyMessage}
                                    onChange={(e) => setNotifyMessage(e.target.value)}
                                    placeholder="Add context or instructions for the team..."
                                    className="bg-black/50 border-white/10 rounded-sm text-white min-h-[100px]"
                                />
                            </div>

                            <div className="flex gap-3 pt-2">
                                <Button
                                    variant="outline"
                                    onClick={() => setShowNotifyModal(false)}
                                    className="flex-1 border-white/20 text-white rounded-sm"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    onClick={handleSendNotification}
                                    disabled={sendingNotification}
                                    className={`flex-1 font-bold uppercase tracking-wider rounded-sm ${
                                        notifyChannel === 'email' 
                                            ? 'bg-cyan-500 text-black hover:bg-cyan-400' 
                                            : 'bg-purple-500 text-white hover:bg-purple-400'
                                    }`}
                                >
                                    {sendingNotification ? (
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <>
                                            <Send className="w-4 h-4 mr-2" />
                                            Send
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>
        </>
    );
};
