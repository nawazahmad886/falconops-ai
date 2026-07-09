import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import * as d3 from 'd3';
import {
    Network, RefreshCw, ZoomIn, ZoomOut, Maximize2, Activity,
    Server, Globe, Database, Shield, CheckCircle, XCircle,
    AlertTriangle, Eye, Wifi,
} from 'lucide-react';

const STATUS_COLORS = {
    healthy: '#22c55e', up: '#22c55e',
    degraded: '#eab308', warning: '#eab308',
    critical: '#ef4444', down: '#ef4444',
    unknown: '#6b7280',
};

const TYPE_COLORS = {
    http: '#3b82f6', ping: '#06b6d4', tcp: '#8b5cf6',
    database: '#f59e0b', dns: '#10b981', ssl: '#ec4899',
};

export default function ServiceMapPage() {
    const { api } = useAuth();
    const svgRef = useRef(null);
    const containerRef = useRef(null);
    const [topology, setTopology] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedNode, setSelectedNode] = useState(null);
    const simRef = useRef(null);

    const fetchTopology = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/topology');
            setTopology(res.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchTopology(); }, [fetchTopology]);

    // D3 Force Graph
    useEffect(() => {
        if (!topology || !svgRef.current || !containerRef.current) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        const width = containerRef.current.clientWidth;
        const height = 500;
        svg.attr('width', width).attr('height', height);

        const nodes = topology.nodes?.map(n => ({
            ...n,
            x: width / 2 + (Math.random() - 0.5) * 200,
            y: height / 2 + (Math.random() - 0.5) * 200,
        })) || [];

        const links = topology.edges?.map(e => ({
            source: nodes.find(n => n.id === e.source) || e.source,
            target: nodes.find(n => n.id === e.target) || e.target,
            status: e.status,
            type: e.dependency_type,
        })).filter(l => l.source && l.target) || [];

        // Zoom
        const g = svg.append('g');
        const zoom = d3.zoom().scaleExtent([0.3, 4]).on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
        svg.call(zoom);

        // Animated grid background
        const gridSize = 40;
        const gridG = g.append('g').attr('class', 'grid');
        for (let x = 0; x < width * 2; x += gridSize) {
            gridG.append('line').attr('x1', x - width/2).attr('y1', -height/2).attr('x2', x - width/2).attr('y2', height * 1.5)
                .attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 0.5);
        }
        for (let y = 0; y < height * 2; y += gridSize) {
            gridG.append('line').attr('x1', -width/2).attr('y1', y - height/2).attr('x2', width * 1.5).attr('y2', y - height/2)
                .attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 0.5);
        }

        // Links
        const link = g.append('g').selectAll('line').data(links).enter().append('line')
            .attr('stroke', d => STATUS_COLORS[d.status] || '#333')
            .attr('stroke-width', 2)
            .attr('stroke-opacity', 0.5)
            .attr('stroke-dasharray', d => d.status === 'critical' ? '5,5' : 'none');

        // Animated particles on links
        const particles = g.append('g').selectAll('circle').data(links).enter().append('circle')
            .attr('r', 2).attr('fill', d => STATUS_COLORS[d.status] || '#3b82f6').attr('opacity', 0.8);

        // Node groups
        const node = g.append('g').selectAll('g').data(nodes).enter().append('g')
            .attr('cursor', 'pointer')
            .call(d3.drag()
                .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
                .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
            );

        // Node glow
        node.append('circle')
            .attr('r', 28)
            .attr('fill', d => STATUS_COLORS[d.status] || '#333')
            .attr('opacity', 0.15);

        // Node circle
        node.append('circle')
            .attr('r', 20)
            .attr('fill', '#0D1117')
            .attr('stroke', d => STATUS_COLORS[d.status] || '#333')
            .attr('stroke-width', 2.5);

        // Node icon (text symbol)
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 5)
            .attr('fill', d => STATUS_COLORS[d.status] || '#666')
            .attr('font-size', 14)
            .attr('font-weight', 'bold')
            .text(d => {
                if (d.type === 'http') return 'W';
                if (d.type === 'database' || d.type === 'tcp') return 'D';
                if (d.type === 'dns') return 'N';
                return 'S';
            });

        // Node label
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 38)
            .attr('fill', 'rgba(255,255,255,0.6)')
            .attr('font-size', 10)
            .text(d => d.name?.length > 15 ? d.name.slice(0, 15) + '...' : d.name);

        // Health score
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', -28)
            .attr('fill', d => STATUS_COLORS[d.status] || '#666')
            .attr('font-size', 9)
            .attr('font-weight', 'bold')
            .text(d => `${d.health_score}%`);

        // Click handler
        node.on('click', (event, d) => {
            setSelectedNode(prev => prev?.id === d.id ? null : d);
        });

        // Simulation
        const sim = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links).id(d => d.id).distance(120).strength(0.5))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide(45));

        simRef.current = sim;

        let tick = 0;
        sim.on('tick', () => {
            tick++;
            link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
            node.attr('transform', d => `translate(${d.x},${d.y})`);

            // Animate particles along links
            const t = (tick % 60) / 60;
            particles.attr('cx', d => {
                const sx = typeof d.source === 'object' ? d.source.x : 0;
                const tx = typeof d.target === 'object' ? d.target.x : 0;
                return sx + (tx - sx) * t;
            }).attr('cy', d => {
                const sy = typeof d.source === 'object' ? d.source.y : 0;
                const ty = typeof d.target === 'object' ? d.target.y : 0;
                return sy + (ty - sy) * t;
            });
        });

        return () => { sim.stop(); };
    }, [topology]);

    const summary = topology?.health_summary;

    return (
        <div className="space-y-6" data-testid="service-map-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/15"><Network className="w-6 h-6 text-cyan-400" /></div>
                        Service Map
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Interactive D3 service dependency graph with real-time health</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchTopology} disabled={loading} className="border-white/10 text-xs" data-testid="refresh-map-btn">
                    <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {/* Health Summary */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-3 flex items-center gap-2">
                        <Server className="w-4 h-4 text-blue-400" /><div><p className="text-[10px] text-white/50">Services</p><p className="text-sm font-bold text-white">{summary.total_services}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-3 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-400" /><div><p className="text-[10px] text-white/50">Healthy</p><p className="text-sm font-bold text-emerald-400">{summary.healthy}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-3 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" /><div><p className="text-[10px] text-white/50">Degraded</p><p className="text-sm font-bold text-amber-400">{summary.degraded}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-3 flex items-center gap-2">
                        <XCircle className="w-4 h-4 text-red-400" /><div><p className="text-[10px] text-white/50">Down</p><p className="text-sm font-bold text-red-400">{summary.down}</p></div>
                    </CardContent></Card>
                    <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-3 flex items-center gap-2">
                        <Network className="w-4 h-4 text-purple-400" /><div><p className="text-[10px] text-white/50">Dependencies</p><p className="text-sm font-bold text-white">{summary.total_dependencies}</p></div>
                    </CardContent></Card>
                </div>
            )}

            {/* D3 Map + Details */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <Card className="lg:col-span-3 bg-[#0D1117] border-white/5 overflow-hidden" ref={containerRef}>
                    <CardContent className="p-0">
                        {(!topology?.nodes || topology.nodes.length === 0) ? (
                            <div className="p-16 text-center text-white/40">
                                <Network className="w-12 h-12 mx-auto mb-4 opacity-30" />
                                <p className="text-sm">No services in topology. Add monitors and dependencies to build your service map.</p>
                            </div>
                        ) : (
                            <svg ref={svgRef} className="w-full" style={{ background: '#080B12', minHeight: 500 }} data-testid="d3-service-map" />
                        )}
                    </CardContent>
                </Card>

                {/* Details Panel */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-sm">{selectedNode ? selectedNode.name : 'Service Details'}</CardTitle>
                    </CardHeader>
                    <CardContent className="p-4">
                        {selectedNode ? (
                            <div className="space-y-3" data-testid="node-details">
                                <div className="flex items-center gap-2">
                                    <div className={`w-3 h-3 rounded-full`} style={{ background: STATUS_COLORS[selectedNode.status] }} />
                                    <span className="text-sm text-white/80 capitalize">{selectedNode.status}</span>
                                </div>
                                <div className="space-y-2 text-xs">
                                    <div><span className="text-white/40">Type:</span> <span className="text-white/70">{selectedNode.type}</span></div>
                                    <div><span className="text-white/40">Target:</span> <span className="text-white/70 font-mono break-all">{selectedNode.target}</span></div>
                                    <div><span className="text-white/40">Health:</span> <span className="text-white/70">{selectedNode.health_score}%</span></div>
                                    {selectedNode.latency_ms != null && <div><span className="text-white/40">Latency:</span> <span className="text-white/70">{selectedNode.latency_ms}ms</span></div>}
                                    <div><span className="text-white/40">Env:</span> <span className="text-white/70">{selectedNode.environment || 'default'}</span></div>
                                    <div><span className="text-white/40">Dependencies:</span> <span className="text-white/70">{selectedNode.dependencies?.length || 0}</span></div>
                                    <div><span className="text-white/40">Dependents:</span> <span className="text-white/70">{selectedNode.dependents?.length || 0}</span></div>
                                </div>
                            </div>
                        ) : (
                            <div className="text-center py-8 text-white/30 text-xs">
                                <Eye className="w-6 h-6 mx-auto mb-2 opacity-30" />
                                Click a node to view details
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Cascade Risks */}
            {topology?.cascade_risks?.length > 0 && (
                <Card className="bg-[#0D1117] border-red-500/20">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2 text-red-400"><AlertTriangle className="w-4 h-4" /> Cascade Risks</CardTitle></CardHeader>
                    <CardContent className="p-0 divide-y divide-white/5">
                        {topology.cascade_risks.map((risk, i) => (
                            <div key={i} className="p-3 flex items-center justify-between" data-testid={`cascade-risk-${i}`}>
                                <div><p className="text-sm text-white/80">{risk.source_monitor}</p><p className="text-[10px] text-white/40">{risk.affected_services} dependent service(s) at risk</p></div>
                                <Badge className={risk.severity === 'critical' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'}>{risk.severity}</Badge>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
