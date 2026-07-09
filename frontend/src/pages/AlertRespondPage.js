import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Shield, ChevronRight, Activity, Bell, Brain, Mail, Zap, Webhook,
    FileText, Settings, AlertTriangle, CheckCircle, XCircle, Clock,
    Plus, Eye, Server, Database, Cpu, Globe, RefreshCw,
    ArrowUpRight, ArrowDownRight, Filter, Pencil, Trash2, Copy,
    PlayCircle, BarChart3, TrendingUp, Lock,
} from 'lucide-react';
import { HealthRulesPage } from './HealthRulesPage';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const getAuth = () => ({ Authorization: `Bearer ${localStorage.getItem('falconToken')}` });

// ─── Sidebar Navigation ───
const ALERT_SECTIONS = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'policies', label: 'Policies', icon: Shield },
    { id: 'health-rules', label: 'Health Rules', icon: Activity },
    { id: 'anomaly', label: 'Anomaly Detection', icon: Brain },
    { id: 'actions', label: 'Actions', icon: Zap },
    { id: 'violations', label: 'Violations', icon: AlertTriangle },
];

// ─── Flow Diagram (SVG) ───
const AlertFlowDiagram = () => (
    <div className="w-full" data-testid="alert-flow-diagram">
        <p className="text-xs text-slate-500 font-mono uppercase tracking-wider mb-4">Alert & Respond Overview</p>
        <svg viewBox="0 0 460 420" className="w-full max-w-[460px] mx-auto">
            {/* Performance Metrics */}
            <rect x="155" y="5" width="150" height="40" rx="6" fill="#121826" stroke="#2D3748" strokeWidth="1.5"/>
            <text x="230" y="30" textAnchor="middle" fill="#94A3B8" fontSize="11" fontFamily="monospace">Performance Metrics</text>

            {/* Arrow down */}
            <line x1="230" y1="45" x2="230" y2="75" stroke="#2D3748" strokeWidth="1.5"/>
            <polygon points="225,72 235,72 230,80" fill="#2D3748"/>

            {/* Alerting box */}
            <rect x="130" y="80" width="200" height="25" rx="4" fill="transparent" stroke="#334155" strokeWidth="1" strokeDasharray="4"/>
            <text x="230" y="97" textAnchor="middle" fill="#64748B" fontSize="10" fontFamily="monospace">Alerting</text>

            {/* Branch lines */}
            <line x1="170" y1="105" x2="170" y2="130" stroke="#2D3748" strokeWidth="1.5"/>
            <line x1="290" y1="105" x2="290" y2="130" stroke="#2D3748" strokeWidth="1.5"/>

            {/* Manual branch */}
            <rect x="95" y="130" width="150" height="35" rx="6" fill="#1a1a2e" stroke="#00E0FF" strokeWidth="1.5"/>
            <text x="120" y="147" fill="#64748B" fontSize="9" fontFamily="monospace">Manual</text>
            <rect x="105" y="140" width="130" height="18" rx="4" fill="#00E0FF" fillOpacity="0.1"/>
            <text x="170" y="153" textAnchor="middle" fill="#00E0FF" fontSize="10" fontWeight="bold" fontFamily="monospace">Health Rules</text>

            {/* AIOps branch */}
            <rect x="255" y="130" width="150" height="35" rx="6" fill="#1a1a2e" stroke="#8B5CF6" strokeWidth="1.5"/>
            <rect x="380" y="128" width="32" height="14" rx="3" fill="#8B5CF6"/>
            <text x="396" y="138" textAnchor="middle" fill="white" fontSize="7" fontWeight="bold">NEW</text>
            <text x="280" y="147" fill="#64748B" fontSize="9" fontFamily="monospace">AIOps</text>
            <rect x="265" y="140" width="130" height="18" rx="4" fill="#8B5CF6" fillOpacity="0.1"/>
            <text x="330" y="153" textAnchor="middle" fill="#8B5CF6" fontSize="10" fontWeight="bold" fontFamily="monospace">Anomaly Detection</text>

            {/* Arrows down from branches */}
            <line x1="170" y1="165" x2="170" y2="195" stroke="#00E0FF" strokeWidth="1.5" strokeOpacity="0.5"/>
            <polygon points="165,192 175,192 170,200" fill="#00E0FF" fillOpacity="0.5"/>
            <line x1="330" y1="165" x2="330" y2="195" stroke="#8B5CF6" strokeWidth="1.5" strokeOpacity="0.5"/>
            <polygon points="325,192 335,192 330,200" fill="#8B5CF6" fillOpacity="0.5"/>

            {/* Violation Events */}
            <rect x="95" y="200" width="150" height="35" rx="6" fill="#121826" stroke="#F59E0B" strokeWidth="1.2"/>
            <text x="170" y="215" textAnchor="middle" fill="#F59E0B" fontSize="9" fontFamily="monospace">Health Rule</text>
            <text x="170" y="227" textAnchor="middle" fill="#F59E0B" fontSize="9" fontFamily="monospace">Violation Events</text>

            {/* Anomaly Events */}
            <rect x="255" y="200" width="150" height="35" rx="6" fill="#121826" stroke="#8B5CF6" strokeWidth="1.2"/>
            <text x="330" y="215" textAnchor="middle" fill="#8B5CF6" fontSize="9" fontFamily="monospace">Anomaly Events</text>
            <text x="330" y="227" textAnchor="middle" fill="#A78BFA" fontSize="8" fontFamily="monospace">Suspected Root Causes</text>

            {/* Merge arrows to Policies */}
            <line x1="170" y1="235" x2="170" y2="260" stroke="#2D3748" strokeWidth="1.5"/>
            <line x1="330" y1="235" x2="330" y2="260" stroke="#2D3748" strokeWidth="1.5"/>
            <line x1="170" y1="260" x2="330" y2="260" stroke="#2D3748" strokeWidth="1.5"/>
            <line x1="250" y1="260" x2="250" y2="280" stroke="#2D3748" strokeWidth="1.5"/>
            <polygon points="245,277 255,277 250,285" fill="#2D3748"/>

            {/* Policies */}
            <rect x="185" y="285" width="130" height="40" rx="6" fill="#10B981" fillOpacity="0.15" stroke="#10B981" strokeWidth="1.5"/>
            <text x="250" y="310" textAnchor="middle" fill="#10B981" fontSize="12" fontWeight="bold" fontFamily="monospace">Policies</text>

            {/* Arrow to Actions */}
            <line x1="250" y1="325" x2="250" y2="350" stroke="#2D3748" strokeWidth="1.5"/>
            <polygon points="245,347 255,347 250,355" fill="#2D3748"/>
            <text x="250" y="370" textAnchor="middle" fill="#64748B" fontSize="10" fontFamily="monospace">Actions</text>

            {/* Action boxes */}
            <rect x="30" y="382" width="80" height="28" rx="4" fill="#121826" stroke="#334155" strokeWidth="1"/>
            <text x="70" y="400" textAnchor="middle" fill="#94A3B8" fontSize="8" fontFamily="monospace">Notifications</text>
            <rect x="120" y="382" width="80" height="28" rx="4" fill="#121826" stroke="#334155" strokeWidth="1"/>
            <text x="160" y="400" textAnchor="middle" fill="#94A3B8" fontSize="8" fontFamily="monospace">Diagnostic</text>
            <rect x="210" y="382" width="80" height="28" rx="4" fill="#121826" stroke="#334155" strokeWidth="1"/>
            <text x="250" y="400" textAnchor="middle" fill="#94A3B8" fontSize="8" fontFamily="monospace">Remediation</text>
            <rect x="300" y="382" width="80" height="28" rx="4" fill="#121826" stroke="#334155" strokeWidth="1"/>
            <text x="340" y="400" textAnchor="middle" fill="#94A3B8" fontSize="8" fontFamily="monospace">Webhook</text>
            <rect x="390" y="382" width="65" height="28" rx="4" fill="#121826" stroke="#334155" strokeWidth="1"/>
            <text x="422" y="400" textAnchor="middle" fill="#94A3B8" fontSize="8" fontFamily="monospace">Custom</text>
        </svg>
    </div>
);

