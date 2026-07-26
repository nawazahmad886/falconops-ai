import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Network,
    Server,
    Globe,
    CheckCircle2,
    XCircle,
    Clock,
    AlertTriangle,
    RefreshCw,
    ArrowDown,
    Wifi,
    Router,
    X,
    Info,
    Target,
    Zap,
    AlertCircle,
} from 'lucide-react';

const statusConfig = {
    success: {
        color: 'green',
        bg: 'bg-green-500/20',
        border: 'border-green-500/50',
        text: 'text-green-400',
        icon: CheckCircle2,
        glow: 'shadow-[0_0_15px_rgba(16,185,129,0.4)]',
    },
    timeout: {
        color: 'yellow',
        bg: 'bg-yellow-500/20',
        border: 'border-yellow-500/50',
        text: 'text-yellow-400',
        icon: Clock,
        glow: 'shadow-[0_0_15px_rgba(245,158,11,0.4)]',
    },
    error: {
        color: 'red',
        bg: 'bg-red-500/20',
        border: 'border-red-500/50',
        text: 'text-red-400',
        icon: XCircle,
        glow: 'shadow-[0_0_15px_rgba(239,68,68,0.5)]',
    },
};

const HopNode = ({ hop, index, isLast, showDetails, onHover }) => {
    const config = statusConfig[hop.status] || statusConfig.success;
    const StatusIcon = config.icon;
    
    const getHopIcon = () => {
        if (hop.is_destination) return Globe;
        if (hop.hop_number === 1) return Router;
        return Server;
    };
    
    const HopIcon = getHopIcon();
    
    return (
        <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1, duration: 0.3 }}
            className="relative"
            onMouseEnter={() => onHover(hop)}
            onMouseLeave={() => onHover(null)}
        >
            {/* Connection Line */}
            {!isLast && (
                <div className="absolute left-[23px] top-[48px] w-[2px] h-[40px] z-0">
                    <div
                        className={`w-full h-full ${
                            hop.status === 'success' ? 'bg-green-500/50' :
                            hop.status === 'timeout' ? 'bg-yellow-500/50' : 'bg-red-500/50'
                        }`}
                    />
                    {/* Animated pulse along the line */}
                    {hop.status === 'success' && (
                        <motion.div
                            className="absolute top-0 left-0 w-full h-2 bg-green-400 rounded-full"
                            animate={{ top: ['0%', '100%'] }}
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear', delay: index * 0.2 }}
                        />
                    )}
                </div>
            )}
            
            {/* Hop Node */}
            <div className="flex items-center gap-4 relative z-10">
                {/* Node Circle */}
                <motion.div
                    className={`
                        w-12 h-12 rounded-full flex items-center justify-center
                        ${config.bg} ${config.border} border-2
                        ${hop.status === 'error' || hop.status === 'timeout' ? config.glow : ''}
                        ${hop.is_destination ? 'ring-2 ring-offset-2 ring-offset-black ring-primary' : ''}
                    `}
                    whileHover={{ scale: 1.1 }}
                    animate={hop.status === 'error' ? { scale: [1, 1.05, 1] } : {}}
                    transition={hop.status === 'error' ? { repeat: Infinity, duration: 1.5 } : {}}
                >
                    <HopIcon className={`w-5 h-5 ${config.text}`} />
                </motion.div>
                
                {/* Hop Details */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-white/40 font-mono text-xs">HOP {hop.hop_number}</span>
                        <Badge className={`${config.bg} ${config.text} text-[9px] uppercase border ${config.border}`}>
                            {hop.status}
                        </Badge>
                        {hop.is_destination && (
                            <Badge className="bg-primary/20 text-primary border border-primary/30 text-[9px] uppercase">
                                Destination
                            </Badge>
                        )}
                    </div>
                    
                    <div className="flex items-center gap-3">
                        <p className="text-white font-medium text-sm truncate">
                            {hop.hostname || hop.ip_address || 'Unknown'}
                        </p>
                        {hop.ip_address && hop.hostname && hop.hostname !== hop.ip_address && (
                            <span className="text-white/40 text-xs font-mono hidden sm:inline">
                                ({hop.ip_address})
                            </span>
                        )}
                    </div>
                    
                    <div className="flex items-center gap-4 mt-1">
                        {hop.latency_ms !== null && hop.latency_ms !== undefined ? (
                            <span className={`text-xs font-mono ${
                                hop.latency_ms < 50 ? 'text-green-400' :
                                hop.latency_ms < 100 ? 'text-yellow-400' : 'text-red-400'
                            }`}>
                                <Clock className="w-3 h-3 inline mr-1" />
                                {hop.latency_ms}ms
                            </span>
                        ) : (
                            <span className="text-xs font-mono text-white/30">
                                <Clock className="w-3 h-3 inline mr-1" />
                                --
                            </span>
                        )}
                        {hop.location && (
                            <span className="text-xs text-white/40">{hop.location}</span>
                        )}
                        {hop.packet_loss_pct !== null && hop.packet_loss_pct !== undefined && hop.packet_loss_pct > 0 && (
                            <span className="text-xs font-mono text-red-400">{hop.packet_loss_pct}% loss</span>
                        )}
                        {hop.jitter_ms !== null && hop.jitter_ms !== undefined && (
                            <span className="text-xs font-mono text-white/40">±{hop.jitter_ms}ms jitter</span>
                        )}
                    </div>

                    {(hop.asn || hop.isp || hop.is_proxy_or_vpn || hop.is_hosting) && (
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                            {(hop.asn || hop.isp) && (
                                <span className="text-[10px] font-mono text-white/30 truncate">
                                    {hop.asn || hop.isp}
                                </span>
                            )}
                            {hop.is_proxy_or_vpn && (
                                <Badge className="bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[9px] uppercase">
                                    VPN/Proxy
                                </Badge>
                            )}
                            {hop.is_hosting && (
                                <Badge className="bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[9px] uppercase">
                                    Hosting
                                </Badge>
                            )}
                        </div>
                    )}
                </div>
                
                {/* Status Icon */}
                <StatusIcon className={`w-5 h-5 ${config.text}`} />
            </div>
            
            {/* Spacer for connection line */}
            {!isLast && <div className="h-10" />}
        </motion.div>
    );
};

