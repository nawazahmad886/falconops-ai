import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
    ShieldCheck,
    ShieldAlert,
    Bug,
    ClipboardCheck,
    Activity,
    RefreshCw,
    MapPin,
} from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';

const SEVERITY_COLOR = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    low: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    unknown: 'text-white/40 bg-white/5 border-white/10',
};

const STATUS_COLOR = {
    pass: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    fail: 'text-red-400 bg-red-500/10 border-red-500/30',
    unknown: 'text-white/40 bg-white/5 border-white/10',
};

const ScoreGauge = ({ label, value }) => {
    const color = value >= 75 ? 'text-emerald-400' : value >= 50 ? 'text-amber-400' : 'text-red-400';
    return (
        <div className="flex flex-col items-center gap-1" data-testid={`score-component-${label}`}>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-[11px] text-white/40 uppercase tracking-wider text-center">{label.replace(/_/g, ' ')}</p>
        </div>
    );
};

export default function ExecutiveSecurityDashboardPage() {
    const { api } = useAuth();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchOverview = useCallback(async () => {
        try {
            setError(null);
            const res = await api.get('/executive/security-overview?hours=24');
            setData(res.data);
        } catch (e) {
            console.error('Executive security overview fetch error:', e);
            setError('Failed to load executive security overview.');
        }
    }, [api]);

    const loadAll = useCallback(async () => {
        setLoading(true);
        await fetchOverview();
        setLoading(false);
    }, [fetchOverview]);

    useEffect(() => { loadAll(); }, [loadAll]);

    if (loading) {
        return <div className="text-center py-20 text-white/40">Loading executive security overview...</div>;
    }
    if (error || !data) {
        return <div className="text-center py-20 text-red-400">{error || 'No data available.'}</div>;
    }

    const { security_score, security_dashboard, vulnerability_dashboard, compliance_dashboard, mitre_matrix } = data;

    return (
        <div className="space-y-6" data-testid="executive-security-dashboard-page">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Executive Security Dashboard</h1>
                    <p className="text-sm text-white/40 mt-1">Composite security posture across threats, compliance, vulnerabilities, and behavioral risk</p>
                </div>
                <button
                    onClick={loadAll}
                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60"
                    data-testid="refresh-executive-dashboard"
                >
                    <RefreshCw className="w-4 h-4" />
                </button>
            </div>

            {/* Composite Security Score */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardContent className="p-6 flex items-center justify-between flex-wrap gap-6">
                    <div className="flex items-center gap-4">
                        <div className="p-4 rounded-2xl bg-white/5">
                            <ShieldCheck className={`w-8 h-8 ${security_score.composite_score >= 75 ? 'text-emerald-400' : security_score.composite_score >= 50 ? 'text-amber-400' : 'text-red-400'}`} />
                        </div>
                        <div>
                            <p className="text-xs text-white/40 uppercase tracking-wider">Composite Security Score</p>
                            <p className="text-4xl font-bold text-white" data-testid="composite-security-score">{security_score.composite_score}<span className="text-lg text-white/30">/100</span></p>
                        </div>
                    </div>
                    <div className="flex items-center gap-8">
                        {Object.entries(security_score.components).map(([key, value]) => (
                            <ScoreGauge key={key} label={key} value={value} />
                        ))}
                    </div>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Attack Timeline */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader><CardTitle className="text-sm text-white/70 flex items-center gap-2"><Activity className="w-4 h-4" /> Attack Timeline (24h)</CardTitle></CardHeader>
                    <CardContent>
                        <ResponsiveContainer width="100%" height={200}>
                            <AreaChart data={security_dashboard.timeline || []}>
                                <XAxis dataKey="hour" tick={{ fontSize: 10, fill: '#ffffff50' }} />
                                <YAxis tick={{ fontSize: 10, fill: '#ffffff50' }} />
                                <Tooltip contentStyle={{ background: '#0D1117', border: '1px solid #ffffff20' }} />
                                <Area type="monotone" dataKey="threats" stroke="#ef4444" fill="#ef444420" name="Threats" />
                                <Area type="monotone" dataKey="events" stroke="#3b82f6" fill="#3b82f610" name="Events" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* MITRE ATT&CK Matrix */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader><CardTitle className="text-sm text-white/70 flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> MITRE ATT&CK Matrix</CardTitle></CardHeader>
                    <CardContent className="space-y-3 max-h-[220px] overflow-y-auto">
                        {(mitre_matrix.tactics || []).filter(t => t.tactic_total > 0).length === 0 && (
                            <p className="text-xs text-white/30">No MITRE-tagged activity in this window.</p>
                        )}
                        {(mitre_matrix.tactics || []).filter(t => t.tactic_total > 0).map(t => (
                            <div key={t.tactic} className="flex items-center justify-between text-xs">
                                <span className="text-white/60">{t.tactic}</span>
                                <div className="flex gap-1 flex-wrap justify-end">
                                    {t.techniques.filter(x => x.count > 0).map(x => (
                                        <Badge key={x.technique_id} className="bg-red-500/10 text-red-400 border-red-500/30 border text-[10px]">
                                            {x.technique_id} ({x.count})
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Top Threats */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader><CardTitle className="text-sm text-white/70 flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> Top Threats</CardTitle></CardHeader>
                    <CardContent className="space-y-2 max-h-[240px] overflow-y-auto">
                        {(security_dashboard.top_threat_types || []).length === 0 && (
                            <p className="text-xs text-white/30">No active threats.</p>
                        )}
                        {(security_dashboard.top_threat_types || []).map(t => (
                            <div key={t.type} className="flex items-center justify-between text-xs p-2 rounded bg-white/[0.02]">
                                <span className="text-white/70">{t.type?.replace(/_/g, ' ')}</span>
                                <Badge className="bg-white/5 text-white/50 border-white/10 border">{t.count}</Badge>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Vulnerability Priorities */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader><CardTitle className="text-sm text-white/70 flex items-center gap-2"><Bug className="w-4 h-4" /> Vulnerability Priorities</CardTitle></CardHeader>
                    <CardContent className="space-y-2 max-h-[240px] overflow-y-auto">
                        {(vulnerability_dashboard.top_priority || []).length === 0 && (
                            <p className="text-xs text-white/30">No synced CVEs yet — trigger a sync from Vulnerability Management.</p>
                        )}
                        {(vulnerability_dashboard.top_priority || []).slice(0, 10).map(v => (
                            <div key={v.cve_id} className="flex items-center justify-between text-xs p-2 rounded bg-white/[0.02]">
                                <div>
                                    <span className="text-white/70 font-medium">{v.cve_id}</span>
                                    <span className="text-white/30 ml-2">{v.matched_keyword}</span>
                                </div>
                                <Badge className={`border text-[10px] ${SEVERITY_COLOR[v.severity] || SEVERITY_COLOR.unknown}`}>
                                    priority {v.priority_score}
                                </Badge>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Compliance Status */}
                <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                    <CardHeader><CardTitle className="text-sm text-white/70 flex items-center gap-2"><ClipboardCheck className="w-4 h-4" /> Compliance Status</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {(compliance_dashboard.frameworks || []).map(f => (
                            <div key={f.framework} className="p-3 rounded bg-white/[0.02] space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-white font-medium">{f.framework}</span>
                                    <span className="text-sm text-white/60">{f.compliance_score != null ? `${f.compliance_score}%` : 'N/A'}</span>
                                </div>
                                <div className="space-y-1">
                                    {f.controls.map(c => (
                                        <div key={c.control_id} className="flex items-center justify-between text-[11px]">
                                            <span className="text-white/40">{c.name}</span>
                                            <Badge className={`border text-[10px] ${STATUS_COLOR[c.status] || STATUS_COLOR.unknown}`}>{c.status}</Badge>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            </div>

            <p className="text-[11px] text-white/20 flex items-center gap-1"><MapPin className="w-3 h-3" /> Attack map omitted — no dedicated geo-IP lookup service exists; geo_location tags on ingested events are best-effort only.</p>
        </div>
    );
}
