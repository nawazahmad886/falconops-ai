import React, { useState, useEffect, useCallback } from 'react';
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
    Bot, RefreshCw, Server, Database, Activity, Download,
    CheckCircle, XCircle, Clock, Terminal, Copy, Wifi,
    WifiOff, Plus, Code, Settings, FileText,
} from 'lucide-react';

const STATUS_STYLES = {
    online: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    stale: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    offline: 'bg-red-500/15 text-red-400 border-red-500/30',
    registered: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
};

export default function DBAgentPage() {
    const { api } = useAuth();
    const [instances, setInstances] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('overview');
    const [installType, setInstallType] = useState('postgres');
    const [installScript, setInstallScript] = useState('');
    const [selectedInstance, setSelectedInstance] = useState(null);
    const [registerForm, setRegisterForm] = useState({ name: '', db_type: 'postgres', host: 'localhost', port: '5432', database: '', environment: 'production' });
    const [showRegister, setShowRegister] = useState(false);

    const API = process.env.REACT_APP_BACKEND_URL;

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/db-monitoring/dashboard-overview');
            setInstances(res.data?.instances || []);
            setSummary(res.data?.summary);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchInstallScript = useCallback(async (dbType) => {
        try {
            const res = await api.get(`/db-monitoring/agent/install-script?db_type=${dbType}&api_url=${API}`, { responseType: 'text' });
            setInstallScript(typeof res.data === 'string' ? res.data : JSON.stringify(res.data));
        } catch (e) { console.error(e); }
    }, [api, API]);

    const registerInstance = useCallback(async () => {
        try {
            await api.post('/db-monitoring/instances', {
                ...registerForm,
                port: parseInt(registerForm.port),
            });
            setShowRegister(false);
            setRegisterForm({ name: '', db_type: 'postgres', host: 'localhost', port: '5432', database: '', environment: 'production' });
            await fetchData();
        } catch (e) { console.error(e); }
    }, [api, registerForm, fetchData]);

    useEffect(() => { fetchData(); }, [fetchData]);
    useEffect(() => { if (tab === 'install') fetchInstallScript(installType); }, [tab, installType, fetchInstallScript]);

    const tabs = [
        { id: 'overview', label: 'Agents', icon: Bot },
        { id: 'install', label: 'Install Agent', icon: Download },
    ];

    return (
        <div className="space-y-6" data-testid="db-agent-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><Bot className="w-6 h-6 text-purple-400" /></div>
                        Database Agents
                    </h1>
                    <p className="text-sm text-white/50 mt-1">External agent management for database metric collection</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs">
                        <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => setShowRegister(!showRegister)} className="bg-purple-600 hover:bg-purple-700 text-white text-xs" data-testid="register-instance-btn">
                        <Plus className="w-3 h-3 mr-1" /> Register Instance
                    </Button>
                </div>
            </div>

            {/* Summary Stats */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><Database className="w-4 h-4 text-blue-400" /></div>
                        <div><p className="text-xs text-white/50">Instances</p><p className="text-lg font-bold text-white">{summary.total_instances}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><CheckCircle className="w-4 h-4 text-emerald-400" /></div>
                        <div><p className="text-xs text-white/50">Active</p><p className="text-lg font-bold text-emerald-400">{summary.active_instances}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/15"><Activity className="w-4 h-4 text-cyan-400" /></div>
                        <div><p className="text-xs text-white/50">Avg Health</p><p className="text-lg font-bold text-cyan-400">{summary.avg_health_score}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/15"><Clock className="w-4 h-4 text-amber-400" /></div>
                        <div><p className="text-xs text-white/50">Slow Queries</p><p className="text-lg font-bold text-amber-400">{summary.total_slow_queries_1h}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><XCircle className="w-4 h-4 text-red-400" /></div>
                        <div><p className="text-xs text-white/50">Locks</p><p className="text-lg font-bold text-red-400">{summary.total_locks_1h}</p></div>
                    </CardContent></Card>
                </div>
            )}

            {/* Register Form */}
            {showRegister && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="register-form">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Plus className="w-4 h-4 text-purple-400" /> Register DB Instance</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={registerForm.name} onChange={e => setRegisterForm(p => ({ ...p, name: e.target.value }))} placeholder="prod-postgres-01" data-testid="instance-name-input" /></div>
                            <div><Label className="text-xs text-white/60">DB Type</Label>
                                <Select value={registerForm.db_type} onValueChange={v => setRegisterForm(p => ({ ...p, db_type: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="postgres">PostgreSQL</SelectItem><SelectItem value="mysql">MySQL</SelectItem><SelectItem value="oracle">Oracle</SelectItem><SelectItem value="sqlserver">SQL Server</SelectItem></SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs text-white/60">Host</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={registerForm.host} onChange={e => setRegisterForm(p => ({ ...p, host: e.target.value }))} /></div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Port</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={registerForm.port} onChange={e => setRegisterForm(p => ({ ...p, port: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Database</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={registerForm.database} onChange={e => setRegisterForm(p => ({ ...p, database: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Environment</Label>
                                <Select value={registerForm.environment} onValueChange={v => setRegisterForm(p => ({ ...p, environment: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="production">Production</SelectItem><SelectItem value="staging">Staging</SelectItem><SelectItem value="development">Development</SelectItem></SelectContent>
                                </Select>
                            </div>
                        </div>
                        <Button onClick={registerInstance} disabled={!registerForm.name} className="bg-purple-600 hover:bg-purple-700 text-white" data-testid="submit-instance-btn"><CheckCircle className="w-3 h-3 mr-1" /> Register</Button>
                    </CardContent>
                </Card>
            )}

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => {
                    const Icon = t.icon;
                    return (
                        <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)}
                            className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                            <Icon className="w-3 h-3 mr-1" /> {t.label}
                        </Button>
                    );
                })}
            </div>

            {/* Agents Overview */}
            {tab === 'overview' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {instances.length === 0 && !loading && (
                        <div className="col-span-2 text-center p-8 text-white/40">
                            <Database className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No database instances registered. Click "Register Instance" to add one.</p>
                        </div>
                    )}
                    {instances.map(inst => {
                        const agentStyle = STATUS_STYLES[inst.agent_status] || STATUS_STYLES.offline;
                        const statusStyle = STATUS_STYLES[inst.status] || STATUS_STYLES.registered;
                        return (
                            <Card key={inst.id} className="bg-[#0D1117] border-white/5 hover:border-white/15 transition-all" data-testid={`instance-card-${inst.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 rounded-lg bg-purple-500/10"><Database className="w-5 h-5 text-purple-400" /></div>
                                            <div>
                                                <h3 className="text-sm font-semibold text-white">{inst.name}</h3>
                                                <p className="text-[10px] text-white/40">{inst.host}:{inst.port} ({inst.db_type})</p>
                                            </div>
                                        </div>
                                        <div className="flex flex-col items-end gap-1">
                                            <Badge className={`text-[9px] ${statusStyle}`}>{inst.status}</Badge>
                                            <Badge className={`text-[9px] ${agentStyle}`}>
                                                {inst.agent_status === 'online' ? <Wifi className="w-2.5 h-2.5 mr-0.5" /> : <WifiOff className="w-2.5 h-2.5 mr-0.5" />}
                                                Agent: {inst.agent_status}
                                            </Badge>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-4 gap-2 text-xs">
                                        <div><span className="text-white/40">Health:</span> <span className={inst.health_score >= 80 ? 'text-emerald-400' : inst.health_score >= 50 ? 'text-amber-400' : 'text-red-400'}>{inst.health_score}</span></div>
                                        <div><span className="text-white/40">Slow Q:</span> <span className="text-white/70">{inst.slow_queries_1h}</span></div>
                                        <div><span className="text-white/40">Locks:</span> <span className="text-white/70">{inst.locks_1h}</span></div>
                                        <div><span className="text-white/40">Env:</span> <span className="text-white/70">{inst.environment}</span></div>
                                    </div>
                                    {inst.agent_version && <p className="text-[9px] text-white/20 mt-2">Agent v{inst.agent_version}</p>}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Install Agent */}
            {tab === 'install' && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <CardTitle className="text-base flex items-center gap-2"><Terminal className="w-4 h-4 text-emerald-400" /> Agent Installation</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 space-y-3">
                            <div className="flex items-center gap-3">
                                <Label className="text-xs text-white/60">Database Type:</Label>
                                <Select value={installType} onValueChange={v => setInstallType(v)}>
                                    <SelectTrigger className="w-48 bg-[#161B22] border-white/10"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="postgres">PostgreSQL</SelectItem><SelectItem value="mysql">MySQL</SelectItem><SelectItem value="oracle">Oracle</SelectItem></SelectContent>
                                </Select>
                                <Button variant="outline" size="sm" className="border-white/10 text-xs" onClick={() => {
                                    const url = `${API}/api/db-monitoring/agent/download`;
                                    window.open(url, '_blank');
                                }} data-testid="download-agent-btn">
                                    <Download className="w-3 h-3 mr-1" /> Download Agent
                                </Button>
                            </div>
                            <div className="relative">
                                <pre className="bg-[#161B22] border border-white/5 rounded-lg p-4 text-xs text-white/60 overflow-x-auto max-h-96 font-mono" data-testid="install-script">
                                    {installScript || 'Loading install script...'}
                                </pre>
                                <Button variant="ghost" size="icon" className="absolute top-2 right-2 h-7 w-7"
                                    onClick={() => navigator.clipboard.writeText(installScript)} title="Copy">
                                    <Copy className="w-3 h-3 text-white/40" />
                                </Button>
                            </div>
                            <p className="text-xs text-white/30">Run this script on your database server as root. Edit the generated config file with your DB credentials before starting the agent.</p>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
