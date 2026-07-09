import React, { useState, useEffect, useCallback } from 'react';

import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import {
    Upload,
    FileSpreadsheet,
    Brain,
    AlertTriangle,
    CheckCircle,
    XCircle,
    Clock,
    Server,
    Activity,
    TrendingUp,
    TrendingDown,
    Zap,
    RefreshCw,
    Download,
    Trash2,
    Eye,
    BarChart3,
    PieChart,
    FileText,
    HelpCircle,
    ChevronRight,
    Lightbulb,
    Target,
    Shield,
    Webhook,
    Database,
    BookOpen,
    Percent,
    Copy,
    Plus,
    Settings,
    GraduationCap,
    CalendarClock,
    Mail,
    Play,
    Pause,
    Fingerprint,
    Hash,
} from 'lucide-react';
import { PieChart as RechartsPie, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts';
import ReactMarkdown from 'react-markdown';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const EventAnalyzerPage = () => {
    const [activeTab, setActiveTab] = useState('upload');
    const [loading, setLoading] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [uploadResult, setUploadResult] = useState(null);
    const [analysisResult, setAnalysisResult] = useState(null);
    const [uploads, setUploads] = useState([]);
    const [dragActive, setDragActive] = useState(false);
    
    // Webhook state
    const [webhooks, setWebhooks] = useState([]);
    const [newWebhook, setNewWebhook] = useState({ name: '', source_type: 'custom', auto_analyze: true, analyze_threshold: 10 });
    
    // Knowledge base state
    const [knowledgeStats, setKnowledgeStats] = useState(null);
    const [knowledgePatterns, setKnowledgePatterns] = useState([]);
    
    // Ingestion stats
    const [ingestionStats, setIngestionStats] = useState(null);

    // Export state
    const [exporting, setExporting] = useState(null);
    const [showBranding, setShowBranding] = useState(false);
    const [branding, setBranding] = useState({ company: '', title: '', footer: '' });
    // Track current analysis_id for exports
    const [currentAnalysisId, setCurrentAnalysisId] = useState(null);

    // Scheduling state
    const [schedules, setSchedules] = useState([]);
    const [showScheduleForm, setShowScheduleForm] = useState(false);
    const [scheduleForm, setScheduleForm] = useState({
        name: '', frequency: 'weekly', day_of_week: 'mon', day_of_month: 1,
        hour: 8, format: 'pdf', recipients: '', email_subject: 'FalconOps AI - Scheduled Report',
        branding: { company: '', title: '', footer: '' }
    });

    // Health Rule Analytics state
    const [ruleAnalytics, setRuleAnalytics] = useState(null);
    const [ruleAnalyticsLoading, setRuleAnalyticsLoading] = useState(false);
    const [selectedRule, setSelectedRule] = useState(null);

    const getAuthHeaders = () => ({
        'Authorization': `Bearer ${localStorage.getItem('falconToken')}`,
    });

    // Fetch previous uploads
    useEffect(() => {
        fetchUploads();
        fetchWebhooks();
        fetchKnowledgeStats();
        fetchKnowledgePatterns();
        fetchIngestionStats();
        fetchSchedules();
        fetchRuleAnalytics();
    }, []);

    const fetchUploads = async () => {
        try {
            const response = await fetch(`${API_URL}/api/events/uploads`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setUploads(data.uploads || []);
        } catch (error) {
            console.error('Error fetching uploads:', error);
        }
    };
    
    const fetchWebhooks = async () => {
        try {
            const response = await fetch(`${API_URL}/api/ingest/webhooks`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setWebhooks(data.webhooks || []);
        } catch (error) {
            console.error('Error fetching webhooks:', error);
        }
    };
    
    const fetchKnowledgeStats = async () => {
        try {
            const response = await fetch(`${API_URL}/api/ingest/knowledge/stats`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setKnowledgeStats(data);
        } catch (error) {
            console.error('Error fetching knowledge stats:', error);
        }
    };
    
    const fetchKnowledgePatterns = async () => {
        try {
            const response = await fetch(`${API_URL}/api/ingest/knowledge/patterns`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setKnowledgePatterns(data.patterns || []);
        } catch (error) {
            console.error('Error fetching patterns:', error);
        }
    };
    
    const fetchIngestionStats = async () => {
        try {
            const response = await fetch(`${API_URL}/api/ingest/stats`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setIngestionStats(data);
        } catch (error) {
            console.error('Error fetching ingestion stats:', error);
        }
    };

    const fetchSchedules = async () => {
        try {
            const res = await fetch(`${API_URL}/api/report-schedules`, { headers: getAuthHeaders() });
            const data = await res.json();
            setSchedules(data.schedules || []);
        } catch (e) { console.error('Error fetching schedules:', e); }
    };

    const fetchRuleAnalytics = async () => {
        setRuleAnalyticsLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/events/health-rule-analytics`, { headers: getAuthHeaders() });
            const data = await res.json();
            setRuleAnalytics(data);
        } catch (e) { console.error('Error fetching rule analytics:', e); }
        finally { setRuleAnalyticsLoading(false); }
    };

    const handleCreateSchedule = async () => {
        if (!scheduleForm.name.trim()) { toast.error('Enter schedule name'); return; }
        setLoading(true);
        try {
            const body = {
                ...scheduleForm,
                recipients: scheduleForm.recipients.split(',').map(r => r.trim()).filter(Boolean),
                analysis_id: currentAnalysisId || null,
            };
            const res = await fetch(`${API_URL}/api/report-schedules`, {
                method: 'POST', headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error('Failed');
            toast.success('Schedule created');
            setShowScheduleForm(false);
            setScheduleForm({ name: '', frequency: 'weekly', day_of_week: 'mon', day_of_month: 1, hour: 8, format: 'pdf', recipients: '', email_subject: 'FalconOps AI - Scheduled Report', branding: { company: '', title: '', footer: '' } });
            fetchSchedules();
        } catch (e) { toast.error(e.message); } finally { setLoading(false); }
    };

    const handleToggleSchedule = async (id, enabled) => {
        try {
            await fetch(`${API_URL}/api/report-schedules/${id}`, {
                method: 'PUT', headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !enabled }),
            });
            fetchSchedules();
        } catch (e) { toast.error('Failed to update'); }
    };

    const handleDeleteSchedule = async (id) => {
        try {
            await fetch(`${API_URL}/api/report-schedules/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
            toast.success('Schedule deleted');
            fetchSchedules();
        } catch (e) { toast.error('Failed to delete'); }
    };

    const handleRunNow = async (id) => {
        try {
            toast.info('Running scheduled report...');
            await fetch(`${API_URL}/api/report-schedules/${id}/run`, { method: 'POST', headers: getAuthHeaders() });
            toast.success('Report generated');
            fetchSchedules();
        } catch (e) { toast.error('Failed to run'); }
    };
    
    const handleCreateWebhook = async () => {
        if (!newWebhook.name.trim()) {
            toast.error('Please enter a webhook name');
            return;
        }
        
        setLoading(true);
        try {
            const response = await fetch(`${API_URL}/api/ingest/webhooks`, {
                method: 'POST',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newWebhook),
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to create webhook');
            }
            
            toast.success('Webhook created successfully');
            setNewWebhook({ name: '', source_type: 'custom', auto_analyze: true, analyze_threshold: 10 });
            fetchWebhooks();
        } catch (error) {
            toast.error(error.message);
        } finally {
            setLoading(false);
        }
    };
    
    const handleDeleteWebhook = async (webhookId) => {
        if (!window.confirm('Delete this webhook?')) return;
        
        try {
            await fetch(`${API_URL}/api/ingest/webhooks/${webhookId}`, {
                method: 'DELETE',
                headers: getAuthHeaders(),
            });
            toast.success('Webhook deleted');
            fetchWebhooks();
        } catch (error) {
            toast.error('Failed to delete webhook');
        }
    };
    
    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        toast.success('Copied to clipboard');
    };

    const handleDrag = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    }, []);

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileUpload(e.target.files[0]);
        }
    };

    const handleFileUpload = async (file) => {
        // Validate file type
        const validTypes = ['.xlsx', '.xls', '.csv'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!validTypes.includes(fileExt)) {
            toast.error('Invalid file type. Please upload .xlsx, .xls, or .csv files.');
            return;
        }

        // Validate file size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            toast.error('File too large. Maximum size is 10MB.');
            return;
        }

        setLoading(true);
        setUploadResult(null);
        setAnalysisResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_URL}/api/events/upload`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('falconToken')}`,
                },
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Upload failed');
            }

            setUploadResult(data);
            toast.success(`Successfully uploaded ${data.total_events} events`);
            fetchUploads();
            
            // Auto-switch to analysis tab
            setActiveTab('analysis');
            
            // Auto-start analysis
            handleAnalyze(data.upload_id);

        } catch (error) {
            toast.error(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAnalyze = async (uploadId) => {
        setAnalyzing(true);
        
        try {
            const response = await fetch(`${API_URL}/api/events/analyze/${uploadId}`, {
                method: 'POST',
                headers: getAuthHeaders(),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Analysis failed');
            }

            setAnalysisResult(data);
            setCurrentAnalysisId(data.analysis_id);
            setShowBranding(true);
            toast.success('AI analysis complete');
            fetchUploads();

        } catch (error) {
            toast.error(error.message);
        } finally {
            setAnalyzing(false);
        }
    };

    const handleViewAnalysis = async (analysisId) => {
        setLoading(true);
        try {
            const response = await fetch(`${API_URL}/api/events/analysis/${analysisId}`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            setAnalysisResult(data);
            setCurrentAnalysisId(analysisId);
            setActiveTab('analysis');
        } catch (error) {
            toast.error('Failed to load analysis');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteUpload = async (uploadId) => {
        if (!window.confirm('Delete this upload and its analysis?')) return;

        try {
            await fetch(`${API_URL}/api/events/upload/${uploadId}`, {
                method: 'DELETE',
                headers: getAuthHeaders(),
            });
            toast.success('Upload deleted');
            fetchUploads();
            if (uploadResult?.upload_id === uploadId) {
                setUploadResult(null);
                setAnalysisResult(null);
            }
        } catch (error) {
            toast.error('Failed to delete upload');
        }
    };

    const handleExport = async (format) => {
        const aid = currentAnalysisId || analysisResult?.analysis_id;
        if (!aid) {
            toast.error('No analysis available to export');
            return;
        }
        setExporting(format);
        try {
            const params = new URLSearchParams();
            if (branding.company) params.append('company', branding.company);
            if (branding.title) params.append('title', branding.title);
            if (branding.footer) params.append('footer', branding.footer);
            if (format === 'docx' && branding.period) params.append('period', branding.period);
            const qs = params.toString() ? `?${params.toString()}` : '';

            const res = await fetch(`${API_URL}/api/events/export/${aid}/${format}${qs}`, {
                headers: getAuthHeaders(),
            });
            if (!res.ok) throw new Error('Export failed');
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const ext = format === 'excel' ? 'xlsx' : format === 'docx' ? 'docx' : 'pdf';
            a.download = format === 'docx'
                ? `Weekly_Report_${(branding.company || 'Fasah').replace(/ /g, '_')}_${new Date().toISOString().split('T')[0]}.docx`
                : `FalconOps_Analysis_${aid.slice(0, 8)}.${ext}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            toast.success(`${format.toUpperCase()} report downloaded`);
        } catch (e) {
            toast.error(e.message);
        } finally {
            setExporting(null);
        }
    };

    const severityColors = {
        critical: '#ef4444',
        warning: '#f59e0b',
        info: '#06b6d4',
    };

    const COLORS = ['#ef4444', '#f59e0b', '#06b6d4', '#10b981', '#8b5cf6'];

    return (
        <>
            <div className="space-y-6" data-testid="event-analyzer-page">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                            <Brain className="w-7 h-7 text-[#00E0FF]" />
                            AI Event Analyzer
                        </h1>
                        <p className="text-white/60 mt-1">
                            Upload event data from monitoring tools for AI-powered analysis
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        className="border-white/20 hover:bg-white/5"
                        onClick={() => window.open(`${API_URL}/api/events/sample-format`, '_blank')}
                    >
                        <HelpCircle className="w-4 h-4 mr-2" />
                        File Format Guide
                    </Button>
                </div>

                {/* Main Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="bg-white/5 border border-white/10">
                        <TabsTrigger value="upload" className="data-[state=active]:bg-[#00E0FF]/20 data-[state=active]:text-[#00E0FF]">
                            <Upload className="w-4 h-4 mr-2" />
                            Upload
                        </TabsTrigger>
                        <TabsTrigger value="analysis" className="data-[state=active]:bg-[#00E0FF]/20 data-[state=active]:text-[#00E0FF]">
                            <Brain className="w-4 h-4 mr-2" />
                            AI Analysis
                        </TabsTrigger>
                        <TabsTrigger value="webhooks" className="data-[state=active]:bg-[#F5B841]/20 data-[state=active]:text-[#F5B841]">
                            <Webhook className="w-4 h-4 mr-2" />
                            Webhooks
                        </TabsTrigger>
                        <TabsTrigger value="knowledge" className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400">
                            <GraduationCap className="w-4 h-4 mr-2" />
                            AI Learning
                        </TabsTrigger>
                        <TabsTrigger value="history" className="data-[state=active]:bg-[#00E0FF]/20 data-[state=active]:text-[#00E0FF]">
                            <FileText className="w-4 h-4 mr-2" />
                            History
                        </TabsTrigger>
                        <TabsTrigger value="schedules" className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-400">
                            <CalendarClock className="w-4 h-4 mr-2" />
                            Schedules
                        </TabsTrigger>
                        <TabsTrigger value="rule-analytics" className="data-[state=active]:bg-red-500/20 data-[state=active]:text-red-400" data-testid="rule-analytics-tab">
                            <Shield className="w-4 h-4 mr-2" />
                            Rule Analytics
                        </TabsTrigger>
                    </TabsList>

                    {/* Upload Tab */}
                    <TabsContent value="upload" className="mt-6">
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Upload Area */}
                            <div className="lg:col-span-2">
                                <Card className="bg-[#0a0a0a] border-white/10">
                                    <CardHeader>
                                        <CardTitle className="text-white flex items-center gap-2">
                                            <FileSpreadsheet className="w-5 h-5 text-[#00E0FF]" />
                                            Upload Event File
                                        </CardTitle>
                                        <CardDescription>
                                            Upload Excel (.xlsx, .xls) or CSV files containing events/alerts
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        {/* Drag & Drop Zone */}
                                        <div
                                            className={`relative border-2 border-dashed rounded-lg p-12 text-center transition-all ${
                                                dragActive 
                                                    ? 'border-[#00E0FF] bg-[#00E0FF]/10' 
                                                    : 'border-white/20 hover:border-white/40'
                                            }`}
                                            onDragEnter={handleDrag}
                                            onDragLeave={handleDrag}
                                            onDragOver={handleDrag}
                                            onDrop={handleDrop}
                                        >
                                            <input
                                                type="file"
                                                accept=".xlsx,.xls,.csv"
                                                onChange={handleFileSelect}
                                                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                                data-testid="file-input"
                                            />
                                            
                                            {loading ? (
                                                <div className="flex flex-col items-center">
                                                    <RefreshCw className="w-12 h-12 text-[#00E0FF] animate-spin mb-4" />
                                                    <p className="text-white font-medium">Processing file...</p>
                                                </div>
                                            ) : (
                                                <>
                                                    <Upload className={`w-12 h-12 mx-auto mb-4 ${dragActive ? 'text-[#00E0FF]' : 'text-white/40'}`} />
                                                    <p className="text-lg text-white font-medium mb-2">
                                                        {dragActive ? 'Drop file here' : 'Drag & drop your file here'}
                                                    </p>
                                                    <p className="text-white/50 text-sm mb-4">or click to browse</p>
                                                    <div className="flex items-center justify-center gap-3">
                                                        <Badge variant="outline" className="border-white/20 text-white/60">.xlsx</Badge>
                                                        <Badge variant="outline" className="border-white/20 text-white/60">.xls</Badge>
                                                        <Badge variant="outline" className="border-white/20 text-white/60">.csv</Badge>
                                                    </div>
                                                    <p className="text-white/40 text-xs mt-4">Maximum file size: 10MB</p>
                                                </>
                                            )}
                                        </div>

                                        {/* Upload Result Preview */}
                                        {uploadResult && (
                                            <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                                                <div className="flex items-center gap-3 mb-3">
                                                    <CheckCircle className="w-5 h-5 text-emerald-400" />
                                                    <span className="font-medium text-emerald-400">File Uploaded Successfully</span>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4 text-sm">
                                                    <div>
                                                        <p className="text-white/50">Filename</p>
                                                        <p className="text-white">{uploadResult.filename}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-white/50">Total Events</p>
                                                        <p className="text-white font-bold">{uploadResult.total_events?.toLocaleString()}</p>
                                                    </div>
                                                    <div className="col-span-2">
                                                        <p className="text-white/50 mb-1">Columns Detected</p>
                                                        <div className="flex flex-wrap gap-2">
                                                            {uploadResult.columns_detected?.map((col, idx) => (
                                                                <Badge key={idx} variant="outline" className="border-emerald-500/30 text-emerald-400">
                                                                    {col}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Expected Format Guide */}
                            <div className="lg:col-span-1">
                                <Card className="bg-[#0a0a0a] border-white/10">
                                    <CardHeader>
                                        <CardTitle className="text-white text-base flex items-center gap-2">
                                            <FileText className="w-4 h-4 text-[#F5B841]" />
                                            Expected Format
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div>
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-2">Required Columns</p>
                                            <ul className="space-y-2 text-sm">
                                                <li className="flex items-center gap-2 text-white/70">
                                                    <Clock className="w-3 h-3 text-[#00E0FF]" />
                                                    <span><strong>timestamp</strong> - Event time</span>
                                                </li>
                                                <li className="flex items-center gap-2 text-white/70">
                                                    <Server className="w-3 h-3 text-emerald-400" />
                                                    <span><strong>service</strong> - Service name</span>
                                                </li>
                                                <li className="flex items-center gap-2 text-white/70">
                                                    <AlertTriangle className="w-3 h-3 text-yellow-400" />
                                                    <span><strong>alert</strong> - Alert description</span>
                                                </li>
                                                <li className="flex items-center gap-2 text-white/70">
                                                    <Target className="w-3 h-3 text-red-400" />
                                                    <span><strong>severity</strong> - critical/warning/info</span>
                                                </li>
                                            </ul>
                                        </div>
                                        <div>
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-2">Optional</p>
                                            <ul className="space-y-1 text-sm text-white/50">
                                                <li>&#8226; host - Server/pod name</li>
                                                <li>&#8226; component - Sub-module</li>
                                                <li>&#8226; message - Details</li>
                                                <li>&#8226; <strong className="text-white/70">rule_name</strong> - Health rule name</li>
                                                <li>&#8226; <strong className="text-white/70">fingerprint</strong> - Alert fingerprint/hash</li>
                                            </ul>
                                        </div>
                                        <div className="p-3 bg-[#F5B841]/10 border border-[#F5B841]/30 rounded-lg">
                                            <p className="text-xs text-[#F5B841]">
                                                <Lightbulb className="w-3 h-3 inline mr-1" />
                                                Column names are flexible - the AI will auto-detect common variations
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Analysis Tab */}
                    <TabsContent value="analysis" className="mt-6">
                        {analyzing ? (
                            <Card className="bg-[#0a0a0a] border-[#00E0FF]/30">
                                <CardContent className="py-16 text-center">
                                    <Brain className="w-16 h-16 mx-auto text-[#00E0FF] animate-pulse mb-6" />
                                    <h3 className="text-xl font-bold text-white mb-2">AI Analysis in Progress</h3>
                                    <p className="text-white/60 mb-6">Analyzing patterns, detecting anomalies, and generating insights...</p>
                                    <div className="flex items-center justify-center gap-2">
                                        <div className="w-2 h-2 bg-[#00E0FF] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <div className="w-2 h-2 bg-[#00E0FF] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <div className="w-2 h-2 bg-[#00E0FF] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </CardContent>
                            </Card>
                        ) : analysisResult ? (
                            <div className="space-y-6">
                                {/* Summary Cards */}
                                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                                    <Card className={`bg-[#0a0a0a] border ${
                                        analysisResult.summary?.status === 'critical' ? 'border-red-500/30' :
                                        analysisResult.summary?.status === 'warning' ? 'border-yellow-500/30' :
                                        'border-emerald-500/30'
                                    }`}>
                                        <CardContent className="p-4">
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-1">Health Score</p>
                                            <p className={`text-3xl font-bold ${
                                                analysisResult.summary?.health_score >= 80 ? 'text-emerald-400' :
                                                analysisResult.summary?.health_score >= 50 ? 'text-yellow-400' :
                                                'text-red-400'
                                            }`}>
                                                {analysisResult.summary?.health_score || 0}%
                                            </p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-[#0a0a0a] border-white/10">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-1">Total Events</p>
                                            <p className="text-3xl font-bold text-white">{analysisResult.summary?.total_events?.toLocaleString() || 0}</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-[#0a0a0a] border-red-500/20">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-1">Critical</p>
                                            <p className="text-3xl font-bold text-red-400">{analysisResult.summary?.critical_count || 0}</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-[#0a0a0a] border-yellow-500/20">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-1">Warning</p>
                                            <p className="text-3xl font-bold text-yellow-400">{analysisResult.summary?.warning_count || 0}</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="bg-[#0a0a0a] border-white/10">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-white/50 uppercase tracking-wider mb-1">Services Affected</p>
                                            <p className="text-3xl font-bold text-[#00E0FF]">{analysisResult.summary?.services_affected || 0}</p>
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Export Toolbar */}
                                <Card className="bg-[#0a0a14] border-white/10">
                                    <CardContent className="p-4">
                                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                                            <div>
                                                <p className="text-sm font-medium text-white">Export Report</p>
                                                <p className="text-xs text-white/40">Download as Excel or PDF with executive summary, detailed alerts &amp; RCA</p>
                                            </div>
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="border-white/20 hover:bg-white/5 text-xs"
                                                    onClick={() => setShowBranding(!showBranding)}
                                                    data-testid="branding-toggle-btn"
                                                >
                                                    <Settings className="w-3.5 h-3.5 mr-1.5" />
                                                    Branding
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                                    onClick={() => handleExport('excel')}
                                                    disabled={!!exporting}
                                                    data-testid="export-excel-btn"
                                                >
                                                    {exporting === 'excel' ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5" />}
                                                    Export Excel
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    className="bg-red-600 hover:bg-red-700 text-white text-xs"
                                                    onClick={() => handleExport('pdf')}
                                                    disabled={!!exporting}
                                                    data-testid="export-pdf-btn"
                                                >
                                                    {exporting === 'pdf' ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <FileText className="w-3.5 h-3.5 mr-1.5" />}
                                                    Export PDF
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    className="bg-gradient-to-r from-[#F5B841] to-amber-500 hover:from-amber-500 hover:to-[#F5B841] text-black text-xs font-semibold shadow-lg shadow-amber-500/20"
                                                    onClick={() => handleExport('docx')}
                                                    disabled={!!exporting}
                                                    data-testid="export-docx-weekly-btn"
                                                    title="Generate Weekly Report in Fasah DOCX format"
                                                >
                                                    {exporting === 'docx' ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <FileText className="w-3.5 h-3.5 mr-1.5" />}
                                                    Weekly Report (DOCX)
                                                </Button>
                                            </div>
                                        </div>
                                        {showBranding && (
                                            <div className="mt-4 pt-4 border-t border-white/10 grid grid-cols-1 sm:grid-cols-4 gap-3">
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Company Name</Label>
                                                    <Input
                                                        value={branding.company}
                                                        onChange={(e) => setBranding({ ...branding, company: e.target.value })}
                                                        placeholder="e.g. Fasah"
                                                        className="bg-white/5 border-white/20 h-8 text-xs"
                                                        data-testid="branding-company-input"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Report Title</Label>
                                                    <Input
                                                        value={branding.title}
                                                        onChange={(e) => setBranding({ ...branding, title: e.target.value })}
                                                        placeholder="e.g. Weekly AIOps Report"
                                                        className="bg-white/5 border-white/20 h-8 text-xs"
                                                        data-testid="branding-title-input"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Period (DOCX only)</Label>
                                                    <Input
                                                        value={branding.period || ''}
                                                        onChange={(e) => setBranding({ ...branding, period: e.target.value })}
                                                        placeholder="12 Apr – 18 Apr 2026"
                                                        className="bg-white/5 border-white/20 h-8 text-xs"
                                                        data-testid="branding-period-input"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Report Footer</Label>
                                                    <Input
                                                        value={branding.footer}
                                                        onChange={(e) => setBranding({ ...branding, footer: e.target.value })}
                                                        placeholder="e.g. Confidential - Internal Use"
                                                        className="bg-white/5 border-white/20 h-8 text-xs"
                                                        data-testid="branding-footer-input"
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>

                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                    {/* AI Analysis */}
                                    <div className="lg:col-span-2">
                                        <Card className="bg-[#0a0a0a] border-[#00E0FF]/20">
                                            <CardHeader>
                                                <CardTitle className="text-white flex items-center gap-2">
                                                    <Brain className="w-5 h-5 text-[#00E0FF]" />
                                                    AI Root Cause Analysis
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent>
                                                <div className="prose prose-invert prose-sm max-w-none">
                                                    <div className="p-4 bg-black/40 rounded-lg border border-white/5 max-h-[500px] overflow-y-auto">
                                                    <div className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap prose prose-invert prose-sm">
                                                        <ReactMarkdown>
                                                            {analysisResult.ai_analysis || 'No analysis available'}
                                                        </ReactMarkdown>
                                                    </div>
                                                </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    </div>

                                    {/* Suggestions */}
                                    <div className="lg:col-span-1">
                                        <Card className="bg-[#0a0a0a] border-white/10">
                                            <CardHeader>
                                                <CardTitle className="text-white text-base flex items-center gap-2">
                                                    <Lightbulb className="w-4 h-4 text-[#F5B841]" />
                                                    AI Recommendations
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-3">
                                                {analysisResult.suggestions?.length > 0 ? (
                                                    analysisResult.suggestions.map((suggestion, idx) => (
                                                        <div 
                                                            key={idx}
                                                            className={`p-3 rounded-lg border ${
                                                                suggestion.priority === 'high' ? 'bg-red-500/10 border-red-500/30' :
                                                                suggestion.priority === 'medium' ? 'bg-yellow-500/10 border-yellow-500/30' :
                                                                'bg-white/5 border-white/10'
                                                            }`}
                                                        >
                                                            <div className="flex items-start gap-2">
                                                                <Badge className={`text-[10px] ${
                                                                    suggestion.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                                                                    suggestion.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                                                    'bg-white/10 text-white/60'
                                                                }`}>
                                                                    {suggestion.priority?.toUpperCase()}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-sm text-white font-medium mt-2">{suggestion.title}</p>
                                                            <p className="text-xs text-white/60 mt-1">{suggestion.description}</p>
                                                            <div className="mt-2 p-2 bg-black/30 rounded text-xs text-[#00E0FF]">
                                                                <Zap className="w-3 h-3 inline mr-1" />
                                                                {suggestion.action}
                                                            </div>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <p className="text-white/50 text-sm">No specific recommendations</p>
                                                )}
                                            </CardContent>
                                        </Card>
                                    </div>
                                </div>

                                {/* Charts */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Severity Distribution */}
                                    <Card className="bg-[#0a0a0a] border-white/10">
                                        <CardHeader>
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <PieChart className="w-4 h-4 text-[#F5B841]" />
                                                Severity Distribution
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="h-[250px]">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <RechartsPie>
                                                        <Pie
                                                            data={Object.entries(analysisResult.patterns?.severity_distribution || {}).map(([name, value]) => ({ name, value }))}
                                                            cx="50%"
                                                            cy="50%"
                                                            innerRadius={60}
                                                            outerRadius={100}
                                                            paddingAngle={5}
                                                            dataKey="value"
                                                            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                                        >
                                                            {Object.entries(analysisResult.patterns?.severity_distribution || {}).map(([name], index) => (
                                                                <Cell key={index} fill={severityColors[name] || COLORS[index % COLORS.length]} />
                                                            ))}
                                                        </Pie>
                                                        <Tooltip 
                                                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                                                            labelStyle={{ color: '#fff' }}
                                                        />
                                                    </RechartsPie>
                                                </ResponsiveContainer>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Top Alerts */}
                                    <Card className="bg-[#0a0a0a] border-white/10">
                                        <CardHeader>
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <BarChart3 className="w-4 h-4 text-[#00E0FF]" />
                                                Top Alerts by Frequency
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="h-[250px]">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart 
                                                        data={analysisResult.patterns?.alert_frequency?.slice(0, 5).map(item => ({
                                                            ...item,
                                                            alert: item.alert?.substring(0, 20) + (item.alert?.length > 20 ? '...' : '')
                                                        })) || []}
                                                        layout="vertical"
                                                    >
                                                        <XAxis type="number" stroke="#666" />
                                                        <YAxis type="category" dataKey="alert" width={100} stroke="#666" tick={{ fill: '#999', fontSize: 11 }} />
                                                        <Tooltip 
                                                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
                                                            labelStyle={{ color: '#fff' }}
                                                        />
                                                        <Bar dataKey="count" fill="#00E0FF" radius={[0, 4, 4, 0]} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Event Clusters */}
                                <Card className="bg-[#0a0a0a] border-white/10">
                                    <CardHeader>
                                        <CardTitle className="text-white flex items-center gap-2">
                                            <Activity className="w-5 h-5 text-emerald-400" />
                                            Event Clusters
                                        </CardTitle>
                                        <CardDescription>Related events grouped by service and alert type</CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                            {analysisResult.clusters?.slice(0, 6).map((cluster, idx) => (
                                                <div 
                                                    key={idx}
                                                    className={`p-4 rounded-lg border ${
                                                        cluster.severity === 'critical' ? 'bg-red-500/5 border-red-500/30' :
                                                        cluster.severity === 'warning' ? 'bg-yellow-500/5 border-yellow-500/30' :
                                                        'bg-white/5 border-white/10'
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between mb-2">
                                                        <Badge className={`${
                                                            cluster.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                                            cluster.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                                                            'bg-cyan-500/20 text-cyan-400'
                                                        }`}>
                                                            {cluster.severity}
                                                        </Badge>
                                                        <span className="text-2xl font-bold text-white">{cluster.count}</span>
                                                    </div>
                                                    <p className="text-sm text-white font-medium truncate">{cluster.service}</p>
                                                    <p className="text-xs text-white/50 truncate mt-1">{cluster.alert_type}</p>
                                                    {cluster.hosts?.length > 0 && (
                                                        <p className="text-xs text-white/40 mt-2">
                                                            Hosts: {cluster.hosts.slice(0, 2).join(', ')}
                                                            {cluster.hosts.length > 2 && ` +${cluster.hosts.length - 2} more`}
                                                        </p>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        ) : (
                            <Card className="bg-[#0a0a0a] border-white/10">
                                <CardContent className="py-16 text-center">
                                    <Brain className="w-16 h-16 mx-auto text-white/20 mb-6" />
                                    <h3 className="text-xl font-medium text-white/60 mb-2">No Analysis Yet</h3>
                                    <p className="text-white/40 mb-6">Upload an event file to start AI analysis</p>
                                    <Button
                                        onClick={() => setActiveTab('upload')}
                                        className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black font-bold"
                                    >
                                        <Upload className="w-4 h-4 mr-2" />
                                        Upload Events
                                    </Button>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* History Tab */}
                    <TabsContent value="history" className="mt-6">
                        <Card className="bg-[#0a0a0a] border-white/10">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle className="text-white">Analysis History</CardTitle>
                                    <CardDescription>Previously uploaded and analyzed event files</CardDescription>
                                </div>
                                <Button variant="ghost" size="sm" onClick={fetchUploads}>
                                    <RefreshCw className="w-4 h-4" />
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {uploads.length === 0 ? (
                                    <div className="text-center py-12 text-white/50">
                                        <FileSpreadsheet className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>No uploads yet</p>
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full">
                                            <thead>
                                                <tr className="border-b border-white/10 text-left">
                                                    <th className="pb-3 text-xs text-white/50 font-medium">Filename</th>
                                                    <th className="pb-3 text-xs text-white/50 font-medium">Events</th>
                                                    <th className="pb-3 text-xs text-white/50 font-medium">Status</th>
                                                    <th className="pb-3 text-xs text-white/50 font-medium">Uploaded</th>
                                                    <th className="pb-3 text-xs text-white/50 font-medium">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {uploads.map((upload) => (
                                                    <tr key={upload.id} className="border-b border-white/5">
                                                        <td className="py-3 text-sm text-white">{upload.filename}</td>
                                                        <td className="py-3 text-sm text-white/70">{upload.total_events?.toLocaleString()}</td>
                                                        <td className="py-3">
                                                            <Badge className={`${
                                                                upload.status === 'analyzed' ? 'bg-emerald-500/20 text-emerald-400' :
                                                                'bg-yellow-500/20 text-yellow-400'
                                                            }`}>
                                                                {upload.status}
                                                            </Badge>
                                                        </td>
                                                        <td className="py-3 text-sm text-white/50">
                                                            {new Date(upload.uploaded_at).toLocaleDateString()}
                                                        </td>
                                                        <td className="py-3">
                                                            <div className="flex items-center gap-2">
                                                                {upload.status === 'analyzed' ? (
                                                                    <>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => handleViewAnalysis(upload.analysis_id)}
                                                                        className="text-[#00E0FF] hover:bg-[#00E0FF]/10"
                                                                    >
                                                                        <Eye className="w-4 h-4 mr-1" />
                                                                        View
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => { setCurrentAnalysisId(upload.analysis_id); handleExport('excel'); }}
                                                                        className="text-emerald-400 hover:bg-emerald-500/10"
                                                                        data-testid={`export-excel-${upload.id}`}
                                                                    >
                                                                        <FileSpreadsheet className="w-4 h-4" />
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => { setCurrentAnalysisId(upload.analysis_id); handleExport('pdf'); }}
                                                                        className="text-red-400 hover:bg-red-400/10"
                                                                        data-testid={`export-pdf-${upload.id}`}
                                                                    >
                                                                        <FileText className="w-4 h-4" />
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => { setCurrentAnalysisId(upload.analysis_id); handleExport('docx'); }}
                                                                        className="text-[#F5B841] hover:bg-[#F5B841]/10"
                                                                        title="Weekly Report DOCX (Fasah format)"
                                                                        data-testid={`export-docx-${upload.id}`}
                                                                    >
                                                                        <FileText className="w-4 h-4" />
                                                                    </Button>
                                                                    </>
                                                                ) : (
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => handleAnalyze(upload.id)}
                                                                        className="text-[#F5B841] hover:bg-[#F5B841]/10"
                                                                    >
                                                                        <Brain className="w-4 h-4 mr-1" />
                                                                        Analyze
                                                                    </Button>
                                                                )}
                                                                <Button
                                                                    size="sm"
                                                                    variant="ghost"
                                                                    onClick={() => handleDeleteUpload(upload.id)}
                                                                    className="text-red-400 hover:bg-red-500/10"
                                                                >
                                                                    <Trash2 className="w-4 h-4" />
                                                                </Button>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                    
                    {/* Webhooks Tab */}
                    <TabsContent value="webhooks" className="mt-6">
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Create Webhook */}
                            <Card className="bg-[#0a0a0a] border-white/10">
                                <CardHeader>
                                    <CardTitle className="text-white flex items-center gap-2">
                                        <Plus className="w-5 h-5 text-[#F5B841]" />
                                        Create Webhook
                                    </CardTitle>
                                    <CardDescription>
                                        Set up automated alert ingestion from monitoring tools
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="webhook-name">Webhook Name</Label>
                                        <Input
                                            id="webhook-name"
                                            placeholder="Production Alerts"
                                            value={newWebhook.name}
                                            onChange={(e) => setNewWebhook({ ...newWebhook, name: e.target.value })}
                                            className="bg-white/5 border-white/20"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="source-type">Source Type</Label>
                                        <select
                                            id="source-type"
                                            value={newWebhook.source_type}
                                            onChange={(e) => setNewWebhook({ ...newWebhook, source_type: e.target.value })}
                                            className="w-full h-10 px-3 rounded-md bg-white/5 border border-white/20 text-white text-sm"
                                        >
                                            <option value="custom">Custom</option>
                                            <option value="prometheus">Prometheus</option>
                                            <option value="grafana">Grafana</option>
                                            <option value="appdynamics">AppDynamics</option>
                                            <option value="elasticsearch">Elasticsearch</option>
                                            <option value="datadog">Datadog</option>
                                            <option value="pagerduty">PagerDuty</option>
                                        </select>
                                    </div>
                                    <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                                        <div>
                                            <p className="text-sm text-white">Auto-Analyze</p>
                                            <p className="text-xs text-white/50">Automatically analyze after threshold</p>
                                        </div>
                                        <Switch
                                            checked={newWebhook.auto_analyze}
                                            onCheckedChange={(checked) => setNewWebhook({ ...newWebhook, auto_analyze: checked })}
                                        />
                                    </div>
                                    {newWebhook.auto_analyze && (
                                        <div className="space-y-2">
                                            <Label htmlFor="threshold">Analysis Threshold</Label>
                                            <Input
                                                id="threshold"
                                                type="number"
                                                min="5"
                                                max="100"
                                                value={newWebhook.analyze_threshold}
                                                onChange={(e) => setNewWebhook({ ...newWebhook, analyze_threshold: parseInt(e.target.value) || 10 })}
                                                className="bg-white/5 border-white/20"
                                            />
                                            <p className="text-xs text-white/50">Auto-analyze after this many alerts</p>
                                        </div>
                                    )}
                                    <Button
                                        className="w-full bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-bold"
                                        onClick={handleCreateWebhook}
                                        disabled={loading || !newWebhook.name}
                                    >
                                        <Plus className="w-4 h-4 mr-2" />
                                        Create Webhook
                                    </Button>
                                </CardContent>
                            </Card>
                            
                            {/* Webhooks List */}
                            <div className="lg:col-span-2">
                                <Card className="bg-[#0a0a0a] border-white/10">
                                    <CardHeader className="flex flex-row items-center justify-between">
                                        <div>
                                            <CardTitle className="text-white">Active Webhooks</CardTitle>
                                            <CardDescription>Endpoints for receiving alerts from monitoring tools</CardDescription>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={fetchWebhooks}>
                                            <RefreshCw className="w-4 h-4" />
                                        </Button>
                                    </CardHeader>
                                    <CardContent>
                                        {webhooks.length === 0 ? (
                                            <div className="text-center py-12 text-white/50">
                                                <Webhook className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                                <p>No webhooks configured</p>
                                                <p className="text-sm mt-2">Create a webhook to start receiving alerts</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-4">
                                                {webhooks.map((webhook) => (
                                                    <div 
                                                        key={webhook.id}
                                                        className="p-4 bg-white/5 border border-white/10 rounded-lg"
                                                    >
                                                        <div className="flex items-start justify-between mb-3">
                                                            <div>
                                                                <div className="flex items-center gap-2">
                                                                    <h4 className="text-white font-medium">{webhook.name}</h4>
                                                                    <Badge className={webhook.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}>
                                                                        {webhook.enabled ? 'Active' : 'Disabled'}
                                                                    </Badge>
                                                                    <Badge className="bg-white/10 text-white/60">{webhook.source_type}</Badge>
                                                                </div>
                                                                <p className="text-xs text-white/50 mt-1">
                                                                    {webhook.alert_count || 0} alerts received
                                                                    {webhook.last_alert_at && ` • Last: ${new Date(webhook.last_alert_at).toLocaleString()}`}
                                                                </p>
                                                            </div>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => handleDeleteWebhook(webhook.id)}
                                                                className="text-red-400 hover:bg-red-500/10"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </Button>
                                                        </div>
                                                        <div className="flex items-center gap-2 p-2 bg-black/40 rounded border border-white/10">
                                                            <code className="flex-1 text-xs text-[#00E0FF] font-mono truncate">
                                                                {API_URL}/api/ingest/webhook/{webhook.id}
                                                            </code>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => copyToClipboard(`${API_URL}/api/ingest/webhook/${webhook.id}`)}
                                                                className="shrink-0"
                                                            >
                                                                <Copy className="w-4 h-4" />
                                                            </Button>
                                                        </div>
                                                        {webhook.auto_analyze && (
                                                            <p className="text-xs text-[#F5B841] mt-2">
                                                                <Zap className="w-3 h-3 inline mr-1" />
                                                                Auto-analyzes after {webhook.analyze_threshold} alerts
                                                            </p>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                                
                                {/* Ingestion Stats */}
                                {ingestionStats && (
                                    <Card className="bg-[#0a0a0a] border-white/10 mt-6">
                                        <CardHeader>
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <BarChart3 className="w-4 h-4 text-[#00E0FF]" />
                                                Ingestion Statistics
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="grid grid-cols-3 gap-4">
                                                <div className="text-center p-3 bg-white/5 rounded-lg">
                                                    <p className="text-2xl font-bold text-white">{ingestionStats.total_alerts?.toLocaleString() || 0}</p>
                                                    <p className="text-xs text-white/50">Total Alerts</p>
                                                </div>
                                                <div className="text-center p-3 bg-emerald-500/10 rounded-lg">
                                                    <p className="text-2xl font-bold text-emerald-400">{ingestionStats.analyzed?.toLocaleString() || 0}</p>
                                                    <p className="text-xs text-white/50">Analyzed</p>
                                                </div>
                                                <div className="text-center p-3 bg-yellow-500/10 rounded-lg">
                                                    <p className="text-2xl font-bold text-yellow-400">{ingestionStats.unanalyzed?.toLocaleString() || 0}</p>
                                                    <p className="text-xs text-white/50">Pending</p>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}
                            </div>
                        </div>
                    </TabsContent>
                    
                    {/* Knowledge Base Tab */}
                    <TabsContent value="knowledge" className="mt-6">
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Stats */}
                            <Card className="bg-[#0a0a0a] border-emerald-500/20">
                                <CardHeader>
                                    <CardTitle className="text-white flex items-center gap-2">
                                        <GraduationCap className="w-5 h-5 text-emerald-400" />
                                        AI Learning Stats
                                    </CardTitle>
                                    <CardDescription>
                                        Self-learning incident knowledge base
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {knowledgeStats ? (
                                        <>
                                            <div className="text-center p-4 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                                                <p className="text-4xl font-bold text-emerald-400">{knowledgeStats.learning_score || 0}%</p>
                                                <p className="text-sm text-white/60 mt-1">Learning Score</p>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3">
                                                <div className="p-3 bg-white/5 rounded-lg text-center">
                                                    <p className="text-xl font-bold text-white">{knowledgeStats.total_patterns || 0}</p>
                                                    <p className="text-xs text-white/50">Patterns Learned</p>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-lg text-center">
                                                    <p className="text-xl font-bold text-[#00E0FF]">{knowledgeStats.total_occurrences || 0}</p>
                                                    <p className="text-xs text-white/50">Total Occurrences</p>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-lg text-center">
                                                    <p className="text-xl font-bold text-emerald-400">{knowledgeStats.total_successes || 0}</p>
                                                    <p className="text-xs text-white/50">Successful Fixes</p>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-lg text-center">
                                                    <p className="text-xl font-bold text-[#F5B841]">{knowledgeStats.avg_confidence || 0}%</p>
                                                    <p className="text-xs text-white/50">Avg Confidence</p>
                                                </div>
                                            </div>
                                            <div className="p-3 bg-[#F5B841]/10 border border-[#F5B841]/30 rounded-lg">
                                                <p className="text-xs text-[#F5B841]">
                                                    <Lightbulb className="w-3 h-3 inline mr-1" />
                                                    The AI learns from every resolved incident. Record your resolutions to improve future suggestions!
                                                </p>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-center py-8 text-white/50">
                                            <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                            <p>Loading knowledge base stats...</p>
                                        </div>
                                    )}
                                    <Button
                                        variant="outline"
                                        className="w-full border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                                        onClick={() => { fetchKnowledgePatterns(); fetchKnowledgeStats(); }}
                                    >
                                        <RefreshCw className="w-4 h-4 mr-2" />
                                        Refresh Stats
                                    </Button>
                                </CardContent>
                            </Card>
                            
                            {/* Learned Patterns */}
                            <div className="lg:col-span-2">
                                <Card className="bg-[#0a0a0a] border-white/10">
                                    <CardHeader className="flex flex-row items-center justify-between">
                                        <div>
                                            <CardTitle className="text-white">Learned Incident Patterns</CardTitle>
                                            <CardDescription>Patterns the AI has learned from past incidents</CardDescription>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={fetchKnowledgePatterns}>
                                            <RefreshCw className="w-4 h-4" />
                                        </Button>
                                    </CardHeader>
                                    <CardContent>
                                        {knowledgePatterns.length === 0 ? (
                                            <div className="text-center py-12 text-white/50">
                                                <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                                <p>No patterns learned yet</p>
                                                <p className="text-sm mt-2">Analyze events and record resolutions to teach the AI</p>
                                            </div>
                                        ) : (
                                            <div className="space-y-3">
                                                {knowledgePatterns.map((pattern) => (
                                                    <div 
                                                        key={pattern.id}
                                                        className="p-4 bg-white/5 border border-white/10 rounded-lg hover:border-emerald-500/30 transition-colors"
                                                    >
                                                        <div className="flex items-start justify-between mb-2">
                                                            <div className="flex items-center gap-2">
                                                                <Badge className={`${
                                                                    pattern.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                                                    pattern.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' :
                                                                    'bg-cyan-500/20 text-cyan-400'
                                                                }`}>
                                                                    {pattern.severity}
                                                                </Badge>
                                                                <span className="text-sm text-white/50">
                                                                    {pattern.occurrence_count} occurrences
                                                                </span>
                                                                {pattern.success_count > 0 && (
                                                                    <span className="text-sm text-emerald-400">
                                                                        • {pattern.success_count} successful fixes
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <div className="flex items-center gap-1 px-2 py-1 bg-emerald-500/10 rounded">
                                                                <Percent className="w-3 h-3 text-emerald-400" />
                                                                <span className="text-sm font-mono text-emerald-400">
                                                                    {Math.round((pattern.confidence_score || 0) * 100)}%
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <h4 className="text-white font-medium mb-1">{pattern.root_cause}</h4>
                                                        <p className="text-sm text-white/60 mb-2">{pattern.resolution}</p>
                                                        <div className="flex flex-wrap gap-1">
                                                            {pattern.alerts?.slice(0, 3).map((alert, idx) => (
                                                                <Badge key={idx} variant="outline" className="text-xs border-white/20 text-white/50">
                                                                    {alert.substring(0, 30)}...
                                                                </Badge>
                                                            ))}
                                                            {pattern.alerts?.length > 3 && (
                                                                <Badge variant="outline" className="text-xs border-white/20 text-white/50">
                                                                    +{pattern.alerts.length - 3} more
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Schedules Tab */}
                    <TabsContent value="schedules" className="mt-6">
                        <div className="space-y-6">
                            <Card className="bg-[#0a0a0a] border-white/10">
                                <CardHeader className="flex flex-row items-center justify-between">
                                    <div>
                                        <CardTitle className="text-white flex items-center gap-2">
                                            <CalendarClock className="w-5 h-5 text-purple-400" />
                                            Automated Report Scheduling
                                        </CardTitle>
                                        <CardDescription>Configure weekly or monthly reports sent automatically to recipients</CardDescription>
                                    </div>
                                    <div className="flex gap-2">
                                        <Button variant="ghost" size="sm" onClick={fetchSchedules}><RefreshCw className="w-4 h-4" /></Button>
                                        <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => setShowScheduleForm(!showScheduleForm)} data-testid="new-schedule-btn">
                                            <Plus className="w-4 h-4 mr-1" /> New Schedule
                                        </Button>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    {showScheduleForm && (
                                        <div className="mb-6 p-4 bg-white/5 rounded-lg border border-purple-500/20 space-y-4" data-testid="schedule-form">
                                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Schedule Name</Label>
                                                    <Input value={scheduleForm.name} onChange={e => setScheduleForm({...scheduleForm, name: e.target.value})} placeholder="Weekly Executive Report" className="bg-white/5 border-white/20 h-8 text-xs" data-testid="schedule-name-input" />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Frequency</Label>
                                                    <select value={scheduleForm.frequency} onChange={e => setScheduleForm({...scheduleForm, frequency: e.target.value})} className="w-full h-8 rounded-md bg-white/5 border border-white/20 text-xs text-white px-2" data-testid="schedule-freq-select">
                                                        <option value="daily">Daily</option>
                                                        <option value="weekly">Weekly</option>
                                                        <option value="monthly">Monthly</option>
                                                    </select>
                                                </div>
                                                {scheduleForm.frequency === 'weekly' && (
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-white/50">Day of Week</Label>
                                                        <select value={scheduleForm.day_of_week} onChange={e => setScheduleForm({...scheduleForm, day_of_week: e.target.value})} className="w-full h-8 rounded-md bg-white/5 border border-white/20 text-xs text-white px-2">
                                                            {['mon','tue','wed','thu','fri','sat','sun'].map(d => <option key={d} value={d}>{d.charAt(0).toUpperCase()+d.slice(1)}</option>)}
                                                        </select>
                                                    </div>
                                                )}
                                                {scheduleForm.frequency === 'monthly' && (
                                                    <div className="space-y-1">
                                                        <Label className="text-xs text-white/50">Day of Month</Label>
                                                        <Input type="number" min={1} max={28} value={scheduleForm.day_of_month} onChange={e => setScheduleForm({...scheduleForm, day_of_month: parseInt(e.target.value)||1})} className="bg-white/5 border-white/20 h-8 text-xs" />
                                                    </div>
                                                )}
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Hour (UTC)</Label>
                                                    <Input type="number" min={0} max={23} value={scheduleForm.hour} onChange={e => setScheduleForm({...scheduleForm, hour: parseInt(e.target.value)||0})} className="bg-white/5 border-white/20 h-8 text-xs" />
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Format</Label>
                                                    <select value={scheduleForm.format} onChange={e => setScheduleForm({...scheduleForm, format: e.target.value})} className="w-full h-8 rounded-md bg-white/5 border border-white/20 text-xs text-white px-2" data-testid="schedule-format-select">
                                                        <option value="pdf">PDF Report</option>
                                                        <option value="excel">Excel Workbook</option>
                                                    </select>
                                                </div>
                                                <div className="space-y-1 sm:col-span-2">
                                                    <Label className="text-xs text-white/50">Recipients (comma-separated emails)</Label>
                                                    <Input value={scheduleForm.recipients} onChange={e => setScheduleForm({...scheduleForm, recipients: e.target.value})} placeholder="cto@company.com, noc@company.com" className="bg-white/5 border-white/20 h-8 text-xs" data-testid="schedule-recipients-input" />
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Company Name</Label>
                                                    <Input value={scheduleForm.branding.company} onChange={e => setScheduleForm({...scheduleForm, branding: {...scheduleForm.branding, company: e.target.value}})} placeholder="Saudi Trading Corp" className="bg-white/5 border-white/20 h-8 text-xs" />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Report Title</Label>
                                                    <Input value={scheduleForm.branding.title} onChange={e => setScheduleForm({...scheduleForm, branding: {...scheduleForm.branding, title: e.target.value}})} placeholder="Weekly AIOps Report" className="bg-white/5 border-white/20 h-8 text-xs" />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label className="text-xs text-white/50">Email Subject</Label>
                                                    <Input value={scheduleForm.email_subject} onChange={e => setScheduleForm({...scheduleForm, email_subject: e.target.value})} placeholder="FalconOps AI - Scheduled Report" className="bg-white/5 border-white/20 h-8 text-xs" />
                                                </div>
                                            </div>
                                            <div className="flex gap-2 justify-end">
                                                <Button variant="ghost" size="sm" onClick={() => setShowScheduleForm(false)}>Cancel</Button>
                                                <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={handleCreateSchedule} disabled={loading} data-testid="save-schedule-btn">
                                                    {loading ? <RefreshCw className="w-3.5 h-3.5 mr-1 animate-spin" /> : <CalendarClock className="w-3.5 h-3.5 mr-1" />}
                                                    Create Schedule
                                                </Button>
                                            </div>
                                        </div>
                                    )}

                                    {schedules.length === 0 ? (
                                        <div className="text-center py-12 text-white/50">
                                            <CalendarClock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                            <p className="mb-2">No schedules configured</p>
                                            <p className="text-xs text-white/30">Create a schedule to automatically send reports</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            {schedules.map(sch => (
                                                <div key={sch.id} className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-white/10 hover:border-white/20 transition-colors" data-testid={`schedule-${sch.id}`}>
                                                    <div className="flex items-center gap-4">
                                                        <div className={`w-10 h-10 rounded-lg ${sch.enabled ? 'bg-purple-500/20' : 'bg-white/5'} flex items-center justify-center`}>
                                                            <CalendarClock className={`w-5 h-5 ${sch.enabled ? 'text-purple-400' : 'text-white/30'}`} />
                                                        </div>
                                                        <div>
                                                            <p className="text-sm font-medium text-white">{sch.name}</p>
                                                            <div className="flex items-center gap-2 mt-1">
                                                                <Badge className="text-[9px] px-1.5 py-0 bg-purple-500/20 text-purple-400 border-0">{sch.frequency}</Badge>
                                                                <Badge className="text-[9px] px-1.5 py-0 bg-white/10 text-white/50 border-0">{sch.format?.toUpperCase()}</Badge>
                                                                <span className="text-[10px] text-white/30">{sch.recipients?.length || 0} recipient(s)</span>
                                                                {sch.last_run && <span className="text-[10px] text-white/30">Last: {new Date(sch.last_run).toLocaleDateString()}</span>}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <Button size="sm" variant="ghost" onClick={() => handleRunNow(sch.id)} className="text-purple-400 hover:bg-purple-500/10" data-testid={`run-schedule-${sch.id}`}>
                                                            <Play className="w-4 h-4" />
                                                        </Button>
                                                        <Switch checked={sch.enabled} onCheckedChange={() => handleToggleSchedule(sch.id, sch.enabled)} data-testid={`toggle-schedule-${sch.id}`} />
                                                        <Button size="sm" variant="ghost" onClick={() => handleDeleteSchedule(sch.id)} className="text-red-400 hover:bg-red-500/10">
                                                            <Trash2 className="w-4 h-4" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    </TabsContent>

                    {/* ════════ RULE ANALYTICS TAB ════════ */}
                    <TabsContent value="rule-analytics" className="mt-6" data-testid="rule-analytics-content">
                        {ruleAnalyticsLoading ? (
                            <Card className="bg-[#0a0a0a] border-white/10">
                                <CardContent className="py-16 text-center">
                                    <RefreshCw className="w-12 h-12 mx-auto text-red-400 animate-spin mb-4" />
                                    <p className="text-white/60">Loading health rule analytics...</p>
                                </CardContent>
                            </Card>
                        ) : ruleAnalytics ? (
                            <div className="space-y-6">
                                {/* Summary Cards */}
                                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                                    {[
                                        { label: 'Total Violations', value: ruleAnalytics.summary?.total_violations, color: '#F5B841', border: 'border-[#F5B841]/20' },
                                        { label: 'Active', value: ruleAnalytics.summary?.active_violations, color: '#EF4444', border: 'border-red-500/20' },
                                        { label: 'Resolved', value: ruleAnalytics.summary?.resolved_violations, color: '#10B981', border: 'border-emerald-500/20' },
                                        { label: 'Critical', value: ruleAnalytics.summary?.total_critical, color: '#EF4444', border: 'border-red-500/20' },
                                        { label: 'Warning', value: ruleAnalytics.summary?.total_warning, color: '#F59E0B', border: 'border-yellow-500/20' },
                                        { label: 'Resolution Rate', value: `${ruleAnalytics.summary?.resolution_rate || 0}%`, color: '#10B981', border: 'border-emerald-500/20' },
                                    ].map(s => (
                                        <Card key={s.label} className={`bg-[#0a0a0a] ${s.border} border`}>
                                            <CardContent className="p-3.5">
                                                <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">{s.label}</p>
                                                <p className="text-2xl font-bold" style={{ color: s.color }}>{s.value ?? 0}</p>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>

                                {/* Charts Row */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                                    {/* Stacked Bar: Alerts per Rule */}
                                    <Card className="bg-[#0a0a0a] border-white/10" data-testid="rule-chart-bar">
                                        <CardHeader className="pb-2">
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <BarChart3 className="w-4 h-4 text-red-400" />
                                                Alerts per Health Rule
                                            </CardTitle>
                                            <CardDescription>Critical vs Warning vs Info per rule</CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            {ruleAnalytics.chart_data?.length > 0 ? (
                                                <div className="h-[300px]">
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <BarChart data={ruleAnalytics.chart_data} layout="vertical" margin={{ left: 10 }}>
                                                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                                                            <XAxis type="number" stroke="#666" tick={{ fill: '#999', fontSize: 11 }} />
                                                            <YAxis type="category" dataKey="rule_name" width={120} stroke="#666" tick={{ fill: '#ccc', fontSize: 11 }} />
                                                            <Tooltip
                                                                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '8px' }}
                                                                labelStyle={{ color: '#fff', fontWeight: 600 }}
                                                            />
                                                            <Legend />
                                                            <Bar dataKey="critical" stackId="a" fill="#EF4444" name="Critical" radius={[0, 0, 0, 0]} />
                                                            <Bar dataKey="warning" stackId="a" fill="#F59E0B" name="Warning" radius={[0, 0, 0, 0]} />
                                                            <Bar dataKey="info" stackId="a" fill="#06b6d4" name="Info" radius={[0, 4, 4, 0]} />
                                                        </BarChart>
                                                    </ResponsiveContainer>
                                                </div>
                                            ) : (
                                                <p className="text-center py-12 text-white/30">No violation data to chart</p>
                                            )}
                                        </CardContent>
                                    </Card>

                                    {/* Severity Pie */}
                                    <Card className="bg-[#0a0a0a] border-white/10" data-testid="rule-chart-pie">
                                        <CardHeader className="pb-2">
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <PieChart className="w-4 h-4 text-[#F5B841]" />
                                                Severity Distribution
                                            </CardTitle>
                                            <CardDescription>Overall severity breakdown across all rules</CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            {ruleAnalytics.severity_distribution ? (
                                                <div className="h-[300px]">
                                                    <ResponsiveContainer width="100%" height="100%">
                                                        <RechartsPie>
                                                            <Pie
                                                                data={Object.entries(ruleAnalytics.severity_distribution).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value }))}
                                                                cx="50%" cy="50%" innerRadius={65} outerRadius={110} paddingAngle={4} dataKey="value"
                                                                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                                                            >
                                                                <Cell fill="#EF4444" />
                                                                <Cell fill="#F59E0B" />
                                                                <Cell fill="#06b6d4" />
                                                            </Pie>
                                                            <Tooltip contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333', borderRadius: '8px' }} />
                                                        </RechartsPie>
                                                    </ResponsiveContainer>
                                                </div>
                                            ) : (
                                                <p className="text-center py-12 text-white/30">No data</p>
                                            )}
                                        </CardContent>
                                    </Card>
                                </div>

                                {/* Per-Rule Detail Table */}
                                <Card className="bg-[#0a0a0a] border-white/10" data-testid="rule-analytics-table">
                                    <CardHeader className="pb-2 flex flex-row items-center justify-between">
                                        <div>
                                            <CardTitle className="text-white text-base flex items-center gap-2">
                                                <Shield className="w-4 h-4 text-red-400" />
                                                Per-Rule Breakdown
                                            </CardTitle>
                                            <CardDescription>Distinct alerts per health rule with severity split and fingerprints</CardDescription>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={fetchRuleAnalytics} data-testid="refresh-rule-analytics">
                                            <RefreshCw className="w-4 h-4" />
                                        </Button>
                                    </CardHeader>
                                    <CardContent>
                                        {ruleAnalytics.rule_analytics?.length > 0 ? (
                                            <div className="space-y-3">
                                                {ruleAnalytics.rule_analytics.map((ra) => (
                                                    <div key={ra.rule_id}
                                                        className={`rounded-xl border transition-all cursor-pointer ${
                                                            selectedRule === ra.rule_id
                                                                ? 'border-red-500/40 bg-red-500/[0.04]'
                                                                : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                                                        }`}
                                                        onClick={() => setSelectedRule(selectedRule === ra.rule_id ? null : ra.rule_id)}
                                                        data-testid={`rule-row-${ra.rule_id}`}
                                                    >
                                                        {/* Main Row */}
                                                        <div className="p-4 flex items-center justify-between">
                                                            <div className="flex items-center gap-4 flex-1 min-w-0">
                                                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                                                                    ra.active_count > 0 ? 'bg-red-500/15' : 'bg-emerald-500/15'
                                                                }`}>
                                                                    <Shield className={`w-5 h-5 ${ra.active_count > 0 ? 'text-red-400' : 'text-emerald-400'}`} />
                                                                </div>
                                                                <div className="min-w-0">
                                                                    <div className="flex items-center gap-2 flex-wrap">
                                                                        <h4 className="text-sm font-medium text-white truncate">{ra.rule_name}</h4>
                                                                        <Badge variant="outline" className={`text-[9px] px-1.5 py-0 ${
                                                                            ra.rule_severity === 'critical' ? 'border-red-500/30 text-red-400' : 'border-yellow-500/30 text-yellow-400'
                                                                        }`}>
                                                                            {ra.rule_severity}
                                                                        </Badge>
                                                                        <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-white/15 text-white/40">
                                                                            {ra.component_type}
                                                                        </Badge>
                                                                    </div>
                                                                    <p className="text-[11px] text-white/35 mt-0.5">
                                                                        {ra.metric} {ra.operator} {ra.threshold} &bull; {ra.distinct_sources} source(s) &bull; Resolution: {ra.resolution_rate}%
                                                                    </p>
                                                                </div>
                                                            </div>
                                                            <div className="flex items-center gap-4 shrink-0">
                                                                <div className="text-center">
                                                                    <div className="text-lg font-bold text-white">{ra.total_violations}</div>
                                                                    <div className="text-[9px] text-white/30">Total</div>
                                                                </div>
                                                                <div className="text-center">
                                                                    <div className="text-lg font-bold text-red-400">{ra.critical_count}</div>
                                                                    <div className="text-[9px] text-white/30">Critical</div>
                                                                </div>
                                                                <div className="text-center">
                                                                    <div className="text-lg font-bold text-yellow-400">{ra.warning_count}</div>
                                                                    <div className="text-[9px] text-white/30">Warning</div>
                                                                </div>
                                                                <div className="text-center">
                                                                    <div className="text-lg font-bold text-emerald-400">{ra.resolved_count}</div>
                                                                    <div className="text-[9px] text-white/30">Resolved</div>
                                                                </div>
                                                                <ChevronRight className={`w-4 h-4 text-white/20 transition-transform ${selectedRule === ra.rule_id ? 'rotate-90' : ''}`} />
                                                            </div>
                                                        </div>

                                                        {/* Expanded Detail */}
                                                        {selectedRule === ra.rule_id && (
                                                            <div className="px-4 pb-4 pt-0 border-t border-white/5">
                                                                <div className="mt-3 space-y-3">
                                                                    {/* Fingerprints Table */}
                                                                    <div>
                                                                        <h5 className="text-xs text-white/50 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                                            <Hash className="w-3 h-3" /> Alert Fingerprints
                                                                        </h5>
                                                                        <div className="overflow-x-auto">
                                                                            <table className="w-full text-xs">
                                                                                <thead>
                                                                                    <tr className="border-b border-white/10">
                                                                                        <th className="pb-2 text-left text-white/40 font-medium">Fingerprint</th>
                                                                                        <th className="pb-2 text-left text-white/40 font-medium">Source</th>
                                                                                        <th className="pb-2 text-left text-white/40 font-medium">Severity</th>
                                                                                        <th className="pb-2 text-left text-white/40 font-medium">State</th>
                                                                                        <th className="pb-2 text-right text-white/40 font-medium">Value</th>
                                                                                        <th className="pb-2 text-right text-white/40 font-medium">Time</th>
                                                                                    </tr>
                                                                                </thead>
                                                                                <tbody>
                                                                                    {ra.fingerprints?.slice(0, 10).map((fp, i) => (
                                                                                        <tr key={i} className="border-b border-white/5">
                                                                                            <td className="py-2 font-mono text-[#00E0FF]/80" data-testid={`fingerprint-${fp.fingerprint}`}>
                                                                                                <Fingerprint className="w-3 h-3 inline mr-1 opacity-50" />
                                                                                                {fp.fingerprint}
                                                                                            </td>
                                                                                            <td className="py-2 text-white/60">{fp.source_name || fp.source_id || '—'}</td>
                                                                                            <td className="py-2">
                                                                                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                                                                                    fp.severity === 'critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                                                                                                }`}>{fp.severity}</span>
                                                                                            </td>
                                                                                            <td className="py-2">
                                                                                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                                                                                    fp.state === 'resolved' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                                                                                                }`}>{fp.state}</span>
                                                                                            </td>
                                                                                            <td className="py-2 text-right text-white/70 font-mono">{fp.value}</td>
                                                                                            <td className="py-2 text-right text-white/40">
                                                                                                {fp.timestamp ? new Date(fp.timestamp).toLocaleString() : '—'}
                                                                                            </td>
                                                                                        </tr>
                                                                                    ))}
                                                                                </tbody>
                                                                            </table>
                                                                        </div>
                                                                        {ra.fingerprints?.length > 10 && (
                                                                            <p className="text-[10px] text-white/25 mt-2">Showing 10 of {ra.fingerprints.length} fingerprints</p>
                                                                        )}
                                                                    </div>

                                                                    {/* Sources */}
                                                                    {ra.sources?.length > 0 && (
                                                                        <div>
                                                                            <h5 className="text-xs text-white/50 uppercase tracking-wider mb-1.5">Affected Sources</h5>
                                                                            <div className="flex flex-wrap gap-1.5">
                                                                                {ra.sources.map((src, i) => (
                                                                                    <Badge key={i} variant="outline" className="text-[10px] border-white/15 text-white/50">{src}</Badge>
                                                                                ))}
                                                                            </div>
                                                                        </div>
                                                                    )}

                                                                    {/* Time range */}
                                                                    <div className="flex items-center gap-4 text-[10px] text-white/30">
                                                                        <span>First seen: {ra.first_seen ? new Date(ra.first_seen).toLocaleString() : '—'}</span>
                                                                        <span>Last seen: {ra.last_seen ? new Date(ra.last_seen).toLocaleString() : '—'}</span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="text-center py-12">
                                                <Shield className="w-12 h-12 mx-auto mb-4 text-white/15" />
                                                <p className="text-white/40">No health rule violations recorded yet</p>
                                                <p className="text-xs text-white/25 mt-1">Violations will appear here when health rules are triggered by metric ingestion</p>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </div>
                        ) : (
                            <Card className="bg-[#0a0a0a] border-white/10">
                                <CardContent className="py-16 text-center">
                                    <Shield className="w-16 h-16 mx-auto text-white/15 mb-4" />
                                    <p className="text-white/40 mb-4">Failed to load analytics</p>
                                    <Button variant="outline" onClick={fetchRuleAnalytics} data-testid="retry-analytics">Retry</Button>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </>
    );
};

export default EventAnalyzerPage;
