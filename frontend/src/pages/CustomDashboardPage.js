import React, { useState, useEffect, useCallback } from 'react';
import { Responsive as ResponsiveGridLayout, useContainerWidth } from 'react-grid-layout';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    LayoutDashboard, Plus, Save, Trash2, X, GripVertical, RefreshCw,
    Radio, Globe, Shield, Key, Gauge, Brain, Bell, AlertTriangle,
    Activity, Building, Edit, FolderOpen,
    TrendingUp, Target, Table2, Server, FileWarning,
} from 'lucide-react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

// react-grid-layout v2 auto-handles width via internal measurement for Responsive.

const WIDGET_ICONS = {
    soc_feed: Radio,
    uptime: Globe,
    threats: Shield,
    billing: Key,
    sla: Gauge,
    ai_agents: Brain,
    alerts: Bell,
    incidents: AlertTriangle,
    metrics: Activity,
    tenants: Building,
    kpi_row: TrendingUp,
    slo_status: Target,
    apm_table: Table2,
    os_gauges: Server,
    log_exceptions: FileWarning,
};

const WIDGET_COLORS = {
    soc_feed: 'text-red-400 bg-red-500/10 border-red-500/20',
    uptime: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    threats: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    billing: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    sla: 'text-[#00E0FF] bg-[#00E0FF]/10 border-[#00E0FF]/20',
    ai_agents: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    alerts: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    incidents: 'text-red-400 bg-red-500/10 border-red-500/20',
    metrics: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    tenants: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    kpi_row: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    slo_status: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
    apm_table: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    os_gauges: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    log_exceptions: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
};