// ─── Section Card for Overview ───
const SectionLink = ({ icon: Icon, title, description, badge, onClick, color = '#00E0FF' }) => (
    <button onClick={onClick} className="text-left w-full group" data-testid={`section-${title.toLowerCase().replace(/\s/g, '-')}`}>
        <div className="flex items-start gap-3 py-4 border-b border-[#2D3748]/30 hover:bg-white/[0.02] transition-colors px-2 rounded-lg">
            <div className="p-2 rounded-lg mt-0.5" style={{ backgroundColor: `${color}10` }}>
                <Icon className="w-4 h-4" style={{ color }} />
            </div>
            <div className="flex-1">
                <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-white group-hover:text-cyan-400 transition-colors">{title}</h3>
                    <ChevronRight className="w-3.5 h-3.5 text-white/20 group-hover:text-cyan-400 transition-colors" />
                    {badge && <Badge className="text-[8px] bg-purple-500/20 text-purple-400 border-0">{badge}</Badge>}
                </div>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{description}</p>
            </div>
        </div>
    </button>
);

// ─── Overview Section ───
const OverviewSection = ({ onNavigate, stats }) => (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6" data-testid="alert-overview">
        {/* Left: Section links */}
        <div className="lg:col-span-3 space-y-1">
            <SectionLink icon={Shield} title="Policies" color="#10B981"
                description="Configure Policies to send alerts, perform diagnostics, or execute scripts when Health Rules are violated, Anomalies are detected, or events such as server crashes occur."
                onClick={() => onNavigate('policies')} />
            <SectionLink icon={Activity} title="Health Rules" color="#00E0FF"
                description="Health Rules compare performance metrics against their baselines or other thresholds. When performance fails to satisfy Health Rules, violation events are created. Create Health Rules for problems whose logic is clear-cut, including violations of SLAs."
                onClick={() => onNavigate('health-rules')} />
            <SectionLink icon={Brain} title="Anomaly Detection" badge="AI" color="#8B5CF6"
                description="Anomaly Detection uses AI to automatically identify problems with application and infrastructure performance. When metrics break from patterns predicted by Machine Learning, anomaly events are created. Anomaly Detection identifies a wider range of problems than Health Rules alone."
                onClick={() => onNavigate('anomaly')} />
            <SectionLink icon={Zap} title="Actions" color="#F59E0B"
                description="Actions are the responses FalconOps takes when Policies are violated. They include sending notifications by email, triggering webhooks, executing runbooks, and creating diagnostic snapshots."
                onClick={() => onNavigate('actions')} />
            <SectionLink icon={AlertTriangle} title="Violation Events" color="#EF4444"
                description="View all health rule violation events, their timeline, severity transitions, and the actions that were executed in response."
                onClick={() => onNavigate('violations')} />
        </div>

        {/* Right: Flow Diagram */}
        <div className="lg:col-span-2">
            <AlertFlowDiagram />

            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-2 mt-4">
                <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-slate-500 font-mono">ACTIVE RULES</p>
                    <p className="text-xl font-bold text-white font-mono">{stats.activeRules || 0}</p>
                </div>
                <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-slate-500 font-mono">VIOLATIONS (24H)</p>
                    <p className="text-xl font-bold text-amber-400 font-mono">{stats.violations24h || 0}</p>
                </div>
                <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-slate-500 font-mono">POLICIES</p>
                    <p className="text-xl font-bold text-emerald-400 font-mono">{stats.policies || 0}</p>
                </div>
                <div className="bg-[#121826] border border-[#2D3748]/50 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-slate-500 font-mono">ACTIONS</p>
                    <p className="text-xl font-bold text-cyan-400 font-mono">{stats.actions || 0}</p>
                </div>
            </div>
        </div>
    </div>
);

