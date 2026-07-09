import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Navigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { OneAgentCard } from '../components/OneAgentCard';
import {
    Download, Key, Shield, Package, Server, Users, Activity, Clock,
    CheckCircle, XCircle, AlertTriangle, Copy, RefreshCw, Trash2,
    FileCode, Box, Building2, Mail, Calendar, Cpu, HardDrive,
    Database, Globe, Terminal, ChevronRight, ExternalLink, Layers,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ═══════════════════════════════════════
//  AGENT CARDS
// ═══════════════════════════════════════

const AGENTS = [
    {
        id: 'server-agent',
        name: 'Server Monitoring Agent',
        icon: Server,
        color: '#00E0FF',
        version: '2.0',
        downloadKey: 'agent',
        filename: 'falcon_server_agent.py',
        description: 'Lightweight Python agent for infrastructure monitoring. Collects system metrics and sends to FalconOps API.',
        features: [
            'CPU, memory, disk, swap usage',
            'Network I/O (in/out Mbps)',
            'Load average (1m, 5m, 15m)',
            'Process count & uptime tracking',
            'Auto-registration with API server',
            'Systemd service integration',
        ],
        requirements: 'Python 3.8+, psutil',
        installCmd: (apiUrl) =>
            `curl -sL ${apiUrl || '<API_URL>'}/api/licenses/download/agent -H "Authorization: Bearer <TOKEN>" -o falcon_server_agent.py && pip install psutil && python3 falcon_server_agent.py --api-url ${apiUrl || '<API_URL>'}`,
    },
    {
        id: 'db-agent',
        name: 'Database Monitoring Agent',
        icon: Database,
        color: '#10B981',
        version: '2.0',
        downloadKey: 'db-agent',
        filename: 'falcon_db_agent.py',
        description: 'Full-featured database agent supporting PostgreSQL, MySQL, and Oracle. Collects DB metrics, runs custom queries, and detects slow queries.',
        features: [
            'Active sessions & connection pool',
            'Cache hit ratio & TPS',
            'Deadlock & replication lag detection',
            'Slow query capture & analysis',
            'Custom SQL query execution',
            'Multi-DB support (PG, MySQL, Oracle)',
        ],
        requirements: 'Python 3.8+, psycopg2 / pymysql / oracledb',
        installCmd: (apiUrl) =>
            `curl -sL ${apiUrl || '<API_URL>'}/api/licenses/download/db-agent -H "Authorization: Bearer <TOKEN>" -o falcon_db_agent.py && pip install psycopg2-binary && python3 falcon_db_agent.py --api-url ${apiUrl || '<API_URL>'} --instance-id <INSTANCE_ID>`,
    },
    {
        id: 'synthetic-agent',
        name: 'Synthetic URL Monitor',
        icon: Globe,
        color: '#8B5CF6',
        version: '1.0',
        downloadKey: null, // built-in, not a downloadable agent
        filename: null,
        description: 'Built-in module for proactive URL monitoring. Runs HTTP checks, login flows, and OTP validation to ensure service availability.',
        features: [
            'HTTP endpoint health checks',
            'Login flow validation',
            'TOTP / OTP verification',
            'Response time tracking',
            'Uptime & availability SLAs',
            'Multi-step journey testing',
        ],
        requirements: 'No agent needed — runs on the FalconOps server',
        installCmd: null,
        builtIn: true,
    },
];

const AgentCard = ({ agent, loading, onDownload }) => {
    const Icon = agent.icon;
    const [showInstall, setShowInstall] = useState(false);

    const copyCmd = () => {
        if (agent.installCmd) {
            navigator.clipboard.writeText(agent.installCmd(API_URL));
            toast.success('Install command copied');
        }
    };

    return (
        <Card className="bg-[#0a0a0a] border-white/10 flex flex-col" data-testid={`agent-card-${agent.id}`}>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg" style={{ background: `${agent.color}15` }}>
                            <Icon className="w-5 h-5" style={{ color: agent.color }} />
                        </div>
                        <div>
                            <CardTitle className="text-white text-base">{agent.name}</CardTitle>
                            <div className="flex items-center gap-2 mt-0.5">
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-white/20 text-white/50">
                                    v{agent.version}
                                </Badge>
                                {agent.builtIn && (
                                    <Badge className="text-[10px] px-1.5 py-0 bg-purple-500/20 text-purple-400 border-purple-500/30">
                                        Built-in
                                    </Badge>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
                <CardDescription className="mt-2 text-xs leading-relaxed">{agent.description}</CardDescription>
            </CardHeader>

            <CardContent className="flex-1 flex flex-col gap-3 pt-0">
                {/* Features */}
                <div className="p-3 bg-white/[0.03] rounded-lg space-y-1.5">
                    <h4 className="text-xs font-medium text-white/70 uppercase tracking-wider">Capabilities</h4>
                    <ul className="space-y-1">
                        {agent.features.map((f, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs text-white/55">
                                <CheckCircle className="w-3 h-3 mt-0.5 shrink-0" style={{ color: agent.color }} />
                                {f}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Requirements */}
                <div className="p-2.5 rounded-lg border border-white/5 bg-white/[0.02]">
                    <p className="text-[11px] text-white/40">
                        <Terminal className="w-3 h-3 inline mr-1.5 opacity-60" />
                        {agent.requirements}
                    </p>
                </div>

                {/* Install command */}
                {agent.installCmd && (
                    <div>
                        <button
                            onClick={() => setShowInstall(!showInstall)}
                            className="flex items-center gap-1 text-[11px] text-white/40 hover:text-white/70 transition-colors"
                        >
                            <ChevronRight className={`w-3 h-3 transition-transform ${showInstall ? 'rotate-90' : ''}`} />
                            Quick install command
                        </button>
                        {showInstall && (
                            <div className="mt-2 relative group">
                                <pre className="p-2.5 bg-black/60 border border-white/5 rounded text-[10px] text-white/50 overflow-x-auto whitespace-pre-wrap break-all font-mono leading-relaxed">
                                    {agent.installCmd(API_URL)}
                                </pre>
                                <Button
                                    size="sm" variant="ghost"
                                    className="absolute top-1 right-1 h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                    onClick={copyCmd}
                                    data-testid={`copy-install-${agent.id}`}
                                >
                                    <Copy className="w-3 h-3" />
                                </Button>
                            </div>
                        )}
                    </div>
                )}

                {/* Spacer */}
                <div className="flex-1" />

                {/* Download button */}
                {agent.downloadKey ? (
                    <Button
                        className="w-full font-medium"
                        style={{ background: agent.color, color: '#000' }}
                        onClick={() => onDownload(agent.downloadKey, agent.filename)}
                        disabled={loading}
                        data-testid={`download-${agent.id}-btn`}
                    >
                        {loading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                        Download {agent.filename}
                    </Button>
                ) : (
                    <Button
                        variant="outline" className="w-full border-purple-500/30 text-purple-400 hover:bg-purple-500/10"
                        onClick={() => { window.location.href = '/synthetic-monitoring'; }}
                        data-testid={`goto-synthetic-btn`}
                    >
                        <ExternalLink className="w-4 h-4 mr-2" />
                        Open Synthetic Monitoring
                    </Button>
                )}
            </CardContent>
        </Card>
    );
};

// ═══════════════════════════════════════
//  LICENSE HELPERS
// ═══════════════════════════════════════

const getLicenseTypeBadge = (type) => {
    const colors = {
        trial: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        standard: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        professional: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
        enterprise: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    };
    return colors[type] || colors.standard;
};

// ═══════════════════════════════════════
//  MAIN PAGE
// ═══════════════════════════════════════

export const DownloadPage = () => {
    const { user } = useAuth();
    const [activeTab, setActiveTab] = useState('download');
    const [loading, setLoading] = useState(false);
    const [currentLicense, setCurrentLicense] = useState(null);
    const [licensePlans, setLicensePlans] = useState({});
    const [licenseRecords, setLicenseRecords] = useState([]);
    const [includeDocker, setIncludeDocker] = useState(true);
    const [archiveFormat, setArchiveFormat] = useState('tar.gz'); // 'tar.gz' | 'zip'
    const [prereqs, setPrereqs] = useState(null);
    const [showPrereqs, setShowPrereqs] = useState(true);
    const [generateForm, setGenerateForm] = useState({
        organization: '', customer_email: '', license_type: 'standard', valid_days: 365,
    });
    const [activateLicenseKey, setActivateLicenseKey] = useState('');
    const [validationResult, setValidationResult] = useState(null);

    const isAdmin = user?.role === 'admin';

    useEffect(() => {
        if (isAdmin) { fetchCurrentLicense(); fetchLicensePlans(); fetchLicenseRecords(); fetchPrerequisites(); }
    }, [isAdmin]);

    if (!isAdmin) return <Navigate to="/dashboard" replace />;

    const getAuthHeaders = () => ({
        'Authorization': `Bearer ${localStorage.getItem('falconToken')}`,
        'Content-Type': 'application/json',
    });

    const fetchCurrentLicense = async () => {
        try {
            const r = await fetch(`${API_URL}/api/licenses/current`, { headers: getAuthHeaders() });
            const d = await r.json();
            setCurrentLicense(d.active ? d.license : null);
        } catch { /* ignore */ }
    };

    const fetchLicensePlans = async () => {
        try {
            const r = await fetch(`${API_URL}/api/licenses/plans`, { headers: getAuthHeaders() });
            const d = await r.json();
            setLicensePlans(d.plans || {});
        } catch { /* ignore */ }
    };

    const fetchLicenseRecords = async () => {
        try {
            const r = await fetch(`${API_URL}/api/licenses/records`, { headers: getAuthHeaders() });
            const d = await r.json();
            setLicenseRecords(d.records || []);
        } catch { /* ignore */ }
    };

    const fetchPrerequisites = async () => {
        try {
            const r = await fetch(`${API_URL}/api/licenses/download/prerequisites`, { headers: getAuthHeaders() });
            if (r.ok) setPrereqs(await r.json());
        } catch { /* ignore */ }
    };

    const handleDownloadSource = async (fmt) => {
        const format = fmt || archiveFormat;
        setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/download/source?include_docker=${includeDocker}&format=${format}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('falconToken')}` },
            });
            if (!r.ok) throw new Error('Download failed');
            const blob = await r.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url;
            const ext = format === 'zip' ? 'zip' : 'tar.gz';
            a.download = `falconops-ai-enterprise-${new Date().toISOString().split('T')[0]}.${ext}`;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
            toast.success(`Bundle (.${ext}) downloaded`);
        } catch { toast.error('Download failed'); }
        finally { setLoading(false); }
    };

    const handleDownloadAgent = async (agentKey, filename) => {
        setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/download/${agentKey}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('falconToken')}` },
            });
            if (!r.ok) throw new Error('Download failed');
            const blob = await r.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url;
            a.download = filename || `falcon_${agentKey}.py`;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
            toast.success(`${filename || 'Agent'} downloaded`);
        } catch { toast.error('Download failed'); }
        finally { setLoading(false); }
    };

    const handleGenerateLicense = async (e) => {
        e.preventDefault(); setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/generate`, {
                method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(generateForm),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Failed');
            toast.success('License generated');
            setValidationResult({ generated: true, license_key: d.license_key, ...d });
            fetchLicenseRecords();
            setGenerateForm({ organization: '', customer_email: '', license_type: 'standard', valid_days: 365 });
        } catch (err) { toast.error(err.message); }
        finally { setLoading(false); }
    };

    const handleValidateLicense = async () => {
        if (!activateLicenseKey.trim()) { toast.error('Enter a license key'); return; }
        setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/validate`, {
                method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ license_key: activateLicenseKey }),
            });
            const d = await r.json(); setValidationResult(d);
            d.valid ? toast.success('License is valid') : toast.error(d.error || 'Invalid');
        } catch { toast.error('Validation failed'); }
        finally { setLoading(false); }
    };

    const handleActivateLicense = async () => {
        if (!activateLicenseKey.trim()) { toast.error('Enter a license key'); return; }
        setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/activate`, {
                method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ license_key: activateLicenseKey }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Activation failed');
            toast.success('License activated');
            setActivateLicenseKey(''); setValidationResult(null); fetchCurrentLicense();
        } catch (err) { toast.error(err.message); }
        finally { setLoading(false); }
    };

    const handleRevokeLicense = async () => {
        if (!window.confirm('Revoke the current license?')) return;
        setLoading(true);
        try {
            const r = await fetch(`${API_URL}/api/licenses/revoke`, { method: 'DELETE', headers: getAuthHeaders() });
            if (!r.ok) throw new Error('Failed');
            toast.success('License revoked'); setCurrentLicense(null);
        } catch (err) { toast.error(err.message); }
        finally { setLoading(false); }
    };

    const copyToClipboard = (text) => { navigator.clipboard.writeText(text); toast.success('Copied'); };

    return (
        <div className="space-y-6" data-testid="download-page">
            {/* ── Header ── */}
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                    <Package className="w-7 h-7 text-[#F5B841]" />
                    Downloads &amp; Licensing
                </h1>
                <p className="text-white/50 mt-1 text-sm">
                    On-premise deployment packages, monitoring agents, and license management
                </p>
            </div>

            {/* ── Active License Banner ── */}
            {currentLicense && (
                <Card className="bg-emerald-500/[0.06] border-emerald-500/20">
                    <CardContent className="p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <CheckCircle className="w-5 h-5 text-emerald-400" />
                            <div className="text-sm">
                                <span className="text-white font-medium">{currentLicense.organization}</span>
                                <span className="mx-2 text-white/20">|</span>
                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${getLicenseTypeBadge(currentLicense.type)}`}>
                                    {currentLicense.type?.toUpperCase()}
                                </span>
                                <span className="mx-2 text-white/20">|</span>
                                <span className="text-white/50">
                                    Expires {new Date(currentLicense.expires_at).toLocaleDateString()}
                                    {currentLicense.days_remaining && (
                                        <span className="text-emerald-400 ml-1">({currentLicense.days_remaining}d left)</span>
                                    )}
                                </span>
                            </div>
                        </div>
                        <Button variant="ghost" size="sm" className="text-red-400/70 hover:text-red-400 hover:bg-red-500/10 h-7 text-xs"
                            onClick={handleRevokeLicense} data-testid="revoke-license-btn">
                            <Trash2 className="w-3 h-3 mr-1" /> Revoke
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* ── Tabs ── */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-white/5 border border-white/10">
                    <TabsTrigger value="download" className="data-[state=active]:bg-[#F5B841]/20 data-[state=active]:text-[#F5B841]">
                        <Download className="w-4 h-4 mr-2" /> Downloads
                    </TabsTrigger>
                    <TabsTrigger value="activate" className="data-[state=active]:bg-[#F5B841]/20 data-[state=active]:text-[#F5B841]">
                        <Key className="w-4 h-4 mr-2" /> Activate
                    </TabsTrigger>
                    <TabsTrigger value="generate" className="data-[state=active]:bg-[#F5B841]/20 data-[state=active]:text-[#F5B841]">
                        <Shield className="w-4 h-4 mr-2" /> Generate
                    </TabsTrigger>
                    <TabsTrigger value="records" className="data-[state=active]:bg-[#F5B841]/20 data-[state=active]:text-[#F5B841]">
                        <FileCode className="w-4 h-4 mr-2" /> Records
                    </TabsTrigger>
                </TabsList>

                {/* ════════ DOWNLOAD TAB ════════ */}
                <TabsContent value="download" className="mt-6 space-y-6">
                    {/* Full Platform Package */}
                    <Card className="bg-gradient-to-r from-[#F5B841]/[0.06] to-transparent border-[#F5B841]/20">
                        <CardContent className="p-5">
                            <div className="flex flex-col lg:flex-row gap-5">
                                <div className="flex-1">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="p-3 bg-[#F5B841]/15 rounded-xl">
                                            <HardDrive className="w-6 h-6 text-[#F5B841]" />
                                        </div>
                                        <div>
                                            <h3 className="text-lg font-semibold text-white">Full Enterprise Platform</h3>
                                            <p className="text-xs text-white/40">Complete on-premise deployment package</p>
                                        </div>
                                    </div>
                                    <p className="text-sm text-white/50 mb-4">
                                        Source code, Docker configs, Kubernetes manifests, database scripts, systemd services, and documentation.
                                    </p>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center mb-4">
                                        {[
                                            { v: '17+', l: 'API Modules', c: '#F5B841' },
                                            { v: '40+', l: 'UI Pages', c: '#00E0FF' },
                                            { v: '7', l: 'K8s Manifests', c: '#10B981' },
                                            { v: '3', l: 'Deploy Options', c: '#8B5CF6' },
                                        ].map((s) => (
                                            <div key={s.l} className="p-2.5 bg-black/30 rounded-lg">
                                                <div className="text-xl font-bold" style={{ color: s.c }}>{s.v}</div>
                                                <div className="text-[10px] text-white/40">{s.l}</div>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="flex flex-wrap gap-2 text-[11px] text-white/40 mb-4">
                                        {['Docker Compose', 'Kubernetes', 'Systemd / Linux', 'Nginx Reverse Proxy', 'MongoDB Scripts', 'Install Wizard'].map(t => (
                                            <span key={t} className="flex items-center gap-1 px-2 py-0.5 rounded bg-white/[0.04] border border-white/5">
                                                <CheckCircle className="w-2.5 h-2.5 text-emerald-500/60" /> {t}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                <div className="lg:w-64 flex flex-col gap-3">
                                    <div className="flex items-center justify-between p-2.5 bg-black/30 rounded-lg">
                                        <span className="text-xs text-white/50 flex items-center gap-1.5">
                                            <Box className="w-3.5 h-3.5 text-blue-400" /> Docker config
                                        </span>
                                        <Switch checked={includeDocker} onCheckedChange={setIncludeDocker} data-testid="include-docker-switch" />
                                    </div>
                                    {/* Format toggle */}
                                    <div className="flex items-center gap-1 p-1 bg-black/40 rounded-lg border border-white/5">
                                        {['tar.gz', 'zip'].map(fmt => (
                                            <button
                                                key={fmt}
                                                onClick={() => setArchiveFormat(fmt)}
                                                data-testid={`archive-format-${fmt}`}
                                                className={`flex-1 py-1.5 text-xs font-mono uppercase tracking-wider rounded transition-all ${
                                                    archiveFormat === fmt
                                                        ? 'bg-[#F5B841]/20 text-[#F5B841] border border-[#F5B841]/40'
                                                        : 'text-white/40 hover:text-white/70 border border-transparent'
                                                }`}
                                            >
                                                .{fmt}
                                            </button>
                                        ))}
                                    </div>
                                    <div className="p-2.5 bg-emerald-500/[0.06] border border-emerald-500/20 rounded-lg text-center">
                                        <div className="text-sm text-emerald-400 font-medium">~1 – 2 MB</div>
                                        <div className="text-[10px] text-emerald-400/50">{archiveFormat === 'zip' ? 'ZIP (Windows-friendly)' : 'TAR.GZ (Linux-native)'}</div>
                                    </div>
                                    <Button className="w-full bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                        onClick={() => handleDownloadSource()} disabled={loading} data-testid="download-source-btn">
                                        {loading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                                        Download .{archiveFormat}
                                    </Button>
                                    <div className="grid grid-cols-2 gap-2">
                                        <Button size="sm" variant="outline"
                                            className="text-[11px] border-white/10 text-white/60 hover:bg-white/5"
                                            onClick={() => handleDownloadSource('tar.gz')} disabled={loading}
                                            data-testid="download-targz-btn">
                                            <Download className="w-3 h-3 mr-1" /> .tar.gz
                                        </Button>
                                        <Button size="sm" variant="outline"
                                            className="text-[11px] border-white/10 text-white/60 hover:bg-white/5"
                                            onClick={() => handleDownloadSource('zip')} disabled={loading}
                                            data-testid="download-zip-btn">
                                            <Download className="w-3 h-3 mr-1" /> .zip
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Linux Prerequisites Panel */}
                    {prereqs && (
                        <Card className="bg-[#0a0a0a] border-white/10" data-testid="prereqs-panel">
                            <CardHeader className="cursor-pointer select-none" onClick={() => setShowPrereqs(!showPrereqs)}>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Terminal className="w-4 h-4 text-[#00E0FF]" />
                                        <CardTitle className="text-white text-base">Linux Server Prerequisites</CardTitle>
                                        <Badge variant="outline" className="text-[10px] border-cyan-500/30 text-cyan-400">
                                            Before you download
                                        </Badge>
                                    </div>
                                    <ChevronRight className={`w-4 h-4 text-white/40 transition-transform ${showPrereqs ? 'rotate-90' : ''}`} />
                                </div>
                                <CardDescription className="text-xs">
                                    Hardware, OS, and package requirements. The bundle ships with <code className="text-[#F5B841]">install-linux.sh</code> — a one-command installer that auto-installs these for you.
                                </CardDescription>
                            </CardHeader>
                            {showPrereqs && (
                                <CardContent className="space-y-5">
                                    {/* Hardware tiers */}
                                    <div>
                                        <h4 className="text-[11px] uppercase tracking-widest text-white/40 mb-2 flex items-center gap-1.5">
                                            <Cpu className="w-3 h-3" /> Hardware Tiers
                                        </h4>
                                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                                            {prereqs.hardware.map((h) => (
                                                <div key={h.tier} className="p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                                                    <div className="text-xs font-semibold text-white mb-1">{h.tier}</div>
                                                    <div className="text-[11px] text-white/50 space-y-0.5">
                                                        <div>{h.vcpu} vCPU · {h.ram_gb} GB RAM</div>
                                                        <div>{h.disk_gb} GB disk</div>
                                                        <div className="text-white/35 text-[10px] mt-1">{h.use_case}</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Two-column: Docker vs Bare-metal */}
                                    <div className="grid md:grid-cols-2 gap-4">
                                        {/* Docker path */}
                                        <div className="p-4 border border-blue-500/20 bg-blue-500/[0.04] rounded-lg">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Box className="w-4 h-4 text-blue-400" />
                                                <h4 className="text-sm font-semibold text-white">Docker Path <span className="text-blue-400 text-[10px] font-mono ml-1">RECOMMENDED</span></h4>
                                            </div>
                                            <p className="text-[11px] text-white/50 mb-3">{prereqs.docker_path.summary}</p>
                                            <div className="space-y-2">
                                                <div>
                                                    <div className="text-[10px] uppercase text-white/40 mb-1">Ubuntu / Debian</div>
                                                    <pre className="p-2 bg-black/60 rounded text-[10px] text-white/60 overflow-x-auto font-mono whitespace-pre-wrap break-all">{prereqs.docker_path.install_ubuntu}</pre>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] uppercase text-white/40 mb-1">RHEL / Rocky / Alma</div>
                                                    <pre className="p-2 bg-black/60 rounded text-[10px] text-white/60 overflow-x-auto font-mono whitespace-pre-wrap break-all">{prereqs.docker_path.install_rhel}</pre>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] uppercase text-white/40 mb-1">Then run</div>
                                                    <pre className="p-2 bg-black/60 rounded text-[10px] text-emerald-400 font-mono">{prereqs.docker_path.run}</pre>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Bare-metal path */}
                                        <div className="p-4 border border-purple-500/20 bg-purple-500/[0.04] rounded-lg">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Server className="w-4 h-4 text-purple-400" />
                                                <h4 className="text-sm font-semibold text-white">Bare-Metal Path</h4>
                                            </div>
                                            <p className="text-[11px] text-white/50 mb-3">{prereqs.baremetal_path.summary}</p>
                                            <div className="space-y-1.5">
                                                {prereqs.baremetal_path.packages.map((p) => (
                                                    <div key={p.name} className="flex items-center justify-between text-[11px] p-1.5 bg-black/30 rounded">
                                                        <div>
                                                            <span className="text-white/80 font-medium">{p.name}</span>
                                                            <span className="text-white/30 mx-1.5">·</span>
                                                            <span className="text-purple-400/80 font-mono text-[10px]">{p.version}</span>
                                                        </div>
                                                        <span className="text-white/35 text-[10px] hidden lg:inline">{p.purpose}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Supported OS + Ports */}
                                    <div className="grid md:grid-cols-2 gap-4">
                                        <div className="p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                                            <h4 className="text-[11px] uppercase tracking-widest text-white/40 mb-2 flex items-center gap-1.5">
                                                <HardDrive className="w-3 h-3" /> Supported OS
                                            </h4>
                                            <ul className="space-y-1">
                                                {prereqs.supported_os.map((os) => (
                                                    <li key={os} className="flex items-start gap-2 text-[11px] text-white/60">
                                                        <CheckCircle className="w-3 h-3 mt-0.5 text-emerald-500/70 shrink-0" /> {os}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                        <div className="p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                                            <h4 className="text-[11px] uppercase tracking-widest text-white/40 mb-2 flex items-center gap-1.5">
                                                <Globe className="w-3 h-3" /> Network Ports
                                            </h4>
                                            <div className="space-y-1">
                                                {prereqs.ports.map((p) => (
                                                    <div key={p.port} className="flex items-center justify-between text-[11px]">
                                                        <span className="font-mono text-[#F5B841]">{p.port}</span>
                                                        <span className="text-white/40">{p.direction}</span>
                                                        <span className="text-white/50 text-[10px] ml-auto hidden lg:inline">{p.purpose}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* API Keys */}
                                    <div className="p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                                        <h4 className="text-[11px] uppercase tracking-widest text-white/40 mb-2 flex items-center gap-1.5">
                                            <Key className="w-3 h-3" /> Recommended API Keys
                                        </h4>
                                        <div className="grid md:grid-cols-2 gap-2">
                                            {prereqs.api_keys.map((k) => (
                                                <div key={k.key} className="p-2 bg-black/30 rounded text-[11px]">
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <code className="text-[#00E0FF] font-mono">{k.key}</code>
                                                        {k.required
                                                            ? <Badge className="text-[9px] px-1.5 py-0 bg-red-500/20 text-red-400 border-red-500/30">required</Badge>
                                                            : <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-white/10 text-white/40">optional</Badge>}
                                                    </div>
                                                    <div className="text-white/45 text-[10px]">{k.purpose}</div>
                                                    <div className="text-white/30 text-[10px] mt-0.5 truncate">{k.where}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Default credentials */}
                                    <div className="p-3 border border-emerald-500/20 bg-emerald-500/[0.04] rounded-lg">
                                        <h4 className="text-[11px] uppercase tracking-widest text-emerald-400/70 mb-2 flex items-center gap-1.5">
                                            <Shield className="w-3 h-3" /> Default Credentials (post-seed)
                                        </h4>
                                        <div className="grid md:grid-cols-2 gap-2 text-[11px]">
                                            <div className="p-2 bg-black/40 rounded">
                                                <div className="text-white/40 text-[10px] uppercase">Admin</div>
                                                <code className="text-white/80">{prereqs.credentials.admin.email}</code>
                                                <div className="text-white/50">pw: <code>{prereqs.credentials.admin.password}</code></div>
                                            </div>
                                            <div className="p-2 bg-black/40 rounded">
                                                <div className="text-white/40 text-[10px] uppercase">Viewer</div>
                                                <code className="text-white/80">{prereqs.credentials.viewer.email}</code>
                                                <div className="text-white/50">pw: <code>{prereqs.credentials.viewer.password}</code></div>
                                            </div>
                                        </div>
                                        <p className="text-[10px] text-emerald-400/60 mt-2">↪ Change the admin password immediately after first login.</p>
                                    </div>
                                </CardContent>
                            )}
                        </Card>
                    )}

                    {/* Agent Downloads */}
                    <div>
                        <h3 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
                            <Layers className="w-4 h-4 text-white/40" />
                            Monitoring Agents
                        </h3>
                        <p className="text-xs text-white/35 mb-4">Deploy agents on your infrastructure to stream metrics to FalconOps</p>
                        <OneAgentCard />
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                            {AGENTS.map(a => (
                                <AgentCard key={a.id} agent={a} loading={loading} onDownload={handleDownloadAgent} />
                            ))}
                        </div>
                    </div>
                </TabsContent>

                {/* ════════ ACTIVATE TAB ════════ */}
                <TabsContent value="activate" className="mt-6">
                    <Card className="bg-[#0a0a0a] border-white/10 max-w-2xl">
                        <CardHeader>
                            <CardTitle className="text-white flex items-center gap-2">
                                <Key className="w-5 h-5 text-[#F5B841]" /> Activate License
                            </CardTitle>
                            <CardDescription>Enter your license key to activate FalconOps AI features</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="license-key">License Key</Label>
                                <Input id="license-key" placeholder="Enter your license key..."
                                    value={activateLicenseKey} onChange={(e) => setActivateLicenseKey(e.target.value)}
                                    className="bg-white/5 border-white/20 font-mono text-sm" data-testid="license-key-input" />
                            </div>
                            <div className="flex gap-3">
                                <Button variant="outline" onClick={handleValidateLicense}
                                    disabled={loading || !activateLicenseKey} data-testid="validate-license-btn">
                                    <Shield className="w-4 h-4 mr-2" /> Validate
                                </Button>
                                <Button className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                    onClick={handleActivateLicense} disabled={loading || !activateLicenseKey} data-testid="activate-license-btn">
                                    {loading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                                    Activate License
                                </Button>
                            </div>
                            {validationResult && !validationResult.generated && (
                                <div className={`p-4 rounded-lg border ${validationResult.valid ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                                    <div className="flex items-center gap-2 mb-3">
                                        {validationResult.valid ? <CheckCircle className="w-5 h-5 text-emerald-400" /> : <XCircle className="w-5 h-5 text-red-400" />}
                                        <span className={`font-medium ${validationResult.valid ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {validationResult.valid ? 'Valid License' : 'Invalid License'}
                                        </span>
                                    </div>
                                    {validationResult.valid ? (
                                        <div className="space-y-2 text-sm">
                                            <p className="text-white/70"><Building2 className="w-4 h-4 inline mr-2" />{validationResult.organization}</p>
                                            <p className="text-white/70"><Shield className="w-4 h-4 inline mr-2" />{validationResult.type}</p>
                                            <p className="text-white/70"><Clock className="w-4 h-4 inline mr-2" />
                                                Expires: {new Date(validationResult.expires_at).toLocaleDateString()}
                                                <span className="ml-2 text-emerald-400">({validationResult.days_remaining} days)</span>
                                            </p>
                                        </div>
                                    ) : (
                                        <p className="text-red-400 text-sm">{validationResult.error}</p>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ════════ GENERATE TAB ════════ */}
                <TabsContent value="generate" className="mt-6">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Plans */}
                        <div className="lg:col-span-1 space-y-3">
                            <h3 className="text-base font-semibold text-white">License Plans</h3>
                            {Object.entries(licensePlans).map(([key, plan]) => (
                                <Card key={key} className={`bg-[#0a0a0a] border cursor-pointer transition-all ${
                                    generateForm.license_type === key ? 'border-[#F5B841] ring-1 ring-[#F5B841]/30' : 'border-white/10 hover:border-white/20'
                                }`} onClick={() => setGenerateForm({ ...generateForm, license_type: key, valid_days: plan.valid_days })}>
                                    <CardContent className="p-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${getLicenseTypeBadge(key)}`}>{plan.name}</span>
                                            <span className="text-lg font-bold text-white">{typeof plan.price === 'number' ? `$${plan.price}` : plan.price}</span>
                                        </div>
                                        <p className="text-xs text-white/50 mb-3">{plan.description}</p>
                                        <div className="space-y-1 text-xs text-white/60">
                                            <p><Users className="w-3 h-3 inline mr-1" /> {plan.max_users?.toLocaleString()} users</p>
                                            <p><Server className="w-3 h-3 inline mr-1" /> {plan.max_servers?.toLocaleString()} servers</p>
                                            <p><Activity className="w-3 h-3 inline mr-1" /> {plan.max_monitors?.toLocaleString()} monitors</p>
                                            <p><Calendar className="w-3 h-3 inline mr-1" /> {plan.valid_days} days</p>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                        {/* Form */}
                        <Card className="lg:col-span-2 bg-[#0a0a0a] border-white/10">
                            <CardHeader>
                                <CardTitle className="text-white">Generate New License</CardTitle>
                                <CardDescription>Create a new license key for a customer</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={handleGenerateLicense} className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>Organization</Label>
                                            <Input placeholder="Acme Corporation" value={generateForm.organization}
                                                onChange={(e) => setGenerateForm({ ...generateForm, organization: e.target.value })}
                                                required className="bg-white/5 border-white/20" data-testid="generate-org-input" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Customer Email</Label>
                                            <Input type="email" placeholder="customer@example.com" value={generateForm.customer_email}
                                                onChange={(e) => setGenerateForm({ ...generateForm, customer_email: e.target.value })}
                                                required className="bg-white/5 border-white/20" data-testid="generate-email-input" />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>License Type</Label>
                                            <select value={generateForm.license_type}
                                                onChange={(e) => {
                                                    const p = licensePlans[e.target.value];
                                                    setGenerateForm({ ...generateForm, license_type: e.target.value, valid_days: p?.valid_days || 365 });
                                                }}
                                                className="w-full h-10 px-3 rounded-md bg-white/5 border border-white/20 text-white text-sm"
                                                data-testid="generate-type-select">
                                                <option value="trial">Trial (14 days)</option>
                                                <option value="standard">Standard</option>
                                                <option value="professional">Professional</option>
                                                <option value="enterprise">Enterprise</option>
                                            </select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Validity (days)</Label>
                                            <Input type="number" min="1" max="3650" value={generateForm.valid_days}
                                                onChange={(e) => setGenerateForm({ ...generateForm, valid_days: parseInt(e.target.value) || 365 })}
                                                className="bg-white/5 border-white/20" data-testid="generate-days-input" />
                                        </div>
                                    </div>
                                    <Button type="submit" className="w-full bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                                        disabled={loading || !generateForm.organization || !generateForm.customer_email}
                                        data-testid="generate-license-btn">
                                        {loading ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Key className="w-4 h-4 mr-2" />}
                                        Generate License Key
                                    </Button>
                                </form>
                                {validationResult?.generated && (
                                    <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                                        <div className="flex items-center gap-2 mb-3">
                                            <CheckCircle className="w-5 h-5 text-emerald-400" />
                                            <span className="font-medium text-emerald-400">License Generated</span>
                                        </div>
                                        <div className="space-y-3">
                                            <div>
                                                <Label className="text-xs text-white/50">License Key</Label>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <code className="flex-1 p-2 bg-black/50 rounded text-xs text-white/80 font-mono break-all">
                                                        {validationResult.license_key}
                                                    </code>
                                                    <Button size="sm" variant="ghost" onClick={() => copyToClipboard(validationResult.license_key)}
                                                        data-testid="copy-license-btn"><Copy className="w-4 h-4" /></Button>
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <p className="text-white/70"><Building2 className="w-4 h-4 inline mr-1" />{validationResult.organization}</p>
                                                <p className="text-white/70"><Mail className="w-4 h-4 inline mr-1" />{validationResult.customer_email}</p>
                                                <p className="text-white/70"><Shield className="w-4 h-4 inline mr-1" />{validationResult.type}</p>
                                                <p className="text-white/70"><Calendar className="w-4 h-4 inline mr-1" />Expires: {new Date(validationResult.expires_at).toLocaleDateString()}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                {/* ════════ RECORDS TAB ════════ */}
                <TabsContent value="records" className="mt-6">
                    <Card className="bg-[#0a0a0a] border-white/10">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-white">License Records</CardTitle>
                                <CardDescription>History of all generated licenses</CardDescription>
                            </div>
                            <Button variant="ghost" size="sm" onClick={fetchLicenseRecords} data-testid="refresh-records-btn">
                                <RefreshCw className="w-4 h-4" />
                            </Button>
                        </CardHeader>
                        <CardContent>
                            {licenseRecords.length === 0 ? (
                                <div className="text-center py-12 text-white/50">
                                    <FileCode className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p>No license records found</p>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead>
                                            <tr className="border-b border-white/10 text-left">
                                                <th className="pb-3 text-xs text-white/50 font-medium">Organization</th>
                                                <th className="pb-3 text-xs text-white/50 font-medium">Type</th>
                                                <th className="pb-3 text-xs text-white/50 font-medium">Email</th>
                                                <th className="pb-3 text-xs text-white/50 font-medium">Expires</th>
                                                <th className="pb-3 text-xs text-white/50 font-medium">Created</th>
                                                <th className="pb-3 text-xs text-white/50 font-medium">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {licenseRecords.map((rec) => (
                                                <tr key={rec.id} className="border-b border-white/5">
                                                    <td className="py-3 text-sm text-white">{rec.organization}</td>
                                                    <td className="py-3">
                                                        <span className={`px-2 py-0.5 rounded text-xs ${getLicenseTypeBadge(rec.type)}`}>{rec.type}</span>
                                                    </td>
                                                    <td className="py-3 text-sm text-white/70">{rec.customer_email}</td>
                                                    <td className="py-3 text-sm text-white/70">{new Date(rec.expires_at).toLocaleDateString()}</td>
                                                    <td className="py-3 text-sm text-white/50">{new Date(rec.created_at).toLocaleDateString()}</td>
                                                    <td className="py-3">
                                                        <Button size="sm" variant="ghost" onClick={() => copyToClipboard(rec.license_key)} className="text-white/50 hover:text-white">
                                                            <Copy className="w-4 h-4" />
                                                        </Button>
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
            </Tabs>
        </div>
    );
};

export default DownloadPage;
