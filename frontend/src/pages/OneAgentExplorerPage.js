import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Stethoscope, Activity, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';

const TABS = ['Overview', 'Hosts', 'Processes', 'Containers', 'Network', 'Changes', 'Diagnostics', 'Agent Health'];

function NotAvailable({ reason }) {
    return <div className="text-xs text-white/40 italic p-3">Not available{reason ? ` — ${reason}` : ''}</div>;
}

export const OneAgentExplorerPage = () => {
    const { api } = useAuth();
    const [activeTab, setActiveTab] = useState('Overview');
    const [agents, setAgents] = useState([]);
    const [health, setHealth] = useState(null);
    const [processes, setProcesses] = useState([]);
    const [containers, setContainers] = useState([]);
    const [networkSummary, setNetworkSummary] = useState(null);
    const [networkDeps, setNetworkDeps] = useState(null);
    const [changes, setChanges] = useState([]);
    const [commands, setCommands] = useState([]);
    const [diagHost, setDiagHost] = useState('');
    const [diagResult, setDiagResult] = useState(null);
    const [diagRunning, setDiagRunning] = useState(false);
    const [selectedHost, setSelectedHost] = useState(null);
    const [hostDetail, setHostDetail] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        try {
            const [agentsRes, healthRes, procRes, contRes] = await Promise.all([
                api.get('/oneagent/agents'),
                api.get('/oneagent/health'),
                api.get('/resources', { params: { category: 'process', limit: 200 } }),
                api.get('/resources', { params: { category: 'container', limit: 200 } }),
            ]);
            setAgents(agentsRes.data.agents || []);
            setHealth(healthRes.data);
            setProcesses(procRes.data.resources || []);
            setContainers(contRes.data.resources || []);
        } catch (e) {
            toast.error('Failed to load OneAgent Explorer data');
        } finally {
            setLoading(false);
        }
    }, [api]);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        if (activeTab === 'Network' && !networkSummary) {
            Promise.all([api.get('/network/flows/summary'), api.get('/network/dependencies')])
                .then(([s, d]) => { setNetworkSummary(s.data); setNetworkDeps(d.data); })
                .catch(() => setNetworkSummary({ error: true }));
        }
        if (activeTab === 'Changes') {
            api.get('/oneagent/changes').then((res) => setChanges(res.data.changes || [])).catch(() => {});
        }
        if (activeTab === 'Diagnostics' && commands.length === 0) {
            api.get('/troubleshooting/commands', { params: { category: 'oneagent_host' } })
                .then((res) => setCommands(res.data.commands || [])).catch(() => {});
        }
    }, [activeTab, api, networkSummary, commands.length]);

    const openHost = useCallback(async (host) => {
        setSelectedHost(host);
        try {
            const res = await api.get(`/oneagent/hosts/${encodeURIComponent(host)}`);
            setHostDetail(res.data);
        } catch (e) {
            toast.error('Failed to load host detail');
        }
    }, [api]);

    const runDiagnostic = useCallback(async (commandId) => {
        if (!diagHost) { toast.warning('Enter a host first'); return; }
        setDiagRunning(true);
        try {
            const res = await api.post(`/troubleshooting/commands/${commandId}/run`, { params: { host: diagHost } });
            setDiagResult(res.data);
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'Diagnostic failed');
        } finally {
            setDiagRunning(false);
        }
    }, [api, diagHost]);

    return (
        <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Activity className="w-5 h-5 text-cyan-400" />OneAgent Explorer
                </h1>
                <Button size="sm" variant="outline" onClick={load}><RefreshCw className="w-3.5 h-3.5 mr-1" />Refresh</Button>
            </div>

            <div className="flex gap-1 border-b border-white/10 overflow-x-auto">
                {TABS.map((tab) => (
                    <button key={tab} onClick={() => setActiveTab(tab)}
                        className={`px-3 py-2 text-xs whitespace-nowrap border-b-2 ${activeTab === tab ? 'border-cyan-400 text-white' : 'border-transparent text-white/50 hover:text-white/80'}`}>
                        {tab}
                    </button>
                ))}
            </div>

            {activeTab === 'Overview' && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        {[
                            ['Agents', agents.length],
                            ['Healthy', health?.healthy_count ?? '—'],
                            ['Offline', health?.offline_count ?? '—'],
                            ['Processes', processes.length],
                            ['Containers', containers.length],
                        ].map(([label, value]) => (
                            <Card key={label} className="bg-white/5 border-white/10">
                                <CardContent className="p-3">
                                    <div className="text-[10px] text-white/50">{label}</div>
                                    <div className="text-lg font-semibold text-white">{value}</div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                    {health?.offline_agents?.length > 0 && (
                        <Card className="bg-white/5 border-white/10">
                            <CardHeader><CardTitle className="text-sm text-amber-300">Offline Agents</CardTitle></CardHeader>
                            <CardContent className="space-y-1">
                                {health.offline_agents.map((a) => (
                                    <div key={a.host} className="text-xs text-white/70 flex justify-between">
                                        <span>{a.host}</span><span className="text-white/40">{a.reason}</span>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeTab === 'Hosts' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Host</th><th className="text-left p-2">Environment</th>
                                    <th className="text-left p-2">Agent Version</th><th className="text-left p-2">Processes</th>
                                    <th className="text-left p-2">Last Seen</th></tr>
                            </thead>
                            <tbody>
                                {agents.map((a) => (
                                    <tr key={a.host} className="border-b border-white/5 hover:bg-white/5 cursor-pointer" onClick={() => openHost(a.host)}>
                                        <td className="p-2 text-white">{a.host}</td>
                                        <td className="p-2 text-white/60">{a.environment}</td>
                                        <td className="p-2 text-white/60">{a.agent_version}</td>
                                        <td className="p-2 text-white/60">{(a.services || []).length}</td>
                                        <td className="p-2 text-white/60">{a.last_seen ? new Date(a.last_seen).toLocaleString() : '—'}</td>
                                    </tr>
                                ))}
                                {!loading && agents.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-white/40">No agents reporting yet.</td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                    {selectedHost && hostDetail && (
                        <div className="p-3 border-t border-white/10 space-y-2">
                            <div className="text-sm text-white font-semibold">{selectedHost} — {hostDetail.status}</div>
                            <div className="text-xs text-white/50">{hostDetail.process_count} processes, {hostDetail.recent_metrics.length} recent metric points</div>
                            <div className="grid grid-cols-3 gap-2">
                                {hostDetail.recent_metrics.slice(0, 9).map((m, i) => (
                                    <div key={i} className="text-[10px] bg-black/30 rounded p-1.5">
                                        <div className="text-white/50">{m.name}</div>
                                        <div className="text-white font-mono">{m.value}{m.unit}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </Card>
            )}

            {activeTab === 'Processes' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Process</th><th className="text-left p-2">Runtime</th>
                                    <th className="text-left p-2">PID</th><th className="text-left p-2">Container</th>
                                    <th className="text-left p-2">Ports</th><th className="text-left p-2">Host</th><th className="text-left p-2">Status</th></tr>
                            </thead>
                            <tbody>
                                {processes.map((p) => (
                                    <tr key={p.id} className="border-b border-white/5">
                                        <td className="p-2 text-white">{p.name}</td>
                                        <td className="p-2 text-white/60">{p.technology}</td>
                                        <td className="p-2 text-white/60 font-mono">{p.metadata?.pid}</td>
                                        <td className="p-2 text-white/60 font-mono">{p.metadata?.container_id || '—'}</td>
                                        <td className="p-2 text-white/60">{(p.metadata?.ports || []).join(', ') || '—'}</td>
                                        <td className="p-2 text-white/60">{p.metadata?.host}</td>
                                        <td className="p-2"><Badge variant="outline" className="text-[10px]">{p.lifecycle_status}</Badge></td>
                                    </tr>
                                ))}
                                {!loading && processes.length === 0 && <tr><td colSpan={7} className="p-4 text-center text-white/40">
                                    No processes discovered yet — requires OneAgent V2 (pid/container_id are only sent by the updated agent).
                                </td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            {activeTab === 'Containers' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-0">
                        <table className="w-full text-xs">
                            <thead className="text-white/40 border-b border-white/10">
                                <tr><th className="text-left p-2">Container ID</th><th className="text-left p-2">Host</th><th className="text-left p-2">Status</th></tr>
                            </thead>
                            <tbody>
                                {containers.map((c) => (
                                    <tr key={c.id} className="border-b border-white/5">
                                        <td className="p-2 text-white font-mono">{c.name}</td>
                                        <td className="p-2 text-white/60">{c.metadata?.host}</td>
                                        <td className="p-2"><Badge variant="outline" className="text-[10px]">{c.lifecycle_status}</Badge></td>
                                    </tr>
                                ))}
                                {!loading && containers.length === 0 && <tr><td colSpan={3} className="p-4 text-center text-white/40">
                                    No containers discovered — requires the 'containers' opt-in plugin enabled on the agent, or no containerized processes on this host.
                                </td></tr>}
                            </tbody>
                        </table>
                    </CardContent>
                </Card>
            )}

            {activeTab === 'Network' && (
                <div className="space-y-3">
                    {networkSummary?.error ? <NotAvailable reason="network flow service unreachable" /> : !networkSummary ? (
                        <div className="text-xs text-white/40">Loading…</div>
                    ) : (
                        <>
                            <Card className="bg-white/5 border-white/10">
                                <CardHeader><CardTitle className="text-sm">Flow Summary (real, from OneAgent's netflow plugin)</CardTitle></CardHeader>
                                <CardContent><pre className="text-[10px] text-white/60 overflow-x-auto">{JSON.stringify(networkSummary, null, 2)}</pre></CardContent>
                            </Card>
                            <Card className="bg-white/5 border-white/10">
                                <CardHeader><CardTitle className="text-sm">Network Dependencies</CardTitle></CardHeader>
                                <CardContent><pre className="text-[10px] text-white/60 overflow-x-auto">{JSON.stringify(networkDeps, null, 2)}</pre></CardContent>
                            </Card>
                        </>
                    )}
                </div>
            )}

            {activeTab === 'Changes' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-3 space-y-2">
                        {changes.map((c) => (
                            <div key={c.id} className="text-xs border-l-2 border-white/10 pl-2 py-1">
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline" className="text-[10px]">{c.change_type}</Badge>
                                    <span className="text-white/40">{c.host}</span>
                                    <span className="text-white/30">{new Date(c.detected_at).toLocaleString()}</span>
                                </div>
                                <div className="text-white/70 mt-0.5">{c.message}</div>
                            </div>
                        ))}
                        {changes.length === 0 && <div className="text-white/40 text-xs">No changes detected yet.</div>}
                    </CardContent>
                </Card>
            )}

            {activeTab === 'Diagnostics' && (
                <div className="space-y-3">
                    <div className="flex items-center gap-2">
                        <Input className="w-64 h-8 text-xs bg-muted/30" placeholder="Host (e.g. web-01)" value={diagHost} onChange={(e) => setDiagHost(e.target.value)} />
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {commands.map((c) => (
                            <Button key={c.id} size="sm" variant="outline" className="h-7 text-[11px]" disabled={diagRunning} onClick={() => runDiagnostic(c.id)}>
                                <Stethoscope className="w-3 h-3 mr-1" />{c.label}
                            </Button>
                        ))}
                    </div>
                    <p className="text-[10px] text-white/40">Reads telemetry OneAgent already collected — never a live remote probe (OneAgent has no inbound command channel by design).</p>
                    {diagResult && (
                        <Card className="bg-white/5 border-white/10">
                            <CardContent className="p-3">
                                {diagResult.output?.available === false ? (
                                    <NotAvailable reason={diagResult.output.reason} />
                                ) : (
                                    <pre className="text-[10px] text-white/70 overflow-x-auto">{JSON.stringify(diagResult.output, null, 2)}</pre>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeTab === 'Agent Health' && (
                <Card className="bg-white/5 border-white/10">
                    <CardContent className="p-3 space-y-2">
                        <div className="grid grid-cols-3 gap-3 mb-3">
                            <div><div className="text-[10px] text-white/50">Total</div><div className="text-lg text-white">{health?.total_agents ?? '—'}</div></div>
                            <div><div className="text-[10px] text-emerald-400">Healthy</div><div className="text-lg text-emerald-300">{health?.healthy_count ?? '—'}</div></div>
                            <div><div className="text-[10px] text-red-400">Offline</div><div className="text-lg text-red-300">{health?.offline_count ?? '—'}</div></div>
                        </div>
                        {(health?.healthy_hosts || []).map((h) => (
                            <div key={h} className="text-xs flex items-center gap-2 text-white/70"><CheckCircle2 className="w-3 h-3 text-emerald-400" />{h}</div>
                        ))}
                        {(health?.offline_agents || []).map((a) => (
                            <div key={a.host} className="text-xs flex items-center gap-2 text-white/70"><XCircle className="w-3 h-3 text-red-400" />{a.host} — {a.reason}</div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

export default OneAgentExplorerPage;
