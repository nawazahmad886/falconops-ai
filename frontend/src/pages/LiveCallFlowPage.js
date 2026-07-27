import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Zap, Wifi, WifiOff, RefreshCw, ArrowRight, CheckCircle2, XCircle } from 'lucide-react';
import ForceServiceMap from '../components/ForceServiceMap';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const GRAPH_REFRESH_MS = 60_000;
const RECENT_EVENTS_MAX = 20;
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

export default function LiveCallFlowPage() {
    const [graph, setGraph] = useState({ nodes: [], edges: [] });
    const [loading, setLoading] = useState(true);
    const [connected, setConnected] = useState(false);
    const [recentEvents, setRecentEvents] = useState([]);

    const mapRef = useRef(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectDelayRef = useRef(RECONNECT_BASE_MS);
    const closedByUsRef = useRef(false);

    const fetchGraph = useCallback(async () => {
        try {
            const r = await fetch(`${API}/api/traces/services/dependencies?hours=24`, { headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            const d = await r.json();
            setGraph({ nodes: d.nodes || [], edges: d.edges || [] });
        } catch (e) {
            toast.error('Failed to load service dependency graph');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchGraph();
        const interval = setInterval(fetchGraph, GRAPH_REFRESH_MS);
        return () => clearInterval(interval);
    }, [fetchGraph]);

    // Live WebSocket feed — one message per real cross-service span, with
    // capped exponential-backoff auto-reconnect (this feature's whole value
    // is continuous liveness, worth the extra complexity vs. other live
    // pages in this app that just show "disconnected — reload").
    useEffect(() => {
        closedByUsRef.current = false;

        const connect = () => {
            const token = localStorage.getItem('falconToken');
            if (!token) return;
            let wsUrl;
            try {
                const u = new URL(API);
                const scheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
                wsUrl = `${scheme}//${u.host}/api/traces/live?token=${encodeURIComponent(token)}`;
            } catch (_e) {
                return;
            }

            let ws;
            try {
                ws = new WebSocket(wsUrl);
            } catch (_e) {
                return;
            }
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                reconnectDelayRef.current = RECONNECT_BASE_MS;
            };
            ws.onmessage = (evt) => {
                try {
                    const msg = JSON.parse(evt.data);
                    if (msg.type === 'call_flow.event') {
                        mapRef.current?.pushCallEvent(msg);
                        setRecentEvents((prev) => [msg, ...prev].slice(0, RECENT_EVENTS_MAX));
                    }
                } catch (_e) { /* ignore malformed message */ }
            };
            const scheduleReconnect = () => {
                setConnected(false);
                if (closedByUsRef.current) return;
                reconnectTimerRef.current = setTimeout(connect, reconnectDelayRef.current);
                reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, RECONNECT_MAX_MS);
            };
            ws.onclose = scheduleReconnect;
            ws.onerror = () => { try { ws.close(); } catch (_e) { /* onclose handles reconnect */ } };
        };

        connect();
        return () => {
            closedByUsRef.current = true;
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            try { wsRef.current?.close(); } catch (_e) { /* ignore */ }
        };
    }, []);

    return (
        <div className="p-6 space-y-5" data-testid="live-call-flow-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Zap className="w-6 h-6 text-cyan-400" />
                        Live Call Flow
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Real service-to-service calls animating as they happen, sourced from OTLP trace ingestion
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge className={connected
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-red-500/15 text-red-300 border border-red-500/30'}>
                        {connected ? <Wifi className="w-3.5 h-3.5 mr-1.5" /> : <WifiOff className="w-3.5 h-3.5 mr-1.5" />}
                        {connected ? 'Live' : 'Reconnecting…'}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={fetchGraph} disabled={loading} data-testid="refresh-call-flow">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh graph
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <Card className="bg-black/40 border-white/10 lg:col-span-3">
                    <CardContent className="p-4">
                        <ForceServiceMap ref={mapRef} nodes={graph.nodes} edges={graph.edges} height={560} />
                    </CardContent>
                </Card>

                <Card className="bg-black/40 border-white/10 lg:col-span-1">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white/70">Recent calls</CardTitle>
                    </CardHeader>
                    <CardContent className="p-3 pt-0 space-y-1.5 max-h-[520px] overflow-y-auto" data-testid="recent-call-events">
                        {recentEvents.length === 0 ? (
                            <div className="text-xs text-white/40 py-6 text-center">Waiting for live calls…</div>
                        ) : recentEvents.map((evt, i) => (
                            <div key={`${evt.trace_id}-${evt.span_id}-${i}`}
                                className="flex items-center gap-1.5 text-[11px] px-2 py-1.5 rounded bg-white/[0.03] border border-white/5">
                                {evt.status === 'ERROR'
                                    ? <XCircle className="w-3 h-3 text-red-400 shrink-0" />
                                    : <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />}
                                <span className="text-white/80 truncate">{evt.source}</span>
                                <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                                <span className="text-white/80 truncate">{evt.target}</span>
                                <span className="ml-auto text-white/40 font-mono shrink-0">{Math.round(evt.duration_ms)}ms</span>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