// ─── Policies Section ───
const PoliciesSection = () => {
    const [policies, setPolicies] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                const res = await fetch(`${API_URL}/api/alert-respond/policies`, { headers: getAuth() });
                if (res.ok) setPolicies((await res.json()).policies || []);
            } catch(e) {}
            setLoading(false);
        })();
    }, []);

    return (
        <div className="space-y-4" data-testid="policies-section">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-bold text-white">Policies</h2>
                    <p className="text-xs text-slate-500">Configure how the system responds when health rules are violated or anomalies are detected</p>
                </div>
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 h-8 text-xs" data-testid="create-policy-btn">
                    <Plus className="w-3 h-3 mr-1" /> New Policy
                </Button>
            </div>
            {policies.length === 0 ? (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardContent className="text-center py-12">
                        <Shield className="w-10 h-10 text-white/10 mx-auto mb-3" />
                        <p className="text-sm text-slate-500">No policies configured</p>
                        <p className="text-xs text-slate-600 mt-1">Policies link health rule violations to actions like notifications and webhooks</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {policies.map(p => (
                        <Card key={p.id} className="bg-[#121826] border-[#2D3748]/50">
                            <CardContent className="p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Shield className="w-4 h-4 text-emerald-400" />
                                    <div>
                                        <p className="text-sm font-medium text-white">{p.name}</p>
                                        <p className="text-[10px] text-slate-500">{p.description}</p>
                                    </div>
                                </div>
                                <Badge className={`text-[9px] border-0 ${p.enabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/5 text-slate-500'}`}>
                                    {p.enabled ? 'Active' : 'Disabled'}
                                </Badge>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
};

// ─── Anomaly Detection Section ───
const AnomalySection = () => {
    const [anomalies, setAnomalies] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                const res = await fetch(`${API_URL}/api/anomaly-detection/scan?hours=24`, { headers: getAuth() });
                if (res.ok) {
                    const data = await res.json();
                    setAnomalies(data.anomalies || []);
                }
            } catch(e) {}
            setLoading(false);
        })();
    }, []);

    return (
        <div className="space-y-4" data-testid="anomaly-section">
            <div>
                <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-white">Anomaly Detection</h2>
                    <Badge className="text-[8px] bg-purple-500/20 text-purple-400 border-0">AI-POWERED</Badge>
                </div>
                <p className="text-xs text-slate-500">AI-driven detection using Z-score, EWMA, Isolation Forest, Dynamic Thresholds, and Seasonal Decomposition</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {['Z-Score', 'EWMA', 'Isolation Forest', 'Dynamic Threshold', 'Seasonal'].map((algo, i) => (
                    <Card key={algo} className="bg-[#121826] border-[#2D3748]/50">
                        <CardContent className="p-3 text-center">
                            <Brain className="w-5 h-5 text-purple-400 mx-auto mb-1" />
                            <p className="text-[10px] text-white font-mono">{algo}</p>
                            <Badge className="text-[8px] bg-emerald-500/10 text-emerald-400 border-0 mt-1">Active</Badge>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {anomalies.length > 0 ? (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-white">Recent Anomalies (24h)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {anomalies.slice(0, 10).map((a, i) => (
                                <div key={i} className="flex items-center justify-between p-2 bg-white/[0.02] rounded-lg border border-[#2D3748]/30">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-2 h-2 rounded-full ${a.severity === 'critical' ? 'bg-red-400' : 'bg-amber-400'}`} />
                                        <span className="text-xs text-white font-mono">{a.metric || a.monitor_name}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge className="text-[9px] bg-purple-500/10 text-purple-400 border-0">{a.algorithm || 'ML'}</Badge>
                                        <span className="text-[10px] text-slate-500">{a.score ? `Score: ${a.score.toFixed(2)}` : ''}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardContent className="text-center py-8">
                        <p className="text-sm text-slate-500">No anomalies detected in the last 24 hours</p>
                        <p className="text-xs text-slate-600 mt-1">The AI engine continuously monitors all metrics for unusual patterns</p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

// ─── Actions Section ───
const ActionsSection = () => {
    const ACTION_TYPES = [
        { id: 'notification', label: 'Notifications', icon: Bell, desc: 'Send alerts via email, SMS, or push notifications', color: '#00E0FF' },
        { id: 'diagnostic', label: 'Diagnostic', icon: Eye, desc: 'Capture snapshots, thread dumps, and diagnostic data', color: '#10B981' },
        { id: 'remediation', label: 'Remediation', icon: PlayCircle, desc: 'Execute automated runbooks to resolve issues', color: '#F59E0B' },
        { id: 'webhook', label: 'HTTP/Webhook', icon: Webhook, desc: 'Trigger HTTP requests to external services', color: '#8B5CF6' },
        { id: 'custom', label: 'Custom Scripts', icon: FileText, desc: 'Run custom scripts for specialized responses', color: '#EC4899' },
        { id: 'escalation', label: 'Escalation', icon: ArrowUpRight, desc: 'Escalate to on-call teams via PagerDuty, Slack', color: '#EF4444' },
    ];

    return (
        <div className="space-y-4" data-testid="actions-section">
            <div>
                <h2 className="text-lg font-bold text-white">Actions</h2>
                <p className="text-xs text-slate-500">Configure response actions triggered when policies detect violations</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {ACTION_TYPES.map(a => (
                    <Card key={a.id} className="bg-[#121826] border-[#2D3748]/50 hover:border-white/10 transition-colors cursor-pointer" data-testid={`action-${a.id}`}>
                        <CardContent className="p-4">
                            <div className="flex items-start gap-3">
                                <div className="p-2 rounded-lg" style={{ backgroundColor: `${a.color}10` }}>
                                    <a.icon className="w-5 h-5" style={{ color: a.color }} />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">{a.label}</h3>
                                    <p className="text-xs text-slate-500 mt-1">{a.desc}</p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
};

// ─── Violations Section ───
const ViolationsSection = () => {
    const [violations, setViolations] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        (async () => {
            try {
                const res = await fetch(`${API_URL}/api/alert-respond/violations?limit=50`, { headers: getAuth() });
                if (res.ok) setViolations((await res.json()).violations || []);
            } catch(e) {}
            setLoading(false);
        })();
    }, []);

    return (
        <div className="space-y-4" data-testid="violations-section">
            <div>
                <h2 className="text-lg font-bold text-white">Health Rule Violation Events</h2>
                <p className="text-xs text-slate-500">Timeline of all violation events with severity transitions and executed actions</p>
            </div>

            {violations.length === 0 ? (
                <Card className="bg-[#121826] border-[#2D3748]/50">
                    <CardContent className="text-center py-12">
                        <CheckCircle className="w-10 h-10 text-emerald-500/20 mx-auto mb-3" />
                        <p className="text-sm text-slate-500">No active violations</p>
                        <p className="text-xs text-slate-600 mt-1">All health rules are within normal thresholds</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {violations.map((v, i) => (
                        <Card key={v.id || i} className="bg-[#121826] border-[#2D3748]/50">
                            <CardContent className="p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex items-start gap-3">
                                        <div className={`p-1.5 rounded-lg mt-0.5 ${v.severity === 'critical' ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
                                            {v.severity === 'critical' ? <XCircle className="w-4 h-4 text-red-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white">{v.rule_name || v.name}</p>
                                            <p className="text-xs text-slate-500 mt-0.5">{v.description || `${v.metric} ${v.operator} ${v.threshold}`}</p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <Badge className={`text-[9px] border-0 ${v.state === 'resolved' ? 'bg-emerald-500/10 text-emerald-400' : v.severity === 'critical' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>
                                            {v.state || v.severity}
                                        </Badge>
                                        <p className="text-[10px] text-slate-600 mt-1">{v.timestamp ? new Date(v.timestamp).toLocaleString() : ''}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
};


// ═══════════════════════════════════════════════════
//  MAIN ALERT & RESPOND PAGE
// ═══════════════════════════════════════════════════

export const AlertRespondPage = () => {
    const [activeSection, setActiveSection] = useState('overview');
    const [stats, setStats] = useState({ activeRules: 0, violations24h: 0, policies: 0, actions: 6 });

    useEffect(() => {
        (async () => {
            try {
                const res = await fetch(`${API_URL}/api/health-rules/stats`, { headers: getAuth() });
                if (res.ok) {
                    const data = await res.json();
                    setStats(prev => ({
                        ...prev,
                        activeRules: data.active_rules || 0,
                        violations24h: data.violations_24h || 0,
                    }));
                }
            } catch(e) {}
            // Fetch policies count
            try {
                const res = await fetch(`${API_URL}/api/alert-respond/policies`, { headers: getAuth() });
                if (res.ok) {
                    const data = await res.json();
                    setStats(prev => ({ ...prev, policies: (data.policies || []).length }));
                }
            } catch(e) {}
        })();
    }, []);

    const renderContent = () => {
        switch (activeSection) {
            case 'overview': return <OverviewSection onNavigate={setActiveSection} stats={stats} />;
            case 'policies': return <PoliciesSection />;
            case 'health-rules': return <HealthRulesPage />;
            case 'anomaly': return <AnomalySection />;
            case 'actions': return <ActionsSection />;
            case 'violations': return <ViolationsSection />;
            default: return <OverviewSection onNavigate={setActiveSection} stats={stats} />;
        }
    };

    return (
        <div className="flex gap-0 min-h-[calc(100vh-120px)]" data-testid="alert-respond-page">
            {/* Left Sidebar Navigation */}
            <div className="w-48 flex-shrink-0 border-r border-[#2D3748]/30 pr-2" data-testid="alert-sidebar">
                <div className="sticky top-0 space-y-0.5 pt-1">
                    {ALERT_SECTIONS.map(section => {
                        const Icon = section.icon;
                        const isActive = activeSection === section.id;
                        return (
                            <button key={section.id} onClick={() => setActiveSection(section.id)}
                                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all ${
                                    isActive ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-500 hover:text-white hover:bg-white/[0.03]'
                                }`}
                                data-testid={`nav-${section.id}`}>
                                <Icon className="w-4 h-4 flex-shrink-0" />
                                <span className="text-xs font-medium">{section.label}</span>
                            </button>
                        );
                    })}

                    {/* Separator + secondary links */}
                    <div className="border-t border-[#2D3748]/30 mt-3 pt-3 space-y-0.5">
                        {[
                            { label: 'Alerting Templates', icon: Copy },
                            { label: 'Email Templates', icon: Mail },
                            { label: 'Notification Config', icon: Settings },
                        ].map(item => (
                            <button key={item.label}
                                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-slate-600 hover:text-slate-400 hover:bg-white/[0.02] transition-all">
                                <item.icon className="w-3.5 h-3.5 flex-shrink-0" />
                                <span className="text-[11px]">{item.label}</span>
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 pl-6 min-w-0">
                {/* Breadcrumb */}
                <div className="flex items-center gap-2 mb-4">
                    <h1 className="text-xl font-bold text-white tracking-tight">Alert & Respond</h1>
                    {activeSection !== 'overview' && (
                        <>
                            <ChevronRight className="w-4 h-4 text-slate-600" />
                            <span className="text-sm text-cyan-400 font-medium">
                                {ALERT_SECTIONS.find(s => s.id === activeSection)?.label}
                            </span>
                        </>
                    )}
                </div>

                {renderContent()}
            </div>
        </div>
    );
};

export default AlertRespondPage;
