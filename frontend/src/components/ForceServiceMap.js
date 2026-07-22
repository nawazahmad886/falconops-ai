import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Badge } from './ui/badge';

const SERVICE_COLORS = [
    '#06b6d4', '#10b981', '#8b5cf6', '#f59e0b',
    '#f43f5e', '#3b82f6', '#d946ef', '#fb923c',
    '#14b8a6', '#ec4899',
];

const colorFor = (name, names = []) => {
    const idx = names.indexOf(name);
    return SERVICE_COLORS[(idx >= 0 ? idx : (name?.length || 0)) % SERVICE_COLORS.length];
};

/**
 * D3 force-directed service dependency map.
 *
 * Props:
 *   nodes: [{name, call_count, error_count, error_rate_pct, avg_latency_ms, p95_latency_ms}]
 *          OR a list of strings (raw service names) — both forms still supported.
 *   edges: [{service, depends_on, call_count, error_count}]
 *   height: number (px, default 480)
 *   onNodeClick: (serviceName) => void  — for the correlation drill-down panel
 */
export default function ForceServiceMap({ nodes, edges, height = 480, onNodeClick }) {
    const svgRef = useRef(null);
    const containerRef = useRef(null);
    const [hovered, setHovered] = useState(null);
    const [width, setWidth] = useState(800);

    // Build normalized node + edge sets
    const { nodeData, edgeData } = React.useMemo(() => {
        const aggMap = new Map();
        const bumpNode = (name) => {
            if (!name) return null;
            if (!aggMap.has(name)) aggMap.set(name, {
                id: name, name, callCount: 0, errorCount: 0,
                avgLatencyMs: null, p95LatencyMs: null, errorRatePct: null,
            });
            return aggMap.get(name);
        };
        (nodes || []).forEach((n) => {
            if (typeof n === 'string') bumpNode(n);
            else if (n && n.name) {
                const x = bumpNode(n.name);
                x.callCount += n.callCount || n.call_count || 0;
                x.errorCount += n.errorCount || n.error_count || 0;
                if (n.avg_latency_ms != null) x.avgLatencyMs = n.avg_latency_ms;
                if (n.p95_latency_ms != null) x.p95LatencyMs = n.p95_latency_ms;
                if (n.error_rate_pct != null) x.errorRatePct = n.error_rate_pct;
            }
        });
        (edges || []).forEach((e) => {
            const a = bumpNode(e.service);
            const b = bumpNode(e.depends_on);
            if (a) {
                a.callCount += e.call_count || 0;
                a.errorCount += e.error_count || 0;
            }
            if (b) {
                b.callCount += Math.floor((e.call_count || 0) / 2);
            }
        });

        const ed = (edges || [])
            .filter((e) => e.service && e.depends_on && e.service !== e.depends_on)
            .map((e) => ({
                source: e.service,
                target: e.depends_on,
                call_count: e.call_count || 0,
                error_count: e.error_count || 0,
                error_rate: e.call_count ? (e.error_count || 0) / e.call_count : 0,
            }));

        return { nodeData: Array.from(aggMap.values()), edgeData: ed };
    }, [nodes, edges]);

    // Responsive width
    useEffect(() => {
        if (!containerRef.current) return;
        const ro = new ResizeObserver((entries) => {
            for (const ent of entries) setWidth(Math.max(320, ent.contentRect.width));
        });
        ro.observe(containerRef.current);
        return () => ro.disconnect();
    }, []);

    // D3 simulation
    useEffect(() => {
        if (!svgRef.current || nodeData.length === 0) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        const names = nodeData.map((n) => n.name);
        const maxCalls = Math.max(1, ...nodeData.map((n) => n.callCount));
        const radiusOf = (n) => 14 + Math.sqrt(n.callCount / maxCalls) * 18;

        // Arrow marker
        const defs = svg.append('defs');
        defs.append('marker')
            .attr('id', 'arrow')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 28)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', 'rgba(255,255,255,0.35)');

        defs.append('marker')
            .attr('id', 'arrow-error')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 28)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#f43f5e');

        const g = svg.append('g');

        // Zoom + pan
        const zoom = d3.zoom()
            .scaleExtent([0.4, 3])
            .on('zoom', (event) => g.attr('transform', event.transform));
        svg.call(zoom);

        const simulation = d3.forceSimulation(nodeData)
            .force('link', d3.forceLink(edgeData).id((d) => d.id).distance(120).strength(0.6))
            .force('charge', d3.forceManyBody().strength(-360))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius((d) => radiusOf(d) + 8));

        // Links
        const link = g.append('g')
            .selectAll('line')
            .data(edgeData)
            .join('line')
            .attr('stroke', (d) => (d.error_rate > 0.05 ? '#f43f5e' : 'rgba(255,255,255,0.18)'))
            .attr('stroke-width', (d) => Math.max(1, Math.min(4, Math.log10((d.call_count || 1) + 1) * 2)))
            .attr('stroke-opacity', 0.85)
            .attr('marker-end', (d) => (d.error_rate > 0.05 ? 'url(#arrow-error)' : 'url(#arrow)'));

        // Link error-rate labels (only if > 5%)
        const linkLabel = g.append('g')
            .selectAll('text')
            .data(edgeData.filter((d) => d.error_rate > 0.05))
            .join('text')
            .attr('font-size', 9)
            .attr('fill', '#fca5a5')
            .attr('text-anchor', 'middle')
            .attr('pointer-events', 'none')
            .text((d) => `${Math.round(d.error_rate * 100)}% err`);

        // Nodes
        const node = g.append('g')
            .selectAll('g')
            .data(nodeData)
            .join('g')
            .attr('cursor', 'pointer')
            .call(
                d3.drag()
                    .on('start', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x; d.fy = d.y;
                    })
                    .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
                    .on('end', (event, d) => {
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null; d.fy = null;
                    })
            )
            .on('mouseenter', (_e, d) => setHovered(d))
            .on('mouseleave', () => setHovered(null))
            .on('click', (_e, d) => { if (onNodeClick) onNodeClick(d.name); });

        node.append('circle')
            .attr('r', (d) => radiusOf(d))
            .attr('fill', (d) => colorFor(d.name, names))
            .attr('fill-opacity', 0.25)
            .attr('stroke', (d) => colorFor(d.name, names))
            .attr('stroke-width', 2);

        // Inner pulse halo when errors exist
        node.filter((d) => d.errorCount > 0)
            .append('circle')
            .attr('r', (d) => radiusOf(d) + 6)
            .attr('fill', 'none')
            .attr('stroke', '#f43f5e')
            .attr('stroke-opacity', 0.4)
            .attr('stroke-width', 1.5)
            .style('animation', 'falcon-pulse 1.6s ease-out infinite');

        // Label — service name
        node.append('text')
            .text((d) => d.name)
            .attr('font-size', 11)
            .attr('font-weight', 600)
            .attr('fill', '#fff')
            .attr('text-anchor', 'middle')
            .attr('dy', (d) => -radiusOf(d) - 6)
            .style('pointer-events', 'none')
            .style('text-shadow', '0 1px 3px rgba(0,0,0,0.9)');

        // Sub-label — latency + error% (only when the backend supplied real metrics)
        node.filter((d) => d.avgLatencyMs != null)
            .append('text')
            .text((d) => `${Math.round(d.avgLatencyMs)}ms${d.errorRatePct > 0 ? ` · ${d.errorRatePct}% err` : ''}`)
            .attr('font-size', 9)
            .attr('font-weight', 500)
            .attr('fill', (d) => (d.errorRatePct > 5 ? '#fca5a5' : 'rgba(255,255,255,0.55)'))
            .attr('text-anchor', 'middle')
            .attr('dy', (d) => -radiusOf(d) - 18)
            .style('pointer-events', 'none')
            .style('text-shadow', '0 1px 3px rgba(0,0,0,0.9)');

        simulation.on('tick', () => {
            link
                .attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y)
                .attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y);
            linkLabel
                .attr('x', (d) => (d.source.x + d.target.x) / 2)
                .attr('y', (d) => (d.source.y + d.target.y) / 2 - 3);
            node.attr('transform', (d) => `translate(${d.x},${d.y})`);
        });

        return () => simulation.stop();
    }, [nodeData, edgeData, width, height, onNodeClick]);

    if (nodeData.length === 0) {
        return (
            <div className="text-center py-10 text-white/40 text-sm" data-testid="force-map-empty">
                No service dependencies observed yet.
            </div>
        );
    }

    return (
        <div ref={containerRef} className="relative w-full" data-testid="force-service-map">
            <style>{`@keyframes falcon-pulse {
                0%   { transform: scale(1);   opacity: 0.6; }
                70%  { transform: scale(1.4); opacity: 0;   }
                100% { transform: scale(1.4); opacity: 0;   }
            }`}</style>
            <svg
                ref={svgRef}
                width={width}
                height={height}
                style={{ background: 'rgba(0,0,0,0.25)', borderRadius: 12, border: '1px solid rgba(255,255,255,0.08)' }}
            />
            {/* Legend / Hover tooltip */}
            <div className="absolute top-3 left-3 text-[10px] text-white/50 space-y-1 pointer-events-none">
                <div>Drag nodes · scroll to zoom · click to diagnose</div>
            </div>
            {hovered && (
                <div
                    className="absolute top-3 right-3 p-2.5 rounded-lg border border-white/10 bg-black/80 backdrop-blur min-w-[180px]"
                    data-testid="force-map-tooltip"
                >
                    <div className="flex items-center gap-2 mb-1">
                        <span
                            className="w-2 h-2 rounded-full"
                            style={{ background: colorFor(hovered.name, nodeData.map((n) => n.name)) }}
                        />
                        <span className="text-sm text-white font-semibold">{hovered.name}</span>
                    </div>
                    <div className="text-[11px] text-white/60 space-y-0.5">
                        <div>Calls: <span className="text-white/80 font-mono">{hovered.callCount}</span></div>
                        <div>Errors: <span className={hovered.errorCount > 0 ? 'text-red-400 font-mono' : 'text-white/80 font-mono'}>{hovered.errorCount}</span></div>
                        {hovered.avgLatencyMs != null && (
                            <div>Avg latency: <span className="text-white/80 font-mono">{Math.round(hovered.avgLatencyMs)}ms</span></div>
                        )}
                        {hovered.p95LatencyMs != null && (
                            <div>p95 latency: <span className="text-white/80 font-mono">{Math.round(hovered.p95LatencyMs)}ms</span></div>
                        )}
                        {hovered.errorRatePct != null && (
                            <div>Error rate: <span className={hovered.errorRatePct > 5 ? 'text-red-400 font-mono' : 'text-white/80 font-mono'}>{hovered.errorRatePct}%</span></div>
                        )}
                    </div>
                    <Badge className="mt-1.5 text-[9px] bg-violet-500/15 text-violet-300 border border-violet-500/30">
                        click → correlation & diagnose
                    </Badge>
                </div>
            )}
        </div>
    );
}