// ============ Widget Renderer ============
const WidgetBody = ({ widget, data, loading }) => {
    if (loading) {
        return (
            <div className="flex items-center justify-center h-full text-white/30">
                <RefreshCw className="w-5 h-5 animate-spin" />
            </div>
        );
    }
    if (!data || data.error) {
        return <div className="text-xs text-white/40 p-2">No data available</div>;
    }

    switch (widget.widget_type) {
        case 'soc_feed':
            return (
                <div className="space-y-1.5 overflow-y-auto max-h-full">
                    <p className="text-xs text-white/40">{data.count || 0} recent events</p>
                    {(data.events || []).slice(0, 5).map((e, i) => (
                        <div key={i} className="text-[11px] p-1.5 rounded bg-white/[0.03] border border-white/5 text-white/70 truncate">
                            <span className="text-red-400">{e.severity || 'info'}</span> · {e.message || e.source}
                        </div>
                    ))}
                </div>
            );
        case 'uptime':
            return (
                <div className="flex flex-col items-center justify-center h-full">
                    <p className="text-4xl font-bold text-emerald-400">{data.up || 0}/{data.total || 0}</p>
                    <p className="text-xs text-white/50 mt-1">Monitors Up</p>
                    {data.down > 0 && (
                        <Badge className="mt-2 bg-red-500/15 text-red-400 border-red-500/30">
                            {data.down} down
                        </Badge>
                    )}
                </div>
            );
        case 'threats':
            return (
                <div className="flex flex-col items-center justify-center h-full">
                    <p className="text-4xl font-bold text-orange-400">{data.count || 0}</p>
                    <p className="text-xs text-white/50 mt-1">Threats detected</p>
                    {data.critical > 0 && (
                        <Badge className="mt-2 bg-red-500/15 text-red-400 border-red-500/30">
                            {data.critical} critical
                        </Badge>
                    )}
                </div>
            );
        case 'billing':
            return (
                <div className="space-y-2">
                    <div>
                        <p className="text-xs text-white/40">Total Usage Events</p>
                        <p className="text-2xl font-bold text-purple-400">{data.total_events || 0}</p>
                    </div>
                    <div>
                        <p className="text-xs text-white/40">Active Plans</p>
                        <p className="text-lg font-semibold text-white">{data.active_plans || 0}</p>
                    </div>
                </div>
            );
        case 'sla':
            return (
                <div className="flex flex-col items-center justify-center h-full">
                    <p className="text-4xl font-bold text-[#00E0FF]">{data.sla_percent || 100}%</p>
                    <p className="text-xs text-white/50 mt-1">SLA Score</p>
                    <p className="text-[10px] text-white/30 mt-1">{data.total_monitors || 0} monitors</p>
                </div>
            );
        case 'ai_agents':
            return (
                <div className="space-y-2">
                    <p className="text-xs text-white/40">Total Runs: <span className="text-white font-semibold">{data.count || 0}</span></p>
                    {(data.runs || []).slice(0, 4).map((r, i) => (
                        <div key={i} className="text-[11px] p-1.5 rounded bg-pink-500/5 border border-pink-500/10 text-white/70">
                            {r.agent_type || 'agent'} · {r.status || 'ok'}
                        </div>
                    ))}
                </div>
            );
        case 'alerts':
            return (
                <div className="space-y-2">
                    <p className="text-3xl font-bold text-amber-400">{data.count || 0}</p>
                    <p className="text-xs text-white/50">Open alerts</p>
                    {(data.alerts || []).slice(0, 3).map((a, i) => (
                        <div key={i} className="text-[10px] p-1 rounded bg-white/[0.03] text-white/60 truncate">
                            {a.title || a.message}
                        </div>
                    ))}
                </div>
            );
        case 'incidents':
            return (
                <div className="space-y-2">
                    <p className="text-3xl font-bold text-red-400">{data.count || 0}</p>
                    <p className="text-xs text-white/50">Open incidents</p>
                    {(data.incidents || []).slice(0, 3).map((inc, i) => (
                        <div key={i} className="text-[10px] p-1 rounded bg-white/[0.03] text-white/60 truncate">
                            {inc.title || inc.summary}
                        </div>
                    ))}
                </div>
            );
        case 'metrics':
            return (
                <div className="space-y-1.5">
                    <div className="flex justify-between"><span className="text-xs text-white/50">CPU</span><span className="text-xs text-white font-semibold">{data.cpu}%</span></div>
                    <div className="w-full bg-white/10 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-blue-400" style={{ width: `${data.cpu}%` }} /></div>
                    <div className="flex justify-between"><span className="text-xs text-white/50">Memory</span><span className="text-xs text-white font-semibold">{data.memory}%</span></div>
                    <div className="w-full bg-white/10 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-emerald-400" style={{ width: `${data.memory}%` }} /></div>
                    <div className="flex justify-between"><span className="text-xs text-white/50">Disk</span><span className="text-xs text-white font-semibold">{data.disk}%</span></div>
                    <div className="w-full bg-white/10 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-amber-400" style={{ width: `${data.disk}%` }} /></div>
                </div>
            );
        case 'tenants':
            return (
                <div className="space-y-2">
                    <p className="text-3xl font-bold text-indigo-400">{data.count || 0}</p>
                    <p className="text-xs text-white/50">Active tenants</p>
                </div>
            );
        case 'kpi_row': {
            const Row = ({ label, value, unit, delta, invert }) => {
                const improving = delta == null ? null : (invert ? delta < 0 : delta > 0);
                return (
                    <div className="flex items-center justify-between py-1 border-b border-white/5 last:border-0">
                        <span className="text-[11px] text-white/50">{label}</span>
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-white">{value}{unit}</span>
                            {delta != null && (
                                <span className={`text-[9px] ${improving ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {delta > 0 ? '▲' : delta < 0 ? '▼' : '—'}{Math.abs(delta)}%
                                </span>
                            )}
                        </div>
                    </div>
                );
            };
            return (
                <div className="space-y-0.5 h-full overflow-y-auto">
                    <Row label="Throughput" value={data.throughput?.value ?? 0} unit="/hr" delta={data.throughput?.delta_pct} />
                    <Row label="Avg Latency" value={data.avg_latency_ms?.value ?? 0} unit="ms" delta={data.avg_latency_ms?.delta_pct} invert />
                    <Row label="Error Rate" value={data.error_rate?.value ?? 0} unit="%" delta={data.error_rate?.delta_pct} invert />
                    <Row label="SLA Compliance" value={data.sla_compliance_pct ?? 100} unit="%" />
                    <p className="text-[10px] text-white/30 pt-1">
                        {data.monitors_compliant ?? 0}/{data.monitors_total ?? 0} monitors compliant
                    </p>
                </div>
            );
        }
        case 'slo_status':
            return (
                <div className="space-y-1.5 overflow-y-auto max-h-full">
                    {(data.monitors || []).length === 0 && (
                        <p className="text-xs text-white/40">No monitors configured</p>
                    )}
                    {(data.monitors || []).slice(0, 5).map((m, i) => (
                        <div key={i}>
                            <div className="flex justify-between text-[10px] mb-0.5">
                                <span className="text-white/60 truncate">{m.name}</span>
                                <span className={m.compliant ? 'text-emerald-400' : 'text-red-400'}>{m.uptime_pct}%</span>
                            </div>
                            <div className="w-full bg-white/10 rounded-full h-1.5">
                                <div
                                    className={`h-1.5 rounded-full ${m.compliant ? 'bg-emerald-400' : 'bg-red-400'}`}
                                    style={{ width: `${Math.min(m.uptime_pct || 0, 100)}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            );
        case 'apm_table':
            return (
                <div className="overflow-y-auto max-h-full space-y-1">
                    {(data.services || []).length === 0 && (
                        <p className="text-xs text-white/40">No services reporting</p>
                    )}
                    {(data.services || []).slice(0, 8).map((s, i) => {
                        const statusColor = s.status === 'critical'
                            ? 'bg-red-500/15 text-red-400'
                            : s.status === 'degraded'
                                ? 'bg-amber-500/15 text-amber-400'
                                : 'bg-emerald-500/15 text-emerald-400';
                        return (
                            <div key={i} className="flex items-center justify-between text-[10px] p-1.5 rounded bg-white/[0.03] gap-2">
                                <span className="text-white/70 truncate flex-1">{s.service_name}</span>
                                <span className="text-white/40 whitespace-nowrap">{s.rpm} rpm</span>
                                <span className="text-white/40 whitespace-nowrap">{s.p99_response_time_ms}ms</span>
                                <span className={`px-1.5 py-0.5 rounded whitespace-nowrap ${statusColor}`}>{s.status}</span>
                            </div>
                        );
                    })}
                </div>
            );
        case 'os_gauges': {
            const single = data.mode === 'single';
            if (single && !data.server) {
                return <p className="text-xs text-white/40">Server not found</p>;
            }
            const s = single ? data.server : null;
            const cpu = s ? s.cpu_usage : data.avg_cpu;
            const mem = s ? s.memory_usage : data.avg_memory;
            const disk = s ? s.disk_usage : data.avg_disk;
            const netIn = s ? s.network_in : data.avg_network_in;
            const netOut = s ? s.network_out : data.avg_network_out;
            const Bar = ({ label, value, color }) => (
                <div>
                    <div className="flex justify-between">
                        <span className="text-[10px] text-white/50">{label}</span>
                        <span className="text-[10px] text-white font-semibold">{value ?? 0}%</span>
                    </div>
                    <div className="w-full bg-white/10 rounded-full h-1.5 mt-0.5">
                        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.min(value || 0, 100)}%` }} />
                    </div>
                </div>
            );
            return (
                <div className="space-y-1.5">
                    <Bar label="CPU" value={cpu} color="bg-blue-400" />
                    <Bar label="Memory" value={mem} color="bg-emerald-400" />
                    <Bar label="Disk" value={disk} color="bg-amber-400" />
                    <div className="flex justify-between text-[10px] text-white/40 pt-1">
                        <span>↓ {netIn ?? 0} Mbps</span><span>↑ {netOut ?? 0} Mbps</span>
                    </div>
                    {!single && (
                        <p className="text-[9px] text-white/30 pt-1">
                            {data.online_servers ?? 0}/{data.total_servers ?? 0} servers online
                        </p>
                    )}
                </div>
            );
        }
        case 'log_exceptions':
            return (
                <div className="space-y-1 overflow-y-auto max-h-full">
                    <p className="text-[10px] text-white/40">{data.count || 0} in last hour</p>
                    {(data.logs || []).slice(0, 6).map((l, i) => (
                        <div key={i} className="text-[10px] p-1.5 rounded bg-white/[0.03] border border-white/5">
                            <div className="flex items-center gap-1.5">
                                <span className={`font-bold ${l.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}`}>
                                    {(l.severity || 'error').toUpperCase()}
                                </span>
                                <span className="text-white/30 font-mono">
                                    {l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''}
                                </span>
                            </div>
                            <p className="text-white/60 truncate mt-0.5">
                                {l.service ? `${l.service}: ` : ''}{l.message}
                            </p>
                        </div>
                    ))}
                </div>
            );
        default:
            return <div className="text-white/40 text-xs">Widget: {widget.widget_type}</div>;
    }
};

// ============ Widget Card ============
const WidgetCard = ({ widget, editing, onRemove, apiClient }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiClient.get(`/custom-dashboards/widgets/data/${widget.widget_type}`, {
                params: widget.config || {},
            });
            setData(res.data);
        } catch (e) {
            setData({ error: e.message });
        }
        setLoading(false);
    }, [apiClient, widget.widget_type, widget.config]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const Icon = WIDGET_ICONS[widget.widget_type] || Activity;
    const colorCls = WIDGET_COLORS[widget.widget_type] || 'text-white bg-white/5 border-white/10';

    return (
        <Card className="h-full bg-[#0D1117] border-white/10 flex flex-col overflow-hidden" data-testid={`widget-${widget.i}`}>
            {/* Widget Header */}
            <div className={`flex items-center justify-between px-3 py-2 border-b border-white/5 ${editing ? 'cursor-move grid-drag-handle' : ''}`}>
                <div className="flex items-center gap-2 min-w-0">
                    {editing && <GripVertical className="w-3.5 h-3.5 text-white/30 shrink-0" />}
                    <div className={`p-1 rounded ${colorCls.replace('text-', 'bg-').split(' ')[0]}/20`}>
                        <Icon className={`w-3.5 h-3.5 ${colorCls.split(' ')[0]}`} />
                    </div>
                    <p className="text-xs font-semibold text-white/90 truncate">
                        {widget.title || widget.widget_type.replace('_', ' ').toUpperCase()}
                    </p>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={fetchData}
                        className="p-1 rounded hover:bg-white/10 text-white/30 hover:text-white/70"
                        title="Refresh"
                    >
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                    {editing && (
                        <button
                            onClick={() => onRemove(widget.i)}
                            className="p-1 rounded hover:bg-red-500/20 text-white/30 hover:text-red-400"
                            title="Remove"
                            data-testid={`remove-widget-${widget.i}`}
                        >
                            <X className="w-3 h-3" />
                        </button>
                    )}
                </div>
            </div>
            {/* Widget Body */}
            <div className="flex-1 p-3 overflow-hidden">
                <WidgetBody widget={widget} data={data} loading={loading} />
            </div>
        </Card>
    );
};

// ============ Main Page ============
export default function CustomDashboardPage() {
    const { api } = useAuth();
    const { containerRef, width } = useContainerWidth({ initialWidth: 1280 });
    const [dashboards, setDashboards] = useState([]);
    const [currentId, setCurrentId] = useState(null);
    const [name, setName] = useState('My Dashboard');
    const [widgets, setWidgets] = useState([]);
    const [editing, setEditing] = useState(true);
    const [catalog, setCatalog] = useState([]);
    const [showCatalog, setShowCatalog] = useState(false);
    const [showLoad, setShowLoad] = useState(false);
    const [saving, setSaving] = useState(false);
    const [pendingWidget, setPendingWidget] = useState(null);
    const [configOptions, setConfigOptions] = useState([]);
    const [selectedConfigValue, setSelectedConfigValue] = useState('all');

    // Widget config_kind -> {query param name, endpoint to list options from, response mapper}
    const CONFIG_KIND_MAP = {
        service: { param: 'service', endpoint: '/apm/services', map: (r) => (r || []).map((s) => ({ value: s.service_name, label: s.service_name })) },
        server: { param: 'server_id', endpoint: '/servers', map: (r) => (r || []).map((s) => ({ value: s.id, label: s.hostname || s.name || s.id })) },
        monitor: { param: 'monitor_id', endpoint: '/sla/overview', map: (r) => (r?.monitors || []).map((m) => ({ value: m.monitor_id, label: m.name || m.monitor_id })) },
    };

    const fetchDashboards = useCallback(async () => {
        try {
            const res = await api.get('/custom-dashboards/list');
            setDashboards(res.data || []);
        } catch (e) {
            console.error(e);
        }
    }, [api]);

    const fetchCatalog = useCallback(async () => {
        try {
            const res = await api.get('/custom-dashboards/widgets/catalog');
            setCatalog(res.data?.widgets || []);
        } catch (e) {
            console.error(e);
        }
    }, [api]);

    useEffect(() => {
        fetchDashboards();
        fetchCatalog();
    }, [fetchDashboards, fetchCatalog]);

    const addWidget = (widgetType, title, config = {}) => {
        const newWidget = {
            i: `w-${Date.now()}`,
            x: (widgets.length * 4) % 12,
            y: Infinity,
            w: 4,
            h: 4,
            widget_type: widgetType,
            title: title,
            config: config || {},
        };
        setWidgets([...widgets, newWidget]);
        setShowCatalog(false);
        setPendingWidget(null);
        toast.success(`Added ${title}`);
    };

    // Configurable widgets (apm_table / os_gauges / slo_status / log_exceptions) get a
    // follow-up "which service/server/monitor" step instead of adding immediately, so a NOC
    // engineer can add the same widget type multiple times scoped to different services.
    const openCatalogItem = async (w) => {
        if (!w.configurable) {
            addWidget(w.type, w.title, {});
            return;
        }
        setPendingWidget(w);
        setSelectedConfigValue('all');
        const kind = CONFIG_KIND_MAP[w.config_kind];
        if (!kind) {
            setConfigOptions([]);
            return;
        }
        try {
            const res = await api.get(kind.endpoint);
            setConfigOptions(kind.map(res.data));
        } catch (e) {
            setConfigOptions([]);
        }
    };

    const confirmConfiguredWidget = () => {
        const kind = CONFIG_KIND_MAP[pendingWidget.config_kind];
        if (selectedConfigValue === 'all' || !kind) {
            addWidget(pendingWidget.type, pendingWidget.title, {});
            return;
        }
        const chosen = configOptions.find((o) => o.value === selectedConfigValue);
        const title = chosen ? `${pendingWidget.title}: ${chosen.label}` : pendingWidget.title;
        addWidget(pendingWidget.type, title, { [kind.param]: selectedConfigValue });
    };

    const removeWidget = (id) => {
        setWidgets(widgets.filter(w => w.i !== id));
    };

    const onLayoutChange = (layout) => {
        const updated = widgets.map(w => {
            const l = layout.find(it => it.i === w.i);
            return l ? { ...w, x: l.x, y: l.y, w: l.w, h: l.h } : w;
        });
        setWidgets(updated);
    };

    const saveDashboard = async () => {
        setSaving(true);
        try {
            const payload = { name, description: '', widgets };
            if (currentId) {
                await api.put(`/custom-dashboards/${currentId}`, payload);
                toast.success('Dashboard updated');
            } else {
                const res = await api.post('/custom-dashboards/create', payload);
                setCurrentId(res.data?.dashboard_id);
                toast.success('Dashboard saved');
            }
            await fetchDashboards();
        } catch (e) {
            toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
        }
        setSaving(false);
    };

    const loadDashboard = (d) => {
        setCurrentId(d.dashboard_id);
        setName(d.name);
        setWidgets(d.widgets || []);
        setShowLoad(false);
        toast.success(`Loaded "${d.name}"`);
    };

    const newDashboard = () => {
        setCurrentId(null);
        setName('My Dashboard');
        setWidgets([]);
        setEditing(true);
    };

    const deleteDashboard = async (id) => {
        if (!window.confirm('Delete this dashboard?')) return;
        try {
            await api.delete(`/custom-dashboards/${id}`);
            if (currentId === id) newDashboard();
            await fetchDashboards();
            toast.success('Dashboard deleted');
        } catch (e) {
            toast.error(`Delete failed: ${e.message}`);
        }
    };

    const layouts = {
        lg: widgets.map(w => ({ i: w.i, x: w.x, y: w.y, w: w.w, h: w.h, minW: 2, minH: 2 })),
    };

    return (
        <div className="space-y-4" data-testid="custom-dashboard-page">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                    <LayoutDashboard className="w-6 h-6 text-[#00E0FF]" />
                    <Input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="bg-[#0D1117] border-white/10 text-white font-semibold w-64"
                        placeholder="Dashboard name"
                        data-testid="dashboard-name-input"
                    />
                    {currentId && (
                        <Badge variant="outline" className="border-white/10 text-white/50 text-[10px]">
                            {currentId}
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditing(!editing)}
                        className={editing ? 'bg-white/10 text-[#00E0FF]' : ''}
                        data-testid="toggle-edit-btn"
                    >
                        <Edit className="w-4 h-4 mr-2" />
                        {editing ? 'Editing' : 'View Mode'}
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowCatalog(true)}
                        disabled={!editing}
                        data-testid="add-widget-btn"
                    >
                        <Plus className="w-4 h-4 mr-2" /> Add Widget
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowLoad(true)}
                        data-testid="load-dashboard-btn"
                    >
                        <FolderOpen className="w-4 h-4 mr-2" /> Load
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={newDashboard}
                        data-testid="new-dashboard-btn"
                    >
                        <Plus className="w-4 h-4 mr-2" /> New
                    </Button>
                    <Button
                        onClick={saveDashboard}
                        disabled={saving || widgets.length === 0}
                        className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                        size="sm"
                        data-testid="save-dashboard-btn"
                    >
                        {saving ? (
                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Save className="w-4 h-4 mr-2" />
                        )}
                        Save
                    </Button>
                </div>
            </div>

            {/* Empty state */}
            {widgets.length === 0 && (
                <Card className="bg-[#0D1117] border-white/5 border-dashed">
                    <CardContent className="py-16 text-center" data-testid="empty-dashboard">
                        <LayoutDashboard className="w-16 h-16 mx-auto text-white/20 mb-4" />
                        <p className="text-white/60 mb-2">No widgets yet</p>
                        <p className="text-sm text-white/40 mb-4">Build your own NOC view by adding widgets</p>
                        <Button onClick={() => setShowCatalog(true)} className="bg-[#00E0FF] text-black hover:bg-[#00E0FF]/90">
                            <Plus className="w-4 h-4 mr-2" /> Add Your First Widget
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Grid Layout */}
            {widgets.length > 0 && (
                <div ref={containerRef} data-testid="grid-container">
                    <ResponsiveGridLayout
                        className="layout"
                        layouts={layouts}
                        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480 }}
                        cols={{ lg: 12, md: 10, sm: 6, xs: 4 }}
                        rowHeight={60}
                        width={width}
                        isDraggable={editing}
                        isResizable={editing}
                        draggableHandle=".grid-drag-handle"
                        onLayoutChange={onLayoutChange}
                        margin={[12, 12]}
                    >
                        {widgets.map((w) => (
                            <div key={w.i}>
                                <WidgetCard widget={w} editing={editing} onRemove={removeWidget} apiClient={api} />
                            </div>
                        ))}
                    </ResponsiveGridLayout>
                </div>
            )}

            {/* Widget Catalog Dialog */}
            <Dialog open={showCatalog} onOpenChange={setShowCatalog}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-2xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Plus className="w-5 h-5 text-[#00E0FF]" />
                            Add Widget
                        </DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            Pick a widget to add to your dashboard.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid grid-cols-2 gap-3 max-h-[60vh] overflow-y-auto">
                        {catalog.map((w) => {
                            const Icon = WIDGET_ICONS[w.type] || Activity;
                            const colorCls = WIDGET_COLORS[w.type] || 'text-white bg-white/5 border-white/10';
                            return (
                                <button
                                    key={w.type}
                                    onClick={() => openCatalogItem(w)}
                                    className="flex items-center gap-3 p-3 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] transition-colors text-left"
                                    data-testid={`catalog-${w.type}`}
                                >
                                    <div className={`p-2 rounded ${colorCls}`}>
                                        <Icon className="w-4 h-4" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-white font-medium">{w.title}</p>
                                        <p className="text-[10px] text-white/40 capitalize">{w.category}</p>
                                    </div>
                                    <Plus className="w-4 h-4 text-white/30" />
                                </button>
                            );
                        })}
                    </div>
                </DialogContent>
            </Dialog>

            {/* Widget Config Picker — shown for widget types with configurable: true, so a NOC
                engineer can scope apm_table/os_gauges/slo_status/log_exceptions to one
                service/server/monitor (or leave as "All / Overview"). */}
            <Dialog open={!!pendingWidget} onOpenChange={(open) => !open && setPendingWidget(null)}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-md">
                    <DialogHeader>
                        <DialogTitle>Configure {pendingWidget?.title}</DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            Optionally scope this widget to one {pendingWidget?.config_kind}, or leave as overview.
                        </DialogDescription>
                    </DialogHeader>
                    <Select value={selectedConfigValue} onValueChange={setSelectedConfigValue}>
                        <SelectTrigger className="bg-white/5 border-white/10 text-white" data-testid="widget-config-select">
                            <SelectValue placeholder="All / Overview" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All / Overview</SelectItem>
                            {configOptions.map((o) => (
                                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        onClick={confirmConfiguredWidget}
                        className="bg-[#00E0FF] text-black hover:bg-[#00E0FF]/90 mt-2"
                        data-testid="confirm-widget-config-btn"
                    >
                        <Plus className="w-4 h-4 mr-2" /> Add Widget
                    </Button>
                </DialogContent>
            </Dialog>

            {/* Load Dashboard Dialog */}
            <Dialog open={showLoad} onOpenChange={setShowLoad}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FolderOpen className="w-5 h-5 text-[#F5B841]" />
                            My Dashboards ({dashboards.length})
                        </DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            Load a saved dashboard or delete old ones.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                        {dashboards.length === 0 && (
                            <p className="text-center text-white/40 py-8 text-sm">No saved dashboards yet</p>
                        )}
                        {dashboards.map((d) => (
                            <div
                                key={d.dashboard_id}
                                className="flex items-center justify-between p-3 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                                data-testid={`saved-dashboard-${d.dashboard_id}`}
                            >
                                <div className="flex-1 min-w-0 cursor-pointer" onClick={() => loadDashboard(d)}>
                                    <p className="text-sm text-white font-medium truncate">{d.name}</p>
                                    <p className="text-xs text-white/40">
                                        {d.widgets?.length || 0} widgets · Updated {new Date(d.updated_at).toLocaleDateString()}
                                    </p>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => deleteDashboard(d.dashboard_id)}
                                    className="text-red-400 hover:bg-red-500/10"
                                    data-testid={`delete-dashboard-${d.dashboard_id}`}
                                >
                                    <Trash2 className="w-4 h-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
