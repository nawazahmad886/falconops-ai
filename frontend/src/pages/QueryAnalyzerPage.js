import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Database, RefreshCw, Search, AlertTriangle, CheckCircle,
    Zap, BarChart3, Clock, FileText, Shield, Eye, Code,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend,
} from 'recharts';

const QUALITY_STYLES = {
    excellent: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    good: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    needs_improvement: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    poor: 'bg-red-500/15 text-red-400 border-red-500/30',
};
const SEVERITY_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};
const PIE_COLORS = ['#22c55e', '#3b82f6', '#eab308', '#ef4444'];

export default function QueryAnalyzerPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('analyze');
    const [query, setQuery] = useState('');
    const [result, setResult] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [slowQueries, setSlowQueries] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);

    const analyzeQuery = useCallback(async () => {
        if (!query.trim()) return;
        setAnalyzing(true);
        setResult(null);
        try {
            const res = await api.post('/query-analyzer/analyze', { query, duration_ms: 0 });
            setResult(res.data);
        } catch (e) { console.error(e); }
        setAnalyzing(false);
    }, [api, query]);

    const fetchSlowQueries = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/query-analyzer/slow-queries?limit=30');
            setSlowQueries(res.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchStats = useCallback(async () => {
        try {
            const res = await api.get('/query-analyzer/stats');
            setStats(res.data);
        } catch (e) { console.error(e); }
    }, [api]);

    useEffect(() => { fetchSlowQueries(); fetchStats(); }, [fetchSlowQueries, fetchStats]);

    const sampleQueries = [
        'SELECT * FROM users',
        'SELECT id, name FROM orders WHERE status = \'pending\' ORDER BY created_at',
        'DELETE FROM sessions',
        'SELECT * FROM products WHERE name LIKE \'%phone%\' ORDER BY price',
        'UPDATE accounts SET balance = 0',
    ];

    const qualityData = stats?.by_quality?.map(q => ({
        name: q.quality,
        value: q.count,
    })) || [];

    const categoryData = stats?.by_finding_category?.map(c => ({
        name: c.category,
        count: c.count,
    })) || [];

    const tabs = [
        { id: 'analyze', label: 'Analyze', icon: Search },
        { id: 'slow', label: 'Slow Queries', icon: Clock },
        { id: 'stats', label: 'Statistics', icon: BarChart3 },
    ];

    return (
        <div className="space-y-6" data-testid="query-analyzer-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/15">
                            <Database className="w-6 h-6 text-cyan-400" />
                        </div>
                        Query Analyzer
                    </h1>
                    <p className="text-sm text-white/50 mt-1">SQL query optimization & performance analysis</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => {
                    const Icon = t.icon;
                    return (
                        <Button key={t.id} variant="ghost" size="sm"
                            onClick={() => setTab(t.id)}
                            className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`}
                            data-testid={`tab-${t.id}`}>
                            <Icon className="w-3 h-3 mr-1" /> {t.label}
                        </Button>
                    );
                })}
            </div>

            {/* Analyze Tab */}
            {tab === 'analyze' && (
                <div className="space-y-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Code className="w-4 h-4 text-cyan-400" />
                                SQL Query Input
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 space-y-3">
                            <textarea
                                className="w-full h-32 bg-[#161B22] border border-white/10 rounded-md p-3 text-sm text-white/80 font-mono resize-none focus:outline-none focus:border-cyan-500/50"
                                placeholder="Enter your SQL query here..."
                                value={query}
                                onChange={e => setQuery(e.target.value)}
                                data-testid="query-input"
                            />
                            <div className="flex items-center gap-2 flex-wrap">
                                <Button onClick={analyzeQuery} disabled={analyzing || !query.trim()}
                                    className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="analyze-btn">
                                    {analyzing ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <Search className="w-3 h-3 mr-1" />}
                                    Analyze
                                </Button>
                                <span className="text-xs text-white/30 mx-2">Quick samples:</span>
                                {sampleQueries.map((sq, i) => (
                                    <Button key={i} variant="outline" size="sm"
                                        onClick={() => setQuery(sq)}
                                        className="text-[10px] border-white/10 text-white/40 hover:text-white" data-testid={`sample-${i}`}>
                                        {sq.slice(0, 30)}...
                                    </Button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Analysis Result */}
                    {result && (
                        <Card className="bg-[#0D1117] border-white/5" data-testid="analysis-result">
                            <CardHeader className="pb-3 border-b border-white/5">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-base flex items-center gap-2">
                                        <Eye className="w-4 h-4 text-white/60" />
                                        Analysis Results
                                    </CardTitle>
                                    <div className="flex items-center gap-2">
                                        <Badge className={QUALITY_STYLES[result.quality] || QUALITY_STYLES.good} data-testid="quality-badge">
                                            {result.quality}
                                        </Badge>
                                        <span className="text-sm font-bold text-white" data-testid="score-value">Score: {result.score}/100</span>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent className="p-4">
                                {/* Score Bar */}
                                <div className="mb-4">
                                    <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all ${result.score >= 90 ? 'bg-emerald-400' : result.score >= 70 ? 'bg-blue-400' : result.score >= 50 ? 'bg-amber-400' : 'bg-red-400'}`}
                                            style={{ width: `${result.score}%` }}
                                        />
                                    </div>
                                </div>

                                {/* Findings */}
                                {result.findings?.length > 0 ? (
                                    <div className="space-y-2">
                                        <p className="text-xs text-white/50 mb-2">{result.finding_count} finding(s):</p>
                                        {result.findings.map((f, i) => {
                                            const sevStyle = SEVERITY_STYLES[f.severity] || SEVERITY_STYLES.info;
                                            return (
                                                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5" data-testid={`finding-${i}`}>
                                                    <div className={`p-1.5 rounded ${sevStyle.split(' ')[0]}`}>
                                                        <AlertTriangle className={`w-3.5 h-3.5 ${sevStyle.split(' ')[1]}`} />
                                                    </div>
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-sm font-medium text-white/80">{f.title}</span>
                                                            <Badge variant="outline" className={`text-[9px] ${sevStyle}`}>{f.severity}</Badge>
                                                            <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">{f.category}</Badge>
                                                        </div>
                                                        <p className="text-xs text-white/50 mt-1">{f.suggestion}</p>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="text-center py-4">
                                        <CheckCircle className="w-8 h-8 mx-auto text-emerald-400 mb-2" />
                                        <p className="text-sm text-emerald-400">No issues found. Query looks good!</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* Slow Queries Tab */}
            {tab === 'slow' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Clock className="w-4 h-4 text-amber-400" />
                                Analyzed Queries
                                <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{slowQueries.length}</Badge>
                            </CardTitle>
                            <Button variant="outline" size="sm" onClick={fetchSlowQueries} disabled={loading} className="border-white/10 text-xs">
                                <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[600px] overflow-y-auto divide-y divide-white/5" data-testid="slow-query-list">
                            {slowQueries.length === 0 ? (
                                <div className="p-8 text-center text-white/40">
                                    <Clock className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                    <p>No analyzed queries yet. Use the Analyze tab to get started.</p>
                                </div>
                            ) : slowQueries.map((sq, i) => {
                                const qStyle = QUALITY_STYLES[sq.quality] || QUALITY_STYLES.good;
                                return (
                                    <div key={sq.id || i} className="p-3 hover:bg-white/[0.02]" data-testid={`slow-query-${i}`}>
                                        <div className="flex items-center justify-between mb-1">
                                            <div className="flex items-center gap-2">
                                                <Badge className={`text-[9px] ${qStyle}`}>{sq.quality}</Badge>
                                                <span className="text-xs text-white/60">Score: {sq.score}</span>
                                                {sq.duration_ms > 0 && <span className="text-xs text-amber-400">{sq.duration_ms}ms</span>}
                                            </div>
                                            <span className="text-[10px] text-white/25">{sq.analyzed_at ? new Date(sq.analyzed_at).toLocaleString() : ''}</span>
                                        </div>
                                        <p className="text-xs text-white/60 font-mono truncate">{sq.query}</p>
                                        <p className="text-[10px] text-white/30 mt-0.5">{sq.finding_count} finding(s)</p>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Stats Tab */}
            {tab === 'stats' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <CardTitle className="text-base">Quality Distribution</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4">
                            {qualityData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={250}>
                                    <PieChart>
                                        <Pie data={qualityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                                            {qualityData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                        </Pie>
                                        <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff' }} />
                                        <Legend />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="text-center py-12 text-white/40"><p>No stats available</p></div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <CardTitle className="text-base">Finding Categories</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4">
                            {categoryData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={250}>
                                    <BarChart data={categoryData}>
                                        <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                        <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                        <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff' }} />
                                        <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="text-center py-12 text-white/40"><p>No finding data yet</p></div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                        <CardContent className="p-4 flex items-center gap-4">
                            <div className="p-2 rounded-lg bg-cyan-500/15"><Database className="w-5 h-5 text-cyan-400" /></div>
                            <div>
                                <p className="text-sm text-white/80">Total Analyzed Queries (24h)</p>
                                <p className="text-2xl font-bold text-white" data-testid="total-analyzed">{stats?.total_analyzed ?? 0}</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