const AnalysisPanel = ({ analysis, destinationReached, routingLoopDetected, routeChanged, blockedLikely }) => {
    if (!analysis) return null;

    const isHealthy = destinationReached && analysis.status === 'healthy';
    const hasWarning = analysis.status === 'connected_with_warnings';
    const hasError = !destinationReached || analysis.issue;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className={`p-4 rounded-sm border ${
                isHealthy ? 'bg-green-500/10 border-green-500/30' :
                hasWarning ? 'bg-yellow-500/10 border-yellow-500/30' :
                'bg-red-500/10 border-red-500/30'
            }`}
        >
            <div className="flex items-start gap-3">
                {isHealthy ? (
                    <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                ) : hasWarning ? (
                    <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                ) : (
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                )}
                <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                        <h4 className={`font-bold text-sm uppercase ${
                            isHealthy ? 'text-green-400' :
                            hasWarning ? 'text-yellow-400' : 'text-red-400'
                        }`}>
                            {isHealthy ? 'Network Path Healthy' :
                             hasWarning ? 'Network Warning' :
                             'Network Issue Detected'}
                        </h4>
                        {routingLoopDetected && (
                            <Badge className="bg-red-500/20 text-red-300 border border-red-500/30 text-[9px] uppercase">
                                Routing Loop
                            </Badge>
                        )}
                        {routeChanged && (
                            <Badge className="bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 text-[9px] uppercase">
                                Route Changed
                            </Badge>
                        )}
                        {blockedLikely && (
                            <Badge className="bg-red-500/20 text-red-300 border border-red-500/30 text-[9px] uppercase">
                                Likely Blocked
                            </Badge>
                        )}
                    </div>
                    <p className="text-white/70 text-sm">
                        {analysis.message || analysis.issue || analysis.warning}
                    </p>
                    {analysis.recommendation && (
                        <p className="text-white/50 text-xs mt-2">
                            <strong>Recommendation:</strong> {analysis.recommendation}
                        </p>
                    )}
                    {analysis.failure_point && (
                        <p className="text-red-400 text-xs mt-1">
                            <strong>Failure Point:</strong> {analysis.failure_point}
                        </p>
                    )}
                </div>
            </div>
        </motion.div>
    );
};

