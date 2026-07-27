import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    ArrowLeft, RefreshCw, Box, HeartPulse, LineChart, Bell, Network, Settings,
    Sparkles, Wrench, ChevronRight, ArrowRight, ArrowDownRight, ArrowUpRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const SEVERITY_BADGE = {
    critical: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    high: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    low: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    info: 'bg-white/10 text-white/50 border-white/20',
};

const HEALTH_COLOR = (score) => {
    if (score == null) return 'text-white/40';
    if (score >= 80) return 'text-emerald-400';
    if (score >= 50) return 'text-amber-400';
    return 'text-red-400';
};

const Spinner = () => <div className="flex justify-center py-10"><RefreshCw className="w-5 h-5 text-white/40 animate-spin" /></div>;

const NotAvailable = ({ reason }) => (
    <div className="p-4 text-xs text-white/40 bg-white/[0.02] border border-white/5 rounded-lg">
        Not available{reason ? ` — ${reason}` : ''}.
    </div>
);

// ───────── Overview Tab ─────────
const OverviewTab = ({ resource }) => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-black/40 border-white/10">
            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm">Identity</CardTitle></CardHeader>
            <CardContent className="p-4 space-y-2 text-xs">
                <Row label="Name" value={resource.name} />
                <Row label="Category" value={resource.resource_category} capitalize />
                <Row label="Technology" value={resource.technology} />
                <Row label="Environment" value={resource.environment} capitalize />
                <Row label="Owner" value={resource.owner || 'Unassigned'} />
                <Row label="Lifecycle status" value={resource.lifecycle_status} capitalize />
                <Row label="Discovered by" value={resource.discovered_by} />
                <Row label="Last seen" value={resource.last_seen ? new Date(resource.last_seen).toLocaleString() : '—'} />
            </CardContent>
        </Card>
        <Card className="bg-black/40 border-white/10">
            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm">Tags &amp; source references</CardTitle></CardHeader>
            <CardContent className="p-4 space-y-3 text-xs">
                <div className="flex flex-wrap gap-1.5">
                    {(resource.tags || []).length === 0 && <span className="text-white/30">No tags</span>}
                    {(resource.tags || []).map((t) => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.05] text-white/50 border border-white/10">{t}</span>
                    ))}
                </div>
                <div className="space-y-1">
                    {(resource.source_refs || []).map((sr, i) => (
                        <div key={i} className="flex items-center gap-2 text-white/50">
                            <Badge className="text-[9px] bg-white/5 border-white/10">{sr.collection}</Badge>
                            <span className="font-mono truncate">{sr.id}</span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    </div>
);

const Row = ({ label, value, capitalize }) => (
    <div className="flex items-center justify-between">
        <span className="text-white/40">{label}</span>
        <span className={`text-white/80 ${capitalize ? 'capitalize' : ''}`}>{value ?? '—'}</span>
    </div>
);

// ───────── Health Tab ─────────
const HealthTab = ({ resource }) => {
    const health = resource.enrichment?.health;
    if (!health) return <NotAvailable reason={resource.enrichment?.health_not_available_reason} />;
    return (
        <Card className="bg-black/40 border-white/10" data-testid="health-tab-card">
            <CardContent className="p-4 flex items-center gap-6">
                <div>
                    <div className="text-[10px] uppercase tracking-widest text-white/50">Health score</div>
                    <div className={`mt-1 text-2xl font-semibold tabular-nums ${HEALTH_COLOR(health.score)}`}>
                        {health.score != null ? `${health.score}/100` : 'n/a'}
                    </div>
                </div>
                <div>
                    <div className="text-[10px] uppercase tracking-widest text-white/50">Status</div>
                    <Badge className="mt-1 capitalize">{health.status || 'n/a'}</Badge>
                </div>
                <div>
                    <div className="text-[10px] uppercase tracking-widest text-white/50">As of</div>
                    <div className="mt-1 text-xs text-white/60">{health.as_of ? new Date(health.as_of).toLocaleString() : '—'}</div>
                </div>
            </CardContent>
        </Card>
    );
};

// ───────── Metrics Tab ─────────
const MetricsTab = ({ resourceId }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/metrics?hours=24`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [resourceId]);

    if (loading) return <Spinner />;
    if (!data?.metrics?.length) return <NotAvailable reason={data?.reason} />;

    return (
        <Card className="bg-black/40 border-white/10" data-testid="metrics-tab-card">
            <CardContent className="p-0">
                <div className="divide-y divide-white/5 max-h-96 overflow-auto">
                    {data.metrics.slice(0, 100).map((m, i) => (
                        <div key={i} className="grid grid-cols-4 gap-2 px-4 py-2 text-xs">
                            <span className="text-white/40">{m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : '—'}</span>
                            <span className="text-white/70 tabular-nums">cpu {m.cpu_usage ?? m.metrics?.cpu_usage ?? '—'}</span>
                            <span className="text-white/70 tabular-nums">mem {m.memory_usage ?? m.metrics?.memory_usage ?? '—'}</span>
                            <span className="text-white/70 tabular-nums">disk {m.disk_usage ?? m.metrics?.disk_usage ?? '—'}</span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// ───────── Alerts Tab ─────────
const AlertsTab = ({ resourceId }) => {
    const [alerts, setAlerts] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/alerts`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setAlerts(d.alerts || []); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [resourceId]);

    if (loading) return <Spinner />;
    if (!alerts?.length) return <div className="p-10 text-center text-white/40 text-sm"><Bell className="w-8 h-8 mx-auto mb-2 opacity-40" />No related alerts.</div>;

    return (
        <Card className="bg-black/40 border-white/10" data-testid="alerts-tab-card">
            <CardContent className="p-0 divide-y divide-white/5">
                {alerts.map((a) => (
                    <div key={a.id} className="p-3 flex items-center gap-3" data-testid={`related-alert-${a.id}`}>
                        <Badge className={`text-[10px] capitalize ${SEVERITY_BADGE[a.severity] || SEVERITY_BADGE.info}`}>{a.severity}</Badge>
                        <span className="text-sm text-white/80 truncate flex-1">{a.title || '(untitled)'}</span>
                        <span className="text-[11px] text-white/40 capitalize">{a.status}</span>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
};

// ───────── Dependencies Tab ─────────
const DependenciesTab = ({ resourceId, resourceName }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/dependencies`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [resourceId]);

    if (loading) return <Spinner />;
    if (!data) return null;

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="bg-black/40 border-white/10" data-testid="upstream-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><ArrowUpRight className="w-4 h-4 text-white/50" /> Depends on</CardTitle></CardHeader>
                <CardContent className="p-3 space-y-1.5">
                    {(data.upstream_dependencies || []).length === 0 && <p className="text-xs text-white/30 p-2">None observed</p>}
                    {(data.upstream_dependencies || []).map((e, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-white/[0.02]">
                            <span className="text-white/50">{resourceName}</span>
                            <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                            <span className="text-white/70 truncate">{e.service?.name}</span>
                        </div>
                    ))}
                </CardContent>
            </Card>
            <Card className="bg-black/40 border-white/10" data-testid="downstream-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><ArrowDownRight className="w-4 h-4 text-white/50" /> Depended on by</CardTitle></CardHeader>
                <CardContent className="p-3 space-y-1.5">
                    {(data.downstream_dependents || []).length === 0 && <p className="text-xs text-white/30 p-2">None observed</p>}
                    {(data.downstream_dependents || []).map((e, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-white/[0.02]">
                            <span className="text-white/70 truncate">{e.service?.name}</span>
                            <ArrowRight className="w-3 h-3 text-white/30 shrink-0" />
                            <span className="text-white/50">{resourceName}</span>
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    );
};

// ───────── Configuration Tab ─────────
const ConfigurationTab = ({ resourceId }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/configuration`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setData(d); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, [resourceId]);

    if (loading) return <Spinner />;
    const entries = Object.entries(data?.configuration || {}).filter(([, v]) => v !== null && v !== undefined && v !== '');

    return (
        <Card className="bg-black/40 border-white/10" data-testid="configuration-tab-card">
            {data?.configuration_note && (
                <div className="p-3 text-xs text-amber-300/80 bg-amber-500/[0.05] border-b border-amber-500/10">{data.configuration_note}</div>
            )}
            <CardContent className="p-4 space-y-1.5 text-xs">
                {entries.length === 0 && <p className="text-white/30">No configuration metadata recorded.</p>}
                {entries.map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                        <span className="text-white/40">{k}</span>
                        <span className="text-white/80 font-mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
};

// ───────── AI Insights Tab ─────────
const AIInsightsTab = ({ resource }) => {
    const { risk, risk_not_available_reason, predicted_failure, predicted_failure_not_available_reason } = resource.enrichment || {};
    return (
        <div className="space-y-4">
            <Card className="bg-black/40 border-white/10" data-testid="risk-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><Sparkles className="w-4 h-4 text-violet-400" /> Risk / blast radius</CardTitle></CardHeader>
                <CardContent className="p-4">
                    {risk ? (
                        <pre className="text-xs text-white/70 whitespace-pre-wrap font-mono">{JSON.stringify(risk, null, 2)}</pre>
                    ) : <NotAvailable reason={risk_not_available_reason} />}
                </CardContent>
            </Card>
            <Card className="bg-black/40 border-white/10" data-testid="predicted-failure-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><LineChart className="w-4 h-4 text-cyan-400" /> Predicted failure</CardTitle></CardHeader>
                <CardContent className="p-4">
                    {predicted_failure ? (
                        <pre className="text-xs text-white/70 whitespace-pre-wrap font-mono">{JSON.stringify(predicted_failure, null, 2)}</pre>
                    ) : <NotAvailable reason={predicted_failure_not_available_reason} />}
                </CardContent>
            </Card>
        </div>
    );
};

// ───────── Automation / Runbooks Tab ─────────
const AutomationTab = ({ resourceId }) => {
    const [runbooks, setRunbooks] = useState([]);
    const [selected, setSelected] = useState('');
    const [loading, setLoading] = useState(true);
    const [executing, setExecuting] = useState(false);
    const [restartNote, setRestartNote] = useState(null);

    useEffect(() => {
        let alive = true;
        fetch(`${API}/api/runbooks`, { headers: authHeaders() })
            .then((r) => r.json())
            .then((d) => { if (alive) { setRunbooks(Array.isArray(d) ? d : []); setLoading(false); } })
            .catch(() => alive && setLoading(false));
        return () => { alive = false; };
    }, []);

    const execute = async () => {
        if (!selected) return;
        setExecuting(true);
        try {
            const r = await fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/execute-runbook`, {
                method: 'POST', headers: authHeaders(), body: JSON.stringify({ runbook_id: selected }),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Runbook execution started');
        } catch (e) {
            toast.error(`Execution failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setExecuting(false);
        }
    };

    const restartAgent = async () => {
        try {
            const r = await fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}/restart-agent`, { method: 'POST', headers: authHeaders() });
            if (!r.ok) throw new Error(await r.text());
            setRestartNote(await r.json());
        } catch (e) {
            toast.error(`Restart-agent lookup failed: ${e.message?.slice(0, 200)}`);
        }
    };

    if (loading) return <Spinner />;

    return (
        <div className="space-y-4">
            <Card className="bg-black/40 border-white/10" data-testid="restart-agent-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><Wrench className="w-4 h-4 text-amber-400" /> Restart agent</CardTitle></CardHeader>
                <CardContent className="p-4 space-y-2">
                    <Button variant="outline" size="sm" onClick={restartAgent} data-testid="restart-agent-btn">Get restart instruction</Button>
                    {restartNote && (
                        <div className="text-xs space-y-1 mt-2">
                            {restartNote.instruction && <code className="block bg-black/50 p-2 rounded text-emerald-300">{restartNote.instruction}</code>}
                            <p className="text-white/40">{restartNote.note}</p>
                        </div>
                    )}
                </CardContent>
            </Card>
            <Card className="bg-black/40 border-white/10" data-testid="execute-runbook-card">
                <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><Wrench className="w-4 h-4 text-cyan-400" /> Execute runbook</CardTitle></CardHeader>
                <CardContent className="p-4 space-y-2">
                    {runbooks.length === 0 ? (
                        <p className="text-xs text-white/30">No runbooks defined yet.</p>
                    ) : (
                        <div className="flex gap-2">
                            <Select value={selected} onValueChange={setSelected}>
                                <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10 flex-1" data-testid="runbook-select">
                                    <SelectValue placeholder="Select a runbook" />
                                </SelectTrigger>
                                <SelectContent>
                                    {runbooks.map((rb) => <SelectItem key={rb.id} value={rb.id}>{rb.name}</SelectItem>)}
                                </SelectContent>
                            </Select>
                            <Button size="sm" onClick={execute} disabled={!selected || executing} data-testid="execute-runbook-btn">
                                {executing ? 'Executing...' : 'Execute'}
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

// ───────── Main Page ─────────
export default function ResourceDetailPage() {
    const { resourceId } = useParams();
    const [searchParams] = useSearchParams();
    const [resource, setResource] = useState(null);
    const [loading, setLoading] = useState(true);

    const loadResource = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/api/resources/${encodeURIComponent(resourceId)}`, { headers: authHeaders() });
            if (r.ok) setResource(await r.json());
            else toast.error('Resource not found');
        } catch (e) {
            toast.error('Failed to load resource');
        }
        setLoading(false);
    }, [resourceId]);

    useEffect(() => { loadResource(); }, [loadResource]);

    if (loading && !resource) return <div className="p-6"><Spinner /></div>;
    if (!resource) return null;

    const defaultTab = searchParams.get('tab') || 'overview';

    return (
        <div className="p-6 space-y-5" data-testid="resource-detail-page">
            <div className="flex items-center gap-2 text-sm text-white/40">
                <Link to="/resources" className="hover:text-white/70 flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> Resource Explorer</Link>
                <ChevronRight className="w-3 h-3" />
                <span className="text-white/70">{resource.name}</span>
            </div>

            <div className="flex items-start justify-between gap-3 flex-wrap">
                <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                    <Box className="w-6 h-6 text-cyan-400" /> {resource.name}
                </h1>
                <Button variant="outline" size="sm" onClick={loadResource} disabled={loading}>
                    <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            <Tabs defaultValue={defaultTab} data-testid="resource-detail-tabs">
                <TabsList className="bg-black/40 border border-white/10 flex-wrap h-auto">
                    <TabsTrigger value="overview" data-testid="tab-overview"><Box className="w-3.5 h-3.5 mr-1.5" />Overview</TabsTrigger>
                    <TabsTrigger value="health" data-testid="tab-health"><HeartPulse className="w-3.5 h-3.5 mr-1.5" />Health</TabsTrigger>
                    <TabsTrigger value="metrics" data-testid="tab-metrics"><LineChart className="w-3.5 h-3.5 mr-1.5" />Metrics</TabsTrigger>
                    <TabsTrigger value="alerts" data-testid="tab-alerts"><Bell className="w-3.5 h-3.5 mr-1.5" />Alerts</TabsTrigger>
                    <TabsTrigger value="dependencies" data-testid="tab-dependencies"><Network className="w-3.5 h-3.5 mr-1.5" />Dependencies</TabsTrigger>
                    <TabsTrigger value="configuration" data-testid="tab-configuration"><Settings className="w-3.5 h-3.5 mr-1.5" />Configuration</TabsTrigger>
                    <TabsTrigger value="ai-insights" data-testid="tab-ai-insights"><Sparkles className="w-3.5 h-3.5 mr-1.5" />AI Insights</TabsTrigger>
                    <TabsTrigger value="automation" data-testid="tab-automation"><Wrench className="w-3.5 h-3.5 mr-1.5" />Automation</TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="mt-4"><OverviewTab resource={resource} /></TabsContent>
                <TabsContent value="health" className="mt-4"><HealthTab resource={resource} /></TabsContent>
                <TabsContent value="metrics" className="mt-4"><MetricsTab resourceId={resourceId} /></TabsContent>
                <TabsContent value="alerts" className="mt-4"><AlertsTab resourceId={resourceId} /></TabsContent>
                <TabsContent value="dependencies" className="mt-4"><DependenciesTab resourceId={resourceId} resourceName={resource.name} /></TabsContent>
                <TabsContent value="configuration" className="mt-4"><ConfigurationTab resourceId={resourceId} /></TabsContent>
                <TabsContent value="ai-insights" className="mt-4"><AIInsightsTab resource={resource} /></TabsContent>
                <TabsContent value="automation" className="mt-4"><AutomationTab resourceId={resourceId} /></TabsContent>
            </Tabs>
        </div>
    );
}
