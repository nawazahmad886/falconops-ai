import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Target, Play, History, AlertTriangle, Shield, RefreshCw,
    Crosshair, Clock, Zap, CheckCircle, XCircle, ChevronRight,
    Skull, Lock, Globe, Server, Database,
} from 'lucide-react';

const SCENARIO_ICONS = {
    brute_force: Lock,
    credential_stuffing: Lock,
    impossible_travel: Globe,
    privilege_escalation: Zap,
    data_exfiltration: Database,
    port_scan: Server,
    insider_threat: Skull,
};

const SEVERITY_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
};

export default function AttackSimulatorPage() {
    const { api } = useAuth();
    const [scenarios, setScenarios] = useState([]);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(null);
    const [lastResult, setLastResult] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [sRes, hRes] = await Promise.all([
                api.get('/security/attack-sim/scenarios'),
                api.get('/security/attack-sim/history?limit=10'),
            ]);
            setScenarios(sRes.data || []);
            setHistory(hRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const runScenario = async (scenarioId) => {
        setRunning(scenarioId);
        setLastResult(null);
        try {
            const res = await api.post('/security/attack-sim/run', { scenario_id: scenarioId });
            setLastResult(res.data);
            // Refresh history
            const hRes = await api.get('/security/attack-sim/history?limit=10');
            setHistory(hRes.data || []);
        } catch (e) { console.error(e); }
        setRunning(null);
    };

    if (loading) return <div className="flex items-center justify-center h-64 text-white/40">Loading scenarios...</div>;

    return (
        <div className="space-y-6" data-testid="attack-sim-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="attack-sim-title">
                        <Target className="w-7 h-7 text-red-400" />
                        Attack Simulator
                    </h1>
                    <p className="text-sm text-white/40 mt-1">Red team simulation engine — test your detection capabilities</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchData} className="border-white/10 text-xs" data-testid="sim-refresh">
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                </Button>
            </div>

            {/* Last Result Banner */}
            {lastResult && (
                <Card className="bg-emerald-500/5 border-emerald-500/20" data-testid="sim-result">
                    <CardContent className="p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <CheckCircle className="w-5 h-5 text-emerald-400" />
                            <div>
                                <p className="text-sm font-medium text-white/80">Simulation Complete: {lastResult.scenario_name}</p>
                                <p className="text-xs text-white/40">
                                    {lastResult.events_generated} events generated | {lastResult.threats_detected} threats detected
                                </p>
                            </div>
                        </div>
                        <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border">{lastResult.status}</Badge>
                    </CardContent>
                </Card>
            )}

            {/* Scenario Grid */}
            <div>
                <h3 className="text-sm font-medium text-white/60 mb-3">Available Scenarios</h3>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {scenarios.map((s) => {
                        const Icon = SCENARIO_ICONS[s.id] || Target;
                        const sevStyle = SEVERITY_STYLES[s.severity] || SEVERITY_STYLES.high;
                        const isRunning = running === s.id;
                        return (
                            <Card key={s.id} className="bg-[#0D1117] border-white/5 hover:border-white/10 transition-colors" data-testid={`scenario-${s.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="p-2 rounded-lg bg-red-500/10">
                                            <Icon className="w-5 h-5 text-red-400" />
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <Badge className={`${sevStyle} border text-[9px]`}>{s.severity}</Badge>
                                            <Badge variant="outline" className="text-[9px] text-purple-400 border-purple-500/30">{s.mitre}</Badge>
                                        </div>
                                    </div>
                                    <h4 className="text-sm font-semibold text-white/90 mb-1">{s.name}</h4>
                                    <p className="text-xs text-white/40 mb-4 line-clamp-2">{s.description}</p>
                                    <Button
                                        size="sm"
                                        onClick={() => runScenario(s.id)}
                                        disabled={!!running}
                                        className="w-full bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30 text-xs"
                                        data-testid={`run-${s.id}`}
                                    >
                                        {isRunning ? (
                                            <><RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Running...</>
                                        ) : (
                                            <><Play className="w-3.5 h-3.5 mr-1.5" /> Run Simulation</>
                                        )}
                                    </Button>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            </div>

            {/* History */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-white/60 flex items-center gap-2">
                        <History className="w-4 h-4" /> Simulation History
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {history.length === 0 ? (
                        <p className="text-center text-white/30 py-8 text-sm">No simulations run yet</p>
                    ) : (
                        <div className="space-y-1.5">
                            {history.map((h, i) => (
                                <div key={h.id || i} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5" data-testid={`history-${i}`}>
                                    <div className="flex items-center gap-3">
                                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                                        <div>
                                            <p className="text-sm font-medium text-white/70">{h.scenario_name || h.scenario}</p>
                                            <p className="text-[10px] text-white/30">{h.events_generated} events | {h.threats_detected} threats</p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <Badge variant="outline" className="text-[10px] text-white/40 border-white/10">{h.status}</Badge>
                                        <p className="text-[10px] text-white/20 mt-0.5">{new Date(h.started_at).toLocaleString()}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
