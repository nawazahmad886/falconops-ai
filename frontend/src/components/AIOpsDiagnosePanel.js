import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Sparkles, RefreshCw, AlertTriangle, Activity, Server, ChevronRight, XCircle, Brain } from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const VERDICT_COLOR = (text = '') => {
    const t = text.toLowerCase();
    if (t.includes('failing') || t.includes('failed') || t.includes('outage') || t.includes('critical')) {
        return { bg: 'from-red-500/[0.10]', border: 'border-red-500/40', text: 'text-red-300' };
    }
    if (t.includes('degraded') || t.includes('slow') || t.includes('warning')) {
        return { bg: 'from-amber-500/[0.10]', border: 'border-amber-500/40', text: 'text-amber-300' };
    }
    if (t.includes('healthy') || t.includes('normal') || t.includes('operational')) {
        return { bg: 'from-emerald-500/[0.08]', border: 'border-emerald-500/40', text: 'text-emerald-300' };
    }
    return { bg: 'from-violet-500/[0.08]', border: 'border-violet-500/40', text: 'text-violet-300' };
};

/**
 * Inline drawer-style component that renders a full AIOps Diagnose panel
 * for a given service. Embedded on APMTracesPage (trace detail) and reusable.
 *
 * Props:
 *   service: string (required)
 *   hours:   number (defaults to 24)
 *   onClose: () => void (optional — renders a close X if provided)
 *   autoRun: boolean — auto-fetch on mount (default true)
 */
