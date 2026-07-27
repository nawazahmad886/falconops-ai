import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Box, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import ResourcesFilterPanel from '../components/resources/ResourcesFilterPanel';
import ResourcesGrid from '../components/resources/ResourcesGrid';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;
const DEFAULT_FILTERS = {};

function buildQuery(filters) {
    const params = new URLSearchParams();
    if (filters.category) params.set('category', filters.category);
    if (filters.technology) params.set('technology', filters.technology);
    if (filters.environment) params.set('environment', filters.environment);
    if (filters.lifecycle_status) params.set('lifecycle_status', filters.lifecycle_status);
    if (filters.owner) params.set('owner', filters.owner);
    if (filters.search) params.set('search', filters.search);
    if (filters.include_retired) params.set('include_retired', 'true');
    (filters.tags || []).forEach((t) => params.append('tags', t));
    params.set('limit', '200');
    return params.toString();
}

export default function ResourceExplorerPage() {
    const navigate = useNavigate();
    const [filters, setFilters] = useState(DEFAULT_FILTERS);
    const [resources, setResources] = useState([]);
    const [total, setTotal] = useState(0);
    const [facets, setFacets] = useState(null);
    const [loading, setLoading] = useState(true);
    const [connected, setConnected] = useState(false);
    const [syncing, setSyncing] = useState(false);

    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectDelayRef = useRef(RECONNECT_BASE_MS);
    const closedByUsRef = useRef(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const qs = buildQuery(filters);
            const [listRes, facetsRes] = await Promise.all([
                fetch(`${API}/api/resources?${qs}`, { headers: authHeaders() }),
                fetch(`${API}/api/resources/facets`, { headers: authHeaders() }),
            ]);
            if (!listRes.ok) throw new Error(await listRes.text());
            const listData = await listRes.json();
            setResources(listData.resources || []);
            setTotal(listData.total || 0);
            if (facetsRes.ok) setFacets(await facetsRes.json());
        } catch (e) {
            toast.error('Failed to load Resource Explorer data');
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // Live feed — same capped exponential-backoff reconnect pattern as
    // ProblemsPage.js/LiveCallFlowPage.js. On any resource.* event, refetch
    // rather than patching one row into a possibly-stale filtered page.
    useEffect(() => {
        closedByUsRef.current = false;

        const connect = () => {
            const token = localStorage.getItem('falconToken');
            if (!token) return;
            let wsUrl;
            try {
                const u = new URL(API);
                const scheme = u.protocol === 'https:' ? 'wss:' : 'ws:';
                wsUrl = `${scheme}//${u.host}/api/resources/live?token=${encodeURIComponent(token)}`;
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
                    if (msg.type?.startsWith('resource.')) {
                        fetchAll();
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
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fetchAll]);

    const runSync = async () => {
        setSyncing(true);
        try {
            const r = await fetch(`${API}/api/resources/sync`, { method: 'POST', headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Resource sync triggered');
            fetchAll();
        } catch (e) {
            toast.error(`Sync failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setSyncing(false);
        }
    };

    const runAction = useCallback(async (resource, action) => {
        if (action === 'open-alerts') {
            navigate(`/resources/${encodeURIComponent(resource.id)}?tab=alerts`);
            return;
        }
        try {
            const r = await fetch(`${API}/api/resources/${encodeURIComponent(resource.id)}/${action}`, {
                method: 'POST', headers: authHeaders(),
                body: action === 'retire' ? JSON.stringify({ reason: 'Retired from Resource Explorer' }) : undefined,
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`${resource.name}: ${action.replace('-', ' ')} done`);
            fetchAll();
        } catch (e) {
            toast.error(`${action} failed: ${e.message?.slice(0, 200)}`);
        }
    }, [fetchAll, navigate]);

    return (
        <div className="p-6 space-y-4" data-testid="resource-explorer-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Box className="w-6 h-6 text-cyan-400" />
                        Resource Explorer
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Central inventory across OneAgent-monitored hosts, databases, and connector-discovered resources ({total} total)
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge className={connected
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-red-500/15 text-red-300 border border-red-500/30'}>
                        {connected ? <Wifi className="w-3.5 h-3.5 mr-1.5" /> : <WifiOff className="w-3.5 h-3.5 mr-1.5" />}
                        {connected ? 'Live' : 'Reconnecting…'}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={runSync} disabled={syncing} data-testid="sync-resources">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${syncing ? 'animate-spin' : ''}`} /> Sync now
                    </Button>
                    <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading} data-testid="refresh-resources">
                        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                <div className="lg:col-span-1 bg-black/40 border border-white/10 rounded-lg">
                    <ResourcesFilterPanel filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} facets={facets} />
                </div>
                <div className="lg:col-span-4">
                    <ResourcesGrid
                        resources={resources}
                        loading={loading}
                        onSelectResource={(r) => navigate(`/resources/${encodeURIComponent(r.id)}`)}
                        onAction={runAction}
                    />
                </div>
            </div>
        </div>
    );
}
