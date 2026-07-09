import React, { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Target, RefreshCw, Shield, Server, AlertTriangle, Users,
    Activity, Zap, Globe, Clock, ChevronRight, BarChart3,
    Search, Layers, Database, Network,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';

const SEVERITY_COLORS = {
    critical: { bg: 'bg-red-500/15', text: 'text-red-400', ring: 'ring-red-500/30' },
    high: { bg: 'bg-orange-500/15', text: 'text-orange-400', ring: 'ring-orange-500/30' },
    medium: { bg: 'bg-amber-500/15', text: 'text-amber-400', ring: 'ring-amber-500/30' },
    low: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', ring: 'ring-emerald-500/30' },
};

export default function ImpactAnalysisPage() {
    const { api } = useAuth();
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [form, setForm] = useState({ host: '', service: '', severity: 'critical', type: 'incident', source_ip: '', user: '' });

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setResult(null);
        try {
            const res = await api.post('/impact/analyze', form);
            setResult(res.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api, form]);

    const sev = result ? SEVERITY_COLORS[result.impact_level] || SEVERITY_COLORS.medium : null;

    return (
        <div className="space-y-6" data-testid="impact-page">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="impact-title">
                    <Target className="w-7 h-7 text-cyan-400" /> Impact Analysis
                </h1>
                <p className="text-sm text-white/40 mt-1">Blast radius analysis — map affected services, users, and dependencies</p>
            </div>

            {/* Input Form */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-white/60">Define Incident</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid md:grid-cols-3 gap-3">
                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Host</Label>
                            <Input placeholder="prod-web-01" value={form.host} onChange={e => setForm(f => ({ ...f, host: e.target.value }))} className="bg-white/5 border-white/10 text-sm" data-testid="input-host" />
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Service</Label>
                            <Input placeholder="api-gateway" value={form.service} onChange={e => setForm(f => ({ ...f, service: e.target.value }))} className="bg-white/5 border-white/10 text-sm" data-testid="input-service" />
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Severity</Label>
                            <Select value={form.severity} onValueChange={v => setForm(f => ({ ...f, severity: v }))}>
                                <SelectTrigger className="bg-white/5 border-white/10 text-xs" data-testid="input-severity"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    <SelectItem value="critical">Critical</SelectItem>
                                    <SelectItem value="high">High</SelectItem>
                                    <SelectItem value="warning">Warning</SelectItem>
                                    <SelectItem value="info">Info</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Incident Type</Label>
                            <Select value={form.type} onValueChange={v => setForm(f => ({ ...f, type: v }))}>
                                <SelectTrigger className="bg-white/5 border-white/10 text-xs" data-testid="input-type"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    <SelectItem value="incident">Incident</SelectItem>
                                    <SelectItem value="brute_force">Brute Force</SelectItem>
                                    <SelectItem value="service_down">Service Down</SelectItem>
                                    <SelectItem value="disk_full">Disk Full</SelectItem>
                                    <SelectItem value="high_cpu">High CPU</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Source IP</Label>
                            <Input placeholder="185.220.101.1" value={form.source_ip} onChange={e => setForm(f => ({ ...f, source_ip: e.target.value }))} className="bg-white/5 border-white/10 text-sm" data-testid="input-ip" />
                        </div>
                        <div className="flex items-end">
                            <Button onClick={runAnalysis} disabled={loading} className="w-full bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 border border-cyan-500/30 text-xs" data-testid="analyze-btn">
                                {loading ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Search className="w-3.5 h-3.5 mr-1.5" />}
                                Analyze Blast Radius
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Results */}
            {result && (
                <div className="space-y-4" data-testid="impact-result">
                    {/* Score Banner */}
                    <Card className={`${sev?.bg} border ${sev?.ring} ring-1`}>
                        <CardContent className="p-5 flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className={`w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold ${sev?.text} ${sev?.bg} ring-2 ${sev?.ring}`}>
                                    {result.impact_score}
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-white/90">Impact Score: {result.impact_score}/100</p>
                                    <Badge className={`${sev?.bg} ${sev?.text} border ${sev?.ring} text-xs mt-1`}>{result.impact_level?.toUpperCase()}</Badge>
                                </div>
                            </div>
                            <div className="grid grid-cols-4 gap-6 text-center">
                                <div><p className="text-lg font-bold text-white">{result.affected_service_count}</p><p className="text-[10px] text-white/40">Services</p></div>
                                <div><p className="text-lg font-bold text-white">{result.affected_user_count}</p><p className="text-[10px] text-white/40">Users</p></div>
                                <div><p className="text-lg font-bold text-white">{result.related_violations?.length || 0}</p><p className="text-[10px] text-white/40">Violations</p></div>
                                <div><p className="text-lg font-bold text-white">{result.related_threats?.length || 0}</p><p className="text-[10px] text-white/40">Threats</p></div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Summary */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardContent className="p-4">
                            <p className="text-sm text-white/60 leading-relaxed">{result.summary}</p>
                        </CardContent>
                    </Card>

                    {/* Detail Grid */}
                    <div className="grid lg:grid-cols-2 gap-4">
                        {/* Related Threats */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-red-400 flex items-center gap-2">
                                    <Shield className="w-4 h-4" /> Related Threats ({result.related_threats?.length || 0})
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {(result.related_threats || []).length === 0 ? (
                                    <p className="text-center text-white/30 py-4 text-sm">No correlated threats</p>
                                ) : (
                                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                                        {result.related_threats.map((t, i) => (
                                            <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
                                                <Badge className="bg-red-500/15 text-red-400 border-red-500/30 border text-[9px]">{t.severity}</Badge>
                                                <span className="text-xs text-white/50 w-24 truncate">{t.type}</span>
                                                <span className="text-xs text-white/40 flex-1 truncate">{t.message}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Affected Users */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-purple-400 flex items-center gap-2">
                                    <Users className="w-4 h-4" /> Affected Users ({result.affected_user_count})
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {(result.affected_users || []).length === 0 ? (
                                    <p className="text-center text-white/30 py-4 text-sm">No affected users found</p>
                                ) : (
                                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                                        {result.affected_users.map((u, i) => (
                                            <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
                                                <span className="text-sm text-white/70">{u.user}</span>
                                                <Badge variant="outline" className="text-[10px] text-white/40 border-white/10">{u.event_count} events</Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Affected Services */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-cyan-400 flex items-center gap-2">
                                    <Layers className="w-4 h-4" /> Affected Services ({result.affected_service_count})
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {(result.affected_services || []).length === 0 ? (
                                    <p className="text-center text-white/30 py-4 text-sm">No affected services in topology</p>
                                ) : (
                                    <div className="space-y-1.5">
                                        {result.affected_services.map((s, i) => (
                                            <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
                                                <Server className="w-3.5 h-3.5 text-white/30" />
                                                <span className="text-xs text-white/70 flex-1">{s.name}</span>
                                                <Badge variant="outline" className={`text-[9px] ${s.impact === 'direct' ? 'text-red-400 border-red-500/30' : 'text-amber-400 border-amber-500/30'}`}>{s.impact}</Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Active Violations */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-amber-400 flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4" /> Health Violations ({result.related_violations?.length || 0})
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {(result.related_violations || []).length === 0 ? (
                                    <p className="text-center text-white/30 py-4 text-sm">No active violations</p>
                                ) : (
                                    <div className="space-y-1.5">
                                        {result.related_violations.map((v, i) => (
                                            <div key={i} className="flex items-center gap-2 p-2.5 rounded-lg bg-white/[0.02] border border-white/5">
                                                <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 border text-[9px]">{v.severity}</Badge>
                                                <span className="text-xs text-white/60 flex-1">{v.rule_name}</span>
                                                <span className="text-xs font-mono text-white/30">{v.metric}: {v.value}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
