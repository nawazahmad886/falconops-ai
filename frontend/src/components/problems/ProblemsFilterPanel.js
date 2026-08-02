import React from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select';

const STATUSES = ['open', 'acknowledged', 'investigating', 'identified', 'monitoring', 'resolved', 'closed'];
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];
const SOURCES = [
    { value: 'alert_engine', label: 'Alert Engine' },
    { value: 'incident_engine', label: 'Incident Engine' },
    { value: 'soc_event', label: 'SOC Event' },
    { value: 'soc_incident', label: 'SOC Incident' },
];

export default function ProblemsFilterPanel({ filters, onChange, onReset }) {
    const set = (patch) => onChange({ ...filters, ...patch });

    return (
        <div className="space-y-4 p-3" data-testid="problems-filter-panel">
            <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-widest text-white/40">Filters</span>
                <Button variant="ghost" size="sm" className="h-6 text-[11px] text-white/50" onClick={onReset} data-testid="reset-filters">
                    Reset
                </Button>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Status</label>
                <Select value={filters.status || 'all'} onValueChange={(v) => set({ status: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-status">
                        <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All statuses</SelectItem>
                        {STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Severity</label>
                <Select value={filters.severity || 'all'} onValueChange={(v) => set({ severity: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-severity">
                        <SelectValue placeholder="All severities" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All severities</SelectItem>
                        {SEVERITIES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Source</label>
                <Select value={filters.source || 'all'} onValueChange={(v) => set({ source: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-source">
                        <SelectValue placeholder="All sources" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All sources</SelectItem>
                        {SOURCES.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Service / host</label>
                <Input
                    className="h-8 text-xs bg-black/40 border-white/10"
                    placeholder="Filter by service or host..."
                    value={filters.service || ''}
                    onChange={(e) => set({ service: e.target.value || undefined })}
                    data-testid="filter-service"
                />
            </div>

            <label className="flex items-center gap-2 text-[11px] text-white/60 cursor-pointer">
                <input
                    type="checkbox"
                    checked={filters.assignedToMe || false}
                    onChange={(e) => set({ assignedToMe: e.target.checked })}
                    data-testid="filter-assigned-to-me"
                />
                Assigned to me
            </label>

            <label className="flex items-center gap-2 text-[11px] text-white/60 cursor-pointer">
                <input
                    type="checkbox"
                    checked={filters.includeSuppressed || false}
                    onChange={(e) => set({ includeSuppressed: e.target.checked })}
                    data-testid="filter-include-suppressed"
                />
                Show suppressed
            </label>
        </div>
    );
}
