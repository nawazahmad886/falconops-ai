import React, { useState, useEffect } from 'react';

import { Button } from '../components/ui/button';
import { 
    Brain, 
    Workflow,
    AppWindow,
    Database,
    Network,
    GitMerge,
    MonitorCheck,
    Route,
    Zap,
    Shield,
    Bot,
    Cpu,
    Activity,
    TrendingUp,
    AlertTriangle,
    CheckCircle,
    Clock,
    Play,
    Settings,
    ArrowRight,
    Sparkles,
    MessageSquareText
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Core Technology Cards - Similar to Dynatrace
const coreTechnologies = [
    {
        id: 'falcon-intelligence',
        name: 'Falcon Intelligence',
        icon: Brain,
        color: 'from-amber-500 to-orange-600',
        description: 'Precise answers, intelligent automation, and AI recommendations powered by advanced machine learning.',
        features: ['Root Cause Analysis', 'Predictive Analytics', 'Anomaly Detection', 'Smart Recommendations'],
        stats: { label: 'AI Insights', value: '24/7' }
    },
    {
        id: 'automation-engine',
        name: 'AutomationEngine',
        icon: Workflow,
        color: 'from-cyan-500 to-blue-600',
        description: 'Extensible and flexible answer-driven automation with runbook orchestration.',
        features: ['Runbook Execution', 'Auto-Remediation', 'Workflow Triggers', 'Approval Chains'],
        stats: { label: 'Automations', value: '50+' }
    },
    {
        id: 'app-engine',
        name: 'AppEngine',
        icon: AppWindow,
        color: 'from-purple-500 to-indigo-600',
        description: 'Easily create custom, compliant, data-driven dashboards and applications.',
        features: ['Custom Dashboards', 'Health Rules', 'Alert Policies', 'Data Visualization'],
        stats: { label: 'Templates', value: '20+' }
    },
    {
        id: 'grail',
        name: 'Grail',
        icon: Database,
        color: 'from-emerald-500 to-teal-600',
        description: 'Store, unify, and contextually analyze all observability, security, and business data.',
        features: ['Unified Data Lake', 'Context Enrichment', 'Query Engine', 'Data Retention'],
        stats: { label: 'Data Sources', value: '∞' }
    },
    {
        id: 'smartscape',
        name: 'Smartscape',
        icon: Network,
        color: 'from-pink-500 to-rose-600',
        description: 'Automatic, real-time topology mapping with full infrastructure context.',
        features: ['Service Mapping', 'Dependency Tracking', 'Impact Analysis', 'Auto-Discovery'],
        stats: { label: 'Entities', value: 'Real-time' }
    },
    {
        id: 'open-pipeline',
        name: 'OpenPipeline',
        icon: GitMerge,
        color: 'from-violet-500 to-purple-600',
        description: 'Ingest, process, enrich, contextualize, and persist data from any source at scale.',
        features: ['Multi-Source Ingestion', 'Data Transformation', 'Stream Processing', 'Webhook APIs'],
        stats: { label: 'Events/sec', value: '10K+' }
    },
    {
        id: 'falcon-agent',
        name: 'FalconAgent',
        icon: MonitorCheck,
        color: 'from-blue-500 to-cyan-600',
        description: 'Continuous, automatic discovery & observability across your full stack.',
        features: ['Auto-Discovery', 'Metric Collection', 'Log Shipping', 'Process Monitoring'],
        stats: { label: 'Coverage', value: '100%' }
    },
    {
        id: 'purepath',
        name: 'PurePath',
        icon: Route,
        color: 'from-orange-500 to-red-600',
        description: 'Distributed tracing and code-level analysis technology for deep visibility.',
        features: ['Distributed Tracing', 'Code Profiling', 'Transaction Flow', 'Latency Analysis'],
        stats: { label: 'Traces', value: 'Full Stack' }
    }
];

// Quick Action Cards
const quickActions = [
    { id: 'create-dashboard', name: 'Create Dashboard', icon: AppWindow, description: 'Build custom monitoring views' },
    { id: 'health-rule', name: 'Configure Health Rule', icon: Activity, description: 'Set alerting thresholds' },
    { id: 'runbook', name: 'New Runbook', icon: Workflow, description: 'Automate incident response' },
    { id: 'ai-analysis', name: 'AI Analysis', icon: Brain, description: 'Analyze events with AI' }
];

const TechnologyCard = ({ tech, onClick }) => {
    const Icon = tech.icon;
    return (
        <div 
            onClick={() => onClick(tech)}
            className="group relative bg-[#0D1117] border border-white/10 rounded-lg p-6 cursor-pointer hover:border-white/20 transition-all duration-300 hover:shadow-lg hover:shadow-black/20"
        >
            {/* Gradient accent line */}
            <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${tech.color} rounded-t-lg opacity-60 group-hover:opacity-100 transition-opacity`} />
            
            <div className="flex items-start gap-4">
                <div className={`p-3 rounded-lg bg-gradient-to-br ${tech.color} bg-opacity-20`}>
                    <Icon className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1">
                    <h3 className="text-lg font-semibold text-white mb-1 group-hover:text-[#F5B841] transition-colors">
                        {tech.name}
                    </h3>
                    <p className="text-sm text-white/60 mb-3 line-clamp-2">
                        {tech.description}
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {tech.features.slice(0, 2).map((feature, idx) => (
                            <span key={idx} className="text-xs px-2 py-1 bg-white/5 rounded text-white/50">
                                {feature}
                            </span>
                        ))}
                        {tech.features.length > 2 && (
                            <span className="text-xs px-2 py-1 bg-white/5 rounded text-white/50">
                                +{tech.features.length - 2} more
                            </span>
                        )}
                    </div>
                </div>
            </div>
            
            {/* Stats badge */}
            <div className="absolute top-4 right-4">
                <div className="text-right">
                    <div className="text-xs text-white/40">{tech.stats.label}</div>
                    <div className={`text-sm font-mono font-bold bg-gradient-to-r ${tech.color} bg-clip-text text-transparent`}>
                        {tech.stats.value}
                    </div>
                </div>
            </div>
        </div>
    );
};

const QuickActionCard = ({ action, onClick }) => {
    const Icon = action.icon;
    return (
        <button 
            onClick={() => onClick(action)}
            className="flex items-center gap-3 p-4 bg-[#0D1117] border border-white/10 rounded-lg hover:border-[#F5B841]/30 hover:bg-[#F5B841]/5 transition-all duration-200 text-left w-full"
        >
            <div className="p-2 rounded-lg bg-[#F5B841]/10">
                <Icon className="w-5 h-5 text-[#F5B841]" />
            </div>
            <div>
                <div className="text-sm font-medium text-white">{action.name}</div>
                <div className="text-xs text-white/50">{action.description}</div>
            </div>
            <ArrowRight className="w-4 h-4 text-white/30 ml-auto" />
        </button>
    );
};

const TechnologyDetailModal = ({ tech, onClose }) => {
    if (!tech) return null;
    const Icon = tech.icon;
    
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={onClose}>
            <div 
                className="bg-[#0D1117] border border-white/10 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className={`p-6 bg-gradient-to-r ${tech.color} bg-opacity-20 border-b border-white/10`}>
                    <div className="flex items-center gap-4">
                        <div className={`p-4 rounded-xl bg-gradient-to-br ${tech.color}`}>
                            <Icon className="w-8 h-8 text-white" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold text-white">{tech.name}</h2>
                            <p className="text-white/70">{tech.description}</p>
                        </div>
                    </div>
                </div>
                
                {/* Content */}
                <div className="p-6 space-y-6">
                    {/* Features */}
                    <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Key Capabilities</h3>
                        <div className="grid grid-cols-2 gap-3">
                            {tech.features.map((feature, idx) => (
                                <div key={idx} className="flex items-center gap-2 p-3 bg-white/5 rounded-lg">
                                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                                    <span className="text-sm text-white/80">{feature}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    
                    {/* Use Cases */}
                    <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Use Cases</h3>
                        <div className="space-y-2">
                            {getUseCases(tech.id).map((useCase, idx) => (
                                <div key={idx} className="flex items-start gap-2 text-sm text-white/70">
                                    <Zap className="w-4 h-4 text-[#F5B841] mt-0.5 flex-shrink-0" />
                                    <span>{useCase}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    
                    {/* Actions */}
                    <div className="flex gap-3 pt-4 border-t border-white/10">
                        <Button className="flex-1 bg-[#F5B841] text-black hover:bg-[#F5B841]/90">
                            <Play className="w-4 h-4 mr-2" />
                            Get Started
                        </Button>
                        <Button variant="outline" className="flex-1 border-white/20 hover:bg-white/5">
                            <Settings className="w-4 h-4 mr-2" />
                            Configure
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
};

const getUseCases = (techId) => {
    const useCases = {
        'falcon-intelligence': [
            'Automatically identify root cause of incidents using AI correlation',
            'Predict potential issues before they impact users',
            'Get intelligent recommendations for optimization',
            'Detect anomalies in metrics and logs automatically'
        ],
        'automation-engine': [
            'Auto-remediate common issues with predefined runbooks',
            'Trigger automated responses based on alert conditions',
            'Create approval workflows for critical operations',
            'Schedule recurring maintenance tasks'
        ],
        'app-engine': [
            'Build custom dashboards for different teams',
            'Create data-driven applications with no code',
            'Design health rules and alerting policies',
            'Generate executive reports automatically'
        ],
        'grail': [
            'Query all your observability data in one place',
            'Correlate events across different data sources',
            'Retain data for compliance requirements',
            'Perform advanced analytics on historical data'
        ],
        'smartscape': [
            'Visualize service dependencies in real-time',
            'Identify cascade failure risks automatically',
            'Track infrastructure changes and drift',
            'Map application flows across microservices'
        ],
        'open-pipeline': [
            'Ingest data from Prometheus, Grafana, and more',
            'Process and enrich incoming events',
            'Transform data formats on the fly',
            'Scale to handle millions of events'
        ],
        'falcon-agent': [
            'Deploy once, monitor everything automatically',
            'Collect metrics, logs, and traces in one agent',
            'Auto-discover new services and containers',
            'Monitor on-premise and cloud infrastructure'
        ],
        'purepath': [
            'Trace requests across distributed systems',
            'Identify slow database queries and API calls',
            'Analyze code-level performance issues',
            'Debug production issues with full context'
        ]
    };
    return useCases[techId] || [];
};

// Ask FalconOps — a plain-English question box wired to the real NL->tool-call
// planner already running in the backend (intelligence_agents_service.ask(), exposed
// at POST /api/ai-intelligence/ask). No new query language is invented here; this is
// just the first frontend surface for a capability that already worked.
const AskFalconOps = () => {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const ask = async () => {
        if (!query.trim()) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${API_URL}/api/ai-intelligence/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({ query, mode: 'auto' }),
            });
            if (response.ok) {
                setResult(await response.json());
            } else {
                setError('Failed to get an answer. Please try again.');
            }
        } catch (e) {
            setError(e.message);
        }
        setLoading(false);
    };

    const sampleQuestions = [
        'What is the most critical active incident right now?',
        'Show me recent errors in the payment service',
        'Are there any slow traces in the last hour?',
    ];

    return (
        <div className="bg-gradient-to-br from-[#0D1117] to-[#161B22] border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
                <MessageSquareText className="w-6 h-6 text-[#00E0FF]" />
                <div>
                    <h2 className="text-xl font-semibold text-white">Ask FalconOps</h2>
                    <p className="text-sm text-white/50">Ask a plain-English question about your logs, metrics, traces, or incidents</p>
                </div>
            </div>

            <div className="flex gap-2 mb-3">
                <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && ask()}
                    placeholder="e.g. Show me errors in payment-service in the last hour"
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-[#F5B841]/50"
                    data-testid="ask-falconops-input"
                />
                <Button onClick={ask} disabled={loading || !query.trim()} className="bg-[#F5B841] text-black hover:bg-[#F5B841]/90" data-testid="ask-falconops-submit">
                    {loading ? 'Asking...' : 'Ask'}
                </Button>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
                {sampleQuestions.map((q, i) => (
                    <button key={i} onClick={() => setQuery(q)} className="text-xs px-2.5 py-1 bg-white/5 rounded-full text-white/50 hover:text-white/80 hover:bg-white/10">
                        {q}
                    </button>
                ))}
            </div>

            {error && <p className="text-sm text-red-400" data-testid="ask-falconops-error">{error}</p>}

            {result && (
                <div className="bg-black/30 border border-white/10 rounded-lg p-4 space-y-3" data-testid="ask-falconops-result">
                    <div className="flex items-center gap-2 flex-wrap">
                        {result.mode && (
                            <span className="text-[10px] px-2 py-0.5 bg-[#00E0FF]/10 text-[#00E0FF] rounded border border-[#00E0FF]/20">
                                {result.mode === 'incident' ? 'Incident Analysis Agent' : 'Monitoring Copilot Agent'}
                            </span>
                        )}
                        {result.confidence != null && (
                            <span className="text-[10px] px-2 py-0.5 bg-white/5 text-white/60 rounded border border-white/10">
                                confidence {Math.round(result.confidence * 100)}%
                            </span>
                        )}
                        {(result.tool_trace || []).map((t, i) => (
                            <span key={i} className="text-[10px] px-2 py-0.5 bg-white/5 text-white/40 rounded border border-white/10">
                                {t.tool}
                            </span>
                        ))}
                    </div>
                    <p className="text-sm text-white/90">{result.summary}</p>
                    {result.evidence?.length > 0 && (
                        <div>
                            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Evidence</p>
                            <ul className="space-y-1">
                                {result.evidence.map((e, i) => (
                                    <li key={i} className="text-xs text-white/60 flex items-start gap-1.5">
                                        <span className="text-[#F5B841] mt-0.5">•</span>{e}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {result.recommended_actions?.length > 0 && (
                        <div>
                            <p className="text-xs text-white/40 uppercase tracking-wider mb-1">Recommended Actions</p>
                            <ul className="space-y-1">
                                {result.recommended_actions.map((a, i) => (
                                    <li key={i} className="text-xs text-white/70 flex items-start gap-1.5">
                                        <ArrowRight className="w-3 h-3 text-[#00E0FF] mt-0.5 shrink-0" />{a}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export const IntelligencePage = () => {
    const [selectedTech, setSelectedTech] = useState(null);
    const [stats, setStats] = useState({
        totalAlerts: 0,
        aiInsights: 0,
        automations: 0,
        healthScore: 98
    });

    useEffect(() => {
        // Fetch some real stats
        const fetchStats = async () => {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${API_URL}/api/analytics/summary`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    setStats({
                        totalAlerts: data.total_alerts || 0,
                        aiInsights: data.open_incidents || 0,
                        automations: data.resolved_alerts || 0,
                        healthScore: Math.round(data.sla_compliance || 98)
                    });
                }
            } catch (error) {
                console.error('Failed to fetch stats:', error);
            }
        };
        fetchStats();
    }, []);

    const handleTechClick = (tech) => {
        setSelectedTech(tech);
    };

    const handleQuickAction = (action) => {
        // Navigate to appropriate page
        switch (action.id) {
            case 'create-dashboard':
                window.location.href = '/admin?tab=dashboards';
                break;
            case 'health-rule':
                window.location.href = '/admin?tab=rules';
                break;
            case 'runbook':
                window.location.href = '/runbooks';
                break;
            case 'ai-analysis':
                window.location.href = '/event-analyzer';
                break;
            default:
                break;
        }
    };

    return (
        <>
            <div className="space-y-8">
                {/* Hero Section */}
                <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-[#0D1117] to-[#161B22] border border-white/10 p-8">
                    <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxjaXJjbGUgZmlsbD0iIzIyMiIgY3g9IjIwIiBjeT0iMjAiIHI9IjEiLz48L2c+PC9zdmc+')] opacity-30" />
                    
                    <div className="relative z-10">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-3 rounded-xl bg-gradient-to-br from-[#F5B841] to-[#F59E0B]">
                                <Sparkles className="w-8 h-8 text-black" />
                            </div>
                            <div>
                                <h1 className="text-3xl font-bold text-white">FalconOps Intelligence</h1>
                                <p className="text-white/60">Enterprise AI Operations Platform</p>
                            </div>
                        </div>
                        
                        <p className="text-lg text-white/70 max-w-3xl mb-6">
                            Unified observability, intelligent automation, and AI-powered insights. 
                            FalconOps combines the power of 8 core technologies to deliver 
                            enterprise-grade monitoring and incident management.
                        </p>
                        
                        {/* Stats Row */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                                <div className="text-2xl font-bold text-[#F5B841]">{stats.totalAlerts}</div>
                                <div className="text-sm text-white/50">Total Alerts</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                                <div className="text-2xl font-bold text-[#00E0FF]">{stats.aiInsights}</div>
                                <div className="text-sm text-white/50">AI Insights</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                                <div className="text-2xl font-bold text-emerald-400">{stats.automations}</div>
                                <div className="text-sm text-white/50">Auto-Resolved</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                                <div className="text-2xl font-bold text-purple-400">{stats.healthScore}%</div>
                                <div className="text-sm text-white/50">Health Score</div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Ask FalconOps — natural language query */}
                <AskFalconOps />

                {/* Quick Actions */}
                <div>
                    <h2 className="text-xl font-semibold text-white mb-4">Quick Actions</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {quickActions.map(action => (
                            <QuickActionCard 
                                key={action.id} 
                                action={action} 
                                onClick={handleQuickAction}
                            />
                        ))}
                    </div>
                </div>

                {/* Core Technologies Grid */}
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-semibold text-white">Core Technologies</h2>
                        <span className="text-sm text-white/50">Click to explore</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {coreTechnologies.map(tech => (
                            <TechnologyCard 
                                key={tech.id} 
                                tech={tech}
                                onClick={handleTechClick}
                            />
                        ))}
                    </div>
                </div>

                {/* AI Capabilities Section */}
                <div className="bg-gradient-to-br from-[#0D1117] to-[#161B22] border border-white/10 rounded-xl p-6">
                    <div className="flex items-center gap-3 mb-6">
                        <Bot className="w-6 h-6 text-[#00E0FF]" />
                        <h2 className="text-xl font-semibold text-white">AI-Powered Capabilities</h2>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="space-y-3">
                            <div className="flex items-center gap-2 text-white">
                                <Brain className="w-5 h-5 text-[#F5B841]" />
                                <span className="font-medium">Root Cause Analysis</span>
                            </div>
                            <p className="text-sm text-white/60 pl-7">
                                AI automatically correlates alerts and identifies the underlying cause of incidents, 
                                reducing MTTR by up to 80%.
                            </p>
                        </div>
                        
                        <div className="space-y-3">
                            <div className="flex items-center gap-2 text-white">
                                <TrendingUp className="w-5 h-5 text-emerald-400" />
                                <span className="font-medium">Predictive Analytics</span>
                            </div>
                            <p className="text-sm text-white/60 pl-7">
                                Machine learning models predict potential issues before they impact users, 
                                enabling proactive remediation.
                            </p>
                        </div>
                        
                        <div className="space-y-3">
                            <div className="flex items-center gap-2 text-white">
                                <AlertTriangle className="w-5 h-5 text-red-400" />
                                <span className="font-medium">Anomaly Detection</span>
                            </div>
                            <p className="text-sm text-white/60 pl-7">
                                Continuous analysis of metrics and logs to detect unusual patterns 
                                and alert teams before failures occur.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Technology Detail Modal */}
            {selectedTech && (
                <TechnologyDetailModal 
                    tech={selectedTech} 
                    onClose={() => setSelectedTech(null)} 
                />
            )}
        </>
    );
};

export default IntelligencePage;
