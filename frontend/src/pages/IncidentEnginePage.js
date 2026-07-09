import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    AlertTriangle, Clock, CheckCircle2, RefreshCw, ChevronDown, ChevronRight,
    Shield, Zap, Users, Server, Activity, Brain, Target, ArrowRight
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SEV_CONFIG = {
    sev1: { color: 'bg-red-500/20 text-red-400 border-red-500/30', label: 'SEV-1 Critical', dot: 'bg-red-500' },
    sev2: { color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', label: 'SEV-2 High', dot: 'bg-orange-500' },
    sev3: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'SEV-3 Medium', dot: 'bg-amber-500' },
    sev4: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'SEV-4 Low', dot: 'bg-blue-500' },
    sev5: { color: 'bg-slate-500/20 text-slate-400 border-slate-500/30', label: 'SEV-5 Info', dot: 'bg-slate-500' },
};

const STATUS_CONFIG = {
    active: { color: 'bg-red-500/20 text-red-400', label: 'Active' },
    investigating: { color: 'bg-amber-500/20 text-amber-400', label: 'Investigating' },
    identified: { color: 'bg-cyan-500/20 text-cyan-400', label: 'Identified' },
    monitoring: { color: 'bg-blue-500/20 text-blue-400', label: 'Monitoring' },
    resolved: { color: 'bg-emerald-500/20 text-emerald-400', label: 'Resolved' },
    closed: { color: 'bg-slate-500/20 text-slate-400', label: 'Closed' },
};

export const IncidentEnginePage = () => {
    const { token } = useAuth();
    const [incidents, setIncidents] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('active');
    const [expandedId, setExpandedId] = useState(null);
    const [rcaLoading, setRcaLoading] = useState(null);

    const headers = useCallback(() => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
    }), [token]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await fetch(`${API_URL}/api/incident-engine/stats`, { headers: headers() });
            if (res.ok) setStats(await res.json());
        } catch (e) { console.error(e); }
    }, [headers]);

    const fetchIncidents = useCallback(async () => {
        setLoading(true);
        try {
            const url = activeTab === 'active'
                ? `${API_URL}/api/incident-engine/active`
                : `${API_URL}/api/incident-engine?limit=50`;
            const res = await fetch(url, { headers: headers() });
            if (res.ok) {
                const data = await res.json();
                setIncidents(data.incidents || []);
            }
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [headers, activeTab]);

    useEffect(() => { fetchStats(); fetchIncidents(); }, [fetchStats, fetchIncidents]);

    const updateStatus = async (id, status) => {
        try {
            const res = await fetch(`${API_URL}/api/incident-engine/${id}/status`, {
                method: 'POST', headers: headers(),
                body: JSON.stringify({ status })
            });
            if (res.ok) {
                toast.success(`Incident ${status}`);
                fetchIncidents(); fetchStats();
            }
        } catch (e) { toast.error(e.message); }
    };

    const runRCA = async (id) => {
        setRcaLoading(id);
        try {
            const res = await fetch(`${API_URL}/api/incident-engine/${id}/analyze-rca`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                toast.success('RCA analysis complete');
                fetchIncidents();
            } else {
                toast.error('RCA analysis failed');
            }
        } catch (e) { toast.error(e.message); }
        setRcaLoading(null);
    };

    const autoCorrelate = async () => {
        try {
            const res = await fetch(`${API_URL}/api/incident-engine/auto-correlate?time_window_minutes=30&min_alerts=2`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                toast.success(data.message);
                fetchIncidents(); fetchStats();
            }
        } catch (e) { toast.error(e.message); }
    };

    const seedIncidents = async () => {
        try {
            const res = await fetch(`${API_URL}/api/seed/incidents`, {
                method: 'POST', headers: headers()
            });
            if (res.ok) {
                const data = await res.json();
                toast.success(data.message);
                fetchIncidents(); fetchStats();
            }
        } catch (e) { toast.error(e.message); }
    };

    return (
        <div data-testid="incident-engine-page" className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white font-[Barlow_Condensed] uppercase tracking-wide">
                        Incident Management
                    </h1>
                    <p className="text-sm text-[#A3A3A3]">Alert correlation, RCA, and incident lifecycle</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button data-testid="auto-correlate-btn" variant="outline" size="sm" onClick={autoCorrelate}
                        className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10">
                        <Brain className="h-4 w-4 mr-1" /> Auto-Correlate
                    </Button>
                    <Button data-testid="seed-incidents-btn" variant="outline" size="sm" onClick={seedIncidents}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white hover:border-[#D4AF37]">
                        <Zap className="h-4 w-4 mr-1" /> Seed Demo
                    </Button>
                    <Button data-testid="refresh-incidents-btn" variant="outline" size="sm"
                        onClick={() => { fetchIncidents(); fetchStats(); }}
                        className="border-[#1F1F1F] text-[#A3A3A3] hover:text-white">
                        <RefreshCw className="h-4 w-4 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {/* Stats */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Active Incidents" value={stats.active_incidents || 0}
                        icon={AlertTriangle} color="bg-red-500/10 text-red-400" />
                    <StatCard label="SEV-1" value={stats.by_severity?.sev1 || 0}
                        icon={Shield} color="bg-red-500/10 text-red-400" />
                    <StatCard label="SEV-2" value={stats.by_severity?.sev2 || 0}
                        icon={AlertTriangle} color="bg-orange-500/10 text-orange-400" />
                    <StatCard label="Avg MTTR" value={stats.avg_mttr_minutes ? `${Math.round(stats.avg_mttr_minutes)}m` : 'N/A'}
                        icon={Clock} color="bg-cyan-500/10 text-cyan-400" subtext="Mean Time to Resolve" />
                </div>
            )}

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="bg-[#0A0A0A] border border-[#1F1F1F]">
                    <TabsTrigger data-testid="tab-active-incidents" value="active" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">Active</TabsTrigger>
                    <TabsTrigger data-testid="tab-all-incidents" value="all" className="data-[state=active]:bg-[#1F1F1F] data-[state=active]:text-[#D4AF37]">All Incidents</TabsTrigger>
                </TabsList>

                <TabsContent value="active" className="mt-4">
                    <IncidentList incidents={incidents} loading={loading} expandedId={expandedId}
                        setExpandedId={setExpandedId} onUpdateStatus={updateStatus}
                        onRunRCA={runRCA} rcaLoading={rcaLoading} />
                </TabsContent>
                <TabsContent value="all" className="mt-4">
                    <IncidentList incidents={incidents} loading={loading} expandedId={expandedId}
                        setExpandedId={setExpandedId} onUpdateStatus={updateStatus}
                        onRunRCA={runRCA} rcaLoading={rcaLoading} />
                </TabsContent>
            </Tabs>
        </div>
    );
};

