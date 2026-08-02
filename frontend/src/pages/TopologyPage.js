import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    Network,
    Server,
    Globe,
    Database,
    Wifi,
    Lock,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    RefreshCw,
    Plus,
    Trash2,
    Link2,
    Unlink,
    Zap,
    TrendingUp,
    Shield,
    Activity,
    Eye,
    GitBranch,
    ArrowRight,
    X,
    Search,
    Sparkles,
    Clock,
    Edit,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useGlobalFilters } from '../context/GlobalFiltersContext';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

// Health color utilities
const getHealthColor = (score) => {
    if (score >= 95) return { bg: 'bg-green-500', text: 'text-green-400', border: 'border-green-500/50' };
    if (score >= 80) return { bg: 'bg-yellow-500', text: 'text-yellow-400', border: 'border-yellow-500/50' };
    if (score >= 50) return { bg: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/50' };
    return { bg: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/50' };
};

const getTypeIcon = (type) => {
    switch (type) {
        case 'http': return Globe;
        case 'ping': return Wifi;
        case 'tcp': return Server;
        case 'ssl': return Lock;
        case 'dns': return Database;
        default: return Server;
    }
};

// Node component for the topology
const TopologyNode = ({ node, isSelected, onClick, position, scale }) => {
    const colors = getHealthColor(node.health_score);
    const Icon = getTypeIcon(node.type);
    
    return (
        <motion.g
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            style={{ cursor: 'pointer' }}
            onClick={() => onClick(node)}
        >
            {/* Glow effect for critical nodes */}
            {node.health_score < 80 && (
                <circle
                    cx={position.x}
                    cy={position.y}
                    r={45 * scale}
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth={2}
                    opacity={0.5}
                    className="animate-pulse"
                />
            )}
            
            {/* Main node circle */}
            <circle
                cx={position.x}
                cy={position.y}
                r={35 * scale}
                fill={node.health_score >= 95 ? '#10b981' : node.health_score >= 80 ? '#f59e0b' : '#ef4444'}
                fillOpacity={0.2}
                stroke={node.health_score >= 95 ? '#10b981' : node.health_score >= 80 ? '#f59e0b' : '#ef4444'}
                strokeWidth={isSelected ? 3 : 2}
            />
            
            {/* Inner circle */}
            <circle
                cx={position.x}
                cy={position.y}
                r={25 * scale}
                fill="#0a0a0a"
                stroke={node.health_score >= 95 ? '#10b981' : node.health_score >= 80 ? '#f59e0b' : '#ef4444'}
                strokeWidth={1}
            />
            
            {/* Status indicator */}
            <circle
                cx={position.x + 25 * scale}
                cy={position.y - 25 * scale}
                r={8 * scale}
                fill={node.status === 'up' ? '#10b981' : node.status === 'down' ? '#ef4444' : '#f59e0b'}
            />
            
            {/* Node label */}
            <text
                x={position.x}
                y={position.y + 55 * scale}
                textAnchor="middle"
                fill="white"
                fontSize={12 * scale}
                fontWeight="bold"
            >
                {node.name.length > 15 ? node.name.substring(0, 15) + '...' : node.name}
            </text>
            
            {/* Health score */}
            <text
                x={position.x}
                y={position.y + 5 * scale}
                textAnchor="middle"
                fill="white"
                fontSize={14 * scale}
                fontWeight="bold"
            >
                {Math.round(node.health_score)}%
            </text>
        </motion.g>
    );
};

// Edge component for dependencies
const TopologyEdge = ({ edge, sourcePos, targetPos, scale }) => {
    const getEdgeColor = () => {
        switch (edge.status) {
            case 'healthy': return '#10b981';
            case 'degraded': return '#f59e0b';
            case 'critical': return '#ef4444';
            default: return '#6b7280';
        }
    };
    
    // Calculate control points for curved line
    const midX = (sourcePos.x + targetPos.x) / 2;
    const midY = (sourcePos.y + targetPos.y) / 2;
    const dx = targetPos.x - sourcePos.x;
    const dy = targetPos.y - sourcePos.y;
    const controlX = midX - dy * 0.2;
    const controlY = midY + dx * 0.2;
    
    // Calculate arrow position
    const arrowAngle = Math.atan2(targetPos.y - controlY, targetPos.x - controlX);
    const arrowX = targetPos.x - 40 * scale * Math.cos(arrowAngle);
    const arrowY = targetPos.y - 40 * scale * Math.sin(arrowAngle);
    
    return (
        <g>
            {/* Edge path */}
            <path
                d={`M ${sourcePos.x} ${sourcePos.y} Q ${controlX} ${controlY} ${targetPos.x} ${targetPos.y}`}
                fill="none"
                stroke={getEdgeColor()}
                strokeWidth={2 * scale}
                strokeOpacity={0.6}
                strokeDasharray={edge.status === 'critical' ? '5,5' : 'none'}
            />
            
            {/* Animated flow indicator */}
            <circle r={4 * scale} fill={getEdgeColor()}>
                <animateMotion
                    dur="2s"
                    repeatCount="indefinite"
                    path={`M ${sourcePos.x} ${sourcePos.y} Q ${controlX} ${controlY} ${targetPos.x} ${targetPos.y}`}
                />
            </circle>
            
            {/* Arrow head */}
            <polygon
                points={`
                    ${arrowX},${arrowY}
                    ${arrowX - 10 * scale * Math.cos(arrowAngle - 0.5)},${arrowY - 10 * scale * Math.sin(arrowAngle - 0.5)}
                    ${arrowX - 10 * scale * Math.cos(arrowAngle + 0.5)},${arrowY - 10 * scale * Math.sin(arrowAngle + 0.5)}
                `}
                fill={getEdgeColor()}
            />
        </g>
    );
};

// Main Topology Page Component
export const TopologyPage = () => {
    const { api, canWrite } = useAuth();
    const { environment } = useGlobalFilters();
    const [topology, setTopology] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedNode, setSelectedNode] = useState(null);
    const [showAddDependency, setShowAddDependency] = useState(false);
    const [monitors, setMonitors] = useState([]);
    const [newDependency, setNewDependency] = useState({ source: '', target: '', type: 'depends_on' });
    const svgRef = useRef(null);
    const [viewBox] = useState({ x: 0, y: 0, width: 1000, height: 600 });

    // fetchTopology returns current-state snapshot data (live health/status),
    // not a historical window — it was never time-scoped and stays that way.
    // The global environment filter IS real here (GET /api/topology already
    // supports it server-side) and was previously never sent.
    const fetchTopology = useCallback(async () => {
        try {
            const [topoRes, monitorsRes] = await Promise.all([
                api.get(`/topology${environment !== 'all' ? `?environment=${environment}` : ''}`),
                api.get('/monitors')
            ]);
            setTopology(topoRes.data);
            setMonitors(monitorsRes.data);
        } catch (error) {
            toast.error('Failed to load topology');
        } finally {
            setLoading(false);
        }
    }, [api, environment]);

    useEffect(() => {
        setLoading(true);
        fetchTopology();
    }, [fetchTopology]);

    useAutoRefresh(fetchTopology);
    
    // Calculate node positions in a force-directed layout
    const nodePositions = React.useMemo(() => {
        if (!topology || !topology.nodes || topology.nodes.length === 0) {
            return {};
        }
        
        const positions = {};
        const nodes = topology.nodes;
        const centerX = 500;
        const centerY = 300;
        const radius = 200;
        
        // Position nodes in a circle
        nodes.forEach((node, i) => {
            const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
            positions[node.id] = {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle)
            };
        });
        
        return positions;
    }, [topology]);
    
    const handleAutoDiscover = async () => {
        try {
            const res = await api.post('/topology/auto-discover');
            toast.success(res.data.message);
            fetchTopology();
        } catch (error) {
            toast.error('Auto-discovery failed');
        }
    };
    
    const handleCreateDependency = async () => {
        if (!newDependency.source || !newDependency.target) {
            toast.error('Please select both source and target');
            return;
        }
        if (newDependency.source === newDependency.target) {
            toast.error('Source and target cannot be the same');
            return;
        }
        
        try {
            await api.post('/topology/dependencies', {
                source_monitor_id: newDependency.source,
                target_monitor_id: newDependency.target,
                dependency_type: newDependency.type
            });
            toast.success('Dependency created');
            setShowAddDependency(false);
            setNewDependency({ source: '', target: '', type: 'depends_on' });
            fetchTopology();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to create dependency');
        }
    };
    
    const handleDeleteDependency = async (depId) => {
        try {
            await api.delete(`/topology/dependencies/${depId}`);
            toast.success('Dependency removed');
            fetchTopology();
        } catch (error) {
            toast.error('Failed to delete dependency');
        }
    };
    
    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-96">
                    <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                </div>
            </>
        );
    }
    
    return (
        <>
            <div className="space-y-6" data-testid="topology-page">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="font-heading text-2xl font-bold uppercase tracking-wider text-white">
                            Service Topology
                        </h1>
                        <p className="text-white/50 text-sm">Real-time dependency mapping and cascade analysis</p>
                    </div>
                    <div className="flex items-center gap-2">
                        {canWrite && (
                            <>
                                <Button
                                    onClick={handleAutoDiscover}
                                    variant="outline"
                                    className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10"
                                >
                                    <Sparkles className="w-4 h-4 mr-2" />
                                    Auto-Discover
                                </Button>
                                <Button
                                    onClick={() => setShowAddDependency(true)}
                                    className="bg-cyan-500 text-black hover:bg-cyan-400"
                                >
                                    <Plus className="w-4 h-4 mr-2" />
                                    Add Dependency
                                </Button>
                            </>
                        )}
                        <Button onClick={fetchTopology} variant="outline" className="border-white/20">
                            <RefreshCw className="w-4 h-4" />
                        </Button>
                    </div>
                </div>
                
                {/* Health Summary Cards */}
                {topology?.health_summary && (
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                        <Card className="bg-black/40 border-white/10">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Total Services</p>
                                <p className="font-heading text-2xl font-bold text-white">
                                    {topology.health_summary.total_services}
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-green-500/10 border-green-500/30">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Healthy</p>
                                <p className="font-heading text-2xl font-bold text-green-400">
                                    {topology.health_summary.healthy}
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-yellow-500/10 border-yellow-500/30">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Degraded</p>
                                <p className="font-heading text-2xl font-bold text-yellow-400">
                                    {topology.health_summary.degraded}
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-red-500/10 border-red-500/30">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Critical</p>
                                <p className="font-heading text-2xl font-bold text-red-400">
                                    {topology.health_summary.critical}
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-black/40 border-white/10">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Dependencies</p>
                                <p className="font-heading text-2xl font-bold text-cyan-400">
                                    {topology.health_summary.total_dependencies}
                                </p>
                            </CardContent>
                        </Card>
                        <Card className="bg-primary/10 border-primary/30">
                            <CardContent className="p-4">
                                <p className="text-[10px] text-white/40 uppercase mb-1">Overall Health</p>
                                <p className="font-heading text-2xl font-bold text-primary">
                                    {topology.health_summary.overall_health}%
                                </p>
                            </CardContent>
                        </Card>
                    </div>
                )}
                
                {/* Main Topology Visualization */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                    {/* Graph */}
                    <Card className="lg:col-span-3 bg-black/40 border-white/10 overflow-hidden">
                        <CardHeader className="border-b border-white/10">
                            <CardTitle className="text-white flex items-center gap-2">
                                <Network className="w-5 h-5 text-cyan-400" />
                                Network Graph
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="relative w-full overflow-hidden" style={{ height: '500px', minHeight: '500px', backgroundColor: '#050505' }}>
                                {/* Grid overlay */}
                                <div 
                                    className="absolute inset-0 opacity-10"
                                    style={{
                                        backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
                                        backgroundSize: '50px 50px'
                                    }}
                                />
                                
                                {topology?.nodes?.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full text-white/50">
                                        <Network className="w-16 h-16 mb-4 opacity-30" />
                                        <p>No services configured</p>
                                        <p className="text-sm">Add monitors to see the topology</p>
                                    </div>
                                ) : (
                                    <>
                                        {/* Edges as SVG overlay */}
                                        <svg 
                                            className="absolute inset-0 w-full h-full pointer-events-none"
                                            viewBox="0 0 1000 600"
                                            preserveAspectRatio="xMidYMid meet"
                                        >
                                            {topology?.edges?.map((edge, i) => {
                                                const sourcePos = nodePositions[edge.source];
                                                const targetPos = nodePositions[edge.target];
                                                if (!sourcePos || !targetPos) return null;
                                                
                                                const edgeColor = edge.status === 'healthy' ? '#10b981' : 
                                                                 edge.status === 'degraded' ? '#f59e0b' : '#ef4444';
                                                
                                                return (
                                                    <line
                                                        key={`edge-${i}`}
                                                        x1={sourcePos.x}
                                                        y1={sourcePos.y}
                                                        x2={targetPos.x}
                                                        y2={targetPos.y}
                                                        stroke={edgeColor}
                                                        strokeWidth="2"
                                                        strokeDasharray={edge.status === 'critical' ? '5,5' : 'none'}
                                                    />
                                                );
                                            })}
                                        </svg>
                                        
                                        {/* Nodes as positioned divs */}
                                        {topology?.nodes?.map((node) => {
                                            const pos = nodePositions[node.id];
                                            if (!pos) return null;
                                            
                                            const nodeColor = node.health_score >= 95 ? '#10b981' : 
                                                            node.health_score >= 80 ? '#f59e0b' : '#ef4444';
                                            const isSelected = selectedNode?.id === node.id;
                                            
                                            // Convert viewBox coordinates to percentage
                                            const leftPercent = (pos.x / 1000) * 100;
                                            const topPercent = (pos.y / 600) * 100;
                                            
                                            return (
                                                <div
                                                    key={node.id}
                                                    className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all duration-200 hover:scale-110"
                                                    style={{
                                                        left: `${leftPercent}%`,
                                                        top: `${topPercent}%`,
                                                    }}
                                                    onClick={() => setSelectedNode(node)}
                                                >
                                                    {/* Glow effect for critical */}
                                                    {node.health_score < 80 && (
                                                        <div 
                                                            className="absolute inset-0 rounded-full animate-pulse"
                                                            style={{
                                                                width: '90px',
                                                                height: '90px',
                                                                marginLeft: '-5px',
                                                                marginTop: '-5px',
                                                                backgroundColor: 'rgba(239, 68, 68, 0.3)',
                                                                boxShadow: '0 0 20px rgba(239, 68, 68, 0.5)'
                                                            }}
                                                        />
                                                    )}
                                                    
                                                    {/* Main node circle */}
                                                    <div
                                                        className="relative flex flex-col items-center justify-center rounded-full"
                                                        style={{
                                                            width: '80px',
                                                            height: '80px',
                                                            backgroundColor: '#1a1a1a',
                                                            border: `${isSelected ? '4px' : '2px'} solid ${nodeColor}`,
                                                            boxShadow: isSelected ? `0 0 15px ${nodeColor}` : 'none'
                                                        }}
                                                    >
                                                        {/* Status indicator */}
                                                        <div
                                                            className="absolute -top-1 -right-1 rounded-full border-2 border-black"
                                                            style={{
                                                                width: '20px',
                                                                height: '20px',
                                                                backgroundColor: node.status === 'up' ? '#10b981' : node.status === 'down' ? '#ef4444' : '#f59e0b'
                                                            }}
                                                        />
                                                        
                                                        {/* Health score */}
                                                        <span className="text-white font-bold text-lg">
                                                            {Math.round(node.health_score)}%
                                                        </span>
                                                    </div>
                                                    
                                                    {/* Node label */}
                                                    <div className="text-center mt-2">
                                                        <p className="text-white text-xs font-bold truncate max-w-[100px]">
                                                            {node.name}
                                                        </p>
                                                        <p className="text-xs font-mono" style={{ color: nodeColor }}>
                                                            {node.type.toUpperCase()}
                                                        </p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </>
                                )}
                                
                                {/* Legend */}
                                <div className="absolute bottom-4 left-4 bg-black/80 p-3 rounded-sm border border-white/10 z-10">
                                    <p className="text-[10px] text-white/50 uppercase mb-2">Legend</p>
                                    <div className="flex flex-col gap-1 text-xs">
                                        <div className="flex items-center gap-2">
                                            <div className="w-3 h-3 rounded-full bg-green-500" />
                                            <span className="text-white/70">Healthy (≥95%)</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <div className="w-3 h-3 rounded-full bg-yellow-500" />
                                            <span className="text-white/70">Degraded (80-95%)</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <div className="w-3 h-3 rounded-full bg-red-500" />
                                            <span className="text-white/70">Critical (&lt;80%)</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    
                    {/* Side Panel */}
                    <div className="space-y-4">
                        {/* Selected Node Details */}
                        {selectedNode ? (
                            <Card className="bg-black/40 border-white/10">
                                <CardHeader className="border-b border-white/10 pb-3">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-white text-sm">Service Details</CardTitle>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setSelectedNode(null)}
                                            className="text-white/50 h-6 w-6 p-0"
                                        >
                                            <X className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-4 space-y-4">
                                    <div>
                                        <p className="text-white font-bold">{selectedNode.name}</p>
                                        <p className="text-white/50 text-xs font-mono">{selectedNode.target}</p>
                                    </div>
                                    
                                    <div className="flex items-center gap-2">
                                        <Badge className={`${getHealthColor(selectedNode.health_score).bg}/20 ${getHealthColor(selectedNode.health_score).text}`}>
                                            {selectedNode.health_score}% Health
                                        </Badge>
                                        <Badge variant="outline" className="text-white/70">
                                            {selectedNode.type.toUpperCase()}
                                        </Badge>
                                    </div>
                                    
                                    {selectedNode.latency_ms && (
                                        <div className="text-sm">
                                            <span className="text-white/50">Avg Latency:</span>
                                            <span className="text-white ml-2">{selectedNode.latency_ms}ms</span>
                                        </div>
                                    )}
                                    
                                    {selectedNode.dependencies?.length > 0 && (
                                        <div>
                                            <p className="text-[10px] text-white/40 uppercase mb-2">Depends On</p>
                                            <div className="flex flex-wrap gap-1">
                                                {selectedNode.dependencies.map(depId => {
                                                    const depNode = topology?.nodes?.find(n => n.id === depId);
                                                    return depNode ? (
                                                        <Badge key={depId} variant="outline" className="text-xs">
                                                            {depNode.name}
                                                        </Badge>
                                                    ) : null;
                                                })}
                                            </div>
                                        </div>
                                    )}
                                    
                                    {selectedNode.dependents?.length > 0 && (
                                        <div>
                                            <p className="text-[10px] text-white/40 uppercase mb-2">Dependents</p>
                                            <div className="flex flex-wrap gap-1">
                                                {selectedNode.dependents.map(depId => {
                                                    const depNode = topology?.nodes?.find(n => n.id === depId);
                                                    return depNode ? (
                                                        <Badge key={depId} variant="outline" className="text-xs text-cyan-400">
                                                            {depNode.name}
                                                        </Badge>
                                                    ) : null;
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ) : (
                            <Card className="bg-black/40 border-white/10">
                                <CardContent className="p-6 text-center">
                                    <Eye className="w-8 h-8 text-white/20 mx-auto mb-2" />
                                    <p className="text-white/50 text-sm">Click a node to view details</p>
                                </CardContent>
                            </Card>
                        )}
                        
                        {/* Cascade Risks */}
                        {topology?.cascade_risks?.length > 0 && (
                            <Card className="bg-red-500/10 border-red-500/30">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-red-400 text-sm flex items-center gap-2">
                                        <AlertTriangle className="w-4 h-4" />
                                        Cascade Risks
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                    {topology.cascade_risks.slice(0, 3).map((risk, i) => (
                                        <div key={i} className="p-2 bg-red-500/10 rounded-sm text-xs">
                                            <p className="text-white font-medium">{risk.at_risk_service.name}</p>
                                            <p className="text-red-400">
                                                ↳ depends on failing: {risk.unhealthy_dependency.name}
                                            </p>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        )}
                        
                        {/* Critical Paths */}
                        {topology?.critical_paths?.length > 0 && (
                            <Card className="bg-orange-500/10 border-orange-500/30">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-orange-400 text-sm flex items-center gap-2">
                                        <GitBranch className="w-4 h-4" />
                                        Impact Analysis
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                    {topology.critical_paths.slice(0, 3).map((path, i) => (
                                        <div key={i} className="p-2 bg-orange-500/10 rounded-sm text-xs">
                                            <p className="text-orange-400 font-medium">
                                                {path.root_cause.name} ({path.root_cause.health_score}%)
                                            </p>
                                            <p className="text-white/70">
                                                Affects {path.affected_services.length} service(s)
                                            </p>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
                
                {/* Add Dependency Modal */}
                <AnimatePresence>
                    {showAddDependency && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                            onClick={(e) => e.target === e.currentTarget && setShowAddDependency(false)}
                        >
                            <motion.div
                                initial={{ scale: 0.95 }}
                                animate={{ scale: 1 }}
                                exit={{ scale: 0.95 }}
                                className="w-full max-w-md bg-[#0a0a0a] border border-white/10 rounded-sm p-6"
                            >
                                <h3 className="font-heading text-lg font-bold text-white mb-4">
                                    Add Service Dependency
                                </h3>
                                
                                <div className="space-y-4">
                                    <div>
                                        <label className="text-white/70 text-sm mb-2 block">Source Service</label>
                                        <Select
                                            value={newDependency.source}
                                            onValueChange={(v) => setNewDependency({ ...newDependency, source: v })}
                                        >
                                            <SelectTrigger className="bg-black/40 border-white/20">
                                                <SelectValue placeholder="Select source..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {monitors.map(m => (
                                                    <SelectItem key={m.id} value={m.id}>
                                                        {m.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    
                                    <div className="flex justify-center">
                                        <ArrowRight className="w-6 h-6 text-white/30" />
                                    </div>
                                    
                                    <div>
                                        <label className="text-white/70 text-sm mb-2 block">Target Service (Depends On)</label>
                                        <Select
                                            value={newDependency.target}
                                            onValueChange={(v) => setNewDependency({ ...newDependency, target: v })}
                                        >
                                            <SelectTrigger className="bg-black/40 border-white/20">
                                                <SelectValue placeholder="Select target..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {monitors.map(m => (
                                                    <SelectItem key={m.id} value={m.id}>
                                                        {m.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    
                                    <div>
                                        <label className="text-white/70 text-sm mb-2 block">Dependency Type</label>
                                        <Select
                                            value={newDependency.type}
                                            onValueChange={(v) => setNewDependency({ ...newDependency, type: v })}
                                        >
                                            <SelectTrigger className="bg-black/40 border-white/20">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="depends_on">Depends On</SelectItem>
                                                <SelectItem value="calls">Calls</SelectItem>
                                                <SelectItem value="uses">Uses</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    
                                    <div className="flex gap-2 pt-4">
                                        <Button
                                            variant="outline"
                                            onClick={() => setShowAddDependency(false)}
                                            className="flex-1"
                                        >
                                            Cancel
                                        </Button>
                                        <Button
                                            onClick={handleCreateDependency}
                                            className="flex-1 bg-cyan-500 text-black hover:bg-cyan-400"
                                        >
                                            <Link2 className="w-4 h-4 mr-2" />
                                            Create
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </>
    );
};

export default TopologyPage;