export default function AIOpsDiagnosePanel({ service, hours = 24, onClose, autoRun = true }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const run = async () => {
        if (!service) return;
        setLoading(true);
        setError(null);
        try {
            const r = await fetch(`${API}/api/aiops/diagnose/${encodeURIComponent(service)}?hours=${hours}`, {
                headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            const d = await r.json();
            setData(d);
            toast.success(`AI diagnosis ready · ${d.diagnosis?.provider || 'rule-based'}`);
        } catch (e) {
            setError(e.message?.slice(0, 200) || 'Diagnosis failed');
            toast.error('AI diagnosis failed');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (autoRun && service) run();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [service, hours]);

    const diag = data?.diagnosis;
    const sig = data?.signals;
    const v = VERDICT_COLOR(diag?.verdict || '');

    return (
        <Card
            className={`bg-gradient-to-br ${v.bg} via-black/40 to-black/40 ${v.border}`}
            data-testid="aiops-diagnose-panel"
        >
            <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2 flex-wrap">
                    <Brain className="w-4 h-4 text-violet-300" />
                    <span className="uppercase tracking-widest text-violet-200/90 text-[11px] font-semibold">
                        AI Diagnosis · {service}
                    </span>
                    <Badge className="text-[10px] bg-white/5 text-white/80 border border-white/10">
                        last {hours}h
                    </Badge>
                    {diag?.provider && (
                        <Badge className="text-[10px] bg-violet-500/15 text-violet-200 border border-violet-500/30">
                            {diag.provider}
                            {diag.model ? ` · ${diag.model}` : ''}
                        </Badge>
                    )}
                    {diag?.fallback_used && (
                        <Badge className="text-[10px] bg-amber-500/15 text-amber-300 border border-amber-500/30">
                            fallback
                        </Badge>
                    )}
                    <div className="flex-1" />
                    <Button size="sm" variant="ghost" onClick={run} disabled={loading} data-testid="diagnose-rerun-btn">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    {onClose && (
                        <Button size="sm" variant="ghost" onClick={onClose} data-testid="diagnose-close-btn">
                            <XCircle className="w-4 h-4" />
                        </Button>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent>
                {loading && !data && (
                    <div className="flex items-center justify-center py-8 text-white/40 text-xs gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin" /> Running AI pipeline…
                    </div>
                )}
                {error && (
                    <div className="text-red-300 text-xs flex items-center gap-2 py-3">
                        <AlertTriangle className="w-4 h-4" /> {error}
                    </div>
                )}
                {diag && (
                    <ScrollArea className="max-h-[60vh]">
                        <div className="space-y-4 pr-2">
                            {/* Verdict */}
                            {diag.verdict && (
                                <div className={`p-3 rounded-lg border ${v.border} bg-black/30`} data-testid="diag-verdict">
                                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">Verdict</div>
                                    <div className={`text-sm ${v.text} leading-relaxed`}>{diag.verdict}</div>
                                </div>
                            )}

                            {/* Root cause */}
                            {diag.root_cause && (
                                <div className="p-3 rounded-lg border border-white/10 bg-black/30" data-testid="diag-root-cause">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Sparkles className="w-3.5 h-3.5 text-violet-300" />
                                        <span className="text-[10px] uppercase tracking-widest text-violet-200/80">
                                            Most Likely Root Cause
                                        </span>
                                    </div>
                                    <p className="text-sm text-white/85 leading-relaxed">{diag.root_cause}</p>
                                </div>
                            )}

                            {/* Evidence */}
                            {(diag.evidence || []).length > 0 && (
                                <div className="p-3 rounded-lg border border-white/10 bg-black/30" data-testid="diag-evidence">
                                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2">Evidence</div>
                                    <ul className="space-y-1.5">
                                        {diag.evidence.map((e, i) => (
                                            <li key={i} className="text-[12px] text-white/75 flex items-start gap-1.5">
                                                <ChevronRight className="w-3 h-3 mt-0.5 text-violet-400/70 shrink-0" />
                                                <span>{e}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Blast radius */}
                            {diag.blast_radius && (
                                <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/[0.04]" data-testid="diag-blast-radius">
                                    <div className="text-[10px] uppercase tracking-widest text-amber-300/80 mb-1">
                                        Blast Radius
                                    </div>
                                    <p className="text-[13px] text-white/85 leading-relaxed">{diag.blast_radius}</p>
                                </div>
                            )}

                            {/* Action grid */}
                            <div className="grid md:grid-cols-2 gap-3">
                                {(diag.immediate_action || []).length > 0 && (
                                    <div className="p-3 rounded-lg border border-red-500/30 bg-red-500/[0.04]" data-testid="diag-immediate">
                                        <div className="text-[10px] uppercase tracking-widest text-red-300/80 mb-2">
                                            Immediate Action
                                        </div>
                                        <ul className="space-y-1.5">
                                            {diag.immediate_action.map((a, i) => (
                                                <li key={i} className="text-[12px] text-white/85 flex items-start gap-1.5">
                                                    <Activity className="w-3 h-3 mt-0.5 text-red-300/70 shrink-0" />
                                                    <span>{a}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {(diag.longer_term_fix || []).length > 0 && (
                                    <div className="p-3 rounded-lg border border-cyan-500/30 bg-cyan-500/[0.04]" data-testid="diag-longer-term">
                                        <div className="text-[10px] uppercase tracking-widest text-cyan-300/80 mb-2">
                                            Longer-term Fix
                                        </div>
                                        <ul className="space-y-1.5">
                                            {diag.longer_term_fix.map((a, i) => (
                                                <li key={i} className="text-[12px] text-white/85 flex items-start gap-1.5">
                                                    <Sparkles className="w-3 h-3 mt-0.5 text-cyan-300/70 shrink-0" />
                                                    <span>{a}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>

                            {/* Confidence */}
                            {diag.confidence_note && (
                                <div className="text-[11px] text-white/50 italic" data-testid="diag-confidence">
                                    Confidence — {diag.confidence_note}
                                </div>
                            )}

                            {/* Signals strip */}
                            {sig && (
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-white/5" data-testid="diag-signals">
                                    <div className="p-2 bg-black/30 rounded text-center">
                                        <Activity className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                                        <div className="text-white font-mono text-sm">{sig.history_count ?? 0}</div>
                                        <div className="text-white/40 text-[10px]">events 7d</div>
                                    </div>
                                    <div className="p-2 bg-black/30 rounded text-center">
                                        <Server className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                                        <div className="text-white font-mono text-sm">
                                            {(sig.topology?.upstream?.length || 0)}/{(sig.topology?.downstream?.length || 0)}
                                        </div>
                                        <div className="text-white/40 text-[10px]">up/down</div>
                                    </div>
                                    <div className="p-2 bg-black/30 rounded text-center">
                                        <AlertTriangle className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                                        <div className="text-white font-mono text-sm">{sig.trace_summary?.errored ?? 0}</div>
                                        <div className="text-white/40 text-[10px]">err traces</div>
                                    </div>
                                    <div className="p-2 bg-black/30 rounded text-center">
                                        <Sparkles className="w-3 h-3 mx-auto mb-0.5 text-white/40" />
                                        <div className="text-white font-mono text-sm">{sig.prior_insights_count ?? 0}</div>
                                        <div className="text-white/40 text-[10px]">prior insights</div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                )}
            </CardContent>
        </Card>
    );
}
