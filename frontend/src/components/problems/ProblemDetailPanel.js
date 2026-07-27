import React from 'react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import {
    Brain, GitBranch, History, Layers, Loader2, Sparkles, X,
} from 'lucide-react';

const SEVERITY_BADGE = {
    critical: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    high: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    low: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    info: 'bg-white/10 text-white/50 border-white/20',
};

// A block that either shows real content or an honest "not available" note —
// never a fabricated placeholder. Matches the existing AI Recommendation
// panel's "review required" discipline elsewhere in this app.
const EnrichmentBlock = ({ icon: Icon, title, children, reason }) => (
    <Card className="bg-black/30 border-white/10">
        <CardHeader className="pb-2">
            <CardTitle className="text-xs text-white/70 flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5" /> {title}
            </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 text-[12px] text-white/70 space-y-1.5">
            {children || <div className="text-white/30 text-[11px]">{reason || 'Not available for this problem.'}</div>}
        </CardContent>
    </Card>
);

export default function ProblemDetailPanel({ problem, loading, onClose }) {
    if (!problem) return null;
    const enrichment = problem.enrichment || {};

    return (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="problem-detail-panel">
            <div className="absolute inset-0 bg-black/60" onClick={onClose} />
            <div className="relative w-full max-w-lg h-full bg-[#0D1117] border-l border-white/10 overflow-y-auto p-4 space-y-4">
                <div className="flex items-start justify-between gap-2">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Badge className={`text-[10px] capitalize ${SEVERITY_BADGE[problem.severity] || SEVERITY_BADGE.info}`}>
                                {problem.severity}
                            </Badge>
                            <Badge className="text-[10px] bg-white/10 text-white/50 border-white/20 capitalize">{problem.status}</Badge>
                            <span className="text-[10px] text-white/30 font-mono">{problem.id}</span>
                        </div>
                        <h2 className="text-base font-semibold text-white">{problem.title || '(untitled)'}</h2>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} data-testid="close-detail-panel">
                        <X className="w-4 h-4" />
                    </Button>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] text-white/50">
                    <div>Source: <span className="text-white/80">{problem.source_collection}</span></div>
                    <div>Affected: <span className="text-white/80">{problem.affected_count}</span></div>
                    <div>Assigned to: <span className="text-white/80">{problem.assigned_to || 'Unassigned'}</span></div>
                    <div>Assignment group: <span className="text-white/80">{problem.assignment_group || '—'}</span></div>
                    <div>Started: <span className="text-white/80">{problem.started_at}</span></div>
                    <div>Correlation ID: <span className="text-white/80 font-mono">{problem.correlation_id || '—'}</span></div>
                </div>

                {loading && (
                    <div className="flex items-center gap-2 text-white/40 text-xs py-4 justify-center">
                        <Loader2 className="w-4 h-4 animate-spin" /> Loading AI analysis, impact, and recommendations...
                    </div>
                )}

                {!loading && (
                    <div className="space-y-3">
                        <EnrichmentBlock icon={Brain} title="AI Root Cause Analysis" reason={enrichment.ai_analysis_not_available_reason}>
                            {enrichment.ai_analysis && (
                                <>
                                    <div className="text-white/80">{enrichment.ai_analysis.summary || enrichment.ai_analysis.root_cause}</div>
                                    {enrichment.ai_analysis.confidence != null && (
                                        <div className="text-white/40">Confidence: {Math.round(enrichment.ai_analysis.confidence * 100)}%</div>
                                    )}
                                </>
                            )}
                        </EnrichmentBlock>

                        <EnrichmentBlock icon={GitBranch} title="Business Impact / Blast Radius" reason={enrichment.impact_not_available_reason}>
                            {enrichment.impact && (
                                <>
                                    <div className="text-white/80">
                                        Impact level: <span className="capitalize">{enrichment.impact.impact_level || enrichment.impact.risk_level}</span>
                                    </div>
                                    {Array.isArray(enrichment.impact.blast_radius) && (
                                        <div className="text-white/40">{enrichment.impact.blast_radius.length} downstream service(s) affected</div>
                                    )}
                                </>
                            )}
                        </EnrichmentBlock>

                        <EnrichmentBlock icon={Sparkles} title="Recommended Remediation (review required — nothing auto-executes)" reason={enrichment.recommendation_not_available_reason}>
                            {enrichment.recommendation && (
                                <>
                                    <div className="text-white/80">{enrichment.recommendation.root_cause_summary}</div>
                                    {(enrichment.recommendation.suggested_actions || []).slice(0, 5).map((a, i) => (
                                        <div key={i} className="flex items-center gap-1.5 text-white/60">
                                            <Layers className="w-3 h-3 shrink-0" /> {a.description || a.label || a.id}
                                        </div>
                                    ))}
                                </>
                            )}
                        </EnrichmentBlock>

                        <EnrichmentBlock icon={History} title="Related Alerts / RCA Chain" reason={enrichment.rca_chain_not_available_reason}>
                            {enrichment.rca_chain && (
                                <div className="text-white/60">{enrichment.rca_chain.summary || 'RCA chain trace available.'}</div>
                            )}
                        </EnrichmentBlock>
                    </div>
                )}
            </div>
        </div>
    );
}
