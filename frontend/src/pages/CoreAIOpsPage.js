import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Zap, GitMerge, Target, Radio, Brain, TrendingUp,
    Bell, AlertTriangle, Monitor, BookOpen, Network, GraduationCap,
    ChevronRight, Activity, Server, Shield, RefreshCw,
    ArrowUpRight, Layers, Eye
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ICON_MAP = {
    'zap': Zap, 'git-merge': GitMerge, 'target': Target, 'radio': Radio,
    'brain': Brain, 'trending-up': TrendingUp, 'bell': Bell,
    'alert-triangle': AlertTriangle, 'monitor': Monitor, 'book-open': BookOpen,
    'network': Network, 'graduation-cap': GraduationCap,
};

const CATEGORY_CONFIG = {
    detection: { label: 'Detection', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
    correlation: { label: 'Correlation', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    analysis: { label: 'Analysis', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
    intelligence: { label: 'Intelligence', color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
    prediction: { label: 'Prediction', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
    operations: { label: 'Operations', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
    monitoring: { label: 'Monitoring', color: 'text-teal-400', bg: 'bg-teal-500/10', border: 'border-teal-500/20' },
    automation: { label: 'Automation', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
    observability: { label: 'Observability', color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' },
};

const HealthRing = ({ score }) => {
    const radius = 54;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;
    const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';

    return (
        <div className="relative w-36 h-36">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r={radius} fill="none" stroke="#1a1a2e" strokeWidth="8" />
                <circle cx="60" cy="60" r={radius} fill="none" stroke={color} strokeWidth="8"
                    strokeDasharray={circumference} strokeDashoffset={offset}
                    strokeLinecap="round" className="transition-all duration-1000 ease-out" />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold" style={{ color }}>{Math.round(score)}</span>
                <span className="text-[10px] text-white/40 uppercase tracking-widest">Health</span>
            </div>
        </div>
    );
};

const StatPill = ({ label, value, color = 'text-white' }) => (
    <div className="flex flex-col items-center px-4 py-2">
        <span className={`text-xl font-bold ${color}`}>{value}</span>
        <span className="text-[10px] text-white/40 uppercase tracking-wider mt-0.5">{label}</span>
    </div>
);

const CapabilityCard = ({ capability, onClick }) => {
    const Icon = ICON_MAP[capability.icon] || Activity;
    const cat = CATEGORY_CONFIG[capability.category] || CATEGORY_CONFIG.detection;
    const stats = capability.stats || {};
    const statEntries = Object.entries(stats).slice(0, 3);

    return (
        <Card
            data-testid={`capability-card-${capability.id}`}
            onClick={onClick}
            className={`group bg-[#0a0a14] border ${cat.border} hover:border-white/30 cursor-pointer transition-all duration-300 hover:shadow-lg hover:shadow-black/40 hover:-translate-y-0.5`}
        >
            <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                    <div className={`w-10 h-10 rounded-lg ${cat.bg} flex items-center justify-center`}>
                        <Icon className={`w-5 h-5 ${cat.color}`} />
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge className={`text-[9px] px-1.5 py-0 ${cat.bg} ${cat.color} border-0`}>
                            {cat.label}
                        </Badge>
                        <ArrowUpRight className="w-4 h-4 text-white/20 group-hover:text-white/60 transition-colors" />
                    </div>
                </div>

                <h3 className="text-sm font-semibold text-white mb-1 group-hover:text-[#00E0FF] transition-colors">
                    {capability.name}
                </h3>
                <p className="text-xs text-white/40 leading-relaxed mb-3 line-clamp-2">
                    {capability.description}
                </p>

                {statEntries.length > 0 && (
                    <div className="flex items-center gap-3 pt-3 border-t border-white/5">
                        {statEntries.map(([key, val]) => (
                            <div key={key} className="flex items-center gap-1.5">
                                <span className="text-sm font-bold text-white/80">{typeof val === 'number' ? val.toLocaleString() : val}</span>
                                <span className="text-[10px] text-white/30 capitalize">{key.replace(/_/g, ' ')}</span>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

const LayerPipeline = () => {
    const layers = [
        { label: 'Data Ingestion', icon: Layers, color: 'text-cyan-400', bg: 'bg-cyan-500/15' },
        { label: 'Anomaly Detection', icon: Zap, color: 'text-purple-400', bg: 'bg-purple-500/15' },
        { label: 'Event Correlation', icon: GitMerge, color: 'text-blue-400', bg: 'bg-blue-500/15' },
        { label: 'Root Cause', icon: Target, color: 'text-amber-400', bg: 'bg-amber-500/15' },
        { label: 'Impact Analysis', icon: Radio, color: 'text-red-400', bg: 'bg-red-500/15' },
        { label: 'Automation', icon: Zap, color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
    ];

    return (
        <div className="flex items-center justify-between gap-1 py-3 px-2 overflow-x-auto" data-testid="ai-pipeline">
            {layers.map((layer, i) => {
                const Icon = layer.icon;
                return (
                    <React.Fragment key={layer.label}>
                        <div className="flex flex-col items-center gap-1.5 min-w-[90px]">
                            <div className={`w-10 h-10 rounded-full ${layer.bg} flex items-center justify-center`}>
                                <Icon className={`w-5 h-5 ${layer.color}`} />
                            </div>
                            <span className="text-[10px] text-white/50 text-center leading-tight">{layer.label}</span>
                        </div>
                        {i < layers.length - 1 && (
                            <ChevronRight className="w-4 h-4 text-white/15 shrink-0" />
                        )}
                    </React.Fragment>
                );
            })}
        </div>
    );
};

export const CoreAIOpsPage = () => {
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');

    const fetchData = async () => {
        try {
            const res = await fetch(`${API_URL}/api/core-aiops/overview`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('falconToken')}` }
            });
            if (!res.ok) throw new Error('Failed to fetch');
            setData(await res.json());
        } catch (e) {
            toast.error('Failed to load AIOps data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchData(); }, []);

    const categories = ['all', ...new Set((data?.capabilities || []).map(c => c.category))];
    const filtered = filter === 'all'
        ? (data?.capabilities || [])
        : (data?.capabilities || []).filter(c => c.category === filter);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]" data-testid="core-aiops-loading">
                <div className="flex flex-col items-center gap-4">
                    <Brain className="w-12 h-12 text-[#00E0FF] animate-pulse" />
                    <span className="text-white/40 text-sm">Loading AI Operations...</span>
                </div>
            </div>
        );
    }

    const s = data?.summary || {};

    return (
        <div className="space-y-6" data-testid="core-aiops-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Shield className="w-7 h-7 text-[#00E0FF]" />
                        Core Intelligent AIOps
                    </h1>
                    <p className="text-white/50 mt-1 text-sm">
                        Unified AI operations hub &mdash; drill into any capability
                    </p>
                </div>
                <Button variant="outline" size="sm" className="border-white/20 hover:bg-white/5" onClick={fetchData} data-testid="refresh-btn">
                    <RefreshCw className="w-4 h-4 mr-2" /> Refresh
                </Button>
            </div>

            {/* Top Strip: Health + Stats + Pipeline */}
            <Card className="bg-[#0a0a14] border-white/10">
                <CardContent className="p-5">
                    <div className="flex flex-col lg:flex-row items-center gap-6">
                        {/* Health Ring */}
                        <HealthRing score={data?.system_health || 0} />

                        {/* Key Metrics */}
                        <div className="flex flex-wrap items-center gap-2 divide-x divide-white/10">
                            <StatPill label="Active Alerts" value={s.active_alerts || 0} color="text-amber-400" />
                            <StatPill label="Critical" value={s.critical_alerts || 0} color="text-red-400" />
                            <StatPill label="Incidents" value={s.active_incidents || 0} color="text-orange-400" />
                            <StatPill label="Servers" value={s.total_servers || 0} color="text-cyan-400" />
                            <StatPill label="Monitors" value={`${s.monitors_up || 0}/${s.monitors_total || 0}`} color="text-emerald-400" />
                            <StatPill label="AI Analyses" value={s.event_analyses || 0} color="text-purple-400" />
                            <StatPill label="KB Patterns" value={s.knowledge_patterns || 0} color="text-blue-400" />
                        </div>
                    </div>

                    {/* 6-Layer Pipeline */}
                    <div className="mt-4 pt-4 border-t border-white/5">
                        <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2">AI Engine Pipeline</p>
                        <LayerPipeline />
                    </div>
                </CardContent>
            </Card>

            {/* Category Filter */}
            <div className="flex items-center gap-2 flex-wrap" data-testid="category-filter">
                {categories.map(cat => {
                    const cfg = CATEGORY_CONFIG[cat] || {};
                    const isActive = filter === cat;
                    return (
                        <button
                            key={cat}
                            data-testid={`filter-${cat}`}
                            onClick={() => setFilter(cat)}
                            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                                isActive
                                    ? 'bg-[#00E0FF]/15 border-[#00E0FF]/40 text-[#00E0FF]'
                                    : 'bg-white/5 border-white/10 text-white/50 hover:text-white/80 hover:border-white/20'
                            }`}
                        >
                            {cat === 'all' ? 'All Capabilities' : (cfg.label || cat)}
                        </button>
                    );
                })}
            </div>

            {/* Capability Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4" data-testid="capabilities-grid">
                {filtered.map(cap => (
                    <CapabilityCard
                        key={cap.id}
                        capability={cap}
                        onClick={() => navigate(cap.path)}
                    />
                ))}
            </div>

            {/* Quick Actions */}
            <Card className="bg-[#0a0a14] border-white/10">
                <CardContent className="p-5">
                    <p className="text-[10px] text-white/30 uppercase tracking-widest mb-3">Quick Actions</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <QuickAction icon={Eye} label="NOC Dashboard" path="/noc-dashboard" color="text-teal-400" navigate={navigate} />
                        <QuickAction icon={Brain} label="Run Anomaly Scan" path="/aiops-brain" color="text-purple-400" navigate={navigate} />
                        <QuickAction icon={Bell} label="View Active Alerts" path="/alert-engine" color="text-amber-400" navigate={navigate} />
                        <QuickAction icon={BookOpen} label="Runbook Automation" path="/runbooks" color="text-orange-400" navigate={navigate} />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

const QuickAction = ({ icon: Icon, label, path, color, navigate }) => (
    <button
        data-testid={`quick-action-${label.toLowerCase().replace(/\s+/g, '-')}`}
        onClick={() => navigate(path)}
        className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5 hover:border-white/20 hover:bg-white/10 transition-all group text-left"
    >
        <Icon className={`w-5 h-5 ${color} shrink-0`} />
        <span className="text-sm text-white/70 group-hover:text-white transition-colors">{label}</span>
        <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-white/50 ml-auto" />
    </button>
);

export default CoreAIOpsPage;
