import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Bell, Plus, Trash2, Pencil, PlayCircle, AlertCircle, CheckCircle2,
    RefreshCw, X, Zap,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const SEV_COLORS = {
    critical: 'bg-red-500/15 text-red-300 border-red-500/30',
    high:     'bg-orange-500/15 text-orange-300 border-orange-500/30',
    medium:   'bg-amber-500/15 text-amber-300 border-amber-500/30',
    low:      'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    info:     'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
};

const EMPTY_RULE = {
    name: '',
    service: '',
    operation: '',
    rule_type: 'latency',
    threshold_ms: 1000,
    threshold_pct: 5,
    metric: 'p95',
    window_minutes: 5,
    min_traces: 5,
    severity: 'high',
    enabled: true,
};

export default function TraceAlertRulesTab({ services = [] }) {
    const [rules, setRules] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);
    const [busy, setBusy] = useState(false);
    const [evalBusy, setEvalBusy] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/api/traces/alert-rules`, { headers: authHeaders() });
            const d = await r.json();
            setRules(d.rules || []);
        } catch (e) {
            toast.error('Failed to load alert rules');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const save = async () => {
        if (!editing.service.trim()) { toast.error('Service is required'); return; }
        setBusy(true);
        try {
            const payload = { ...editing };
            // Drop empty operation
            if (!payload.operation?.trim()) payload.operation = null;
            const method = payload.id ? 'PUT' : 'POST';
            const url = payload.id ? `${API}/api/traces/alert-rules/${payload.id}` : `${API}/api/traces/alert-rules`;
            const r = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(payload) });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`Rule ${payload.id ? 'updated' : 'created'}`);
            setEditing(null);
            load();
        } catch (e) {
            toast.error(`Save failed: ${e.message}`);
        } finally {
            setBusy(false);
        }
    };

    const remove = async (rule) => {
        if (!window.confirm(`Delete rule "${rule.name}"?`)) return;
        try {
            const r = await fetch(`${API}/api/traces/alert-rules/${rule.id}`, {
                method: 'DELETE', headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Rule deleted');
            load();
        } catch (e) {
            toast.error(`Delete failed: ${e.message}`);
        }
    };

    const evaluateNow = async () => {
        setEvalBusy(true);
        try {
            const r = await fetch(`${API}/api/traces/alert-rules/evaluate`, {
                method: 'POST', headers: authHeaders(),
            });
            const d = await r.json();
            const breaching = (d.results || []).filter((x) => x.breaching).length;
            toast.success(`Evaluated ${d.evaluated} rule(s) · ${breaching} breaching`);
            load();
        } catch (e) {
            toast.error(`Eval failed: ${e.message}`);
        } finally {
            setEvalBusy(false);
        }
    };

    return (
        <div className="space-y-4" data-testid="trace-alert-rules-tab">
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                    <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Bell className="w-5 h-5 text-amber-400" /> Trace-Driven Alert Rules
                    </h2>
                    <p className="text-xs text-white/50 mt-1">
                        Alert when latency or error rate for a service breaches a threshold. Evaluator runs every 60s.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={evaluateNow} disabled={evalBusy} data-testid="evaluate-now-btn">
                        {evalBusy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <PlayCircle className="w-4 h-4 mr-1.5" />}
                        Evaluate Now
                    </Button>
                    <Button size="sm" onClick={() => setEditing({ ...EMPTY_RULE })} data-testid="new-alert-rule-btn">
                        <Plus className="w-4 h-4 mr-1.5" /> New Rule
                    </Button>
                </div>
            </div>

            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-3">
                    {loading ? (
                        <div className="py-10 text-center"><RefreshCw className="w-5 h-5 text-white/40 animate-spin inline" /></div>
                    ) : rules.length === 0 ? (
                        <div className="py-10 text-center text-white/40 text-sm" data-testid="no-rules">
                            <Zap className="w-8 h-8 mx-auto mb-2 opacity-40" />
                            No alert rules yet. Click <strong>New Rule</strong> to create your first SLO.
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            {rules.map((r) => {
                                const breaching = r.last_state === 'breaching';
                                return (
                                    <div
                                        key={r.id}
                                        className={`p-3 rounded-lg border ${
                                            breaching ? 'border-red-500/40 bg-red-500/[0.04]' : 'border-white/10 bg-black/30'
                                        }`}
                                        data-testid={`rule-row-${r.id}`}
                                    >
                                        <div className="flex items-start justify-between gap-3 flex-wrap">
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2 flex-wrap mb-1">
                                                    {breaching
                                                        ? <AlertCircle className="w-4 h-4 text-red-400" />
                                                        : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                                                    <span className="text-sm font-semibold text-white truncate">{r.name}</span>
                                                    <Badge className={`text-[10px] border ${SEV_COLORS[r.severity] || SEV_COLORS.info}`}>
                                                        {r.severity}
                                                    </Badge>
                                                    {!r.enabled && (
                                                        <Badge className="text-[10px] bg-zinc-500/15 text-zinc-400 border border-zinc-500/30">disabled</Badge>
                                                    )}
                                                    {breaching && (
                                                        <Badge className="text-[10px] bg-red-500/15 text-red-300 border border-red-500/30">BREACHING</Badge>
                                                    )}
                                                </div>
                                                <div className="text-[11px] text-white/65">
                                                    <code className="text-cyan-200">{r.service}{r.operation ? `.${r.operation}` : ''}</code>
                                                    {' · '}
                                                    {r.rule_type === 'latency'
                                                        ? <>{r.metric} latency &gt; <strong className="text-white">{r.threshold_ms} ms</strong></>
                                                        : <>error rate &gt; <strong className="text-white">{r.threshold_pct}%</strong></>}
                                                    {' · '}window {r.window_minutes}m · min {r.min_traces} traces
                                                </div>
                                                {r.last_evaluated_at && (
                                                    <div className="text-[10px] text-white/40 mt-0.5">
                                                        Last eval: {new Date(r.last_evaluated_at).toLocaleString()}
                                                        {r.last_value !== null && r.last_value !== undefined && (
                                                            <> · observed {Number(r.last_value).toFixed(2)} ({r.last_samples ?? 0} samples)</>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-1 shrink-0">
                                                <Button variant="ghost" size="sm" onClick={() => setEditing(r)} data-testid={`edit-rule-${r.id}`}>
                                                    <Pencil className="w-3.5 h-3.5" />
                                                </Button>
                                                <Button variant="ghost" size="sm" onClick={() => remove(r)} data-testid={`delete-rule-${r.id}`}>
                                                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
                <DialogContent className="bg-zinc-950 border-white/10 max-w-lg" data-testid="rule-edit-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white">
                            {editing?.id ? 'Edit Alert Rule' : 'New Alert Rule'}
                        </DialogTitle>
                        <DialogDescription className="text-white/50 text-xs">
                            Fire an alert when a service breaches the latency or error-rate threshold for the configured window.
                        </DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <div className="space-y-3">
                            <div>
                                <Label className="text-xs text-white/70">Rule name</Label>
                                <Input
                                    value={editing.name}
                                    onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                                    placeholder="checkout-api latency SLO"
                                    className="bg-black/40 border-white/10 mt-1"
                                    data-testid="rule-name-input"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Service</Label>
                                    {services.length ? (
                                        <Select value={editing.service} onValueChange={(v) => setEditing({ ...editing, service: v })}>
                                            <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="rule-service-select">
                                                <SelectValue placeholder="select service" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {services.map((s) => (<SelectItem key={s} value={s}>{s}</SelectItem>))}
                                            </SelectContent>
                                        </Select>
                                    ) : (
                                        <Input
                                            value={editing.service}
                                            onChange={(e) => setEditing({ ...editing, service: e.target.value })}
                                            placeholder="checkout-api"
                                            className="bg-black/40 border-white/10 mt-1"
                                            data-testid="rule-service-input"
                                        />
                                    )}
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Operation (optional)</Label>
                                    <Input
                                        value={editing.operation || ''}
                                        onChange={(e) => setEditing({ ...editing, operation: e.target.value })}
                                        placeholder="POST /api/checkout"
                                        className="bg-black/40 border-white/10 mt-1"
                                        data-testid="rule-operation-input"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Rule type</Label>
                                    <Select value={editing.rule_type} onValueChange={(v) => setEditing({ ...editing, rule_type: v })}>
                                        <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="rule-type-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="latency">Latency</SelectItem>
                                            <SelectItem value="error_rate">Error rate</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Severity</Label>
                                    <Select value={editing.severity} onValueChange={(v) => setEditing({ ...editing, severity: v })}>
                                        <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="rule-severity-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="critical">Critical</SelectItem>
                                            <SelectItem value="high">High</SelectItem>
                                            <SelectItem value="medium">Medium</SelectItem>
                                            <SelectItem value="low">Low</SelectItem>
                                            <SelectItem value="info">Info</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            {editing.rule_type === 'latency' ? (
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-xs text-white/70">Metric</Label>
                                        <Select value={editing.metric} onValueChange={(v) => setEditing({ ...editing, metric: v })}>
                                            <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="rule-metric-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="p95">P95</SelectItem>
                                                <SelectItem value="avg">Average</SelectItem>
                                                <SelectItem value="max">Max</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label className="text-xs text-white/70">Threshold (ms)</Label>
                                        <Input
                                            type="number" min="0"
                                            value={editing.threshold_ms}
                                            onChange={(e) => setEditing({ ...editing, threshold_ms: Number(e.target.value) })}
                                            className="bg-black/40 border-white/10 mt-1"
                                            data-testid="rule-threshold-ms-input"
                                        />
                                    </div>
                                </div>
                            ) : (
                                <div>
                                    <Label className="text-xs text-white/70">Error-rate threshold (%)</Label>
                                    <Input
                                        type="number" min="0" max="100" step="0.1"
                                        value={editing.threshold_pct}
                                        onChange={(e) => setEditing({ ...editing, threshold_pct: Number(e.target.value) })}
                                        className="bg-black/40 border-white/10 mt-1"
                                        data-testid="rule-threshold-pct-input"
                                    />
                                </div>
                            )}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Window (minutes)</Label>
                                    <Input
                                        type="number" min="1" max="1440"
                                        value={editing.window_minutes}
                                        onChange={(e) => setEditing({ ...editing, window_minutes: Number(e.target.value) })}
                                        className="bg-black/40 border-white/10 mt-1"
                                        data-testid="rule-window-input"
                                    />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Min traces</Label>
                                    <Input
                                        type="number" min="1"
                                        value={editing.min_traces}
                                        onChange={(e) => setEditing({ ...editing, min_traces: Number(e.target.value) })}
                                        className="bg-black/40 border-white/10 mt-1"
                                        data-testid="rule-min-traces-input"
                                    />
                                </div>
                            </div>
                            <div className="flex items-center justify-between pt-2">
                                <Label className="text-xs text-white/70">Enabled</Label>
                                <Switch
                                    checked={editing.enabled}
                                    onCheckedChange={(v) => setEditing({ ...editing, enabled: v })}
                                    data-testid="rule-enabled-switch"
                                />
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEditing(null)}>
                            <X className="w-4 h-4 mr-1.5" /> Cancel
                        </Button>
                        <Button onClick={save} disabled={busy} data-testid="save-rule-btn">
                            {busy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
