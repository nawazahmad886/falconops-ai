import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Brain, Activity, AlertTriangle, DollarSign, Zap, Shield,
    Cpu, RefreshCw, ChevronRight, Sparkles, Network, Clock,
    CheckCircle2, XCircle, AlertCircle, TrendingUp, TrendingDown,
    Target, Eye, Layers, Search,
} from 'lucide-react';
import AIOpsDiagnosePanel from '../components/AIOpsDiagnosePanel';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const SEVERITY_BORDER = {
    critical: 'border-l-red-500',
    warning: 'border-l-amber-500',
    info: 'border-l-cyan-500',
    informational: 'border-l-zinc-500',
};

const STATUS_COLORS = {
    pending_review: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    informational: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
    approved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    rejected: 'bg-red-500/15 text-red-400 border-red-500/30',
};

const RISK_COLORS = {
    low: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/[0.06]',
    medium: 'text-amber-400 border-amber-500/30 bg-amber-500/[0.06]',
    high: 'text-red-400 border-red-500/30 bg-red-500/[0.06]',
    informational: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/[0.06]',
};

// ─────────────────────────────────────────────────────
//  Stat card
// ─────────────────────────────────────────────────────

const StatCard = ({ icon: Icon, label, value, sub, color = 'cyan', testId }) => (
    <div className={`p-4 rounded-lg border bg-${color}-500/[0.04] border-${color}-500/20`} data-testid={testId}>
        <div className="flex items-start justify-between mb-2">
            <Icon className={`w-4 h-4 text-${color}-400`} />
            <span className={`text-[10px] uppercase tracking-widest text-${color}-400/60`}>{label}</span>
        </div>
        <div className="text-2xl font-bold text-white">{value}</div>
        {sub && <p className="text-[11px] text-white/40 mt-1">{sub}</p>}
    </div>
);

// ─────────────────────────────────────────────────────
//  Insight card
// ─────────────────────────────────────────────────────

