import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

// Severity colors drawn from the dataviz skill's pre-validated reference
// palette (status roles + categorical slot 1 + muted ink), not eyeballed —
// critical/high/medium map onto the skill's validated critical/serious/warning
// status steps, low reuses the validated dark-mode categorical "blue" slot,
// info reuses the mode-invariant muted-ink gray.
const SEVERITY_COLORS = {
    critical: '#d03b3b',
    high: '#ec835a',
    medium: '#fab219',
    low: '#3987e5',
    info: '#898781',
};
const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];
const SURFACE = '#0a0a0a'; // matches this app's dark card background — used as the stacked-segment gap stroke

function formatBucketLabel(bucket) {
    const d = new Date(bucket);
    if (Number.isNaN(d.getTime())) return bucket;
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function TimelineTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    const total = payload.reduce((sum, p) => sum + (p.value || 0), 0);
    return (
        <div className="rounded-lg border border-white/10 bg-black/90 backdrop-blur px-3 py-2 text-[11px]">
            <div className="text-white/70 mb-1">{formatBucketLabel(label)} &middot; {total} problem{total === 1 ? '' : 's'}</div>
            {payload.filter((p) => p.value > 0).map((p) => (
                <div key={p.dataKey} className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-sm" style={{ background: SEVERITY_COLORS[p.dataKey] }} />
                    <span className="text-white/60 capitalize">{p.dataKey}</span>
                    <span className="ml-auto text-white/90 font-mono">{p.value}</span>
                </div>
            ))}
        </div>
    );
}

export default function ProblemsTimelineChart({ buckets = [], height = 220 }) {
    if (!buckets.length) {
        return (
            <div className="text-center py-10 text-white/40 text-sm" data-testid="problems-timeline-empty">
                No problems in the selected time range.
            </div>
        );
    }

    return (
        <div data-testid="problems-timeline-chart">
            <ResponsiveContainer width="100%" height={height}>
                <BarChart data={buckets} barCategoryGap={4}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c2c2a" vertical={false} />
                    <XAxis
                        dataKey="bucket"
                        tickFormatter={formatBucketLabel}
                        tick={{ fill: '#898781', fontSize: 10 }}
                        axisLine={{ stroke: '#383835' }}
                        tickLine={false}
                    />
                    <YAxis
                        allowDecimals={false}
                        tick={{ fill: '#898781', fontSize: 10 }}
                        axisLine={{ stroke: '#383835' }}
                        tickLine={false}
                        width={28}
                    />
                    <Tooltip content={<TimelineTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                    <Legend
                        wrapperStyle={{ fontSize: 11, color: '#c3c2b7' }}
                        formatter={(value) => <span className="capitalize text-white/60">{value}</span>}
                    />
                    {SEVERITY_ORDER.map((sev) => (
                        <Bar
                            key={sev}
                            dataKey={sev}
                            name={sev}
                            stackId="severity"
                            fill={SEVERITY_COLORS[sev]}
                            stroke={SURFACE}
                            strokeWidth={2}
                        />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
