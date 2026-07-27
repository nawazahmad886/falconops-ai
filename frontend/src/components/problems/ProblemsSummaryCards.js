import React from 'react';
import { Card, CardContent } from '../ui/card';
import { AlertTriangle, CheckCircle2, Clock, GitMerge, Layers, ShieldCheck } from 'lucide-react';

const Tile = ({ icon: Icon, label, value, accent = 'border-white/10', testid }) => (
    <Card className={`bg-black/40 border ${accent}`} data-testid={testid}>
        <CardContent className="p-3">
            <div className="flex items-center gap-2 text-white/50 text-[11px] mb-1">
                <Icon className="w-3.5 h-3.5" />
                {label}
            </div>
            <div className="text-xl font-semibold text-white tabular-nums">{value}</div>
        </CardContent>
    </Card>
);

export default function ProblemsSummaryCards({ stats, loading }) {
    if (loading || !stats) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3" data-testid="problems-summary-loading">
                {Array.from({ length: 8 }).map((_, i) => (
                    <Card key={i} className="bg-black/40 border-white/10 animate-pulse">
                        <CardContent className="p-3 h-[58px]" />
                    </Card>
                ))}
            </div>
        );
    }

    const byStatus = stats.by_status || {};
    const bySeverity = stats.by_severity || {};

    return (
        <div className="space-y-2" data-testid="problems-summary-cards">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
                <Tile testid="stat-total" icon={Layers} label="Total" value={stats.total ?? 0} />
                <Tile testid="stat-open" icon={AlertTriangle} label="Open" value={byStatus.open ?? 0} accent="border-cyan-500/30" />
                <Tile testid="stat-critical" icon={AlertTriangle} label="Critical" value={bySeverity.critical ?? 0} accent="border-rose-500/30" />
                <Tile testid="stat-high" icon={AlertTriangle} label="High" value={bySeverity.high ?? 0} accent="border-orange-500/30" />
                <Tile testid="stat-medium" icon={AlertTriangle} label="Medium" value={bySeverity.medium ?? 0} accent="border-amber-500/30" />
                <Tile testid="stat-resolved-today" icon={CheckCircle2} label="Resolved Today" value={stats.resolved_today ?? 0} accent="border-emerald-500/30" />
                <Tile testid="stat-ai-correlated" icon={GitMerge} label="AI Correlated" value={stats.ai_correlated_count ?? 0} accent="border-violet-500/30" />
                <Tile
                    testid="stat-mttr"
                    icon={Clock}
                    label="MTTR"
                    value={stats.mttr_minutes != null ? `${stats.mttr_minutes}m` : 'n/a'}
                />
            </div>
            {stats.sla_computed_over > 0 && (
                <div className="flex items-center gap-2 text-[11px] text-white/40 px-1" data-testid="stat-sla-compliance">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    SLA compliance: <span className="text-white/70 font-mono">{stats.sla_compliance_pct}%</span>
                    <span>({stats.sla_computed_over} incident{stats.sla_computed_over === 1 ? '' : 's'} with an SLA target)</span>
                </div>
            )}
        </div>
    );
}