const InsightCard = ({ insight }) => {
    const ev = insight.event_summary || {};
    const action = insight.recommended_action;
    const rca = insight.root_cause || {};
    const ctx = insight.context || {};
    const sevColor = SEVERITY_BORDER[ev.severity] || 'border-l-zinc-500';

    return (
        <Card className={`bg-[#0a0a0a] border-white/10 border-l-4 ${sevColor}`} data-testid={`insight-${insight.id}`}>
            <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                            <Badge className={`text-[10px] border ${STATUS_COLORS[insight.status] || ''}`}>
                                {insight.status}
                            </Badge>
                            {insight.is_duplicate && (
                                <Badge variant="outline" className="text-[10px] border-zinc-500/30 text-zinc-400">
                                    duplicate
                                </Badge>
                            )}
                            {ctx.is_recurring && (
                                <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
                                    recurring
                                </Badge>
                            )}
                            {ctx.runbook_present && (
                                <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400">
                                    runbook
                                </Badge>
                            )}
                        </div>
                        <CardTitle className="mt-1.5 text-sm flex items-center gap-2">
                            <span className="text-white/90 truncate">{ev.alert || 'Unknown alert'}</span>
                            <span className="text-white/30">·</span>
                            <span className="text-white/60 truncate">{ev.service || 'unknown service'}</span>
                        </CardTitle>
                    </div>
                    <span className="text-[10px] text-white/30 shrink-0">{new Date(insight.created_at).toLocaleTimeString()}</span>
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
                {/* Root cause */}
                <div className="p-3 bg-white/[0.02] border border-white/5 rounded-lg">
                    <div className="flex items-center gap-2 mb-1.5">
                        <Target className="w-3.5 h-3.5 text-[#F5B841]" />
                        <span className="text-[10px] uppercase tracking-widest text-[#F5B841]/80">Root Cause</span>
                        <span className="ml-auto text-[10px] text-white/40 font-mono">
                            confidence {Math.round((rca.confidence || 0) * 100)}%
                        </span>
                    </div>
                    <p className="text-sm text-white/85 mb-1.5 leading-relaxed">{rca.summary}</p>
                    {(rca.evidence || []).length > 0 && (
                        <ul className="space-y-0.5">
                            {(rca.evidence || []).map((e, i) => (
                                <li key={i} className="text-[11px] text-white/50 flex items-start gap-1.5">
                                    <ChevronRight className="w-2.5 h-2.5 mt-1 text-white/30 shrink-0" /> {e}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {/* Recommended action */}
                {action && (
                    <div className={`p-3 rounded-lg border ${RISK_COLORS[action.risk] || RISK_COLORS.medium}`}>
                        <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                                <Zap className="w-3.5 h-3.5" />
                                <span className="text-[10px] uppercase tracking-widest opacity-70">Recommended Action</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <Badge variant="outline" className="text-[9px] border-white/20 capitalize">
                                    {action.risk} risk
                                </Badge>
                                {action.auto_executable ? (
                                    <Badge className="text-[9px] bg-emerald-500/20 text-emerald-300 border-emerald-500/30">auto-executable</Badge>
                                ) : (
                                    <Badge className="text-[9px] bg-amber-500/20 text-amber-300 border-amber-500/30">approval required</Badge>
                                )}
                            </div>
                        </div>
                        <code className="text-sm font-semibold">{action.kind}</code>
                        <p className="text-[11px] opacity-80 mt-1">{action.rationale}</p>
                    </div>
                )}

                {/* Context strip */}
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                    <div className="p-2 bg-black/30 rounded text-center">
                        <Layers className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                        <div className="text-white font-mono">{ctx.history_count || 0}</div>
                        <div className="text-white/40">events / 7d</div>
                    </div>
                    <div className="p-2 bg-black/30 rounded text-center">
                        <Network className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                        <div className="text-white font-mono">
                            {(ctx.topology?.upstream?.length || 0)} / {(ctx.topology?.downstream?.length || 0)}
                        </div>
                        <div className="text-white/40">up / down</div>
                    </div>
                    <div className="p-2 bg-black/30 rounded text-center">
                        <Sparkles className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                        <div className="text-white font-mono">{(insight.agents_consulted || []).length}</div>
                        <div className="text-white/40">agents</div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};

// ─────────────────────────────────────────────────────
//  Cost / Prevention / Noise list cards
// ─────────────────────────────────────────────────────

const ListItemCard = ({ icon: Icon, title, sub, badges, color = 'cyan' }) => (
    <div className={`p-3 bg-${color}-500/[0.04] border border-${color}-500/20 rounded-lg`}>
        <div className="flex items-start gap-2.5">
            <Icon className={`w-4 h-4 text-${color}-400 mt-0.5 shrink-0`} />
            <div className="min-w-0 flex-1">
                <div className="text-sm text-white/90">{title}</div>
                {sub && <p className="text-[11px] text-white/50 mt-1">{sub}</p>}
                {badges && badges.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                        {badges.map((b, i) => (
                            <Badge key={i} variant="outline" className="text-[10px] border-white/15 text-white/70">{b}</Badge>
                        ))}
                    </div>
                )}
            </div>
        </div>
    </div>
);

// ─────────────────────────────────────────────────────
//  Demo event tester
// ─────────────────────────────────────────────────────

const DemoEventTester = ({ onProcessed }) => {
    const [busy, setBusy] = useState(false);
    const [form, setForm] = useState({
        service: 'Payment Gateway',
        alert: 'API 500 - Internal Server Error',
        severity: 'Critical',
        host: 'pg-prod-01',
    });

    const send = async () => {
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/ai-engine/process`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ event: { ...form, timestamp: new Date().toISOString() } }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Process failed');
            toast.success('Insight generated');
            if (onProcessed) onProcessed(d);
        } catch (e) { toast.error(e.message || 'Process failed'); }
        finally { setBusy(false); }
    };

    return (
        <Card className="bg-[#0a0a0a] border-white/10">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                    <Eye className="w-4 h-4 text-[#F5B841]" /> Test Event Pipeline
                </CardTitle>
                <CardDescription className="text-xs">Send a sample event through the unified AI pipeline.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                    <Input value={form.service} onChange={(e) => setForm({ ...form, service: e.target.value })} placeholder="Service" className="bg-black/40 border-white/10 h-8 text-xs" data-testid="demo-service" />
                    <Input value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} placeholder="Severity" className="bg-black/40 border-white/10 h-8 text-xs" data-testid="demo-severity" />
                </div>
                <Input value={form.alert} onChange={(e) => setForm({ ...form, alert: e.target.value })} placeholder="Alert description" className="bg-black/40 border-white/10 h-8 text-xs" data-testid="demo-alert" />
                <Input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} placeholder="Host" className="bg-black/40 border-white/10 h-8 text-xs" data-testid="demo-host" />
                <Button onClick={send} disabled={busy}
                        className="w-full bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold h-8 text-xs"
                        data-testid="demo-send-btn">
                    {busy ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
                    Process Through AI Pipeline
                </Button>
            </CardContent>
        </Card>
    );
};

// ─────────────────────────────────────────────────────
//  Main page
// ─────────────────────────────────────────────────────

export default function AIInsightPanel() {
    const { user } = useAuth();
    const [summary, setSummary] = useState(null);
    const [insights, setInsights] = useState([]);
    const [warnings, setWarnings] = useState([]);
    const [costRecs, setCostRecs] = useState([]);
    const [noiseBuckets, setNoiseBuckets] = useState([]);
    const [scanning, setScanning] = useState(false);
    const [tab, setTab] = useState('insights');
    const [diagInput, setDiagInput] = useState('');
    const [diagService, setDiagService] = useState(null);
    const [diagHours, setDiagHours] = useState(24);

    const loadAll = async () => {
        try {
            const [s, i, w, c, n] = await Promise.all([
                fetch(`${API}/api/ai-engine/summary?hours=24`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/ai-engine/insights?hours=24&limit=50`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/ai-engine/prevention/warnings?hours=24`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/ai-engine/cost/scan`, { headers: headers() }).then(r => r.json()),
                fetch(`${API}/api/ai-engine/noise/top-buckets?limit=20`, { headers: headers() }).then(r => r.json()),
            ]);
            setSummary(s);
            setInsights(i.insights || []);
            setWarnings(w.warnings || []);
            setCostRecs(c.recommendations || []);
            setNoiseBuckets(n.buckets || []);
        } catch { toast.error('Failed to load AI engine data'); }
    };

    useEffect(() => { loadAll(); }, []);

    const runPreventionScan = async () => {
        if (user?.role !== 'admin') { toast.error('Admin only'); return; }
        setScanning(true);
        try {
            const r = await fetch(`${API}/api/ai-engine/prevention/scan`, { method: 'POST', headers: headers() });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Scan failed');
            toast.success(`Prevention scan complete — ${(d.warnings || []).length} warning(s)`);
            loadAll();
        } catch (e) { toast.error(e.message); }
        finally { setScanning(false); }
    };

    if (!user) return <Navigate to="/login" replace />;

    return (
        <div className="space-y-5" data-testid="ai-insight-panel">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-gradient-to-br from-[#F5B841]/20 to-amber-500/10 border border-[#F5B841]/30 rounded-lg">
                        <Brain className="w-5 h-5 text-[#F5B841]" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-white">Autonomous AI Engine</h1>
                        <p className="text-xs text-white/50">
                            Context · Multi-agent · Prevention · Noise reduction · Cost optimization · Unified insights
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {user?.role === 'admin' && (
                        <Button size="sm" onClick={runPreventionScan} disabled={scanning}
                                className="bg-cyan-500 hover:bg-cyan-500/90 text-black text-xs font-semibold"
                                data-testid="prevention-scan-btn">
                            {scanning ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Activity className="w-3.5 h-3.5 mr-1.5" />}
                            Run Prevention Scan
                        </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={loadAll} className="border-white/10 text-white/70" data-testid="refresh-btn">
                        <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Stat row */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <StatCard icon={Sparkles} label="24h" value={summary.insights_total} sub="Insights generated" color="cyan" testId="stat-insights" />
                    <StatCard icon={AlertCircle} label="pending" value={summary.insights_pending_review} sub="Awaiting admin approval" color="amber" testId="stat-pending" />
                    <StatCard icon={TrendingDown} label="reduction" value={`${summary.noise_reduction_pct}%`} sub="Noise suppressed" color="emerald" testId="stat-noise" />
                    <StatCard icon={AlertTriangle} label="prevention" value={summary.prevention_warnings} sub="Early warnings" color="purple" testId="stat-prevention" />
                    <StatCard icon={DollarSign} label="cost" value={summary.cost_recommendations} sub="Optimization wins" color="green" testId="stat-cost" />
                </div>
            )}

            <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="bg-[#0a0a0a] border border-white/10">
                    <TabsTrigger value="insights" data-testid="tab-insights"><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Insights</TabsTrigger>
                    <TabsTrigger value="prevention" data-testid="tab-prevention"><Activity className="w-3.5 h-3.5 mr-1.5" /> Prevention</TabsTrigger>
                    <TabsTrigger value="cost" data-testid="tab-cost"><DollarSign className="w-3.5 h-3.5 mr-1.5" /> Cost</TabsTrigger>
                    <TabsTrigger value="noise" data-testid="tab-noise"><TrendingDown className="w-3.5 h-3.5 mr-1.5" /> Noise</TabsTrigger>
                    <TabsTrigger value="diagnose" data-testid="tab-diagnose"><Search className="w-3.5 h-3.5 mr-1.5" /> Diagnose</TabsTrigger>
                    <TabsTrigger value="test" data-testid="tab-test"><Eye className="w-3.5 h-3.5 mr-1.5" /> Test Pipeline</TabsTrigger>
                </TabsList>

                <TabsContent value="insights" className="mt-4">
                    <ScrollArea className="h-[calc(100vh-22rem)]">
                        <div className="space-y-3 pr-2">
                            {insights.length === 0 && (
                                <p className="text-sm text-white/40 text-center py-12">
                                    No insights yet. Use <strong>Test Pipeline</strong> to generate a sample, or trigger from real events.
                                </p>
                            )}
                            {insights.map(i => <InsightCard key={i.id} insight={i} />)}
                        </div>
                    </ScrollArea>
                </TabsContent>

                <TabsContent value="prevention" className="mt-4">
                    <ScrollArea className="h-[calc(100vh-22rem)]">
                        <div className="space-y-2 pr-2">
                            {warnings.length === 0 && (
                                <p className="text-sm text-white/40 text-center py-12">
                                    No prevention warnings. Click <strong>Run Prevention Scan</strong> to scan all monitors against rolling 7-day baselines.
                                </p>
                            )}
                            {warnings.map((w, i) => (
                                <ListItemCard
                                    key={w.id || i}
                                    icon={w.severity === 'critical' ? AlertTriangle : Activity}
                                    title={`${w.monitor_name} · ${w.message}`}
                                    sub={`Detected ${new Date(w.detected_at).toLocaleString()}`}
                                    badges={[
                                        `severity ${w.severity}`,
                                        `ETA ${w.eta_minutes_to_incident} min`,
                                        ...(w.drivers || []),
                                    ]}
                                    color={w.severity === 'critical' ? 'red' : 'amber'}
                                />
                            ))}
                        </div>
                    </ScrollArea>
                </TabsContent>

                <TabsContent value="cost" className="mt-4">
                    <ScrollArea className="h-[calc(100vh-22rem)]">
                        <div className="space-y-2 pr-2">
                            {costRecs.length === 0 && (
                                <p className="text-sm text-white/40 text-center py-12">No cost optimization opportunities found.</p>
                            )}
                            {costRecs.map((r, i) => (
                                <ListItemCard
                                    key={i}
                                    icon={DollarSign}
                                    title={`${r.kind.replace(/_/g, ' ')} — ${r.monitor_name || r.url || `${r.count || ''} item(s)`}`}
                                    sub={r.rationale}
                                    badges={[r.estimated_savings, `${Math.round((r.confidence || 0) * 100)}% confidence`]}
                                    color="emerald"
                                />
                            ))}
                        </div>
                    </ScrollArea>
                </TabsContent>

                <TabsContent value="noise" className="mt-4">
                    <ScrollArea className="h-[calc(100vh-22rem)]">
                        <div className="space-y-2 pr-2">
                            {noiseBuckets.length === 0 && (
                                <p className="text-sm text-white/40 text-center py-12">No noise buckets recorded yet.</p>
                            )}
                            {noiseBuckets.map((b, i) => (
                                <ListItemCard
                                    key={b.fingerprint || i}
                                    icon={TrendingDown}
                                    title={`${b.alert || 'Unknown alert'} · ${b.service || 'unknown service'}`}
                                    sub={`First seen ${new Date(b.first_seen).toLocaleString()}, last ${new Date(b.last_seen).toLocaleString()}`}
                                    badges={[
                                        `${b.count} fires`,
                                        `${b.suppressed_count || 0} suppressed`,
                                        b.host ? `host ${b.host}` : null,
                                    ].filter(Boolean)}
                                    color="zinc"
                                />
                            ))}
                        </div>
                    </ScrollArea>
                </TabsContent>

                <TabsContent value="diagnose" className="mt-4">
                    <div className="space-y-4" data-testid="diagnose-panel-wrap">
                        <Card className="bg-[#0a0a0a] border-white/10">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm flex items-center gap-2">
                                    <Brain className="w-4 h-4 text-violet-300" /> AIOps Service Diagnose
                                </CardTitle>
                                <CardDescription className="text-xs">
                                    Fuses Context Engine + recent traces + prior insights and asks the AI for a structured Senior-SRE diagnosis.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="flex flex-col md:flex-row gap-2 items-stretch md:items-center">
                                    <Input
                                        value={diagInput}
                                        onChange={(e) => setDiagInput(e.target.value)}
                                        placeholder="Service name (e.g. payment-service)"
                                        className="bg-black/40 border-white/10 text-sm"
                                        data-testid="diagnose-input"
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && diagInput.trim()) {
                                                setDiagService(diagInput.trim());
                                            }
                                        }}
                                    />
                                    <select
                                        value={diagHours}
                                        onChange={(e) => setDiagHours(Number(e.target.value))}
                                        className="bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm text-white/85"
                                        data-testid="diagnose-hours"
                                    >
                                        <option value={1}>last 1h</option>
                                        <option value={6}>last 6h</option>
                                        <option value={24}>last 24h</option>
                                        <option value={168}>last 7d</option>
                                    </select>
                                    <Button
                                        onClick={() => diagInput.trim() && setDiagService(diagInput.trim())}
                                        disabled={!diagInput.trim()}
                                        className="bg-violet-500/[0.15] border border-violet-500/40 text-violet-200 hover:bg-violet-500/[0.25]"
                                        data-testid="diagnose-run-btn"
                                    >
                                        <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Run Diagnosis
                                    </Button>
                                </div>
                                <p className="mt-2 text-[11px] text-white/40">
                                    Tip: try a known service from your trace data — the AI will pull events, dependency topology,
                                    runbook (if any), errored traces, and prior insights into one consolidated report.
                                </p>
                            </CardContent>
                        </Card>

                        {diagService && (
                            <AIOpsDiagnosePanel
                                service={diagService}
                                hours={diagHours}
                                onClose={() => setDiagService(null)}
                            />
                        )}
                    </div>
                </TabsContent>

                <TabsContent value="test" className="mt-4">
                    <div className="grid lg:grid-cols-2 gap-4">
                        <DemoEventTester onProcessed={loadAll} />
                        <Card className="bg-[#0a0a0a] border-white/10">
                            <CardHeader className="pb-3">
                                <CardTitle className="flex items-center gap-2 text-sm">
                                    <Cpu className="w-4 h-4 text-[#F5B841]" /> How the Pipeline Works
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ol className="space-y-2 text-xs text-white/70">
                                    {[
                                        'Event arrives at /api/ai-engine/process',
                                        'Context Engine enriches with last 50 same-service events, topology, runbook, baseline',
                                        'Noise Reducer fingerprints + suppresses if duplicate within 10-min window',
                                        'Agents (SRE / Security / Cost) emit verdicts with confidence scores',
                                        'Root-Cause Inference walks topology + history to suggest cause',
                                        'Recommended Action assembled — risk-classified, gated by Auto-Action Allowlist',
                                        'High-risk actions queued for admin approval via AI Copilot workflow',
                                    ].map((step, i) => (
                                        <li key={i} className="flex items-start gap-2">
                                            <span className="w-5 h-5 rounded-full bg-[#F5B841]/15 border border-[#F5B841]/30 text-[#F5B841] text-[10px] flex items-center justify-center shrink-0 font-bold">{i + 1}</span>
                                            {step}
                                        </li>
                                    ))}
                                </ol>
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
}
