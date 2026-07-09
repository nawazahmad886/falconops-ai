import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Code2, Plus, Trash2, Play, RefreshCw, BarChart3, TrendingUp,
    Clock, CheckCircle, XCircle, Eye, Pencil, Gauge, AreaChart as AreaIcon,
    LineChart as LineIcon, LayoutGrid, List, Sparkles, Database,
} from 'lucide-react';
import {
    LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis,
    CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const getAuth = () => ({ Authorization: `Bearer ${localStorage.getItem('falconToken')}` });

const CHART_TYPES = [
    { value: 'line', label: 'Line', icon: LineIcon },
    { value: 'area', label: 'Area', icon: AreaIcon },
    { value: 'bar', label: 'Bar', icon: BarChart3 },
    { value: 'gauge', label: 'Gauge', icon: Gauge },
];

const PRESET_COLORS = ['#00E0FF', '#10B981', '#8B5CF6', '#F59E0B', '#EF4444', '#EC4899', '#3B82F6', '#6366F1'];

// Gauge visual for single-value display
const GaugeWidget = ({ value, unit, color, label }) => {
    const pct = Math.min(100, Math.max(0, typeof value === 'number' ? (unit === '%' ? value : Math.min(value / 100 * 100, 100)) : 0));
    const r = 54;
    const c = Math.PI * r;
    const offset = c - (pct / 100) * c;
    return (
        <div className="flex flex-col items-center py-4">
            <svg width="140" height="80" viewBox="0 0 140 80">
                <path d="M 10 75 A 54 54 0 0 1 130 75" fill="none" stroke="#1a1a2e" strokeWidth="10" strokeLinecap="round" />
                <path d="M 10 75 A 54 54 0 0 1 130 75" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
                    strokeDasharray={c} strokeDashoffset={offset} className="transition-all duration-700" />
            </svg>
            <div className="text-center -mt-6">
                <span className="text-2xl font-bold text-white">{typeof value === 'number' ? value.toLocaleString() : value}</span>
                {unit && <span className="text-xs text-white/40 ml-1">{unit}</span>}
            </div>
            <span className="text-[10px] text-white/30 mt-1">{label}</span>
        </div>
    );
};

// Chart widget that renders based on chart_type
const ChartWidget = ({ query, timeseries, latestResult }) => {
    const chartType = query.chart_type || 'line';
    const color = query.color || '#00E0FF';
    const data = (timeseries || []).map(r => ({
        time: new Date(r.executed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        value: r.value ?? 0,
    }));

    const latestValue = latestResult?.value;
    const latestFormatted = typeof latestValue === 'number' ? latestValue.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';

    if (chartType === 'gauge') {
        return <GaugeWidget value={latestValue} unit={query.unit} color={color} label={query.name} />;
    }

    if (data.length === 0) {
        return (
            <div className="flex items-center justify-center h-[180px] text-white/30 text-sm">
                No data yet. Execute the query to collect data.
            </div>
        );
    }

    const chartProps = {
        data,
        children: [
            <CartesianGrid key="g" strokeDasharray="3 3" stroke="#1a1a2e" />,
            <XAxis key="x" dataKey="time" tick={{ fill: '#94A3B8', fontSize: 9 }} interval="preserveStartEnd" />,
            <YAxis key="y" tick={{ fill: '#94A3B8', fontSize: 9 }} width={50} />,
            <Tooltip key="t" contentStyle={{ background: '#0F172A', border: '1px solid #334155', borderRadius: 8, fontSize: 11 }}
                formatter={(v) => [typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v, query.name]} />,
        ]
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-lg font-bold text-white">{latestFormatted} <span className="text-xs text-white/40">{query.unit}</span></span>
                <span className="text-[10px] text-white/30">{data.length} points</span>
            </div>
            <ResponsiveContainer width="100%" height={180}>
                {chartType === 'area' ? (
                    <AreaChart data={data}>
                        {chartProps.children}
                        <Area type="monotone" dataKey="value" stroke={color} fill={color} fillOpacity={0.15} strokeWidth={2} />
                    </AreaChart>
                ) : chartType === 'bar' ? (
                    <BarChart data={data}>
                        {chartProps.children}
                        <Bar dataKey="value" fill={color} radius={[3, 3, 0, 0]} />
                    </BarChart>
                ) : (
                    <LineChart data={data}>
                        {chartProps.children}
                        <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />
                    </LineChart>
                )}
            </ResponsiveContainer>
        </div>
    );
};

const EMPTY_FORM = {
    name: '', query: '', interval: 60, chart_type: 'line',
    description: '', unit: '', color: '#00E0FF', enabled: true,
};

export const CustomQueryDashboard = ({ instanceId, instanceName }) => {
    const [widgets, setWidgets] = useState([]);
    const [queries, setQueries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeView, setActiveView] = useState('dashboard');
    const [showForm, setShowForm] = useState(false);
    const [editingQuery, setEditingQuery] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [executing, setExecuting] = useState({});
    const [seeding, setSeeding] = useState(false);
    const [execHistory, setExecHistory] = useState([]);

    const fetchDashboard = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/db-monitoring/custom-queries/${instanceId}/dashboard`, { headers: getAuth() });
            const data = await res.json();
            setWidgets(data.widgets || []);
            setQueries((data.widgets || []).map(w => w.query));
        } catch (e) { toast.error('Failed to load custom queries'); }
        finally { setLoading(false); }
    }, [instanceId]);

    const fetchHistory = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/db-monitoring/custom-results/${instanceId}?limit=100`, { headers: getAuth() });
            const data = await res.json();
            setExecHistory(data.results || []);
        } catch (e) { /* silent */ }
    }, [instanceId]);

    useEffect(() => { fetchDashboard(); fetchHistory(); }, [fetchDashboard, fetchHistory]);

    const handleSave = async () => {
        if (!form.name || !form.query) { toast.error('Name and query are required'); return; }
        try {
            const url = editingQuery
                ? `${API_URL}/api/db-monitoring/custom-queries/${editingQuery.id}`
                : `${API_URL}/api/db-monitoring/custom-queries`;
            const method = editingQuery ? 'PUT' : 'POST';
            const body = editingQuery ? form : { ...form, instance_id: instanceId };
            const res = await fetch(url, {
                method, headers: { ...getAuth(), 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error('Failed to save');
            toast.success(editingQuery ? 'Query updated' : 'Query created');
            setShowForm(false);
            setEditingQuery(null);
            setForm(EMPTY_FORM);
            fetchDashboard();
        } catch (e) { toast.error(e.message); }
    };

    const handleDelete = async (queryId) => {
        try {
            await fetch(`${API_URL}/api/db-monitoring/custom-queries/${queryId}`, { method: 'DELETE', headers: getAuth() });
            toast.success('Query deleted');
            fetchDashboard();
        } catch (e) { toast.error('Failed to delete'); }
    };

    const handleToggle = async (queryId) => {
        try {
            await fetch(`${API_URL}/api/db-monitoring/custom-queries/${queryId}/toggle`, { method: 'POST', headers: getAuth() });
            fetchDashboard();
        } catch (e) { toast.error('Toggle failed'); }
    };

    const handleExecute = async (queryId) => {
        setExecuting(prev => ({ ...prev, [queryId]: true }));
        try {
            const res = await fetch(`${API_URL}/api/db-monitoring/custom-queries/${queryId}/execute`, { method: 'POST', headers: getAuth() });
            if (!res.ok) throw new Error('Execution failed');
            const data = await res.json();
            toast.success(`Executed: ${data.query_name} = ${data.value}`);
            fetchDashboard();
            fetchHistory();
        } catch (e) { toast.error(e.message); }
        finally { setExecuting(prev => ({ ...prev, [queryId]: false })); }
    };

    const handleSeedData = async () => {
        setSeeding(true);
        try {
            const res = await fetch(`${API_URL}/api/db-monitoring/custom-queries/seed/${instanceId}`, { method: 'POST', headers: getAuth() });
            if (!res.ok) throw new Error('Seed failed');
            const data = await res.json();
            toast.success(`Seeded ${data.queries_created} queries with ${data.results_seeded} data points`);
            fetchDashboard();
            fetchHistory();
        } catch (e) { toast.error(e.message); }
        finally { setSeeding(false); }
    };

    const openEdit = (q) => {
        setEditingQuery(q);
        setForm({ name: q.name, query: q.query, interval: q.interval, chart_type: q.chart_type || 'line', description: q.description || '', unit: q.unit || '', color: q.color || '#00E0FF', enabled: q.enabled ?? true });
        setShowForm(true);
    };

    const openCreate = () => {
        setEditingQuery(null);
        setForm(EMPTY_FORM);
        setShowForm(true);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20" data-testid="custom-queries-loading">
                <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-4" data-testid="custom-query-dashboard">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Tabs value={activeView} onValueChange={setActiveView}>
                        <TabsList className="bg-white/5 border border-white/10 h-8">
                            <TabsTrigger value="dashboard" className="text-xs data-[state=active]:bg-cyan-500/20 data-[state=active]:text-cyan-400 h-7 px-3">
                                <LayoutGrid className="w-3 h-3 mr-1" /> Dashboard
                            </TabsTrigger>
                            <TabsTrigger value="manage" className="text-xs data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-400 h-7 px-3">
                                <Code2 className="w-3 h-3 mr-1" /> Manage
                            </TabsTrigger>
                            <TabsTrigger value="history" className="text-xs data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400 h-7 px-3">
                                <Clock className="w-3 h-3 mr-1" /> History
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <Badge className="bg-white/5 text-white/50 border-0 text-[10px]">{queries.length} queries</Badge>
                </div>
                <div className="flex gap-2">
                    {queries.length === 0 && (
                        <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-400 h-7 text-xs" onClick={handleSeedData} disabled={seeding} data-testid="seed-queries-btn">
                            {seeding ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />} Seed Demo Queries
                        </Button>
                    )}
                    <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 h-7 text-xs" onClick={openCreate} data-testid="add-custom-query-btn">
                        <Plus className="w-3 h-3 mr-1" /> New Query
                    </Button>
                </div>
            </div>

            {/* Dashboard View */}
            {activeView === 'dashboard' && (
                <div data-testid="custom-query-widgets">
                    {widgets.length === 0 ? (
                        <Card className="bg-[#0a0a14] border-white/10">
                            <CardContent className="flex flex-col items-center justify-center py-16">
                                <Database className="w-12 h-12 text-white/10 mb-4" />
                                <p className="text-white/40 text-sm">No custom queries configured</p>
                                <p className="text-white/20 text-xs mt-1">Create queries to build your custom monitoring dashboard</p>
                                <div className="flex gap-2 mt-4">
                                    <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-400 text-xs" onClick={handleSeedData} disabled={seeding} data-testid="seed-queries-empty-btn">
                                        <Sparkles className="w-3 h-3 mr-1" /> Load Demo Data
                                    </Button>
                                    <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 text-xs" onClick={openCreate}>
                                        <Plus className="w-3 h-3 mr-1" /> Create Query
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                            {widgets.map(w => (
                                <Card key={w.query.id} className="bg-[#0a0a14] border-white/10 hover:border-white/20 transition-colors" data-testid={`widget-${w.query.id}`}>
                                    <CardHeader className="pb-2 pt-3 px-4">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: w.query.color || '#00E0FF' }} />
                                                <CardTitle className="text-sm text-white truncate">{w.query.name}</CardTitle>
                                            </div>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                <Badge className="text-[9px] bg-white/5 text-white/40 border-0">{w.query.interval}s</Badge>
                                                <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-white/30 hover:text-cyan-400" onClick={() => handleExecute(w.query.id)} disabled={executing[w.query.id]} data-testid={`exec-widget-${w.query.id}`}>
                                                    {executing[w.query.id] ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                                </Button>
                                            </div>
                                        </div>
                                        {w.query.description && <p className="text-[10px] text-white/30 mt-0.5 truncate">{w.query.description}</p>}
                                    </CardHeader>
                                    <CardContent className="px-3 pb-3">
                                        <ChartWidget query={w.query} timeseries={w.timeseries} latestResult={w.latest_result} />
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Manage View */}
            {activeView === 'manage' && (
                <div className="space-y-3" data-testid="custom-query-manage">
                    {queries.length === 0 ? (
                        <Card className="bg-[#0a0a14] border-white/10">
                            <CardContent className="text-center py-12 text-white/30 text-sm">No custom queries. Click "New Query" to get started.</CardContent>
                        </Card>
                    ) : queries.map(q => (
                        <Card key={q.id} className="bg-[#0a0a14] border-white/10" data-testid={`query-card-${q.id}`}>
                            <CardContent className="p-4">
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: q.color || '#00E0FF' }} />
                                        <div>
                                            <h4 className="text-sm font-semibold text-white">{q.name}</h4>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                <Badge className="text-[9px] bg-white/5 text-white/40 border-0">{q.chart_type}</Badge>
                                                <Badge className="text-[9px] bg-white/5 text-white/40 border-0">Every {q.interval}s</Badge>
                                                {q.unit && <Badge className="text-[9px] bg-white/5 text-white/40 border-0">{q.unit}</Badge>}
                                                <Badge className={`text-[9px] border-0 ${q.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white/40'}`}>
                                                    {q.enabled ? 'Enabled' : 'Disabled'}
                                                </Badge>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <Switch checked={q.enabled} onCheckedChange={() => handleToggle(q.id)} data-testid={`toggle-${q.id}`} />
                                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-white/30 hover:text-cyan-400" onClick={() => handleExecute(q.id)} disabled={executing[q.id]} data-testid={`exec-${q.id}`}>
                                            {executing[q.id] ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                                        </Button>
                                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-white/30 hover:text-blue-400" onClick={() => openEdit(q)} data-testid={`edit-${q.id}`}>
                                            <Pencil className="w-3.5 h-3.5" />
                                        </Button>
                                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-white/30 hover:text-red-400" onClick={() => handleDelete(q.id)} data-testid={`delete-${q.id}`}>
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </div>
                                </div>
                                <pre className="text-xs text-white/50 bg-black/40 p-3 rounded-lg overflow-x-auto font-mono border border-white/5">{q.query}</pre>
                                {q.description && <p className="text-xs text-white/30 mt-2">{q.description}</p>}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* History View */}
            {activeView === 'history' && (
                <Card className="bg-[#0a0a14] border-white/10" data-testid="custom-query-history">
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm text-white flex items-center gap-2"><Clock className="w-4 h-4 text-amber-400" /> Execution History</CardTitle>
                            <Button size="sm" variant="ghost" className="h-7 text-xs text-white/40" onClick={fetchHistory}><RefreshCw className="w-3 h-3 mr-1" /> Refresh</Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {execHistory.length === 0 ? (
                            <p className="text-center py-8 text-white/30 text-sm">No execution history</p>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs" data-testid="history-table">
                                    <thead>
                                        <tr className="border-b border-white/10 text-white/40">
                                            <th className="text-left py-2 px-2 font-medium">Query</th>
                                            <th className="text-left py-2 px-2 font-medium">Status</th>
                                            <th className="text-right py-2 px-2 font-medium">Value</th>
                                            <th className="text-right py-2 px-2 font-medium">Duration</th>
                                            <th className="text-right py-2 px-2 font-medium">Rows</th>
                                            <th className="text-right py-2 px-2 font-medium">Executed At</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {execHistory.slice(0, 50).map((r, i) => (
                                            <tr key={r.id || i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                                <td className="py-2 px-2 text-white/70">{r.query_name}</td>
                                                <td className="py-2 px-2">
                                                    {r.status === 'success' ? (
                                                        <span className="flex items-center gap-1 text-emerald-400"><CheckCircle className="w-3 h-3" /> OK</span>
                                                    ) : (
                                                        <span className="flex items-center gap-1 text-red-400"><XCircle className="w-3 h-3" /> Fail</span>
                                                    )}
                                                </td>
                                                <td className="py-2 px-2 text-right text-white font-mono">{r.value != null ? Number(r.value).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-'}</td>
                                                <td className="py-2 px-2 text-right text-white/50">{r.duration_ms?.toFixed(1)}ms</td>
                                                <td className="py-2 px-2 text-right text-white/50">{r.rows_returned ?? '-'}</td>
                                                <td className="py-2 px-2 text-right text-white/40">{r.executed_at ? new Date(r.executed_at).toLocaleString() : '-'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Create/Edit Dialog */}
            <Dialog open={showForm} onOpenChange={(open) => { if (!open) { setShowForm(false); setEditingQuery(null); } }}>
                <DialogContent className="bg-[#0a0a14] border-white/10 max-w-2xl" data-testid="query-form-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white flex items-center gap-2">
                            <Code2 className="w-5 h-5 text-cyan-400" />
                            {editingQuery ? 'Edit Custom Query' : 'Create Custom Query'}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Query Name</Label>
                                <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                                    placeholder="e.g. Active Connections" className="bg-white/5 border-white/20 h-9 text-sm" data-testid="query-name-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Description</Label>
                                <Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                                    placeholder="What this query monitors" className="bg-white/5 border-white/20 h-9 text-sm" data-testid="query-desc-input" />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">SQL Query</Label>
                            <textarea value={form.query} onChange={e => setForm({ ...form, query: e.target.value })}
                                placeholder="SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
                                rows={4} className="w-full bg-black/40 border border-white/10 rounded-lg p-3 text-sm text-cyan-300 font-mono resize-none focus:outline-none focus:border-cyan-500/50 placeholder:text-white/20"
                                data-testid="query-sql-input" />
                        </div>

                        <div className="grid grid-cols-4 gap-3">
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Interval (sec)</Label>
                                <Input type="number" min={10} value={form.interval} onChange={e => setForm({ ...form, interval: parseInt(e.target.value) || 60 })}
                                    className="bg-white/5 border-white/20 h-9 text-sm" data-testid="query-interval-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Unit</Label>
                                <Input value={form.unit} onChange={e => setForm({ ...form, unit: e.target.value })}
                                    placeholder="%, MB, conn" className="bg-white/5 border-white/20 h-9 text-sm" data-testid="query-unit-input" />
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Chart Type</Label>
                                <select value={form.chart_type} onChange={e => setForm({ ...form, chart_type: e.target.value })}
                                    className="w-full h-9 rounded-md bg-white/5 border border-white/20 text-sm text-white px-2" data-testid="query-chart-type">
                                    {CHART_TYPES.map(ct => <option key={ct.value} value={ct.value}>{ct.label}</option>)}
                                </select>
                            </div>
                            <div className="space-y-1.5">
                                <Label className="text-xs text-white/50">Color</Label>
                                <div className="flex items-center gap-1.5 h-9">
                                    {PRESET_COLORS.map(c => (
                                        <button key={c} className={`w-5 h-5 rounded-full border-2 transition-all ${form.color === c ? 'border-white scale-110' : 'border-transparent opacity-60 hover:opacity-100'}`}
                                            style={{ backgroundColor: c }} onClick={() => setForm({ ...form, color: c })} />
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
                        <Button className="bg-cyan-600 hover:bg-cyan-700" onClick={handleSave} data-testid="save-query-btn">
                            {editingQuery ? 'Update Query' : 'Create Query'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
