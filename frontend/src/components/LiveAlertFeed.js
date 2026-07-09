import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Radio, Bell, X, Volume2, VolumeX, AlertTriangle, Zap } from 'lucide-react';

const severityColors = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
};

const severityIcons = {
    critical: AlertTriangle,
    warning: Zap,
    info: Bell,
};

export const LiveAlertFeed = ({ maxAlerts = 10 }) => {
    const [alerts, setAlerts] = useState([]);
    const [connected, setConnected] = useState(false);
    const [soundEnabled, setSoundEnabled] = useState(true);
    const [expanded, setExpanded] = useState(false);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const audioRef = useRef(null);

    // Create audio for alert sound
    useEffect(() => {
        // Create a simple beep sound using Web Audio API
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioRef.current = audioContext;
        return () => {
            if (audioContext.state !== 'closed') {
                audioContext.close();
            }
        };
    }, []);

    const playAlertSound = useCallback((severity) => {
        if (!soundEnabled || !audioRef.current) return;
        
        try {
            const ctx = audioRef.current;
            if (ctx.state === 'suspended') {
                ctx.resume();
            }
            
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);
            
            // Different tones for different severities
            const frequencies = {
                critical: 880,
                warning: 660,
                info: 440,
            };
            
            oscillator.frequency.setValueAtTime(frequencies[severity] || 440, ctx.currentTime);
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            
            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + 0.3);
        } catch (e) {
            console.log('Audio playback error:', e);
        }
    }, [soundEnabled]);

    const connectWebSocket = useCallback(() => {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/alerts`;
        
        try {
            const ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                setConnected(true);
            };
            
            ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    
                    if (message.type === 'new_alert') {
                        const newAlert = {
                            ...message.data,
                            receivedAt: new Date().toISOString(),
                            id: message.data.id || Date.now().toString(),
                        };
                        
                        setAlerts(prev => {
                            const updated = [newAlert, ...prev].slice(0, maxAlerts);
                            return updated;
                        });
                        
                        // Play sound
                        playAlertSound(newAlert.severity);
                    }
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setConnected(false);
                // Attempt to reconnect after 5 seconds
                reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                ws.close();
            };
            
            wsRef.current = ws;
        } catch (e) {
            console.error('WebSocket connection error:', e);
            setConnected(false);
            // Retry connection
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000);
        }
    }, [maxAlerts, playAlertSound]);

    useEffect(() => {
        connectWebSocket();
        
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connectWebSocket]);

    // Send ping every 30 seconds to keep connection alive
    useEffect(() => {
        const pingInterval = setInterval(() => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send('ping');
            }
        }, 30000);
        
        return () => clearInterval(pingInterval);
    }, []);

    const dismissAlert = (alertId) => {
        setAlerts(prev => prev.filter(a => a.id !== alertId));
    };

    const formatTime = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    return (
        <Card className="bg-[#0a0a0a] border-white/5 rounded-sm overflow-hidden">
            <CardHeader className="pb-2 border-b border-white/5">
                <div className="flex items-center justify-between">
                    <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2 text-white">
                        <Radio className={`w-4 h-4 ${connected ? 'text-green-400' : 'text-red-400'}`} />
                        Live Alert Feed
                        {connected && (
                            <span className="flex items-center gap-1 px-2 py-0.5 bg-green-500/10 border border-green-500/20 rounded-sm">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                                <span className="text-[10px] text-green-400 font-mono">LIVE</span>
                            </span>
                        )}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSoundEnabled(!soundEnabled)}
                            className="h-8 w-8 p-0 text-white/50 hover:text-white hover:bg-white/5"
                            data-testid="toggle-sound-btn"
                        >
                            {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpanded(!expanded)}
                            className="text-xs text-cyan-400 hover:text-cyan-300 uppercase tracking-wider"
                            data-testid="toggle-expand-btn"
                        >
                            {expanded ? 'Collapse' : 'Expand'}
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className={`p-0 ${expanded ? 'max-h-[500px]' : 'max-h-[300px]'} overflow-y-auto transition-all duration-300`}>
                {alerts.length === 0 ? (
                    <div className="text-center py-12 text-white/30">
                        <Radio className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p className="text-sm font-medium mb-1">Listening for alerts...</p>
                        <p className="text-xs font-mono">
                            {connected ? 'Connected to real-time feed' : 'Connecting...'}
                        </p>
                    </div>
                ) : (
                    <AnimatePresence mode="popLayout">
                        {alerts.map((alert, index) => {
                            const SeverityIcon = severityIcons[alert.severity] || Bell;
                            return (
                                <motion.div
                                    key={alert.id}
                                    initial={{ opacity: 0, x: -20, height: 0 }}
                                    animate={{ opacity: 1, x: 0, height: 'auto' }}
                                    exit={{ opacity: 0, x: 20, height: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className={`border-b border-white/5 ${index === 0 ? 'bg-white/5' : ''}`}
                                >
                                    <div className="p-4 flex items-start gap-3">
                                        <div className={`w-8 h-8 rounded-sm flex items-center justify-center shrink-0 ${
                                            alert.severity === 'critical' ? 'bg-red-500/20' :
                                            alert.severity === 'warning' ? 'bg-yellow-500/20' :
                                            'bg-cyan-500/20'
                                        }`}>
                                            <SeverityIcon className={`w-4 h-4 ${
                                                alert.severity === 'critical' ? 'text-red-400' :
                                                alert.severity === 'warning' ? 'text-yellow-400' :
                                                'text-cyan-400'
                                            }`} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="min-w-0">
                                                    <p className="text-sm font-medium text-white truncate">{alert.title}</p>
                                                    <p className="text-xs text-white/50 font-mono mt-0.5">
                                                        {alert.source} • {alert.service}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-2 shrink-0">
                                                    <Badge className={`${severityColors[alert.severity]} text-[10px] uppercase rounded-sm border`}>
                                                        {alert.severity}
                                                    </Badge>
                                                    <button
                                                        onClick={() => dismissAlert(alert.id)}
                                                        className="text-white/30 hover:text-white/70 p-1"
                                                        data-testid={`dismiss-alert-${alert.id}`}
                                                    >
                                                        <X className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2 mt-2">
                                                <span className="text-[10px] text-white/30 font-mono">
                                                    {formatTime(alert.receivedAt || alert.created_at)}
                                                </span>
                                                {index === 0 && (
                                                    <span className="text-[10px] text-cyan-400 font-mono uppercase">New</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                )}
            </CardContent>
        </Card>
    );
};
