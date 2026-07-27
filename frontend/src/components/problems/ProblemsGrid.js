import React, { useMemo, useRef } from 'react';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
    CheckCircle2, Check, GitMerge, MoreHorizontal, ShieldOff, UserPlus, XCircle,
} from 'lucide-react';
import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../ui/dropdown-menu';

const SEVERITY_BADGE = {
    critical: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    high: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    low: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    info: 'bg-white/10 text-white/50 border-white/20',
};

const STATUS_BADGE = {
    open: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    acknowledged: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    investigating: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    identified: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    monitoring: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    resolved: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    closed: 'bg-white/10 text-white/40 border-white/20',
};

const SOURCE_LABEL = {
    alert_engine: 'Alert', incident_engine: 'Incident', soc_event: 'SOC Event', soc_incident: 'SOC Incident',
};

function formatDuration(seconds) {
    if (seconds == null) return '—';
    const m = Math.floor(seconds / 60);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ${m % 60}m`;
    return `${Math.floor(h / 24)}d ${h % 24}h`;
}

function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const columnHelper = createColumnHelper();

export default function ProblemsGrid({ problems, loading, onSelectProblem, onAction }) {
    const parentRef = useRef(null);

    const columns = useMemo(() => [
        columnHelper.accessor('severity', {
            header: 'Severity',
            size: 90,
            cell: (info) => (
                <Badge className={`text-[10px] capitalize ${SEVERITY_BADGE[info.getValue()] || SEVERITY_BADGE.info}`}>
                    {info.getValue()}
                </Badge>
            ),
        }),
        columnHelper.accessor('status', {
            header: 'Status',
            size: 100,
            cell: (info) => (
                <Badge className={`text-[10px] capitalize ${STATUS_BADGE[info.getValue()] || STATUS_BADGE.open}`}>
                    {info.getValue()}
                </Badge>
            ),
        }),
        columnHelper.accessor('title', {
            header: 'Title',
            size: 280,
            cell: (info) => (
                <div className="truncate max-w-[280px]" title={info.getValue()}>
                    {info.getValue() || '(untitled)'}
                </div>
            ),
        }),
        columnHelper.accessor('source_collection', {
            header: 'Source',
            size: 100,
            cell: (info) => <span className="text-[11px] text-white/50">{SOURCE_LABEL[info.getValue()] || info.getValue()}</span>,
        }),
        columnHelper.accessor('affected_entities', {
            header: 'Affected entity',
            size: 150,
            cell: (info) => <span className="text-[11px] text-white/60 truncate">{(info.getValue() || [])[0] || '—'}</span>,
        }),
        columnHelper.accessor('affected_count', {
            header: 'Affected',
            size: 70,
            cell: (info) => <span className="tabular-nums">{info.getValue() ?? 1}</span>,
        }),
        columnHelper.accessor('started_at', {
            header: 'Started',
            size: 140,
            cell: (info) => <span className="text-[11px] text-white/50">{formatTime(info.getValue())}</span>,
        }),
        columnHelper.accessor('duration_seconds', {
            header: 'Duration',
            size: 90,
            cell: (info) => <span className="text-[11px] text-white/50 tabular-nums">{formatDuration(info.getValue())}</span>,
        }),
        columnHelper.accessor('assigned_to', {
            header: 'Assigned to',
            size: 130,
            cell: (info) => <span className="text-[11px] text-white/60 truncate">{info.getValue() || 'Unassigned'}</span>,
        }),
        columnHelper.display({
            id: 'correlation',
            header: 'Correlated',
            size: 80,
            cell: ({ row }) => {
                const p = row.original;
                const isCorrelated = p.source_collection === 'incident_engine' || p.source_collection === 'soc_incident';
                return isCorrelated ? (
                    <Badge className="text-[10px] bg-violet-500/15 text-violet-300 border-violet-500/30">
                        <GitMerge className="w-3 h-3 mr-1" />{p.affected_count}
                    </Badge>
                ) : <span className="text-white/20 text-[11px]">—</span>;
            },
        }),
        columnHelper.accessor('confidence', {
            header: 'Confidence',
            size: 90,
            cell: (info) => {
                const v = info.getValue();
                return v != null ? <span className="tabular-nums text-[11px]">{Math.round(v * 100)}%</span> : <span className="text-white/20 text-[11px]">n/a</span>;
            },
        }),
        columnHelper.display({
            id: 'actions',
            header: '',
            size: 50,
            cell: ({ row }) => {
                const p = row.original;
                return (
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => e.stopPropagation()} data-testid={`row-actions-${p.id}`}>
                                <MoreHorizontal className="w-4 h-4 text-white/50" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                            <DropdownMenuItem onSelect={() => onAction(p, 'acknowledge')}>
                                <Check className="w-3.5 h-3.5 mr-2" /> Acknowledge
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => onAction(p, 'resolve')}>
                                <CheckCircle2 className="w-3.5 h-3.5 mr-2" /> Resolve
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => onAction(p, 'close')}>
                                <XCircle className="w-3.5 h-3.5 mr-2" /> Close
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => onAction(p, 'assign')}>
                                <UserPlus className="w-3.5 h-3.5 mr-2" /> Assign
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => onAction(p, 'suppress')}>
                                <ShieldOff className="w-3.5 h-3.5 mr-2" /> Suppress
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                );
            },
        }),
    ], [onAction]);

    const table = useReactTable({
        data: problems,
        columns,
        getCoreRowModel: getCoreRowModel(),
    });

    const rows = table.getRowModel().rows;

    const rowVirtualizer = useVirtualizer({
        count: rows.length,
        getScrollElement: () => parentRef.current,
        estimateSize: () => 40,
        overscan: 12,
    });

    if (!loading && rows.length === 0) {
        return (
            <div className="text-center py-16 text-white/40 text-sm" data-testid="problems-grid-empty">
                No problems match the current filters.
            </div>
        );
    }

    return (
        <div className="rounded-lg border border-white/10 bg-black/20 overflow-hidden" data-testid="problems-grid">
            <div className="flex bg-white/[0.03] border-b border-white/10 text-[11px] uppercase tracking-wide text-white/40">
                {table.getHeaderGroups()[0].headers.map((header) => (
                    <div key={header.id} style={{ width: header.getSize() }} className="px-3 py-2 shrink-0">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                    </div>
                ))}
            </div>
            <div ref={parentRef} className="overflow-auto" style={{ height: 520 }}>
                <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
                    {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                        const row = rows[virtualRow.index];
                        const p = row.original;
                        return (
                            <div
                                key={row.id}
                                data-testid={`problem-row-${p.id}`}
                                onClick={() => onSelectProblem(p)}
                                className="flex items-center border-b border-white/5 hover:bg-white/[0.04] cursor-pointer text-[12px] text-white/80"
                                style={{
                                    position: 'absolute', top: 0, left: 0, width: '100%',
                                    height: virtualRow.size, transform: `translateY(${virtualRow.start}px)`,
                                }}
                            >
                                {row.getVisibleCells().map((cell) => (
                                    <div key={cell.id} style={{ width: cell.column.getSize() }} className="px-3 shrink-0 overflow-hidden">
                                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                    </div>
                                ))}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
