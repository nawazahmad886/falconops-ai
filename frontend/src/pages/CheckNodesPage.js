import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Server, RefreshCw, Plus, Trash2, Wifi, WifiOff, Map,
    Activity, CheckCircle, Download, Copy, Terminal, Globe,
    BarChart3, Clock, Code,
} from 'lucide-react';

const STATUS_STYLES = {
    online: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    stale: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    offline: 'bg-red-500/15 text-red-400 border-red-500/30',
};

export default function CheckNodesPage() {
    const { api } = useAuth();
    const [nodes, setNodes] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('nodes');
    const [showRegister, setShowRegister] = useState(false);
    const [form, setForm] = useState({ name: '', region: 'us-east', ip: '' });

    const API = process.env.REACT_APP_BACKEND_URL;

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [nRes, sRes] = await Promise.all([api.get('/check-nodes'), api.get('/check-nodes/stats')]);
            setNodes(nRes.data || []);
            setStats(sRes.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const registerNode = useCallback(async () => {
        try {
            await api.post('/check-nodes/register', form);
            setShowRegister(false);
            setForm({ name: '', region: 'us-east', ip: '' });
            await fetchData();
        } catch (e) { console.error(e); }
    }, [api, form, fetchData]);

    const deleteNode = useCallback(async (id) => {
        try { await api.delete(`/check-nodes/${id}`); await fetchData(); } catch (e) { console.error(e); }
    }, [api, fetchData]);

    useEffect(() => { fetchData(); const i = setInterval(fetchData, 15000); return () => clearInterval(i); }, [fetchData]);

    const dockerCmd = `docker run -d \\
  --name falconops-check-node \\
  -e API_URL=${API} \\
  -e NODE_REGION=us-east \\
  -e NODE_NAME=my-node \\
  -e CHECK_INTERVAL=60 \\
  falconops/check-node:latest`;

    const regions = ['us-east', 'us-west', 'eu-west', 'me-south', 'ap-southeast'];
    const tabs = [
        { id: 'nodes', label: 'Nodes', icon: Server },
        { id: 'deploy', label: 'Deploy', icon: Download },
    ];

    return (
        <div className="space-y-6" data-testid="check-nodes-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/15"><Server className="w-6 h-6 text-cyan-400" /></div>
                        Check Nodes
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Distributed check node infrastructure for multi-region monitoring</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs"><RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh</Button>
                    <Button size="sm" onClick={() => setShowRegister(!showRegister)} className="bg-cyan-600 hover:bg-cyan-700 text-white text-xs" data-testid="register-node-btn"><Plus className="w-3 h-3 mr-1" /> Register Node</Button>
                </div>
            </div>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><Server className="w-4 h-4 text-blue-400" /></div>
                        <div><p className="text-xs text-white/50">Total Nodes</p><p className="text-lg font-bold text-white" data-testid="total-nodes">{stats.total_nodes}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><Wifi className="w-4 h-4 text-emerald-400" /></div>
                        <div><p className="text-xs text-white/50">Online</p><p className="text-lg font-bold text-emerald-400">{stats.online}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><WifiOff className="w-4 h-4 text-red-400" /></div>
                        <div><p className="text-xs text-white/50">Offline</p><p className="text-lg font-bold text-red-400">{stats.offline}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><Activity className="w-4 h-4 text-purple-400" /></div>
                        <div><p className="text-xs text-white/50">Total Checks</p><p className="text-lg font-bold text-white">{stats.total_checks}</p></div>
                    </CardContent></Card>
                </div>
            )}

            {showRegister && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="register-node-form">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Plus className="w-4 h-4 text-cyan-400" /> Register Node</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="node-us-east-01" data-testid="node-name-input" /></div>
                            <div><Label className="text-xs text-white/60">Region</Label>
                                <Select value={form.region} onValueChange={v => setForm(p => ({ ...p, region: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        {regions.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs text-white/60">IP Address</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.ip} onChange={e => setForm(p => ({ ...p, ip: e.target.value }))} placeholder="1.2.3.4" data-testid="node-ip-input" /></div>
                        </div>
                        <Button onClick={registerNode} disabled={!form.name || !form.ip} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="submit-node-btn"><CheckCircle className="w-3 h-3 mr-1" /> Register</Button>
                    </CardContent>
                </Card>
            )}

            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {tab === 'nodes' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {nodes.length === 0 && !loading && (
                        <div className="col-span-2 text-center p-8 text-white/40"><Server className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No check nodes registered. Deploy nodes to enable multi-region monitoring.</p></div>
                    )}
                    {nodes.map(node => {
                        const stStyle = STATUS_STYLES[node.status] || STATUS_STYLES.offline;
                        return (
                            <Card key={node.id} className="bg-[#0D1117] border-white/5" data-testid={`node-card-${node.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 rounded-lg bg-cyan-500/10"><Server className="w-5 h-5 text-cyan-400" /></div>
                                            <div>
                                                <h3 className="text-sm font-semibold text-white">{node.name}</h3>
                                                <p className="text-[10px] text-white/40 font-mono">{node.ip} | {node.region}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge className={`text-[9px] ${stStyle}`}>
                                                {node.status === 'online' ? <Wifi className="w-2.5 h-2.5 mr-0.5" /> : <WifiOff className="w-2.5 h-2.5 mr-0.5" />}
                                                {node.status}
                                            </Badge>
                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => deleteNode(node.id)}><Trash2 className="w-3 h-3 text-red-400/50" /></Button>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2 text-xs">
                                        <div><span className="text-white/40">Checks:</span> <span className="text-white/70">{node.checks_performed || 0}</span></div>
                                        <div><span className="text-white/40">Version:</span> <span className="text-white/70">v{node.version}</span></div>
                                        <div><span className="text-white/40">Last HB:</span> <span className="text-white/70">{node.last_heartbeat ? new Date(node.last_heartbeat).toLocaleTimeString() : 'N/A'}</span></div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {tab === 'deploy' && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Terminal className="w-4 h-4 text-emerald-400" /> Docker Deployment</CardTitle></CardHeader>
                        <CardContent className="p-4 space-y-3">
                            <p className="text-xs text-white/50">Deploy check nodes to any region using Docker:</p>
                            <div className="relative">
                                <pre className="bg-[#161B22] border border-white/5 rounded-lg p-4 text-xs text-emerald-400/80 font-mono overflow-x-auto" data-testid="docker-cmd">{dockerCmd}</pre>
                                <Button variant="ghost" size="icon" className="absolute top-2 right-2 h-7 w-7" onClick={() => navigator.clipboard.writeText(dockerCmd)}><Copy className="w-3 h-3 text-white/40" /></Button>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                                <Card className="bg-white/[0.02] border-white/5"><CardContent className="p-3">
                                    <p className="text-xs font-semibold text-white/70 mb-2">Environment Variables</p>
                                    <div className="space-y-1 text-[10px] font-mono">
                                        <p><span className="text-cyan-400">API_URL</span> <span className="text-white/40">Central API endpoint</span></p>
                                        <p><span className="text-cyan-400">NODE_REGION</span> <span className="text-white/40">us-east | us-west | eu-west | me-south | ap-southeast</span></p>
                                        <p><span className="text-cyan-400">NODE_NAME</span> <span className="text-white/40">Unique node identifier</span></p>
                                        <p><span className="text-cyan-400">CHECK_INTERVAL</span> <span className="text-white/40">Seconds between check cycles (default: 60)</span></p>
                                    </div>
                                </CardContent></Card>
                                <Card className="bg-white/[0.02] border-white/5"><CardContent className="p-3">
                                    <p className="text-xs font-semibold text-white/70 mb-2">On-Premise Setup</p>
                                    <div className="space-y-1 text-[10px] text-white/50">
                                        <p>1. Pull the check-node Docker image</p>
                                        <p>2. Set API_URL to your FalconOps server</p>
                                        <p>3. Set NODE_REGION to your location</p>
                                        <p>4. Node auto-registers on startup</p>
                                        <p>5. Pulls monitor configs & pushes results</p>
                                    </div>
                                </CardContent></Card>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
