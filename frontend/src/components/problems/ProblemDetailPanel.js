import React, { useState } from 'react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import {
    Brain, GitBranch, History, Layers, Loader2, Mail, MessageSquare, Send,
    Sparkles, Terminal, Wand2, X,
} from 'lucide-react';

// Curated for the Problems console — a subset of remediation_service.py's
// full ACTION_LIBRARY that's directly relevant to "handle this problem right
// now" (restart/kill a process, clear logs, restart a resource hog), not the
// whole library (block_ip, rotate_credentials, etc. belong to other flows).
const REMEDIATION_ACTIONS = [
    { id: 'restart_service', label: 'Restart Service', fields: ['service_name', 'host'] },
    { id: 'kill_process', label: 'Kill Runaway Process', fields: ['process_name', 'host'] },
    { id: 'restart_top_consumer', label: 'Restart Top CPU/Memory Consumer', fields: ['process_name', 'host', 'resource_type'] },
    { id: 'clear_logs', label: 'Clear/Truncate Logs', fields: ['log_path', 'host'] },
];

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

export default function ProblemDetailPanel({
    problem, loading, onClose,
    onNotify, onRemediate, onGenerateFixSuggestion,
    fixSuggestion, fixSuggestionLoading,
}) {
    const [notifyOpen, setNotifyOpen] = useState(false);
    const [notifyChannels, setNotifyChannels] = useState(['email']);
    const [notifyMessage, setNotifyMessage] = useState('');
    const [notifying, setNotifying] = useState(false);

    const [remediateOpen, setRemediateOpen] = useState(false);
    const [remediateActionId, setRemediateActionId] = useState(REMEDIATION_ACTIONS[0].id);
    const [remediateParams, setRemediateParams] = useState({});
    const [remediating, setRemediating] = useState(false);
    const [remediateResult, setRemediateResult] = useState(null);

    if (!problem) return null;
    const enrichment = problem.enrichment || {};
    const selectedAction = REMEDIATION_ACTIONS.find((a) => a.id === remediateActionId) || REMEDIATION_ACTIONS[0];

    const toggleChannel = (channel) => {
        setNotifyChannels((prev) => (prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]));
    };

    const submitNotify = async () => {
        setNotifying(true);
        try {
            await onNotify(problem.id, notifyChannels, notifyMessage || undefined);
            setNotifyOpen(false);
            setNotifyMessage('');
        } catch (_e) {
            // already toasted by the caller (ProblemsPage.js) — keep the
            // dialog open so the user can see the error and retry.
        } finally {
            setNotifying(false);
        }
    };

    const submitRemediate = async () => {
        setRemediating(true);
        setRemediateResult(null);
        try {
            const result = await onRemediate(problem.id, remediateActionId, remediateParams);
            setRemediateResult(result);
        } catch (_e) {
            // already toasted by the caller (ProblemsPage.js)
        } finally {
            setRemediating(false);
        }
    };

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

                <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => setNotifyOpen(true)} data-testid="action-notify-owner">
                        <Send className="w-3.5 h-3.5 mr-1.5" /> Notify Owner
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setRemediateOpen(true)} data-testid="action-remediate">
                        <Terminal className="w-3.5 h-3.5 mr-1.5" /> Remediate (Preview)
                    </Button>
                    <Button
                        size="sm"
                        variant="outline"
                        disabled={fixSuggestionLoading}
                        onClick={() => onGenerateFixSuggestion(problem.id)}
                        data-testid="action-generate-fix-suggestion"
                    >
                        {fixSuggestionLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5 mr-1.5" />}
                        {fixSuggestion ? 'Regenerate Fix Suggestion' : 'Generate Fix Suggestion'}
                    </Button>
                </div>

                {(fixSuggestion || fixSuggestionLoading) && (
                    <Card className="bg-black/30 border-cyan-500/20">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs text-cyan-300 flex items-center gap-1.5">
                                <Wand2 className="w-3.5 h-3.5" /> Engineer Fix Suggestion (AI-generated)
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0 text-[12px] text-white/70 space-y-1.5">
                            {fixSuggestionLoading && <div className="text-white/40">Generating…</div>}
                            {fixSuggestion && !fixSuggestionLoading && (
                                <>
                                    <div className="text-white/50 text-[11px]">{fixSuggestion.summary}</div>
                                    <div className="text-white/80 whitespace-pre-line">{fixSuggestion.fix_suggestion}</div>
                                    <div className="text-white/30 text-[10px]">Generated {fixSuggestion.generated_at}</div>
                                </>
                            )}
                        </CardContent>
                    </Card>
                )}

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

            <Dialog open={notifyOpen} onOpenChange={setNotifyOpen}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-sm">
                    <DialogHeader>
                        <DialogTitle className="text-white text-sm">Notify owner</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3 text-sm text-white/70">
                        <div>Owner: <span className="text-white">{problem.assigned_to || 'Unassigned'}</span></div>
                        {!problem.assigned_to && (
                            <div className="text-amber-400 text-xs">This problem has no assigned owner — assign one first.</div>
                        )}
                        <div className="flex gap-3">
                            <label className="flex items-center gap-1.5 text-xs">
                                <input type="checkbox" checked={notifyChannels.includes('email')} onChange={() => toggleChannel('email')} />
                                <Mail className="w-3.5 h-3.5" /> Email
                            </label>
                            <label className="flex items-center gap-1.5 text-xs">
                                <input type="checkbox" checked={notifyChannels.includes('sms')} onChange={() => toggleChannel('sms')} />
                                <MessageSquare className="w-3.5 h-3.5" /> SMS
                            </label>
                        </div>
                        <Input
                            placeholder="Optional message (defaults to problem summary)"
                            value={notifyMessage}
                            onChange={(e) => setNotifyMessage(e.target.value)}
                            className="bg-black/40 border-white/10"
                            data-testid="notify-message-input"
                        />
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" size="sm" onClick={() => setNotifyOpen(false)}>Cancel</Button>
                        <Button
                            size="sm"
                            disabled={!problem.assigned_to || notifyChannels.length === 0 || notifying}
                            onClick={submitNotify}
                            data-testid="notify-submit"
                        >
                            {notifying ? 'Sending…' : 'Send'}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            <Dialog open={remediateOpen} onOpenChange={(open) => { setRemediateOpen(open); if (!open) setRemediateResult(null); }}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-white text-sm">Remediation preview</DialogTitle>
                    </DialogHeader>
                    <div className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-2 py-1.5">
                        Preview only — this resolves and logs the exact command that would run, but never
                        executes it against real infrastructure. See the Live Execution Roadmap for what
                        real execution would require.
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs text-white/50">Action</label>
                        <select
                            value={remediateActionId}
                            onChange={(e) => { setRemediateActionId(e.target.value); setRemediateParams({}); setRemediateResult(null); }}
                            className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-sm text-white"
                            data-testid="remediate-action-select"
                        >
                            {REMEDIATION_ACTIONS.map((a) => (
                                <option key={a.id} value={a.id}>{a.label}</option>
                            ))}
                        </select>
                        {selectedAction.fields.map((field) => (
                            <Input
                                key={field}
                                placeholder={field.replace(/_/g, ' ')}
                                value={remediateParams[field] || ''}
                                onChange={(e) => setRemediateParams((prev) => ({ ...prev, [field]: e.target.value }))}
                                className="bg-black/40 border-white/10"
                                data-testid={`remediate-param-${field}`}
                            />
                        ))}
                    </div>
                    {remediateResult && (
                        <div className="text-[11px] bg-black/40 border border-white/10 rounded p-2 space-y-1">
                            <div className="font-mono text-white/70">{remediateResult.resolved_script}</div>
                            <div className="text-emerald-300">{remediateResult.result}</div>
                        </div>
                    )}
                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="outline" size="sm" onClick={() => setRemediateOpen(false)}>Close</Button>
                        <Button size="sm" disabled={remediating} onClick={submitRemediate} data-testid="remediate-submit">
                            {remediating ? 'Previewing…' : 'Preview Action'}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
