/* eslint-disable react-hooks/exhaustive-deps */
/**
 * AI Log Analyzer Tab — Senior-AI-Architect-grade log triage UI.
 *
 * Paste any logs → instant LLM diagnosis with severity, root cause,
 * suggested fix, recurring-pattern detection, and "Explain this error"
 * shortcuts on the highlighted lines.
 */
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Terminal, Sparkles, AlertTriangle, AlertCircle, CheckCircle2, Activity,
    Trash2, FileText, ListChecks, Zap, RotateCcw, Loader2, BookOpen, Layers, Database, Workflow,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('falconToken');
const headers = () => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` });
async function api(path, opts = {}) {
    const r = await fetch(`${API}${path}`, { headers: headers(), ...opts });
    if (!r.ok) throw new Error((await r.text()).slice(0, 300) || `HTTP ${r.status}`);
    return r.json();
}

const SEVERITY_STYLES = {
    Low:      { Icon: CheckCircle2,  cls: 'border-emerald-500/40 text-emerald-200 bg-emerald-500/10' },
    Medium:   { Icon: Activity,      cls: 'border-amber-500/40 text-amber-200 bg-amber-500/10' },
    High:     { Icon: AlertTriangle, cls: 'border-orange-500/40 text-orange-200 bg-orange-500/10' },
    Critical: { Icon: AlertCircle,   cls: 'border-red-500/40 text-red-200 bg-red-500/10' },
};

const SAMPLE = `2026-02-23 12:01:02 INFO  Starting payments-service v3.4.1
2026-02-23 12:01:05 ERROR Connection refused: postgresql://db:5432/payments
2026-02-23 12:01:06 ERROR Retry 1/3 failed: connection refused
2026-02-23 12:01:08 ERROR Retry 2/3 failed: connection refused
2026-02-23 12:01:10 FATAL Connection pool exhausted
2026-02-23 12:01:11 ERROR java.lang.OutOfMemoryError: Java heap space
2026-02-23 12:01:12 ERROR pod payments-7f4d5b-xkz9z OOMKilled, restart 4`;

function SeverityBadge({ severity }) {
    const s = SEVERITY_STYLES[severity] || SEVERITY_STYLES.Medium;
    return (
        <Badge className={`text-xs px-2.5 py-1 border font-bold uppercase tracking-wider ${s.cls}`}
               data-testid={`severity-${severity}`}>
            <s.Icon className="w-3.5 h-3.5 mr-1.5" /> {severity}
        </Badge>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────────

export default function LogAnalyzerTab() {
    const [logs, setLogs] = useState('');
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    const [history, setHistory] = useState([]);
    const [stats, setStats] = useState(null);
    const [patterns, setPatterns] = useState([]);
    const [explainOpen, setExplainOpen] = useState(false);
    const [explainLoading, setExplainLoading] = useState(false);
    const [explainResult, setExplainResult] = useState(null);
    const [remediating, setRemediating] = useState(false);

    const onRemediate = async () => {
        if (!result?.id) return;
        setRemediating(true);
        try {
            const r = await api(`/api/log-analyzer/analysis/${result.id}/remediate`, { method: 'POST' });
            setResult(prev => ({ ...prev, remediation: r.remediation }));
            toast.success('N8n remediation workflow triggered');
        } catch (e) {
            toast.error(`Remediation failed: ${e.message}`);
        } finally {
            setRemediating(false);
        }
    };

    const loadSidebars = () => {
        api('/api/log-analyzer/history?limit=10').then(d => setHistory(d.items || [])).catch(() => {});
        api('/api/log-analyzer/stats').then(setStats).catch(() => {});
        api('/api/log-analyzer/patterns').then(d => setPatterns(d.patterns || [])).catch(() => {});
    };
    useEffect(loadSidebars, []);

    const onAnalyze = async () => {
        if (!logs.trim()) {
            toast.error('Paste some logs first');
            return;
        }
        setAnalyzing(true);
        setResult(null);
        try {
            const r = await api('/api/log-analyzer/analyze', {
                method: 'POST',
                body: JSON.stringify({ logs, source: 'paste' }),
            });
            setResult(r);
            toast.success(r.cached ? 'Cached verdict — sub-second response' : `Analyzed in ${Math.round(r.pipeline_latency_ms || 0)}ms`);
            loadSidebars();
        } catch (e) {
            toast.error(`Analyze failed: ${e.message}`);
        } finally {
            setAnalyzing(false);
        }
    };

    const onClear = () => { setLogs(''); setResult(null); };
    const onLoadSample = () => setLogs(SAMPLE);

    const onLoadHistory = async (id) => {
        try {
            const d = await api(`/api/log-analyzer/analysis/${id}`);
            setResult(d);
            setLogs(d.raw_preview || '');
        } catch (e) {
            toast.error(`Load failed: ${e.message}`);
        }
    };

    const onDelete = async (id, e) => {
        e?.stopPropagation();
        try {
            await api(`/api/log-analyzer/analysis/${id}`, { method: 'DELETE' });
            toast.success('Analysis deleted');
            loadSidebars();
            if (result?.id === id) setResult(null);
        } catch (err) {
            toast.error(`Delete failed: ${err.message}`);
        }
    };

    const onExplain = async (errorText) => {
        setExplainOpen(true);
        setExplainLoading(true);
        setExplainResult(null);
        try {
            const r = await api('/api/log-analyzer/explain', {
                method: 'POST',
                body: JSON.stringify({ error: errorText, context: logs.slice(0, 2000) }),
            });
            setExplainResult(r);
        } catch (e) {
            toast.error(`Explain failed: ${e.message}`);
            setExplainOpen(false);
        } finally {
            setExplainLoading(false);
        }
    };

    return (
        <div className="space-y-4" data-testid="log-analyzer-tab">
            {/* KPI strip */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    <Card className="bg-black/40 border-white/10" data-testid="la-stat-total">
                        <CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Total Analyses</div>
                            <div className="text-base font-bold text-white">{stats.total_analyses}</div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-red-500/30" data-testid="la-stat-critical">
                        <CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Critical</div>
                            <div className="text-base font-bold text-red-300">{stats.critical_count}</div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-orange-500/30" data-testid="la-stat-high">
                        <CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">High</div>
                            <div className="text-base font-bold text-orange-300">{stats.high_count}</div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-white/10" data-testid="la-stat-last">
                        <CardContent className="p-2.5">
                            <div className="text-[10px] uppercase tracking-widest text-white/40">Last Severity</div>
                            <div className="text-base font-bold text-white">{stats.last_severity || '–'}</div>
                        </CardContent>
                    </Card>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* LEFT 2/3 — input + result */}
                <div className="lg:col-span-2 space-y-3">
                    <Card className="bg-black/40 border-white/10">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2 text-white">
                                <Terminal className="w-4 h-4 text-cyan-400" /> Paste Logs
                                <span className="text-[10px] text-white/40 ml-auto font-normal">
                                    cleans → prioritizes → chunks → LLM → caches
                                </span>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <Textarea
                                rows={12}
                                value={logs}
                                onChange={(e) => setLogs(e.target.value)}
                                placeholder="Paste raw logs (any format) — multi-line, ANSI codes, timestamps OK..."
                                className="bg-black/60 border-white/10 text-white font-mono text-[12px] resize-vertical"
                                data-testid="logs-textarea"
                            />
                            <div className="flex flex-wrap items-center gap-2">
                                <Button onClick={onAnalyze} disabled={analyzing || !logs.trim()}
                                        className="h-9 bg-fuchsia-500/20 border border-fuchsia-500/40 text-fuchsia-200 hover:bg-fuchsia-500/30"
                                        data-testid="analyze-btn">
                                    {analyzing
                                        ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Analyzing…</>
                                        : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Analyze</>}
                                </Button>
                                <Button variant="outline" onClick={onLoadSample}
                                        className="h-9 border-white/15 text-white/70" data-testid="sample-btn">
                                    <FileText className="w-3.5 h-3.5 mr-1.5" /> Load sample
                                </Button>
                                <Button variant="ghost" onClick={onClear}
                                        className="h-9 text-white/55" data-testid="clear-btn">
                                    <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Clear
                                </Button>
                                <span className="text-[11px] text-white/40 ml-auto">{logs.length.toLocaleString()} chars</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Result panel */}
                    {result && (
                        <Card className="bg-black/40 border-white/10" data-testid="analysis-result">
                            <CardHeader className="pb-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <CardTitle className="text-sm text-white flex items-center gap-2">
                                        <Zap className="w-4 h-4 text-amber-400" />
                                        AI Verdict
                                    </CardTitle>
                                    <SeverityBadge severity={result.severity} />
                                    <Badge className="text-[10px] border-white/15 text-white/65 bg-black/30 border">
                                        {result.error_type || 'Unknown'}
                                    </Badge>
                                    {result.cached && (
                                        <Badge className="text-[10px] border-cyan-500/40 text-cyan-300 bg-black/30 border">
                                            <Zap className="w-3 h-3 mr-1" /> Cached
                                        </Badge>
                                    )}
                                    {result.quarantined && (
                                        <Badge className="text-[10px] border-red-500/40 text-red-300 bg-black/30 border"
                                               data-testid="quarantined-badge">
                                            Quarantined
                                        </Badge>
                                    )}
                                    {result.remediation && (
                                        <Badge className={`text-[10px] border bg-black/30 ${result.remediation.status === 'sent' ? 'border-emerald-500/40 text-emerald-300' : 'border-red-500/40 text-red-300'}`}
                                               data-testid="remediation-status-badge">
                                            N8n {result.remediation.status === 'sent' ? 'Triggered' : 'Failed'}{result.remediation.auto ? ' (auto)' : ''}
                                        </Badge>
                                    )}
                                    {(result.severity === 'High' || result.severity === 'Critical') && (
                                        <Button size="sm" onClick={onRemediate} disabled={remediating}
                                            className="h-7 text-xs ml-auto bg-orange-500/20 border border-orange-500/40 text-orange-200 hover:bg-orange-500/30"
                                            data-testid="remediate-n8n-btn">
                                            <Workflow className="w-3.5 h-3.5 mr-1.5" />
                                            {remediating ? 'Triggering…' : 'Remediate via N8n'}
                                        </Button>
                                    )}
                                    <span className="text-[10px] text-white/40 ml-auto">
                                        {result.line_count} lines · {result.chunks} chunk{result.chunks !== 1 ? 's' : ''} · {Math.round(result.pipeline_latency_ms || 0)}ms · {result.provider || ''}{result.model ? `/${result.model.slice(0, 20)}` : ''}
                                    </span>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {/* Summary */}
                                <Section title="Summary" data-testid="result-summary">
                                    <p className="text-sm text-white/85 leading-relaxed">{result.summary}</p>
                                </Section>

                                {/* Root cause */}
                                <Section title="Root Cause" data-testid="result-root-cause">
                                    <p className="text-sm text-white/85 leading-relaxed">{result.root_cause}</p>
                                </Section>

                                {/* Fix */}
                                <Section title="Suggested Fix" data-testid="result-fix">
                                    <p className="text-sm text-emerald-200/90 leading-relaxed">{result.suggested_fix}</p>
                                </Section>

                                {/* Recurring */}
                                {result.recurring_pattern && (
                                    <Section title={`Recurring Pattern · ${result.recurring_pattern.status ? 'Detected' : 'None'}`}
                                             accent={result.recurring_pattern.status ? 'border-amber-500/30' : 'border-white/10'}>
                                        <p className="text-[13px] text-white/75">{result.recurring_pattern.explanation}</p>
                                    </Section>
                                )}

                                {/* Affected components */}
                                {(result.affected_components?.length || 0) > 0 && (
                                    <Section title="Affected Components">
                                        <div className="flex flex-wrap gap-1.5">
                                            {result.affected_components.map((c) => (
                                                <Badge key={c} className="text-[10px] border-blue-500/30 text-blue-200 bg-black/30 border">
                                                    {c}
                                                </Badge>
                                            ))}
                                        </div>
                                    </Section>
                                )}

                                {/* Key lines */}
                                {(result.key_lines?.length || 0) > 0 && (
                                    <Section title="Key Lines">
                                        <div className="space-y-1">
                                            {result.key_lines.map((line, idx) => (
                                                <div key={idx}
                                                     className="text-[11px] font-mono bg-black/50 rounded p-2 flex items-start gap-2"
                                                     data-testid={`key-line-${idx}`}>
                                                    <span className="flex-1 text-white/80 break-all">{line}</span>
                                                    <Button size="sm" variant="ghost"
                                                            className="h-6 px-2 text-[10px] text-cyan-300 hover:text-cyan-200 shrink-0"
                                                            onClick={() => onExplain(line)}
                                                            data-testid={`explain-btn-${idx}`}>
                                                        <BookOpen className="w-3 h-3 mr-1" /> Explain
                                                    </Button>
                                                </div>
                                            ))}
                                        </div>
                                    </Section>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* RIGHT 1/3 — history + patterns */}
                <div className="space-y-3">
                    <Card className="bg-black/40 border-white/10">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2 text-white">
                                <ListChecks className="w-4 h-4 text-emerald-400" /> Recent Analyses
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <ScrollArea className="h-[280px] px-3 pb-3">
                                {history.length === 0 ? (
                                    <div className="text-center text-white/40 text-xs py-8">No analyses yet</div>
                                ) : (
                                    <div className="space-y-1.5">
                                        {history.map((h) => (
                                            <div key={h.id}
                                                 className="rounded border border-white/10 bg-black/30 p-2 hover:bg-black/50 cursor-pointer"
                                                 onClick={() => onLoadHistory(h.id)}
                                                 data-testid={`history-item-${h.id}`}>
                                                <div className="flex items-center gap-1.5 mb-1">
                                                    <SeverityBadge severity={h.severity} />
                                                    <span className="text-[10px] text-white/40 ml-auto">{(h.created_at || '').slice(11, 19)}</span>
                                                </div>
                                                <div className="text-[11px] text-white/80 font-semibold truncate">{h.error_type}</div>
                                                <div className="text-[10px] text-white/50 line-clamp-2">{h.summary}</div>
                                                <div className="flex items-center justify-between mt-1">
                                                    <span className="text-[9px] text-white/35">{h.line_count} lines</span>
                                                    <Button size="sm" variant="ghost" className="h-5 px-1.5 text-[9px] text-red-300/80"
                                                            onClick={(e) => onDelete(h.id, e)}
                                                            data-testid={`history-delete-${h.id}`}>
                                                        <Trash2 className="w-2.5 h-2.5" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </ScrollArea>
                        </CardContent>
                    </Card>

                    <Card className="bg-black/40 border-white/10">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2 text-white">
                                <Layers className="w-4 h-4 text-fuchsia-400" /> Top Patterns
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1.5">
                            {patterns.length === 0 ? (
                                <div className="text-center text-white/40 text-xs py-4">No patterns yet</div>
                            ) : patterns.slice(0, 8).map((p) => (
                                <div key={p.error_type} className="flex items-center gap-2"
                                     data-testid={`pattern-${p.error_type}`}>
                                    <span className="text-[11px] text-white/80 flex-1 truncate font-mono">{p.error_type}</span>
                                    <Badge className="text-[9px] border-white/15 text-white/65 bg-black/30 border">×{p.occurrences}</Badge>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Explain dialog */}
            <Dialog open={explainOpen} onOpenChange={setExplainOpen}>
                <DialogContent className="bg-[#0a0a0a] border-white/10 max-w-2xl" data-testid="explain-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white flex items-center gap-2">
                            <BookOpen className="w-4 h-4 text-cyan-400" /> Explain this error
                        </DialogTitle>
                        <DialogDescription className="text-white/55">
                            Plain-English breakdown + likely causes + next steps.
                        </DialogDescription>
                    </DialogHeader>
                    {explainLoading
                        ? <div className="py-8 text-center text-white/55 text-sm"><Loader2 className="w-5 h-5 mx-auto animate-spin mb-2" />Thinking…</div>
                        : explainResult && (
                            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
                                <div>
                                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Explanation</div>
                                    <p className="text-sm text-white/85 leading-relaxed">{explainResult.explanation}</p>
                                </div>
                                {(explainResult.likely_causes?.length || 0) > 0 && (
                                    <div>
                                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Likely causes</div>
                                        <ul className="list-disc pl-5 text-sm text-white/80 space-y-0.5">
                                            {explainResult.likely_causes.map((c, i) => <li key={i}>{c}</li>)}
                                        </ul>
                                    </div>
                                )}
                                {(explainResult.next_steps?.length || 0) > 0 && (
                                    <div>
                                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Next steps</div>
                                        <ul className="list-disc pl-5 text-sm text-emerald-200/90 space-y-0.5">
                                            {explainResult.next_steps.map((c, i) => <li key={i}>{c}</li>)}
                                        </ul>
                                    </div>
                                )}
                                {explainResult.external_docs_hint && (
                                    <div className="text-[11px] text-white/55 italic border-t border-white/10 pt-2">
                                        Search hint: <span className="font-mono text-white/80">{explainResult.external_docs_hint}</span>
                                    </div>
                                )}
                            </div>
                        )}
                </DialogContent>
            </Dialog>
        </div>
    );
}

function Section({ title, children, accent = 'border-white/10', ...rest }) {
    return (
        <div className={`rounded-md border ${accent} bg-black/30 p-3`} {...rest}>
            <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5">{title}</div>
            {children}
        </div>
    );
}
