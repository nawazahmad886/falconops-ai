import React, { useMemo, useRef } from 'react';
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
    MoreHorizontal, PlayCircle, PauseCircle, Archive, ArchiveRestore, RefreshCw, Bell,
} from 'lucide-react';
import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../ui/dropdown-menu';

const CATEGORY_BADGE = {
    infrastructure: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    database: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    application: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    kubernetes: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
    cloud: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    middleware: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    network: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    storage: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
    security: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    other: 'bg-white/10 text-white/50 border-white/20',
};

const LIFECYCLE_BADGE = {
    discovered: 'bg-white/10 text-white/50 border-white/20',
    monitored: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    unreachable: 'bg-red-500/15 text-red-300 border-red-500/30',
    retired: 'bg-white/5 text-white/30 border-white/10',
};

const HEALTH_BADGE = (status) => ({
    healthy: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    degraded: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    critical: 'bg-red-500/15 text-red-300 border-red-500/30',
}[status] || 'bg-white/10 text-white/40 border-white/20');

function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const columnHelper = createColumnHelper();

export default function ResourcesGrid({ resources, loading, onSelectResource, onAction }) {
    const parentRef = useRef(null);

    const columns = useMemo(() => [
        columnHelper.accessor('resource_category', {
            header: 'Category',
            size: 110,
            cell: (info) => (
                <Badge className={`text-[10px] capitalize ${CATEGORY_BADGE[info.getValue()] || CATEGORY_BADGE.other}`}>
                    {info.getValue()}
                </Badge>
            ),
        }),
        columnHelper.accessor('name', {
            header: 'Name',
            size: 220,
            cell: (info) => (
                <div className="truncate max-w-[220px] text-white/85" title={info.getValue()}>
                    {info.getValue() || '(unnamed)'}
                </div>
            ),
        }),
        columnHelper.accessor('technology', {
            header: 'Technology',
            size: 110,
            cell: (info) => <span className="text-[11px] text-white/50">{info.getValue() || '—'}</span>,
        }),
        columnHelper.accessor('environment', {
            header: 'Environment',
            size: 100,
            cell: (info) => <span className="text-[11px] text-white/50 capitalize">{info.getValue() || '—'}</span>,
        }),
        columnHelper.accessor('lifecycle_status', {
            header: 'Lifecycle',
            size: 100,
            cell: (info) => (
                <Badge className={`text-[10px] capitalize ${LIFECYCLE_BADGE[info.getValue()] || LIFECYCLE_BADGE.discovered}`}>
                    {info.getValue() || 'discovered'}
                </Badge>
            ),
        }),
        columnHelper.accessor('status', {
            header: 'Health',
            size: 90,
            cell: (info) => (
                <Badge className={`text-[10px] capitalize ${HEALTH_BADGE(info.getValue())}`}>
                    {info.getValue() || 'n/a'}
                </Badge>
            ),
        }),
        columnHelper.accessor('owner', {
            header: 'Owner',
            size: 130,
            cell: (info) => <span className="text-[11px] text-white/60 truncate">{info.getValue() || 'Unassigned'}</span>,
        }),
        columnHelper.accessor('tags', {
            header: 'Tags',
            size: 160,
            cell: (info) => {
                const tags = info.getValue() || [];
                return (
                    <div className="flex gap-1 overflow-hidden">
                        {tags.slice(0, 2).map((t) => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/[0.05] text-white/50 border border-white/10 shrink-0">{t}</span>
                        ))}
                        {tags.length > 2 && <span className="text-[10px] text-white/30">+{tags.length - 2}</span>}
                    </div>
                );
            },
        }),
        columnHelper.accessor('last_seen', {
            header: 'Last seen',
            size: 140,
            cell: (info) => <span className="text-[11px] text-white/50">{formatTime(info.getValue())}</span>,
        }),
        columnHelper.display({
            id: 'actions',
            header: '',
            size: 50,
            cell: ({ row }) => {
                const r = row.original;
                const isRetired = r.lifecycle_status === 'retired';
                const isDisabled = !!(r.metadata || {}).monitoring_disabled;
                return (
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => e.stopPropagation()} data-testid={`row-actions-${r.id}`}>
                                <MoreHorizontal className="w-4 h-4 text-white/50" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                            {isDisabled ? (
                                <DropdownMenuItem onSelect={() => onAction(r, 'enable-monitoring')}>
                                    <PlayCircle className="w-3.5 h-3.5 mr-2" /> Enable monitoring
                                </DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem onSelect={() => onAction(r, 'disable-monitoring')}>
                                    <PauseCircle className="w-3.5 h-3.5 mr-2" /> Disable monitoring
                                </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onSelect={() => onAction(r, 'restart-agent')}>
                                <RefreshCw className="w-3.5 h-3.5 mr-2" /> Restart agent
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => onAction(r, 'open-alerts')}>
                                <Bell className="w-3.5 h-3.5 mr-2" /> Open related alerts
                            </DropdownMenuItem>
                            {isRetired ? (
                                <DropdownMenuItem onSelect={() => onAction(r, 'restore')}>
                                    <ArchiveRestore className="w-3.5 h-3.5 mr-2" /> Restore
                                </DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem onSelect={() => onAction(r, 'retire')}>
                                    <Archive className="w-3.5 h-3.5 mr-2" /> Retire
                                </DropdownMenuItem>
                            )}
                        </DropdownMenuContent>
                    </DropdownMenu>
                );
            },
        }),
    ], [onAction]);

    const table = useReactTable({
        data: resources,
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
            <div className="text-center py-16 text-white/40 text-sm" data-testid="resources-grid-empty">
                No resources match the current filters.
            </div>
        );
    }

    return (
        <div className="rounded-lg border border-white/10 bg-black/20 overflow-hidden" data-testid="resources-grid">
            <div className="flex bg-white/[0.03] border-b border-white/10 text-[11px] uppercase tracking-wide text-white/40">
                {table.getHeaderGroups()[0].headers.map((header) => (
                    <div key={header.id} style={{ width: header.getSize() }} className="px-3 py-2 shrink-0">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                    </div>
                ))}
            </div>
            <div ref={parentRef} className="overflow-auto" style={{ height: 560 }}>
                <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
                    {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                        const row = rows[virtualRow.index];
                        const r = row.original;
                        return (
                            <div
                                key={row.id}
                                data-testid={`resource-row-${r.id}`}
                                onClick={() => onSelectResource(r)}
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
