import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    FileText, Upload, RefreshCw, Download, Sparkles, AlertTriangle,
    Bot, CheckCircle, Clock, BarChart3, FileSpreadsheet, Brain, FileDown,
    Shield, Gauge, Activity, Share2, Copy, Lock, Eye,
} from 'lucide-react';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const SEV_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};

export default function WeeklyReportsPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('generate');
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [currentReport, setCurrentReport] = useState(null);
    const [period, setPeriod] = useState('7');
    const [templateId, setTemplateId] = useState('');
    const [availableTemplates, setAvailableTemplates] = useState([]);
    const [shareOpen, setShareOpen] = useState(false);
    const [shareReportId, setShareReportId] = useState('');
    const [sharePassword, setSharePassword] = useState('');
    const [shareExpiry, setShareExpiry] = useState('7');
    const [shareRequireOtp, setShareRequireOtp] = useState(false);
    const [creatingShare, setCreatingShare] = useState(false);
    const [shareLink, setShareLink] = useState('');
    const [existingShares, setExistingShares] = useState([]);
    const fileInputRef = useRef(null);

    const fetchReports = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/weekly-reports/list?limit=20');
            setReports(res.data || []);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchReports(); }, [fetchReports]);

    // Load available templates for the generate dropdown
    useEffect(() => {
        api.get('/report-templates/list')
            .then(r => setAvailableTemplates(r.data || []))
            .catch(() => {});
    }, [api]);

    const generateFromSOC = async () => {
        setGenerating(true);
        setCurrentReport(null);
        try {
            const res = await api.post('/weekly-reports/generate/auto', {
                days: parseInt(period, 10),
                period: '',
                include_pdf: true,
                executive: true,
                template_id: templateId || null,
            });
            setCurrentReport(res.data);
            toast.success('AI Weekly Report generated successfully');
            await fetchReports();
        } catch (e) {
            toast.error(`Generation failed: ${e.response?.data?.detail || e.message}`);
        }
        setGenerating(false);
    };

    const handleUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const name = file.name.toLowerCase();
        const allowed = ['.docx', '.xlsx', '.xls', '.csv'];
        if (!allowed.some(ext => name.endsWith(ext))) {
            toast.error('Supported formats: .docx, .xlsx, .csv');
            return;
        }
        setGenerating(true);
        setCurrentReport(null);
        const fd = new FormData();
        fd.append('file', file);
        try {
            const qs = templateId ? `?include_pdf=true&executive=true&template_id=${encodeURIComponent(templateId)}` : '?include_pdf=true&executive=true';
            const res = await fetch(`${BACKEND_URL}/api/weekly-reports/generate/upload${qs}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('falconToken')}` },
                body: fd,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Upload failed');
            setCurrentReport(data);
            const src = data.alerts?.length || 0;
            toast.success(`Report generated from ${file.name} (${src} alerts parsed)`);
            await fetchReports();
        } catch (err) {
            toast.error(`Upload failed: ${err.message}`);
        }
        setGenerating(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const downloadReport = (reportId, fmt) => {
        const url = `${BACKEND_URL}/api/weekly-reports/${reportId}/download/${fmt}`;
        const token = localStorage.getItem('falconToken');
        const ext = fmt === 'excel' ? 'xlsx' : fmt;
        fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
            .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.blob(); })
            .then(blob => {
                const link = document.createElement('a');
                link.href = window.URL.createObjectURL(blob);
                link.download = `FalconOps_Report_${reportId}.${ext}`;
                link.click();
                window.URL.revokeObjectURL(link.href);
                toast.success(`${fmt.toUpperCase()} downloaded`);
            })
            .catch(err => toast.error(`Download failed: ${err.message}`));
    };

    const openShareDialog = async (reportId) => {
        setShareReportId(reportId);
        setSharePassword('');
        setShareExpiry('7');
        setShareRequireOtp(false);
        setShareLink('');
        setShareOpen(true);
        try {
            const res = await api.get(`/share/report/${reportId}`);
            setExistingShares(res.data || []);
        } catch (e) {
            setExistingShares([]);
        }
    };

    const createShare = async () => {
        setCreatingShare(true);
        try {
            const payload = {
                report_id: shareReportId,
                expiry_days: parseInt(shareExpiry, 10),
                password: sharePassword || null,
                require_otp: shareRequireOtp,
            };
            const res = await api.post('/share/create', payload);
            const token = res.data?.token;
            const url = `${window.location.origin}/portal/${token}`;
            setShareLink(url);
            toast.success('Share link created');
            const listRes = await api.get(`/share/report/${shareReportId}`);
            setExistingShares(listRes.data || []);
        } catch (e) {
            toast.error(`Share failed: ${e.response?.data?.detail || e.message}`);
        }
        setCreatingShare(false);
    };

    const copyLink = (link) => {
        navigator.clipboard.writeText(link);
        toast.success('Link copied to clipboard');
    };

    const revokeShare = async (token) => {
        try {
            await api.post(`/share/${token}/revoke`);
            toast.success('Share revoked');
            const listRes = await api.get(`/share/report/${shareReportId}`);
            setExistingShares(listRes.data || []);
        } catch (e) {
            toast.error(`Revoke failed: ${e.message}`);
        }
    };

    const tabs = [
        { id: 'generate', label: 'Generate Report', icon: Sparkles },
        { id: 'history', label: 'Report History', icon: Clock },
    ];

    return (
        <div className="space-y-6" data-testid="weekly-reports-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Brain className="w-6 h-6 text-[#00E0FF]" />
                        AI Weekly Report Generator
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Automated weekly alert summaries in the Fasah format · DOCX + Excel export · AI-powered insights
                    </p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchReports}
                    disabled={loading}
                    data-testid="refresh-reports-btn"
                >
                    <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/10">
                {tabs.map(t => (
                    <Button
                        key={t.id}
                        variant="ghost"
                        onClick={() => setTab(t.id)}
                        className={`rounded-none border-b-2 transition-all ${
                            tab === t.id
                                ? 'border-[#00E0FF] text-[#00E0FF] bg-white/5'
                                : 'border-transparent text-white/50 hover:text-white'
                        }`}
                        data-testid={`tab-${t.id}`}
                    >
                        <t.icon className="w-4 h-4 mr-2" />
                        {t.label}
                    </Button>
                ))}
            </div>

            {/* Generate Tab */}
            {tab === 'generate' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Control Panel */}
                    <Card className="bg-[#0D1117] border-white/5 lg:col-span-1">
                        <CardHeader>
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-[#00E0FF]" />
                                Generate New Report
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Auto Fetch Section */}
                            <div className="space-y-2 p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                                <Label className="text-xs text-white/60">Auto-Fetch from SOC Engine</Label>
                                <Select value={period} onValueChange={setPeriod}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 text-xs" data-testid="period-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        <SelectItem value="7">Last 7 Days</SelectItem>
                                        <SelectItem value="14">Last 14 Days</SelectItem>
                                        <SelectItem value="30">Last 30 Days</SelectItem>
                                    </SelectContent>
                                </Select>

                                {/* Template selector */}
                                <Label className="text-xs text-white/60 pt-2 block">PDF Template</Label>
                                <Select value={templateId || 'default'} onValueChange={(v) => setTemplateId(v === 'default' ? '' : v)}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 text-xs" data-testid="template-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        <SelectItem value="default">Default (Full Layout)</SelectItem>
                                        {availableTemplates.map(t => (
                                            <SelectItem key={t.template_id} value={t.template_id}>
                                                {t.name} ({t.sections?.length || 0} sections)
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    onClick={generateFromSOC}
                                    disabled={generating}
                                    className="w-full bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                                    data-testid="generate-auto-btn"
                                >
                                    {generating ? (
                                        <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Generating...</>
                                    ) : (
                                        <><Sparkles className="w-4 h-4 mr-2" /> Generate Weekly Report</>
                                    )}
                                </Button>
                            </div>

                            {/* Upload Section */}
                            <div className="space-y-2 p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                                <Label className="text-xs text-white/60">Or Upload Alerts File</Label>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".docx,.xlsx,.xls,.csv"
                                    onChange={handleUpload}
                                    className="hidden"
                                    data-testid="file-upload-input"
                                />
                                <Button
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={generating}
                                    variant="outline"
                                    className="w-full border-white/10"
                                    data-testid="upload-docx-btn"
                                >
                                    <Upload className="w-4 h-4 mr-2" />
                                    Upload Excel / CSV / DOCX
                                </Button>
                                <p className="text-[10px] text-white/30">
                                    Accepts <b>.xlsx</b>, <b>.csv</b>, or <b>.docx</b>. File must have a header row with at least <code className="text-[#00E0FF]">rule_name</code>, optionally <code>severity</code>, <code>count</code>, <code>summary</code>. AI rebuilds the report in Fasah format.
                                </p>
                            </div>

                            {/* Legend */}
                            <div className="text-xs text-white/40 space-y-1 pt-2 border-t border-white/5">
                                <p className="font-semibold text-white/60 mb-1">What you get:</p>
                                <p>• AI-generated executive summary</p>
                                <p>• Alert breakdown table (Fasah format)</p>
                                <p>• DOCX + Excel exports with charts</p>
                                <p>• Severity-coded critical/warning counts</p>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Preview */}
                    <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                        <CardHeader>
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <FileText className="w-4 h-4 text-[#F5B841]" />
                                Report Preview
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {!currentReport && !generating && (
                                <div className="text-center py-12 text-white/40" data-testid="empty-preview">
                                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                    <p className="text-sm">No report yet.</p>
                                    <p className="text-xs mt-1">Generate one from SOC data or upload a DOCX template.</p>
                                </div>
                            )}
                            {generating && (
                                <div className="text-center py-12" data-testid="generating-state">
                                    <Brain className="w-12 h-12 mx-auto mb-3 text-[#00E0FF] animate-pulse" />
                                    <p className="text-sm text-white">AI is analyzing alerts...</p>
                                    <p className="text-xs text-white/50 mt-1">This takes ~15-30 seconds</p>
                                </div>
                            )}
                            {currentReport && !generating && (
                                <div className="space-y-4" data-testid="report-preview">
                                    {/* Stats Grid */}
                                    <div className="grid grid-cols-4 gap-3">
                                        <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                                            <p className="text-[10px] text-white/40 uppercase">Total Alerts</p>
                                            <p className="text-2xl font-bold text-white mt-1">{currentReport.total_alerts}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                            <p className="text-[10px] text-red-400/70 uppercase">Critical</p>
                                            <p className="text-2xl font-bold text-red-400 mt-1">{currentReport.critical_count}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                                            <p className="text-[10px] text-amber-400/70 uppercase">Warning</p>
                                            <p className="text-2xl font-bold text-amber-400 mt-1">{currentReport.warning_count}</p>
                                        </div>
                                        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                                            <p className="text-[10px] text-blue-400/70 uppercase">Occurrences</p>
                                            <p className="text-2xl font-bold text-blue-400 mt-1">{currentReport.total_occurrences || 0}</p>
                                        </div>
                                    </div>

                                    {/* SLA Metrics */}
                                    {currentReport.sla_metrics && (
                                        <div className="grid grid-cols-4 gap-3" data-testid="sla-metrics">
                                            <div className={`p-3 rounded-lg border ${
                                                currentReport.sla_metrics.risk_posture === 'High' ? 'bg-red-500/10 border-red-500/20' :
                                                currentReport.sla_metrics.risk_posture === 'Medium' ? 'bg-amber-500/10 border-amber-500/20' :
                                                'bg-emerald-500/10 border-emerald-500/20'
                                            }`}>
                                                <div className="flex items-center gap-1.5">
                                                    <Shield className="w-3 h-3" />
                                                    <p className="text-[10px] uppercase opacity-70">Risk Posture</p>
                                                </div>
                                                <p className="text-xl font-bold mt-1">{currentReport.sla_metrics.risk_posture}</p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-[#00E0FF]/10 border border-[#00E0FF]/20">
                                                <div className="flex items-center gap-1.5">
                                                    <Gauge className="w-3 h-3 text-[#00E0FF]" />
                                                    <p className="text-[10px] text-[#00E0FF]/70 uppercase">SLA Uptime</p>
                                                </div>
                                                <p className="text-xl font-bold text-[#00E0FF] mt-1">{currentReport.sla_metrics.uptime_pct?.toFixed(2)}%</p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                                                <div className="flex items-center gap-1.5">
                                                    <Clock className="w-3 h-3 text-purple-400" />
                                                    <p className="text-[10px] text-purple-400/70 uppercase">MTTR</p>
                                                </div>
                                                <p className="text-xl font-bold text-purple-400 mt-1">{currentReport.sla_metrics.mttr_minutes} min</p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                                                <div className="flex items-center gap-1.5">
                                                    <Activity className="w-3 h-3 text-white/50" />
                                                    <p className="text-[10px] text-white/40 uppercase">Compliance</p>
                                                </div>
                                                <p className="text-xl font-bold text-white mt-1">{currentReport.sla_metrics.sla_compliance}</p>
                                            </div>
                                        </div>
                                    )}

                                    {/* AI Summary */}
                                    <div className="p-4 rounded-lg bg-gradient-to-br from-[#00E0FF]/5 to-purple-500/5 border border-[#00E0FF]/20">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Bot className="w-4 h-4 text-[#00E0FF]" />
                                            <p className="text-xs font-semibold text-[#00E0FF]">AI-Generated Executive Summary</p>
                                        </div>
                                        <p className="text-sm text-white/80 whitespace-pre-wrap leading-relaxed" data-testid="ai-summary">
                                            {currentReport.ai_summary || 'No summary available'}
                                        </p>
                                    </div>

                                    {/* Alert Table */}
                                    <div className="overflow-hidden rounded-lg border border-white/5">
                                        <table className="w-full text-xs">
                                            <thead className="bg-white/5 text-white/50">
                                                <tr>
                                                    <th className="text-left p-2">Rule Name</th>
                                                    <th className="text-left p-2">Severity</th>
                                                    <th className="text-left p-2">Count</th>
                                                    <th className="text-left p-2">Summary</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(currentReport.alerts || []).slice(0, 10).map((a, i) => (
                                                    <tr key={i} className="border-t border-white/5" data-testid={`alert-row-${i}`}>
                                                        <td className="p-2 text-white/80">{a.rule_name}</td>
                                                        <td className="p-2">
                                                            <Badge className={SEV_STYLES[a.severity] || SEV_STYLES.info}>
                                                                {a.severity}
                                                            </Badge>
                                                        </td>
                                                        <td className="p-2 text-white/60">{a.count}</td>
                                                        <td className="p-2 text-white/50 truncate max-w-xs">{a.summary}</td>
                                                    </tr>
                                                ))}
                                                {(!currentReport.alerts || currentReport.alerts.length === 0) && (
                                                    <tr>
                                                        <td colSpan="4" className="p-6 text-center text-white/40">
                                                            No alerts found for this period
                                                        </td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>

                                    {/* Download Buttons */}
                                    {currentReport.report_id && (
                                        <div className="flex gap-2 pt-2 flex-wrap">
                                            {currentReport.has_pdf && (
                                                <Button
                                                    onClick={() => downloadReport(currentReport.report_id, 'pdf')}
                                                    className="bg-gradient-to-r from-[#00E0FF] to-[#F5B841] text-black hover:opacity-90 font-semibold"
                                                    data-testid="download-pdf-btn"
                                                >
                                                    <FileDown className="w-4 h-4 mr-2" />
                                                    Download PDF (Enterprise)
                                                </Button>
                                            )}
                                            <Button
                                                onClick={() => downloadReport(currentReport.report_id, 'docx')}
                                                variant="outline"
                                                className="border-[#00E0FF]/30 text-[#00E0FF] hover:bg-[#00E0FF]/10"
                                                data-testid="download-docx-btn"
                                            >
                                                <FileText className="w-4 h-4 mr-2" />
                                                Download DOCX
                                            </Button>
                                            <Button
                                                onClick={() => downloadReport(currentReport.report_id, 'excel')}
                                                variant="outline"
                                                className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                                                data-testid="download-excel-btn"
                                            >
                                                <FileSpreadsheet className="w-4 h-4 mr-2" />
                                                Download Excel
                                            </Button>
                                            <Button
                                                onClick={() => openShareDialog(currentReport.report_id)}
                                                variant="outline"
                                                className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
                                                data-testid="share-report-btn"
                                            >
                                                <Share2 className="w-4 h-4 mr-2" />
                                                Share
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* History Tab */}
            {tab === 'history' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader>
                        <CardTitle className="text-sm text-white flex items-center gap-2">
                            <Clock className="w-4 h-4" />
                            Past Reports ({reports.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {reports.length === 0 ? (
                            <div className="text-center py-12 text-white/40" data-testid="empty-history">
                                <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                <p className="text-sm">No reports generated yet</p>
                            </div>
                        ) : (
                            <div className="space-y-2" data-testid="reports-history-list">
                                {reports.map((r) => (
                                    <div
                                        key={r.report_id}
                                        className="flex items-center justify-between p-3 rounded-lg border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors"
                                        data-testid={`report-item-${r.report_id}`}
                                    >
                                        <div className="flex items-center gap-3 flex-1 min-w-0">
                                            <div className="p-2 rounded-lg bg-[#00E0FF]/10">
                                                <FileText className="w-4 h-4 text-[#00E0FF]" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <p className="text-sm text-white font-medium truncate">
                                                        Report {r.report_id}
                                                    </p>
                                                    <Badge variant="outline" className="text-[9px] border-white/10 text-white/50">
                                                        {r.source}
                                                    </Badge>
                                                </div>
                                                <div className="flex items-center gap-3 mt-1 text-xs text-white/50">
                                                    <span>{new Date(r.created_at).toLocaleString()}</span>
                                                    <span>· {r.total_alerts} alerts</span>
                                                    {r.critical_count > 0 && (
                                                        <span className="text-red-400">· {r.critical_count} critical</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {r.has_pdf && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => downloadReport(r.report_id, 'pdf')}
                                                    className="text-[#F5B841] hover:bg-[#F5B841]/10"
                                                    data-testid={`history-pdf-${r.report_id}`}
                                                >
                                                    <FileDown className="w-3.5 h-3.5 mr-1" /> PDF
                                                </Button>
                                            )}
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => downloadReport(r.report_id, 'docx')}
                                                data-testid={`history-docx-${r.report_id}`}
                                            >
                                                <Download className="w-3.5 h-3.5 mr-1" /> DOCX
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => downloadReport(r.report_id, 'excel')}
                                                data-testid={`history-excel-${r.report_id}`}
                                            >
                                                <Download className="w-3.5 h-3.5 mr-1" /> Excel
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => openShareDialog(r.report_id)}
                                                className="text-purple-400 hover:bg-purple-500/10"
                                                data-testid={`history-share-${r.report_id}`}
                                            >
                                                <Share2 className="w-3.5 h-3.5 mr-1" /> Share
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Share Dialog */}
            <Dialog open={shareOpen} onOpenChange={setShareOpen}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Share2 className="w-5 h-5 text-purple-400" />
                            Share Report
                        </DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            Create a public shareable link. Recipients can view the report without logging in.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        {/* Config */}
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs text-white/60 mb-1 block">Expires in (days)</label>
                                <Input
                                    type="number" min="1" max="365"
                                    value={shareExpiry}
                                    onChange={(e) => setShareExpiry(e.target.value)}
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="share-expiry-input"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-white/60 mb-1 block flex items-center gap-1">
                                    <Lock className="w-3 h-3" /> Password (optional)
                                </label>
                                <Input
                                    type="password"
                                    value={sharePassword}
                                    onChange={(e) => setSharePassword(e.target.value)}
                                    placeholder="Leave empty for no password"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="share-password-input"
                                />
                            </div>
                        </div>

                        {/* OTP toggle */}
                        <label className="flex items-start gap-2 p-3 rounded-lg border border-white/10 bg-white/[0.02] cursor-pointer hover:bg-white/[0.04]">
                            <input
                                type="checkbox"
                                checked={shareRequireOtp}
                                onChange={(e) => setShareRequireOtp(e.target.checked)}
                                className="mt-0.5 cursor-pointer"
                                data-testid="share-otp-toggle"
                            />
                            <div className="flex-1">
                                <p className="text-xs text-white font-medium flex items-center gap-1">
                                    <Eye className="w-3 h-3 text-purple-400" />
                                    Require email OTP verification
                                </p>
                                <p className="text-[10px] text-white/40 mt-0.5">
                                    Recipients must enter their email and receive a 6-digit code (10-min TTL) before viewing.
                                </p>
                            </div>
                        </label>

                        <Button
                            onClick={createShare}
                            disabled={creatingShare}
                            className="w-full bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                            data-testid="create-share-btn"
                        >
                            {creatingShare ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Share2 className="w-4 h-4 mr-2" />}
                            Generate Link
                        </Button>

                        {/* Generated link */}
                        {shareLink && (
                            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30" data-testid="generated-share-link">
                                <p className="text-xs text-emerald-400 mb-2 flex items-center gap-1">
                                    <CheckCircle className="w-3 h-3" /> Link ready
                                </p>
                                <div className="flex gap-2">
                                    <Input
                                        readOnly
                                        value={shareLink}
                                        className="bg-[#161B22] border-white/10 text-xs font-mono"
                                        data-testid="share-link-value"
                                    />
                                    <Button
                                        onClick={() => copyLink(shareLink)}
                                        variant="outline"
                                        className="border-white/10 shrink-0"
                                        data-testid="copy-share-link"
                                    >
                                        <Copy className="w-4 h-4" />
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Existing shares */}
                        {existingShares.length > 0 && (
                            <div>
                                <p className="text-xs text-white/60 mb-2">Active Share Links ({existingShares.length})</p>
                                <div className="space-y-2 max-h-48 overflow-y-auto">
                                    {existingShares.map(s => (
                                        <div
                                            key={s.token}
                                            className={`p-2 rounded border text-xs ${
                                                s.revoked
                                                    ? 'bg-red-500/5 border-red-500/20 opacity-60'
                                                    : 'bg-white/[0.02] border-white/5'
                                            }`}
                                            data-testid={`existing-share-${s.token}`}
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        {s.password_protected && <Lock className="w-3 h-3 text-amber-400" />}
                                                        {s.require_otp && <Eye className="w-3 h-3 text-purple-400" title="OTP required" />}
                                                        <span className="font-mono text-white/70 truncate">{s.token.slice(0, 16)}…</span>
                                                        {s.revoked && <Badge className="bg-red-500/15 text-red-400 text-[9px]">Revoked</Badge>}
                                                    </div>
                                                    <div className="text-[10px] text-white/40 mt-0.5">
                                                        <Eye className="w-2.5 h-2.5 inline mr-0.5" /> {s.access_count || 0} views ·
                                                        Expires {new Date(s.expires_at).toLocaleDateString()} ·
                                                        {s.created_by}
                                                    </div>
                                                </div>
                                                <div className="flex gap-1 shrink-0">
                                                    <Button
                                                        size="icon"
                                                        variant="ghost"
                                                        className="h-7 w-7"
                                                        onClick={() => copyLink(`${window.location.origin}/portal/${s.token}`)}
                                                        title="Copy link"
                                                        disabled={s.revoked}
                                                    >
                                                        <Copy className="w-3 h-3" />
                                                    </Button>
                                                    {!s.revoked && (
                                                        <Button
                                                            size="icon"
                                                            variant="ghost"
                                                            className="h-7 w-7 text-red-400 hover:bg-red-500/10"
                                                            onClick={() => revokeShare(s.token)}
                                                            title="Revoke"
                                                            data-testid={`revoke-${s.token}`}
                                                        >
                                                            ×
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
