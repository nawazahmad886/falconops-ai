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
    FileText,
    Plus,
    RefreshCw,
    Send,
    Trash2,
    Clock,
    Mail,
    Calendar,
    Play,
    Pause,
    Eye,
    TrendingUp,
    Target,
    AlertTriangle,
} from 'lucide-react';
import { motion } from 'framer-motion';

const frequencyLabels = {
    daily: 'Daily',
    weekly: 'Weekly',
    monthly: 'Monthly',
};

const dayLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export const ReportsPage = () => {
    const { api } = useAuth();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAddDialog, setShowAddDialog] = useState(false);
    const [showPreviewDialog, setShowPreviewDialog] = useState(false);
    const [previewData, setPreviewData] = useState(null);
    const [sendingReport, setSendingReport] = useState(null);
    const [newReport, setNewReport] = useState({
        name: '',
        frequency: 'weekly',
        recipients: '',
        report_type: 'executive',
        day_of_week: 0,
        hour: 8,
        enabled: true,
        include_pdf: true,
        include_ai_summary: true,
    });

    const reportTypeLabels = {
        executive: 'Executive Summary',
        sla: 'SLA & Availability',
        incidents: 'Incident Analytics',
        uptime_summary: 'Uptime Summary',
    };

    const fetchReports = async () => {
        setLoading(true);
        try {
            const res = await api.get('/reports/scheduled');
            setReports(res.data);
        } catch (error) {
            toast.error('Failed to fetch reports');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
    }, []);

    const handleAddReport = async () => {
        if (!newReport.name || !newReport.recipients) {
            toast.error('Please fill in all required fields');
            return;
        }
        
        try {
            await api.post('/reports/scheduled', {
                ...newReport,
                recipients: newReport.recipients.split(',').map(e => e.trim()).filter(e => e),
            });
            toast.success('Scheduled report created');
            setShowAddDialog(false);
            setNewReport({
                name: '',
                frequency: 'weekly',
                recipients: '',
                report_type: 'executive',
                day_of_week: 0,
                hour: 8,
                enabled: true,
                include_pdf: true,
                include_ai_summary: true,
            });
            fetchReports();
        } catch (error) {
            toast.error('Failed to create report');
        }
    };

    const handleDeleteReport = async (reportId) => {
        if (!window.confirm('Are you sure you want to delete this scheduled report?')) return;
        try {
            await api.delete(`/reports/scheduled/${reportId}`);
            toast.success('Report deleted');
            fetchReports();
        } catch (error) {
            toast.error('Failed to delete report');
        }
    };

    const handleToggleReport = async (reportId) => {
        try {
            await api.patch(`/reports/scheduled/${reportId}/toggle`);
            toast.success('Report toggled');
            fetchReports();
        } catch (error) {
            toast.error('Failed to toggle report');
        }
    };

    const handleSendNow = async (reportId) => {
        setSendingReport(reportId);
        try {
            await api.post(`/reports/scheduled/${reportId}/send`);
            toast.success('Report sent successfully!');
            fetchReports();
        } catch (error) {
            toast.error('Failed to send report');
        } finally {
            setSendingReport(null);
        }
    };

    const handlePreviewReport = async (periodHours = 24) => {
        try {
            const res = await api.post(`/reports/generate?period_hours=${periodHours}`);
            setPreviewData(res.data);
            setShowPreviewDialog(true);
        } catch (error) {
            toast.error('Failed to generate preview');
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return 'Never';
        return new Date(dateStr).toLocaleString();
    };

    return (
        <>
            <div className="space-y-6" data-testid="reports-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h1 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-wider text-white flex items-center gap-3">
                                <FileText className="w-7 h-7 text-primary" />
                                Scheduled Reports
                            </h1>
                        </div>
                        <p className="text-white/50 text-sm font-mono">Automated uptime & SLA compliance reports</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            onClick={() => handlePreviewReport(24)}
                            variant="outline"
                            size="sm"
                            className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 rounded-sm"
                        >
                            <Eye className="w-4 h-4 mr-2" />
                            Preview 24h Report
                        </Button>
                        <Button
                            onClick={fetchReports}
                            variant="outline"
                            size="sm"
                            className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm font-medium"
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                            <DialogTrigger asChild>
                                <Button className="bg-primary text-black hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm">
                                    <Plus className="w-4 h-4 mr-2" />
                                    New Report
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-md">
                                <DialogHeader>
                                    <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white">Create Scheduled Report</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 mt-4">
                                    <div className="space-y-2">
                                        <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Report Name</Label>
                                        <Input
                                            value={newReport.name}
                                            onChange={(e) => setNewReport({ ...newReport, name: e.target.value })}
                                            placeholder="e.g., Weekly Executive Summary"
                                            className="bg-black/50 border-white/10 rounded-sm text-white"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Report Type</Label>
                                        <Select value={newReport.report_type} onValueChange={(v) => setNewReport({ ...newReport, report_type: v })}>
                                            <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                <SelectItem value="executive">Executive Summary (AI-Powered)</SelectItem>
                                                <SelectItem value="sla">SLA & Availability</SelectItem>
                                                <SelectItem value="incidents">Incident Analytics</SelectItem>
                                                <SelectItem value="uptime_summary">Uptime Summary</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Recipients (comma-separated)</Label>
                                        <Input
                                            value={newReport.recipients}
                                            onChange={(e) => setNewReport({ ...newReport, recipients: e.target.value })}
                                            placeholder="cio@company.com, noc@company.com"
                                            className="bg-black/50 border-white/10 rounded-sm text-white"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Frequency</Label>
                                            <Select value={newReport.frequency} onValueChange={(v) => setNewReport({ ...newReport, frequency: v })}>
                                                <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                    <SelectItem value="daily">Daily</SelectItem>
                                                    <SelectItem value="weekly">Weekly</SelectItem>
                                                    <SelectItem value="monthly">Monthly</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Send At (Hour)</Label>
                                            <Select value={String(newReport.hour)} onValueChange={(v) => setNewReport({ ...newReport, hour: parseInt(v) })}>
                                                <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent className="bg-[#0a0a0a] border-white/10 max-h-[200px]">
                                                    {[...Array(24)].map((_, i) => (
                                                        <SelectItem key={i} value={String(i)}>{i.toString().padStart(2, '0')}:00</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    {newReport.frequency === 'weekly' && (
                                        <div className="space-y-2">
                                            <Label className="text-white/70 text-xs uppercase tracking-wider font-mono">Day of Week</Label>
                                            <Select value={String(newReport.day_of_week)} onValueChange={(v) => setNewReport({ ...newReport, day_of_week: parseInt(v) })}>
                                                <SelectTrigger className="bg-black/50 border-white/10 rounded-sm text-white">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent className="bg-[#0a0a0a] border-white/10">
                                                    {dayLabels.map((day, i) => (
                                                        <SelectItem key={i} value={String(i)}>{day}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    )}
                                    <div className="flex items-center gap-6 p-3 bg-white/5 rounded-sm">
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={newReport.include_pdf}
                                                onChange={(e) => setNewReport({ ...newReport, include_pdf: e.target.checked })}
                                                className="w-4 h-4 accent-primary"
                                            />
                                            <span className="text-white/70 text-sm">Include PDF Attachment</span>
                                        </label>
                                        {newReport.report_type === 'executive' && (
                                            <label className="flex items-center gap-2 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={newReport.include_ai_summary}
                                                    onChange={(e) => setNewReport({ ...newReport, include_ai_summary: e.target.checked })}
                                                    className="w-4 h-4 accent-cyan-400"
                                                />
                                                <span className="text-white/70 text-sm">AI Executive Summary</span>
                                            </label>
                                        )}
                                    </div>
                                    <Button onClick={handleAddReport} className="w-full bg-primary text-black hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm">
                                        Create Report
                                    </Button>
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>

                {/* Reports List */}
                <Card className="bg-[#0a0a0a] border-white/5 rounded-sm">
                    <CardHeader className="pb-2 border-b border-white/5">
                        <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                            <Calendar className="w-4 h-4 text-primary" />
                            Configured Reports ({reports.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-4">
                        {loading ? (
                            <div className="flex items-center justify-center py-12">
                                <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                            </div>
                        ) : reports.length === 0 ? (
                            <div className="text-center py-12 text-white/40">
                                <FileText className="w-16 h-16 mx-auto mb-4 opacity-30" />
                                <p className="text-lg font-heading font-bold uppercase tracking-wider mb-2">No scheduled reports</p>
                                <p className="text-sm font-mono mb-4">Create your first automated report to keep stakeholders informed</p>
                                <Button onClick={() => setShowAddDialog(true)} className="bg-primary text-black hover:bg-primary/90">
                                    <Plus className="w-4 h-4 mr-2" />
                                    Create Report
                                </Button>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {reports.map((report, idx) => (
                                    <motion.div
                                        key={report.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: idx * 0.05 }}
                                        className={`p-4 rounded-sm border transition-colors ${
                                            report.enabled 
                                                ? 'bg-white/5 border-white/10 hover:border-primary/30' 
                                                : 'bg-white/[0.02] border-white/5 opacity-60'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-3 mb-2 flex-wrap">
                                                    <h3 className="font-medium text-white">{report.name}</h3>
                                                    <Badge className={`text-[10px] uppercase rounded-sm ${
                                                        report.enabled 
                                                            ? 'bg-green-500/20 text-green-400 border-green-500/30' 
                                                            : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                                                    } border`}>
                                                        {report.enabled ? 'Active' : 'Paused'}
                                                    </Badge>
                                                    <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 text-[10px] uppercase rounded-sm border">
                                                        {reportTypeLabels[report.report_type] || report.report_type}
                                                    </Badge>
                                                    <Badge className="bg-primary/20 text-primary border-primary/30 text-[10px] uppercase rounded-sm border">
                                                        {frequencyLabels[report.frequency]}
                                                    </Badge>
                                                    {report.include_pdf && (
                                                        <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-[10px] uppercase rounded-sm border">
                                                            PDF
                                                        </Badge>
                                                    )}
                                                    {report.include_ai_summary && report.report_type === 'executive' && (
                                                        <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30 text-[10px] uppercase rounded-sm border">
                                                            AI
                                                        </Badge>
                                                    )}
                                                </div>
                                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-white/50 font-mono">
                                                    <div>
                                                        <span className="text-white/30 uppercase">Recipients</span>
                                                        <p className="text-white/70 mt-1">{report.recipients.join(', ')}</p>
                                                    </div>
                                                    <div>
                                                        <span className="text-white/30 uppercase">Schedule</span>
                                                        <p className="text-white/70 mt-1">
                                                            {report.frequency === 'weekly' && `${dayLabels[report.day_of_week]} `}
                                                            {String(report.hour).padStart(2, '0')}:00 UTC
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <span className="text-white/30 uppercase">Last Sent</span>
                                                        <p className="text-white/70 mt-1">{formatDate(report.last_sent)}</p>
                                                    </div>
                                                    <div>
                                                        <span className="text-white/30 uppercase">Next Run</span>
                                                        <p className="text-white/70 mt-1">{formatDate(report.next_run)}</p>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => handleSendNow(report.id)}
                                                    disabled={sendingReport === report.id}
                                                    className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 rounded-sm"
                                                >
                                                    {sendingReport === report.id ? (
                                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                                    ) : (
                                                        <Send className="w-4 h-4" />
                                                    )}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => handleToggleReport(report.id)}
                                                    className={`rounded-sm ${
                                                        report.enabled 
                                                            ? 'border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10' 
                                                            : 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                                                    }`}
                                                >
                                                    {report.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => handleDeleteReport(report.id)}
                                                    className="border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-sm"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Report Preview Dialog */}
                <Dialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
                    <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-3xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading text-xl uppercase tracking-wider text-white flex items-center gap-3">
                                <Eye className="w-6 h-6 text-cyan-400" />
                                Report Preview
                            </DialogTitle>
                        </DialogHeader>
                        
                        {previewData && (
                            <div className="space-y-6 mt-4">
                                {/* Stats Grid */}
                                <div className="grid grid-cols-4 gap-4">
                                    <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-sm text-center">
                                        <TrendingUp className="w-6 h-6 text-green-400 mx-auto mb-2" />
                                        <p className="font-heading font-bold text-2xl text-green-400">{previewData.overall_uptime}%</p>
                                        <p className="text-[10px] text-white/40 uppercase">Overall Uptime</p>
                                    </div>
                                    <div className="p-4 bg-primary/5 border border-primary/20 rounded-sm text-center">
                                        <Target className="w-6 h-6 text-primary mx-auto mb-2" />
                                        <p className="font-heading font-bold text-2xl text-primary">{previewData.sla_compliance}%</p>
                                        <p className="text-[10px] text-white/40 uppercase">SLA Compliance</p>
                                    </div>
                                    <div className="p-4 bg-cyan-500/5 border border-cyan-500/20 rounded-sm text-center">
                                        <FileText className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
                                        <p className="font-heading font-bold text-2xl text-cyan-400">{previewData.total_monitors}</p>
                                        <p className="text-[10px] text-white/40 uppercase">Monitors</p>
                                    </div>
                                    <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-sm text-center">
                                        <AlertTriangle className="w-6 h-6 text-red-400 mx-auto mb-2" />
                                        <p className="font-heading font-bold text-2xl text-red-400">{previewData.alerts.total}</p>
                                        <p className="text-[10px] text-white/40 uppercase">Alerts</p>
                                    </div>
                                </div>

                                {/* Alert Summary */}
                                <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                                    <h4 className="font-heading font-bold text-sm uppercase tracking-wider text-white/60 mb-3">Alert Summary</h4>
                                    <div className="flex gap-3 flex-wrap">
                                        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">Critical: {previewData.alerts.critical}</Badge>
                                        <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">Warning: {previewData.alerts.warning}</Badge>
                                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30">Resolved: {previewData.alerts.resolved}</Badge>
                                        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">Open: {previewData.alerts.open}</Badge>
                                    </div>
                                </div>

                                {/* Monitor Performance */}
                                <div className="p-4 bg-white/5 rounded-sm border border-white/10">
                                    <h4 className="font-heading font-bold text-sm uppercase tracking-wider text-white/60 mb-3">Monitor Performance</h4>
                                    <div className="space-y-2">
                                        {previewData.monitors.map((m, idx) => (
                                            <div key={idx} className="flex items-center justify-between p-2 bg-black/30 rounded-sm">
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-2 h-2 rounded-full ${m.sla_met ? 'bg-green-400' : 'bg-red-400'}`} />
                                                    <span className="text-white text-sm">{m.name}</span>
                                                    <span className="text-white/40 text-xs font-mono uppercase">{m.type}</span>
                                                </div>
                                                <div className="flex items-center gap-4 text-xs font-mono">
                                                    <span className={m.uptime_percent >= m.sla_target ? 'text-green-400' : 'text-red-400'}>
                                                        {m.uptime_percent}% uptime
                                                    </span>
                                                    <span className="text-white/40">{m.avg_latency_ms}ms</span>
                                                    <Badge className={`text-[10px] ${m.sla_met ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                                        {m.sla_met ? 'SLA Met' : 'SLA Breached'}
                                                    </Badge>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>
            </div>
        </>
    );
};
