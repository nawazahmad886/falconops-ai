import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
    Radio, Shield, AlertTriangle, Users, Activity, RefreshCw,
    Wifi, WifiOff, Clock, Target, Eye, Zap, Server,
} from 'lucide-react';

const SEVERITY_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    low: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
};

const TYPE_ICONS = {
    threat: Target,
    security_event: Shield,
    remediation: Zap,
};

export default function SOCLiveFeedPage() {
    const { api } = useAuth();
    const [feed, setFeed] = useState([]);
    const [wsConnected, setWsConnected] = useState(false);
    const [stats, setStats] = useState(null);
    const [paused, setPaused] = useState(false);
    const wsRef = useRef(null);
    const feedRef = useRef(feed);
    feedRef.current = feed;

    const fetchInitialFeed = useCallback(async () => {
        try {
            const res = await api.get('/soc/feed?limit=50');
            setFeed(res.data || []);
        } catch (e) { console.error(e); }
    }, [api]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await api.get('/soc/stats');
            setStats(res.data);
        } catch (e) { console.error(e); }
    }, [api]);

    // WebSocket connection
    useEffect(() => {
        const backendUrl = process.env.REACT_APP_BACKEND_URL || '';
        const wsUrl = backendUrl.replace(/^http/, 'ws') + '/ws/soc-feed';
        let ws;
        try {
            ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => setWsConnected(true);
            ws.onclose = () => setWsConnected(false);
            ws.onerror = () => setWsConnected(false);

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'initial') {
                        setFeed(msg.data || []);
                    } else {
                        setFeed(prev => [msg, ...prev].slice(0, 200));
                    }
                } catch (e) { console.error('WS parse error', e); }
            };
        } catch (e) {
            console.error('WS connection failed', e);
        }

        return () => {
            if (ws) ws.close();
        };
    }, []);

    useEffect(() => {
        fetchInitialFeed();
        fetchStats();
        const interval = setInterval(fetchStats, 10000);
        return () => clearInterval(interval);
    }, [fetchInitialFeed, fetchStats]);

    const severityCounts = feed.reduce((acc, item) => {
        const sev = item.data?.severity || item.severity || 'info';
        acc[sev] = (acc[sev] || 0) + 1;
        return acc;
    }, {});

    return (
        <div className="space-y-6" data-testid="soc-live-feed-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15">
                            <Radio className="w-6 h-6 text-red-400" />
                        </div>
                        SOC Live Feed
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Real-time Security Operations Center threat feed</p>
                </div>
                <div className="flex items-center gap-3">
                    <Badge
                        data-testid="ws-status-badge"
                        className={wsConnected
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : 'bg-red-500/15 text-red-400 border-red-500/30'
                        }
                    >
                        {wsConnected ? <Wifi className="w-3 h-3 mr-1" /> : <WifiOff className="w-3 h-3 mr-1" />}
                        {wsConnected ? 'Connected' : 'Disconnected'}
                    </Badge>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPaused(!paused)}
                        className="border-white/10 text-xs"
                        data-testid="pause-feed-btn"
                    >
                        {paused ? <Activity className="w-3 h-3 mr-1" /> : <Clock className="w-3 h-3 mr-1" />}
                        {paused ? 'Resume' : 'Pause'}
                    </Button>
                    <Button variant="outline" size="sm" onClick={fetchInitialFeed} className="border-white/10 text-xs" data-testid="refresh-feed-btn">
                        <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Stats Bar */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><Activity className="w-4 h-4 text-blue-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Feed Items</p>
                            <p className="text-lg font-bold text-white" data-testid="feed-count">{feed.length}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><Users className="w-4 h-4 text-emerald-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">SOC Clients</p>
                            <p className="text-lg font-bold text-white" data-testid="client-count">{stats?.connected_clients ?? 0}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15"><AlertTriangle className="w-4 h-4 text-red-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Critical</p>
                            <p className="text-lg font-bold text-red-400">{severityCounts.critical || 0}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-orange-500/15"><Shield className="w-4 h-4 text-orange-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">High</p>
                            <p className="text-lg font-bold text-orange-400">{severityCounts.high || 0}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/15"><Eye className="w-4 h-4 text-amber-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Warnings</p>
                            <p className="text-lg font-bold text-amber-400">{severityCounts.warning || 0}</p>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Live Feed */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-3 border-b border-white/5">
                    <CardTitle className="text-base flex items-center gap-2">
                        <Radio className="w-4 h-4 text-red-400" />
                        Live Threat Feed
                        <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse ml-2" />
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="max-h-[600px] overflow-y-auto divide-y divide-white/5" data-testid="feed-list">
                        {feed.length === 0 ? (
                            <div className="p-8 text-center text-white/40">
                                <Radio className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                <p>No feed items yet. Events will appear here in real-time.</p>
                            </div>
                        ) : feed.map((item, i) => {
                            const data = item.data || item;
                            const type = item.type || 'threat';
                            const sev = data.severity || 'info';
                            const Icon = TYPE_ICONS[type] || Shield;
                            const sevStyle = SEVERITY_STYLES[sev] || SEVERITY_STYLES.info;

                            return (
                                <div key={i} className="flex items-start gap-3 p-3 hover:bg-white/[0.02] transition-colors" data-testid={`feed-item-${i}`}>
                                    <div className={`p-1.5 rounded-lg ${sevStyle.split(' ')[0]}`}>
                                        <Icon className={`w-4 h-4 ${sevStyle.split(' ')[1]}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <Badge variant="outline" className={`text-[9px] ${sevStyle}`}>{sev}</Badge>
                                            <Badge variant="outline" className="text-[9px] text-white/50 border-white/10">{type}</Badge>
                                            {data.source_ip && <span className="text-[10px] text-white/30 font-mono">{data.source_ip}</span>}
                                        </div>
                                        <p className="text-sm text-white/80 mt-1 truncate">{data.message || data.threat_type || data.action_name || 'Security event'}</p>
                                        {data.user && <p className="text-xs text-white/30 mt-0.5">User: {data.user}</p>}
                                    </div>
                                    <span className="text-[10px] text-white/25 whitespace-nowrap">
                                        {data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : ''}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
