import React, { useEffect, useState, useCallback } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Radar, RefreshCw, Server, Boxes, Clock, Download, CircleDot } from 'lucide-react';
import { Link } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const ONLINE_WINDOW_MS = 3 * 60 * 1000; // heartbeat every 60s → online if seen <3min

function isOnline(agent) {
    if (!agent.last_seen) return false;
    return Date.now() - new Date(agent.last_seen).getTime() < ONLINE_WINDOW_MS;
}

function timeAgo(iso) {
    if (!iso) return '–';
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
}

const RUNTIME_COLORS = {
    nodejs: 'border-green-500/30 text-green-300',
    python: 'border-blue-500/30 text-blue-300',
    java: 'border-orange-500/30 text-orange-300',
    go: 'border-cyan-500/30 text-cyan-300',
    dotnet: 'border-violet-500/30 text-violet-300',
    native: 'border-white/20 text-white/60',
};

function AgentRow({ agent }) {
    const online = isOnline(agent);
    const services = agent.services || [];
    return (
        <Card data-testid={`fleet-agent-${agent.host}`}
              className={`bg-black/40 border ${online ? 'border-emerald-500/25' : 'border-white/10'}`}>
            <CardContent className="p-4 flex flex-wrap items-start gap-4">
                <div className="flex items-center gap-3 min-w-[220px]">
                    <div className={`p-2 rounded-lg ${online ? 'bg-emerald-500/15' : 'bg-white/5'}`}>
                        <Server className={`w-5 h-5 ${online ? 'text-emerald-300' : 'text-white/40'}`} />
                    </div>
                    <div>
                        <div className="text-sm font-semibold text-white flex items-center gap-2">
                            {agent.host}
                            <CircleDot className={`w-3 h-3 ${online ? 'text-emerald-400 animate-pulse' : 'text-white/25'}`} />
                        </div>
                        <div className="text-[11px] text-white/40">
                            v{agent.agent_version || '?'} · {agent.environment || 'unknown'} · key: {agent.api_key_name || '–'}
                        </div>
                    </div>
                </div>
                <div className="flex-1 min-w-[220px]">
                    <div className="text-[10px] uppercase tracking-widest text-white/35 mb-1.5 flex items-center gap-1">
                        <Boxes className="w-3 h-3" /> Discovered services ({services.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {services.length === 0 && <span className="text-xs text-white/30">none reported yet</span>}
                        {services.slice(0, 12).map((s, i) => (
                            <Badge key={i} variant="outline"
                                   className={`text-[10px] ${RUNTIME_COLORS[s.runtime] || RUNTIME_COLORS.native}`}>
                                {s.name} · {s.runtime}
                            </Badge>
                        ))}
                        {services.length > 12 && (
                            <Badge variant="outline" className="text-[10px] border-white/15 text-white/40">
                                +{services.length - 12} more
                            </Badge>
                        )}
                    </div>
                </div>
                <div className="text-right min-w-[110px] ml-auto">
                    <Badge className={`text-[10px] ${online ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/10 text-white/40'}`}
                           data-testid={`fleet-status-${agent.host}`}>
                        {online ? 'ONLINE' : 'OFFLINE'}
                    </Badge>
                    <div className="text-[11px] text-white/40 mt-1.5 flex items-center justify-end gap-1">
                        <Clock className="w-3 h-3" /> {timeAgo(agent.last_seen)}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

export default function OneAgentFleetPage() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const r = await fetch(`${API}/api/oneagent/agents`, { headers: headers() });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            setAgents(data.agents || []);
        } catch {
            if (!silent) toast.error('Failed to load agent fleet');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const t = setInterval(() => load(true), 30000);
        return () => clearInterval(t);
    }, [load]);

    const online = agents.filter(isOnline).length;
    const totalServices = agents.reduce((n, a) => n + (a.services || []).length, 0);

    return (
        <div data-testid="oneagent-fleet-page" className="p-4 lg:p-6 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h1 className="text-xl font-bold text-white flex items-center gap-2">
                        <Radar className="w-5 h-5 text-cyan-300" /> OneAgent Fleet
                    </h1>
                    <p className="text-xs text-white/40 mt-0.5">
                        Every host running FalconOpsAI OneAgent — heartbeats, versions & auto-discovered services.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" className="border-white/15 text-white/70 h-8 text-xs"
                            onClick={() => load()} data-testid="fleet-refresh-btn">
                        <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Link to="/download">
                        <Button size="sm" className="h-8 text-xs bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 hover:bg-cyan-500/30"
                                data-testid="fleet-install-btn">
                            <Download className="w-3.5 h-3.5 mr-1" /> Install OneAgent
                        </Button>
                    </Link>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-3 max-w-xl">
                {[
                    { label: 'Agents', value: agents.length, tid: 'fleet-stat-total' },
                    { label: 'Online', value: online, tid: 'fleet-stat-online', cls: 'text-emerald-300' },
                    { label: 'Services discovered', value: totalServices, tid: 'fleet-stat-services' },
                ].map((s) => (
                    <Card key={s.tid} className="bg-black/40 border-white/10" data-testid={s.tid}>
                        <CardContent className="p-3">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">{s.label}</div>
                            <div className={`text-xl font-bold tabular-nums ${s.cls || 'text-white'}`}>{s.value}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="space-y-3">
                {!loading && agents.length === 0 && (
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-10 text-center text-white/40 space-y-3">
                            <Radar className="w-10 h-10 mx-auto text-cyan-500/40" />
                            <p className="text-sm">No agents connected yet. Install OneAgent on a host and it will appear here within a minute.</p>
                        </CardContent>
                    </Card>
                )}
                {agents.map(a => <AgentRow key={a.id || a.host} agent={a} />)}
            </div>
        </div>
    );
}
