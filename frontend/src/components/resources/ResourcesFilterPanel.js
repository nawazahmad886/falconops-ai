import React from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../ui/select';

const CATEGORIES = [
    'infrastructure', 'database', 'application', 'kubernetes', 'cloud',
    'middleware', 'network', 'storage', 'security', 'other',
];
const LIFECYCLE_STATUSES = ['discovered', 'monitored', 'unreachable', 'retired'];

export default function ResourcesFilterPanel({ filters, onChange, onReset, facets }) {
    const set = (patch) => onChange({ ...filters, ...patch });
    const selectedTags = filters.tags || [];

    const toggleTag = (tag) => {
        const next = selectedTags.includes(tag) ? selectedTags.filter((t) => t !== tag) : [...selectedTags, tag];
        set({ tags: next.length ? next : undefined });
    };

    return (
        <div className="space-y-4 p-3" data-testid="resources-filter-panel">
            <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-widest text-white/40">Filters</span>
                <Button variant="ghost" size="sm" className="h-6 text-[11px] text-white/50" onClick={onReset} data-testid="reset-resource-filters">
                    Reset
                </Button>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Search</label>
                <Input
                    className="h-8 text-xs bg-black/40 border-white/10"
                    placeholder="Search by name..."
                    value={filters.search || ''}
                    onChange={(e) => set({ search: e.target.value || undefined })}
                    data-testid="filter-search"
                />
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Category</label>
                <Select value={filters.category || 'all'} onValueChange={(v) => set({ category: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-category">
                        <SelectValue placeholder="All categories" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All categories</SelectItem>
                        {CATEGORIES.map((c) => <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Lifecycle status</label>
                <Select value={filters.lifecycle_status || 'all'} onValueChange={(v) => set({ lifecycle_status: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-lifecycle-status">
                        <SelectValue placeholder="Any status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Any status</SelectItem>
                        {LIFECYCLE_STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Technology</label>
                <Select value={filters.technology || 'all'} onValueChange={(v) => set({ technology: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-technology">
                        <SelectValue placeholder="All technologies" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All technologies</SelectItem>
                        {(facets?.technologies || []).map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Environment</label>
                <Select value={filters.environment || 'all'} onValueChange={(v) => set({ environment: v === 'all' ? undefined : v })}>
                    <SelectTrigger className="h-8 text-xs bg-black/40 border-white/10" data-testid="filter-environment">
                        <SelectValue placeholder="All environments" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All environments</SelectItem>
                        {(facets?.environments || []).map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-1.5">
                <label className="text-[11px] text-white/50">Owner</label>
                <Input
                    className="h-8 text-xs bg-black/40 border-white/10"
                    placeholder="Filter by owner..."
                    value={filters.owner || ''}
                    onChange={(e) => set({ owner: e.target.value || undefined })}
                    data-testid="filter-owner"
                />
            </div>

            {(facets?.tags || []).length > 0 && (
                <div className="space-y-1.5">
                    <label className="text-[11px] text-white/50">Tags</label>
                    <div className="flex flex-wrap gap-1.5">
                        {facets.tags.map((tag) => (
                            <button
                                key={tag}
                                onClick={() => toggleTag(tag)}
                                data-testid={`filter-tag-${tag}`}
                                className={`text-[10px] px-2 py-1 rounded-full border ${
                                    selectedTags.includes(tag)
                                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                                        : 'bg-white/[0.03] text-white/50 border-white/10 hover:bg-white/[0.06]'
                                }`}
                            >
                                {tag}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <label className="flex items-center gap-2 text-[11px] text-white/60 cursor-pointer">
                <input
                    type="checkbox"
                    checked={filters.include_retired || false}
                    onChange={(e) => set({ include_retired: e.target.checked })}
                    data-testid="filter-include-retired"
                />
                Show retired
            </label>
        </div>
    );
}