export const TracerouteVisualizer = ({
    monitorId,
    monitorName,
    target,
    api,
    onClose,
    isModal = true,
}) => {
    const [traceData, setTraceData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hoveredHop, setHoveredHop] = useState(null);
    
    const runTrace = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.post(`/topology/${monitorId}/traceroute`);
            setTraceData(response.data);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to execute traceroute');
        } finally {
            setLoading(false);
        }
    };
    
    useEffect(() => {
        if (monitorId) {
            runTrace();
        }
    }, [monitorId]);
    
    const content = (
        <div className="space-y-6" data-testid="traceroute-visualizer">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-sm bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                        <Network className="w-5 h-5 text-cyan-400" />
                    </div>
                    <div>
                        <h3 className="font-heading font-bold text-lg uppercase text-white">
                            Network Path Analysis
                        </h3>
                        <p className="text-white/50 text-xs font-mono">{target}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        onClick={runTrace}
                        disabled={loading}
                        size="sm"
                        className="bg-cyan-500 text-black hover:bg-cyan-400 font-bold uppercase text-xs"
                    >
                        {loading ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                            <>
                                <RefreshCw className="w-4 h-4 mr-1" />
                                Trace
                            </>
                        )}
                    </Button>
                    {isModal && onClose && (
                        <Button
                            onClick={onClose}
                            variant="ghost"
                            size="sm"
                            className="text-white/50 hover:text-white"
                        >
                            <X className="w-5 h-5" />
                        </Button>
                    )}
                </div>
            </div>
            
            {/* Stats Summary */}
            {traceData && !loading && (
                <div className="grid grid-cols-4 gap-3">
                    <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                        <p className="text-[10px] text-white/40 uppercase mb-1">Total Hops</p>
                        <p className="font-heading font-bold text-xl text-cyan-400">{traceData.total_hops}</p>
                    </div>
                    <div className={`p-3 rounded-sm border ${
                        traceData.destination_reached
                            ? 'bg-green-500/10 border-green-500/30'
                            : 'bg-red-500/10 border-red-500/30'
                    }`}>
                        <p className="text-[10px] text-white/40 uppercase mb-1">Status</p>
                        <p className={`font-heading font-bold text-sm uppercase ${
                            traceData.destination_reached ? 'text-green-400' : 'text-red-400'
                        }`}>
                            {traceData.destination_reached ? 'Reachable' : 'Unreachable'}
                        </p>
                    </div>
                    <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                        <p className="text-[10px] text-white/40 uppercase mb-1">Success Rate</p>
                        <p className="font-heading font-bold text-xl text-primary">
                            {traceData.hops.length > 0
                                ? Math.round((traceData.hops.filter(h => h.status === 'success').length / traceData.hops.length) * 100)
                                : 0}%
                        </p>
                    </div>
                    <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                        <p className="text-[10px] text-white/40 uppercase mb-1">Failure Hop</p>
                        <p className={`font-heading font-bold text-xl ${traceData.failure_hop ? 'text-red-400' : 'text-white/30'}`}>
                            {traceData.failure_hop || '--'}
                        </p>
                    </div>
                    {traceData.avg_packet_loss_pct !== null && traceData.avg_packet_loss_pct !== undefined && (
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <p className="text-[10px] text-white/40 uppercase mb-1">Avg Packet Loss</p>
                            <p className={`font-heading font-bold text-xl ${traceData.avg_packet_loss_pct > 0 ? 'text-red-400' : 'text-green-400'}`}>
                                {traceData.avg_packet_loss_pct}%
                            </p>
                        </div>
                    )}
                    {traceData.avg_jitter_ms !== null && traceData.avg_jitter_ms !== undefined && (
                        <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                            <p className="text-[10px] text-white/40 uppercase mb-1">Avg Jitter</p>
                            <p className="font-heading font-bold text-xl text-cyan-400">
                                {traceData.avg_jitter_ms}ms
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* DNS / TCP / TLS Timing Breakdown */}
            {traceData && !loading && (traceData.dns_resolution_ms != null || traceData.tcp_connect_ms != null || traceData.tls_handshake_ms != null) && (
                <div className="flex items-center gap-4 p-3 bg-white/5 rounded-sm border border-white/10 text-xs font-mono">
                    {traceData.dns_resolution_ms != null && (
                        <span className="text-white/50">DNS <span className="text-white">{traceData.dns_resolution_ms}ms</span></span>
                    )}
                    {traceData.tcp_connect_ms != null && (
                        <span className="text-white/50">TCP <span className="text-white">{traceData.tcp_connect_ms}ms</span></span>
                    )}
                    {traceData.tls_handshake_ms != null && (
                        <span className="text-white/50">TLS <span className="text-white">{traceData.tls_handshake_ms}ms</span></span>
                    )}
                    <span className={traceData.tcp_reachable ? 'text-green-400' : 'text-red-400'}>
                        {traceData.tcp_reachable ? 'Port Reachable' : 'Port Unreachable'}
                    </span>
                </div>
            )}
            
            {/* Loading State */}
            {loading && (
                <div className="flex flex-col items-center justify-center py-12">
                    <div className="relative">
                        <div className="w-16 h-16 rounded-full border-4 border-cyan-500/20" />
                        <div className="absolute inset-0 w-16 h-16 rounded-full border-4 border-transparent border-t-cyan-400 animate-spin" />
                        <Network className="w-6 h-6 text-cyan-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                    </div>
                    <p className="text-white/50 mt-4 font-mono text-sm">Tracing network path...</p>
                    <p className="text-white/30 text-xs mt-1">This may take up to 60 seconds</p>
                </div>
            )}
            
            {/* Error State */}
            {error && !loading && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-sm">
                    <div className="flex items-center gap-2 text-red-400">
                        <AlertCircle className="w-5 h-5" />
                        <span className="font-bold">Error</span>
                    </div>
                    <p className="text-white/70 mt-2">{error}</p>
                    <Button onClick={runTrace} size="sm" className="mt-3 bg-red-500/20 text-red-400 hover:bg-red-500/30">
                        Retry
                    </Button>
                </div>
            )}
            
            {/* Trace Results */}
            {traceData && !loading && (
                <>
                    {/* Network Path Visualization */}
                    <div className="p-4 bg-black/30 rounded-sm border border-white/5">
                        <div className="flex items-center gap-2 mb-4">
                            <Target className="w-4 h-4 text-primary" />
                            <span className="text-white/50 text-xs uppercase font-mono">Network Path</span>
                        </div>
                        
                        <div className="space-y-0">
                            {traceData.hops.map((hop, index) => (
                                <HopNode
                                    key={hop.hop_number}
                                    hop={hop}
                                    index={index}
                                    isLast={index === traceData.hops.length - 1}
                                    showDetails={hoveredHop?.hop_number === hop.hop_number}
                                    onHover={setHoveredHop}
                                />
                            ))}
                        </div>
                    </div>
                    
                    {/* Analysis */}
                    <AnalysisPanel
                        analysis={traceData.analysis}
                        destinationReached={traceData.destination_reached}
                        routingLoopDetected={traceData.routing_loop_detected}
                        routeChanged={traceData.route_changed}
                        blockedLikely={traceData.blocked_likely}
                    />
                    
                    {/* Timestamp */}
                    <p className="text-white/30 text-xs text-center font-mono">
                        Executed at: {new Date(traceData.executed_at).toLocaleString()}
                    </p>
                </>
            )}
        </div>
    );
    
    if (!isModal) {
        return content;
    }
    
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={(e) => e.target === e.currentTarget && onClose?.()}
        >
            <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-[#0a0a0a] border border-white/10 rounded-sm p-6"
            >
                {content}
            </motion.div>
        </motion.div>
    );
};

export default TracerouteVisualizer;