const StatCard = ({ label, value, icon: Icon, color, subtext }) => (
    <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
        <CardContent className="p-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed]">{label}</p>
                    <p className="text-2xl font-bold text-white mt-1 font-[JetBrains_Mono]">{value}</p>
                    {subtext && <p className="text-xs text-[#A3A3A3] mt-1">{subtext}</p>}
                </div>
                <div className={`p-2 rounded-lg ${color}`}>
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </CardContent>
    </Card>
);

const IncidentList = ({ incidents, loading, expandedId, setExpandedId, onUpdateStatus, onRunRCA, rcaLoading }) => {
    if (loading) return (
        <div className="flex items-center justify-center py-12">
            <RefreshCw className="h-6 w-6 text-[#A3A3A3] animate-spin" />
        </div>
    );
    if (!incidents.length) return (
        <Card className="bg-[#0A0A0A] border-[#1F1F1F]">
            <CardContent className="py-12 text-center">
                <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                <p className="text-white font-medium">No Active Incidents</p>
                <p className="text-sm text-[#A3A3A3]">All systems operating normally</p>
            </CardContent>
        </Card>
    );

    return (
        <div className="space-y-3">
            {incidents.map(incident => {
                const sev = SEV_CONFIG[incident.severity] || SEV_CONFIG.sev3;
                const status = STATUS_CONFIG[incident.status] || STATUS_CONFIG.active;
                const isExpanded = expandedId === incident.id;

                return (
                    <Card key={incident.id} data-testid={`incident-card-${incident.id}`}
                        className="bg-[#0A0A0A] border-[#1F1F1F] hover:border-[#2A2A2A] transition-colors">
                        <CardContent className="p-0">
                            {/* Header row */}
                            <div className="flex items-center justify-between p-4 cursor-pointer"
                                onClick={() => setExpandedId(isExpanded ? null : incident.id)}>
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                    {isExpanded ? <ChevronDown className="h-4 w-4 text-[#A3A3A3] shrink-0" /> : <ChevronRight className="h-4 w-4 text-[#A3A3A3] shrink-0" />}
                                    <div className={`w-2 h-2 rounded-full ${sev.dot} shrink-0`} />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-medium text-white truncate">{incident.title}</span>
                                            <Badge className={`text-[10px] ${sev.color} border`}>{sev.label}</Badge>
                                            <Badge className={`text-[10px] ${status.color}`}>{status.label}</Badge>
                                        </div>
                                        <div className="flex items-center gap-3 mt-1 text-[10px] text-[#525252]">
                                            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(incident.created_at).toLocaleString()}</span>
                                            <span>{incident.alert_count || 0} alerts</span>
                                            {incident.affected_services?.length > 0 && (
                                                <span className="flex items-center gap-1"><Server className="h-3 w-3" />{incident.affected_services.join(', ')}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-1 shrink-0">
                                    {incident.status === 'active' && (
                                        <>
                                            <Button data-testid={`investigate-btn-${incident.id}`} size="sm" variant="outline"
                                                onClick={(e) => { e.stopPropagation(); onUpdateStatus(incident.id, 'investigating'); }}
                                                className="text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10 h-7 px-2">
                                                Investigate
                                            </Button>
                                            <Button data-testid={`rca-btn-${incident.id}`} size="sm" variant="outline"
                                                onClick={(e) => { e.stopPropagation(); onRunRCA(incident.id); }}
                                                disabled={rcaLoading === incident.id}
                                                className="text-xs border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 h-7 px-2">
                                                <Brain className="h-3 w-3 mr-1" />{rcaLoading === incident.id ? 'Analyzing...' : 'RCA'}
                                            </Button>
                                        </>
                                    )}
                                    {['active', 'investigating', 'identified', 'monitoring'].includes(incident.status) && (
                                        <Button data-testid={`resolve-incident-btn-${incident.id}`} size="sm" variant="outline"
                                            onClick={(e) => { e.stopPropagation(); onUpdateStatus(incident.id, 'resolved'); }}
                                            className="text-xs border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 h-7 px-2">
                                            Resolve
                                        </Button>
                                    )}
                                </div>
                            </div>

                            {/* Expanded details */}
                            {isExpanded && (
                                <div className="border-t border-[#1F1F1F] p-4 space-y-4">
                                    <p className="text-sm text-[#A3A3A3]">{incident.description}</p>

                                    {/* Root Cause */}
                                    {incident.root_cause && (
                                        <div className="bg-[#121212] border border-cyan-500/20 rounded-lg p-3">
                                            <p className="text-xs text-cyan-400 font-[Barlow_Condensed] uppercase tracking-wider mb-1">Root Cause Analysis</p>
                                            <p className="text-sm text-white">{incident.root_cause}</p>
                                            {incident.root_cause_analysis?.remediation && (
                                                <div className="mt-2">
                                                    <p className="text-xs text-[#A3A3A3] mb-1">Remediation Steps:</p>
                                                    <ul className="text-xs text-[#A3A3A3] space-y-1">
                                                        {(Array.isArray(incident.root_cause_analysis.remediation)
                                                            ? incident.root_cause_analysis.remediation
                                                            : [incident.root_cause_analysis.remediation]
                                                        ).map((step, i) => (
                                                            <li key={i} className="flex items-start gap-1">
                                                                <ArrowRight className="h-3 w-3 mt-0.5 text-cyan-400 shrink-0" />
                                                                {step}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Timeline */}
                                    {incident.timeline?.length > 0 && (
                                        <div>
                                            <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed] mb-2">Timeline</p>
                                            <div className="space-y-2">
                                                {incident.timeline.slice(-5).reverse().map((entry, i) => (
                                                    <div key={i} className="flex items-start gap-2 text-xs">
                                                        <div className="w-1.5 h-1.5 rounded-full bg-[#525252] mt-1.5 shrink-0" />
                                                        <div>
                                                            <span className="text-[#525252] font-[JetBrains_Mono]">
                                                                {new Date(entry.timestamp).toLocaleTimeString()}
                                                            </span>
                                                            <span className="text-[#A3A3A3] ml-2">{entry.details}</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Linked alerts */}
                                    {incident.alerts?.length > 0 && (
                                        <div>
                                            <p className="text-xs text-[#A3A3A3] uppercase tracking-wider font-[Barlow_Condensed] mb-2">Linked Alerts ({incident.alerts.length})</p>
                                            <div className="grid gap-1">
                                                {incident.alerts.slice(0, 5).map(alert => (
                                                    <div key={alert.id} className="flex items-center gap-2 text-xs bg-[#121212] rounded p-2">
                                                        <div className={`w-1.5 h-1.5 rounded-full ${alert.severity === 'critical' ? 'bg-red-500' : alert.severity === 'high' ? 'bg-orange-500' : 'bg-amber-500'}`} />
                                                        <span className="text-white truncate flex-1">{alert.title}</span>
                                                        <Badge className="text-[9px] bg-[#1F1F1F] text-[#A3A3A3]">{alert.severity}</Badge>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
};

export default IncidentEnginePage;
