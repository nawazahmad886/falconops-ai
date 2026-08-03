import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useGlobalFilters } from '../context/GlobalFiltersContext';
import { useTheme } from '../context/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { FalconLogo } from '../components/FalconLogo';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '../components/ui/dialog';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Command,
    CommandInput,
    CommandList,
    CommandEmpty,
    CommandGroup,
    CommandItem,
} from '../components/ui/command';
import {
    LayoutDashboard,
    Bell,
    AlertTriangle,
    BookOpen,
    BarChart3,
    Settings,
    User,
    LogOut,
    Menu,
    X,
    Activity,
    Hexagon,
    FileText,
    GitBranch,
    Cpu,
    Server,
    Shield,
    ScrollText,
    Download,
    Brain,
    Sparkles,
    Search,
    Clock,
    Globe,
    Bot,
    ChevronDown,
    ChevronRight,
    Zap,
    Eye,
    Network,
    Database,
    Workflow,
    TrendingUp,
    Users,
    Key,
    Plug,
    History,
    Target,
    Gauge,
    LineChart,
    PieChart,
    Map,
    Radio,
    MessageSquareText,    Layers,
    Box,
    Terminal,
    PlayCircle,
    Calendar,
    Building,
    UserCog,
    Lock,
    Webhook,
    CloudCog,
    MonitorCheck,
    Monitor,
    RefreshCw,
    Wrench,
    Package,
    UserCheck,
    Mail,
    Cloud,
    BrainCircuit,
    MemoryStick,
    Sun,
    Moon,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ======================== MODULE DEFINITIONS ========================

const MODULES = {
    problems: {
        id: 'problems',
        label: 'Problems',
        icon: AlertTriangle,
        color: 'text-rose-400',
        description: 'Unified Problem Console',
        sidebar: [
            { path: '/problems', label: 'Problems Console', icon: AlertTriangle },
        ]
    },
    resources: {
        id: 'resources',
        label: 'Resources',
        icon: Box,
        color: 'text-cyan-400',
        description: 'Enterprise Resource Explorer',
        sidebar: [
            { path: '/resources', label: 'Resource Explorer', icon: Box },
        ]
    },
    command: {
        id: 'command',
        label: 'Command',
        icon: LayoutDashboard,
        color: 'text-amber-400',
        description: 'NOC Command Center',
        sidebar: [
            { path: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
            { path: '/custom-dashboard', label: 'My Dashboard (Builder)', icon: Layers },
            { path: '/noc-dashboard', label: 'NOC Dashboard', icon: Eye },
            { path: '/self-monitoring', label: 'Platform Health', icon: Activity },
            { path: '/control-center', label: 'Control Center', icon: Cpu },
            { path: '/alert-respond', label: 'Alert & Respond', icon: Shield },
            { path: '/alert-engine', label: 'Alert Engine', icon: Bell },
            { path: '/incident-engine', label: 'Incidents', icon: AlertTriangle },
            { path: '/wallboard', label: 'NOC Wallboard', icon: Monitor },
        ]
    },
    monitoring: {
        id: 'monitoring',
        label: 'Monitoring',
        icon: Activity,
        color: 'text-emerald-400',
        description: 'Infrastructure Monitoring',
        sidebar: [
            { path: '/monitoring', label: 'Monitors', icon: MonitorCheck },
            { path: '/oneagent-fleet', label: 'OneAgent Fleet', icon: Radio },
            { path: '/uptime-monitor', label: 'Uptime Monitor', icon: Globe },
            { path: '/sla-dashboard', label: 'SLA Dashboard', icon: Shield },
            { path: '/check-nodes', label: 'Check Nodes', icon: Server },
            { path: '/servers', label: 'Servers', icon: Server },
            { path: '/db-monitoring', label: 'Databases', icon: Database },
            { path: '/db-agents', label: 'DB Agents', icon: Bot },
            { path: '/query-analyzer', label: 'Query Analyzer', icon: Search },
            { path: '/synthetic-monitoring', label: 'Synthetic Tests', icon: Globe },
            { path: '/health-rules', label: 'Health Rules', icon: Shield },
            { path: '/apm', label: 'APM', icon: Cpu },
            { path: '/honeycomb', label: 'Service Health', icon: Hexagon },
        ]
    },
    observability: {
        id: 'observability',
        label: 'Observability',
        icon: Eye,
        color: 'text-cyan-400',
        description: 'Full-Stack Observability',
        sidebar: [
            { path: '/logs', label: 'Logs', icon: ScrollText },
            { path: '/apm-traces', label: 'APM Traces', icon: Cpu },
            { path: '/apm-quickstart', label: 'APM Quickstart', icon: Zap },
            { path: '/service-map', label: 'Service Map (D3)', icon: Network },
            { path: '/topology', label: 'Topology Map', icon: Network },
            { path: '/live-call-flow', label: 'Live Call Flow', icon: Zap },
            { path: '/metrics-explorer', label: 'Metrics Explorer', icon: LineChart },
        ]
    },
    aiops: {
        id: 'aiops',
        label: 'AI Ops',
        icon: Brain,
        color: 'text-purple-400',
        description: 'AI-Powered Operations',
        sidebar: [
            { path: '/core-aiops', label: 'Core AIOps', icon: Shield },
            { path: '/ai-engine', label: 'Autonomous AI Engine', icon: Brain },
            { path: '/ai-copilot', label: 'AI Copilot Chat', icon: Sparkles },
            { path: '/ai-monitoring', label: 'AI Monitoring (legacy)', icon: BrainCircuit },
            { path: '/ai-agents', label: 'AI Agents', icon: Brain },
            { path: '/alert-correlation', label: 'Alert Correlation', icon: GitBranch },
            { path: '/aiops-brain', label: 'AIOps Brain', icon: Brain },
            { path: '/event-analyzer', label: 'Event Analyzer', icon: Sparkles },
            { path: '/capacity-prediction', label: 'Capacity Prediction', icon: TrendingUp },
            { path: '/remediation', label: 'Auto-Remediation', icon: Wrench },
            { path: '/k8s-healing', label: 'K8s Auto-Healing', icon: Shield },
            { path: '/impact-analysis', label: 'Impact Analysis', icon: Target },
        ]
    },
    ai_observability: {
        id: 'ai_observability',
        label: 'AI Observability',
        icon: Radio,
        color: 'text-fuchsia-400',
        description: '10-Agent LLM Monitoring v2',
        sidebar: [
            { path: '/ask-falconops', label: 'Ask FalconOpsAI', icon: MessageSquareText },
            { path: '/ai-observability', label: 'Observability Center', icon: Radio },
            { path: '/ai-observability?tab=agents', label: 'Agent Drilldowns', icon: BrainCircuit },
            { path: '/ai-observability?tab=live', label: 'Live Feed (WS)', icon: Activity },
            { path: '/ai-observability?tab=log-analyzer', label: 'AI Log Analyzer', icon: Terminal },
            { path: '/ai-observability?tab=policies', label: 'Policies', icon: Shield },
            { path: '/ai-observability?tab=quarantine', label: 'Quarantine Queue', icon: Lock },
            { path: '/ai-observability?tab=gpu', label: 'GPU Monitoring', icon: MemoryStick },
            { path: '/ai-monitoring', label: 'Legacy Dashboard', icon: BrainCircuit },
        ]
    },
    agentic_workflow: {
        id: 'agentic_workflow',
        label: 'Agentic AI Workflow',
        icon: Sparkles,
        color: 'text-cyan-400',
        description: 'Supervisor, Diagnoser, Forecaster — one ask-anything hub',
        sidebar: [
            { path: '/agentic-workflow', label: 'Agentic Workflow Hub', icon: Sparkles },
        ]
    },
    security: {
        id: 'security',
        label: 'Security',
        icon: Shield,
        color: 'text-red-400',
        description: 'Threat Detection & Response',
        sidebar: [
            { path: '/executive-security', label: 'Executive Dashboard', icon: Shield },
            { path: '/security-monitoring', label: 'Security Overview', icon: Shield },
            { path: '/soc-live-feed', label: 'SOC Live Feed', icon: Radio },
            { path: '/security-monitoring?tab=threats', label: 'Threat Detection', icon: Target },
            { path: '/security-monitoring?tab=users', label: 'User Activity', icon: Users },
            { path: '/security-monitoring?tab=events', label: 'Security Events', icon: ScrollText },
            { path: '/ueba', label: 'Behavior Analytics', icon: Eye },
            { path: '/attack-simulator', label: 'Attack Simulator', icon: Target },
            { path: '/aws-connectors', label: 'AWS Connectors', icon: CloudCog },
            { path: '/detection-rules', label: 'Detection Rules', icon: Shield },
        ]
    },
    automation: {
        id: 'automation',
        label: 'Automation',
        icon: Workflow,
        color: 'text-orange-400',
        description: 'Runbook Automation',
        sidebar: [
            { path: '/runbooks', label: 'Runbooks', icon: BookOpen },
            { path: '/runbooks?tab=templates', label: 'Templates', icon: Layers },
            { path: '/runbooks?tab=scheduled', label: 'Schedules', icon: Calendar },
            { path: '/runbooks?tab=executions', label: 'Executions', icon: PlayCircle },
        ]
    },
    insights: {
        id: 'insights',
        label: 'Insights',
        icon: TrendingUp,
        color: 'text-blue-400',
        description: 'Analytics & Reports',
        sidebar: [
            { path: '/analytics', label: 'Analytics', icon: BarChart3 },
            { path: '/reports', label: 'Reports', icon: FileText },
            { path: '/weekly-reports', label: 'AI Weekly Report', icon: Sparkles },
            { path: '/report-builder', label: 'Report Template Builder', icon: Layers },
            { path: '/scheduled-reports', label: 'Scheduled Reports', icon: Calendar },
            { path: '/tenant-schedules', label: 'Tenant Schedules', icon: Building },
        ]
    },
    enterprise: {
        id: 'enterprise',
        label: 'Enterprise',
        icon: Building,
        color: 'text-red-400',
        description: 'Platform Governance',
        adminOnly: true,
        sidebar: [
            { path: '/admin', label: 'Administration', icon: Shield },
            { path: '/admin/control-console', label: 'Control Console', icon: Settings },
            { path: '/admin-console', label: 'Admin Console (legacy)', icon: Settings },
            { path: '/tenants', label: 'Tenants', icon: Building },
            { path: '/tenant-branding', label: 'Tenant Branding', icon: Sparkles },
            { path: '/admin?tab=users', label: 'Users & Teams', icon: Users },
            { path: '/rbac', label: 'Access Control', icon: Lock },
            { path: '/integrations', label: 'Integrations', icon: Plug },
            { path: '/kafka-pipeline', label: 'Kafka Pipeline', icon: Workflow },
            { path: '/billing', label: 'Billing & Plans', icon: Key },
            { path: '/admin/plans', label: 'Plans (CRUD)', icon: Package },
            { path: '/admin/email-templates', label: 'Email Templates', icon: Mail },
            { path: '/admin/leads', label: 'Sales Leads', icon: UserCheck },
            { path: '/admin/automation-templates', label: 'AI Automation Templates', icon: Workflow },
            { path: '/admin/aws-deploy', label: 'AWS Deploy Wizard', icon: Cloud },
            { path: '/admin?tab=audit', label: 'Audit Logs', icon: History },
            { path: '/download', label: 'Downloads & Licensing', icon: Download },
        ]
    }
};

// Time range options
const TIME_RANGES = [
    { value: '5m', label: 'Last 5 minutes' },
    { value: '15m', label: 'Last 15 minutes' },
    { value: '1h', label: 'Last 1 hour' },
    { value: '6h', label: 'Last 6 hours' },
    { value: '24h', label: 'Last 24 hours' },
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: 'custom', label: 'Custom Range' },
];

// Environment options
const ENVIRONMENTS = [
    { value: 'all', label: 'All Environments' },
    { value: 'production', label: 'Production', color: 'text-red-400' },
    { value: 'staging', label: 'Staging', color: 'text-amber-400' },
    { value: 'development', label: 'Development', color: 'text-emerald-400' },
];

// Timezone options — 'browser' and 'UTC' cover the two cases every display
// formatter needs; any other IANA zone name works too (Intl.DateTimeFormat
// takes an arbitrary zone string), these are just the pinned shortcuts.
const TIMEZONES = [
    { value: 'browser', label: 'Browser Time' },
    { value: 'UTC', label: 'UTC' },
    { value: 'Asia/Riyadh', label: 'Saudi Time' },
];

// Auto-refresh interval options, in ms. 'off' disables polling entirely.
const REFRESH_INTERVALS = [
    { value: 'off', label: 'Off' },
    { value: '10000', label: '10s' },
    { value: '30000', label: '30s' },
    { value: '60000', label: '1m' },
    { value: '300000', label: '5m' },
    { value: '900000', label: '15m' },
    { value: '1800000', label: '30m' },
];

// ======================== GLOBAL SEARCH ========================

const GlobalSearch = ({ open, onOpenChange }) => {
    const [query, setQuery] = useState('');
    const [problemResults, setProblemResults] = useState([]);
    const navigate = useNavigate();
    const { api } = useAuth();

    // Live Problems search — debounced, only once the query is long enough to
    // be worth a round-trip. Substring match server-side, not full-text-at-scale
    // (no Elasticsearch in this stack) — see problems_service.search_problems.
    useEffect(() => {
        if (query.trim().length < 2) {
            setProblemResults([]);
            return;
        }
        let alive = true;
        const timer = setTimeout(async () => {
            try {
                const res = await api.get(`/problems/search?q=${encodeURIComponent(query.trim())}`);
                if (alive) setProblemResults(res.data?.problems || []);
            } catch (_e) {
                if (alive) setProblemResults([]);
            }
        }, 300);
        return () => { alive = false; clearTimeout(timer); };
    }, [query, api]);

    const searchResults = [
        { type: 'page', label: 'Problems Console', path: '/problems', icon: AlertTriangle },
        { type: 'page', label: 'Resource Explorer', path: '/resources', icon: Box },
        { type: 'page', label: 'Agentic AI Workflow', path: '/agentic-workflow', icon: Sparkles },
        { type: 'page', label: 'Core AIOps', path: '/core-aiops', icon: Shield },
        { type: 'page', label: 'Database Monitoring', path: '/db-monitoring', icon: Database },
        { type: 'page', label: 'Command Center', path: '/dashboard', icon: LayoutDashboard },
        { type: 'page', label: 'Alert Engine', path: '/alert-engine', icon: Bell },
        { type: 'page', label: 'Incident Management', path: '/incident-engine', icon: AlertTriangle },
        { type: 'page', label: 'Server Monitoring', path: '/servers', icon: Server },
        { type: 'page', label: 'AI Analyzer', path: '/event-analyzer', icon: Brain },
        { type: 'page', label: 'Runbooks', path: '/runbooks', icon: BookOpen },
        { type: 'page', label: 'Logs', path: '/logs', icon: ScrollText },
        { type: 'page', label: 'APM', path: '/apm', icon: Cpu },
        { type: 'page', label: 'Topology', path: '/topology', icon: GitBranch },
        { type: 'page', label: 'Live Call Flow', path: '/live-call-flow', icon: Zap },
        { type: 'page', label: 'Reports', path: '/reports', icon: FileText },
        { type: 'page', label: 'Metrics Explorer', path: '/metrics-explorer', icon: LineChart },
        { type: 'page', label: 'Capacity Prediction', path: '/capacity-prediction', icon: TrendingUp },
        { type: 'page', label: 'Synthetic Monitoring', path: '/synthetic-monitoring', icon: Globe },
        { type: 'page', label: 'Platform Health', path: '/self-monitoring', icon: Activity },
        { type: 'page', label: 'Control Center', path: '/control-center', icon: Cpu },
        { type: 'page', label: 'Security Monitoring', path: '/security-monitoring', icon: Shield },
        { type: 'page', label: 'Behavior Analytics (UEBA)', path: '/ueba', icon: Eye },
        { type: 'page', label: 'Attack Simulator', path: '/attack-simulator', icon: Target },
        { type: 'page', label: 'Integrations', path: '/integrations', icon: Plug },
        { type: 'page', label: 'Auto-Remediation', path: '/remediation', icon: Wrench },
        { type: 'page', label: 'Impact Analysis', path: '/impact-analysis', icon: Target },
        { type: 'page', label: 'SOC Live Feed', path: '/soc-live-feed', icon: Radio },
        { type: 'page', label: 'AWS Connectors', path: '/aws-connectors', icon: CloudCog },
        { type: 'page', label: 'Kafka Pipeline', path: '/kafka-pipeline', icon: Workflow },
        { type: 'page', label: 'Access Control (RBAC)', path: '/rbac', icon: Lock },
        { type: 'page', label: 'Query Analyzer', path: '/query-analyzer', icon: Database },
        { type: 'page', label: 'Uptime Monitor', path: '/uptime-monitor', icon: Globe },
        { type: 'page', label: 'Multi-Tenant Management', path: '/tenants', icon: Building },
        { type: 'page', label: 'Database Agents', path: '/db-agents', icon: Bot },
        { type: 'page', label: 'Billing & Plans', path: '/billing', icon: Key },
        { type: 'page', label: 'SLA Dashboard', path: '/sla-dashboard', icon: Shield },
        { type: 'page', label: 'Check Nodes', path: '/check-nodes', icon: Server },
        { type: 'page', label: 'Service Map (D3)', path: '/service-map', icon: GitBranch },
        { type: 'page', label: 'Detection Rules', path: '/detection-rules', icon: Shield },
        { type: 'page', label: 'AI Agents', path: '/ai-agents', icon: Brain },
        { type: 'page', label: 'AI Weekly Report', path: '/weekly-reports', icon: Sparkles },
        { type: 'page', label: 'Custom Dashboard Builder', path: '/custom-dashboard', icon: Layers },
        { type: 'page', label: 'Tenant Branding', path: '/tenant-branding', icon: Sparkles },
        { type: 'page', label: 'Scheduled Reports', path: '/scheduled-reports', icon: Calendar },
    ];

    const filteredResults = query 
        ? searchResults.filter(r => r.label.toLowerCase().includes(query.toLowerCase()))
        : searchResults;

    const handleSelect = (path) => {
        navigate(path);
        onOpenChange(false);
        setQuery('');
        setProblemResults([]);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="p-0 bg-[#0D1117] border-white/10 max-w-xl">
                <Command className="bg-transparent">
                    <CommandInput 
                        placeholder="Search pages, alerts, services..." 
                        value={query}
                        onValueChange={setQuery}
                        className="border-b border-white/10"
                    />
                    <CommandList className="max-h-80">
                        <CommandEmpty>No results found.</CommandEmpty>
                        <CommandGroup heading="Pages">
                            {filteredResults.map((item) => {
                                const Icon = item.icon;
                                return (
                                    <CommandItem
                                        key={item.path}
                                        onSelect={() => handleSelect(item.path)}
                                        className="cursor-pointer"
                                    >
                                        <Icon className="w-4 h-4 mr-2 text-white/50" />
                                        {item.label}
                                    </CommandItem>
                                );
                            })}
                        </CommandGroup>
                        {problemResults.length > 0 && (
                            <CommandGroup heading="Problems">
                                {problemResults.map((p) => (
                                    <CommandItem
                                        key={p.id}
                                        onSelect={() => handleSelect(`/problems?open=${encodeURIComponent(p.id)}`)}
                                        className="cursor-pointer"
                                    >
                                        <AlertTriangle className="w-4 h-4 mr-2 text-rose-400" />
                                        <span className="truncate">{p.title || p.id}</span>
                                        <span className="ml-auto text-[10px] text-white/40 uppercase">{p.severity}</span>
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        )}
                    </CommandList>
                </Command>
            </DialogContent>
        </Dialog>
    );
};

// ======================== NOTIFICATIONS PANEL ========================

const NotificationsPanel = ({ open, onOpenChange, notifications }) => {
    return (
        <DropdownMenu open={open} onOpenChange={onOpenChange}>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative hover:bg-white/5">
                    <Bell className="w-5 h-5 text-white/70" />
                    {notifications.length > 0 && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-[10px] font-bold flex items-center justify-center">
                            {notifications.length}
                        </span>
                    )}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80 bg-[#0D1117] border-white/10">
                <div className="px-3 py-2 border-b border-white/10">
                    <h3 className="font-semibold text-white">Notifications</h3>
                </div>
                {notifications.length === 0 ? (
                    <div className="px-3 py-8 text-center text-white/50 text-sm">
                        No new notifications
                    </div>
                ) : (
                    <div className="max-h-80 overflow-y-auto">
                        {notifications.map((n, i) => (
                            <DropdownMenuItem key={i} className="flex items-start gap-3 p-3 cursor-pointer">
                                <div className={`p-1.5 rounded ${
                                    n.type === 'critical' ? 'bg-red-500/20' : 
                                    n.type === 'warning' ? 'bg-amber-500/20' : 'bg-blue-500/20'
                                }`}>
                                    {n.type === 'critical' ? <AlertTriangle className="w-4 h-4 text-red-400" /> :
                                     n.type === 'warning' ? <Bell className="w-4 h-4 text-amber-400" /> :
                                     <Sparkles className="w-4 h-4 text-blue-400" />}
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm text-white">{n.title}</p>
                                    <p className="text-xs text-white/50">{n.time}</p>
                                </div>
                            </DropdownMenuItem>
                        ))}
                    </div>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
};

// ======================== AI COPILOT PANEL ========================

const AICopilotPanel = ({ open, onOpenChange }) => {
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState([]);
    const [sending, setSending] = useState(false);
    const [sessionId] = useState(() => `copilot-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    const scrollRef = React.useRef(null);
    const inputRef = React.useRef(null);

    const API = process.env.REACT_APP_BACKEND_URL;
    const getAuth = () => ({ 'Authorization': `Bearer ${localStorage.getItem('falconToken')}`, 'Content-Type': 'application/json' });

    // Auto-scroll on new messages
    React.useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages]);

    // Focus input when opened
    React.useEffect(() => {
        if (open && inputRef.current) setTimeout(() => inputRef.current?.focus(), 200);
    }, [open]);

    const sendMessage = async (text) => {
        const msg = (text || message).trim();
        if (!msg || sending) return;
        setMessage('');
        setMessages(prev => [...prev, { role: 'user', content: msg, ts: new Date().toISOString() }]);
        setSending(true);
        try {
            const res = await fetch(`${API}/api/logs/copilot/chat`, {
                method: 'POST', headers: getAuth(),
                body: JSON.stringify({ message: msg, session_id: sessionId, context: {} }),
            });
            const data = await res.json();
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: data.response || data.error || 'No response',
                ts: new Date().toISOString(),
            }]);
        } catch (e) {
            setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}`, ts: new Date().toISOString(), error: true }]);
        }
        setSending(false);
    };

    const handleKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } };

    const quickActions = [
        { label: 'Critical alerts', q: 'What are the current critical alerts and violations?' },
        { label: 'Run RCA', q: 'Analyze the active violations and tell me the root cause' },
        { label: 'What\'s at risk?', q: 'Which servers or services are at risk right now?' },
        { label: 'System status', q: 'Give me a summary of the overall system health' },
    ];

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="bg-[#0D1117] border-white/10 max-w-xl p-0 gap-0" data-testid="copilot-dialog">
                <DialogHeader className="px-5 pt-4 pb-3 border-b border-white/5">
                    <DialogTitle className="flex items-center gap-2 text-base">
                        <div className="p-1.5 rounded-lg bg-[#00E0FF]/15"><Bot className="w-4 h-4 text-[#00E0FF]" /></div>
                        FalconOps AI Copilot
                        <Badge className="text-[9px] px-1.5 py-0 bg-emerald-500/20 text-emerald-400 border-emerald-500/30 ml-auto">Live</Badge>
                    </DialogTitle>
                </DialogHeader>

                {/* Messages Area */}
                <div ref={scrollRef} className="px-5 py-4 min-h-[320px] max-h-[420px] overflow-y-auto space-y-4" data-testid="copilot-messages">
                    {messages.length === 0 && (
                        <div className="text-center py-6">
                            <Bot className="w-10 h-10 mx-auto text-[#00E0FF]/30 mb-3" />
                            <p className="text-sm text-white/60 mb-1">Hi! I'm your AI NOC Copilot.</p>
                            <p className="text-xs text-white/30 mb-4">Ask about alerts, violations, root causes, or system health.</p>
                            <div className="flex flex-wrap justify-center gap-1.5">
                                {quickActions.map(a => (
                                    <button key={a.label} onClick={() => sendMessage(a.q)}
                                        className="text-[10px] px-2.5 py-1.5 rounded-full border border-[#00E0FF]/20 text-[#00E0FF]/70 hover:bg-[#00E0FF]/10 hover:text-[#00E0FF] transition-colors"
                                        data-testid={`quick-${a.label.toLowerCase().replace(/\s/g, '-')}`}>
                                        {a.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                    {messages.map((m, i) => (
                        <div key={i} className={`flex gap-2.5 ${m.role === 'user' ? 'justify-end' : ''}`} data-testid={`msg-${m.role}-${i}`}>
                            {m.role === 'assistant' && (
                                <div className="p-1.5 rounded-lg bg-[#00E0FF]/10 h-fit mt-0.5 shrink-0">
                                    <Bot className="w-3.5 h-3.5 text-[#00E0FF]" />
                                </div>
                            )}
                            <div className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                                m.role === 'user'
                                    ? 'bg-[#00E0FF]/15 text-white/90'
                                    : m.error ? 'bg-red-500/10 text-red-400/80 border border-red-500/20' : 'bg-white/[0.04] text-white/75 border border-white/5'
                            }`}>
                                <div className="whitespace-pre-wrap break-words">{m.content}</div>
                                <div className="text-[9px] text-white/20 mt-1.5">{new Date(m.ts).toLocaleTimeString()}</div>
                            </div>
                            {m.role === 'user' && (
                                <div className="p-1.5 rounded-lg bg-[#F5B841]/10 h-fit mt-0.5 shrink-0">
                                    <User className="w-3.5 h-3.5 text-[#F5B841]" />
                                </div>
                            )}
                        </div>
                    ))}
                    {sending && (
                        <div className="flex gap-2.5" data-testid="typing-indicator">
                            <div className="p-1.5 rounded-lg bg-[#00E0FF]/10 h-fit"><Bot className="w-3.5 h-3.5 text-[#00E0FF]" /></div>
                            <div className="bg-white/[0.04] border border-white/5 rounded-xl px-4 py-3">
                                <div className="flex gap-1.5">
                                    <span className="w-1.5 h-1.5 rounded-full bg-[#00E0FF]/50 animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <span className="w-1.5 h-1.5 rounded-full bg-[#00E0FF]/50 animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <span className="w-1.5 h-1.5 rounded-full bg-[#00E0FF]/50 animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="px-5 pb-4 pt-2 border-t border-white/5">
                    {messages.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-2.5">
                            {quickActions.map(a => (
                                <button key={a.label} onClick={() => sendMessage(a.q)} disabled={sending}
                                    className="text-[9px] px-2 py-1 rounded-full border border-white/10 text-white/30 hover:bg-white/5 hover:text-white/50 transition-colors disabled:opacity-30">
                                    {a.label}
                                </button>
                            ))}
                        </div>
                    )}
                    <div className="flex gap-2">
                        <Input ref={inputRef} placeholder="Ask FalconOps AI..." value={message}
                            onChange={(e) => setMessage(e.target.value)} onKeyDown={handleKey}
                            disabled={sending} className="bg-[#161B22] border-white/10 text-sm"
                            data-testid="copilot-input" />
                        <Button onClick={() => sendMessage()} disabled={sending || !message.trim()}
                            className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black font-medium px-4 shrink-0"
                            data-testid="copilot-send-btn">
                            {sending ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Ask'}
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};

// ======================== MAIN ENTERPRISE LAYOUT ========================

export const EnterpriseLayout = ({ children }) => {
    const { user, logout, api } = useAuth();
    const {
        timeRange, setTimeRange,
        environment, setEnvironment,
        customRange, setCustomRange,
        timezone, setTimezone,
        refreshInterval, setRefreshInterval,
    } = useGlobalFilters();
    const { theme, toggleTheme } = useTheme();
    const location = useLocation();
    const navigate = useNavigate();

    // State
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    const [copilotOpen, setCopilotOpen] = useState(false);
    const [notificationsOpen, setNotificationsOpen] = useState(false);
    const [notifications, setNotifications] = useState([]);
    
    // Determine active module based on path
    const getActiveModule = () => {
        const path = location.pathname;
        if (path.startsWith('/problems')) return 'problems';
        if (path.startsWith('/resources')) return 'resources';
        if (path.startsWith('/agentic-workflow')) return 'agentic_workflow';
        if (['/dashboard', '/noc-dashboard', '/alert-engine', '/incident-engine', '/wallboard', '/alert-respond', '/self-monitoring', '/control-center', '/custom-dashboard'].some(p => path.startsWith(p))) return 'command';
        if (['/monitoring', '/servers', '/db-monitoring', '/apm', '/honeycomb', '/health-rules', '/synthetic-monitoring', '/query-analyzer', '/uptime-monitor', '/db-agents', '/sla-dashboard', '/check-nodes', '/oneagent-fleet'].some(p => path.startsWith(p))) return 'monitoring';
        if (['/logs', '/topology', '/metrics-explorer', '/service-map'].some(p => path.startsWith(p))) return 'observability';
        if (path.startsWith('/ai-observability') || path.startsWith('/ask-falconops')) return 'ai_observability';
        if (['/core-aiops', '/aiops-brain', '/event-analyzer', '/capacity-prediction', '/intelligence', '/remediation', '/impact-analysis', '/ai-agents', '/alert-correlation', '/k8s-healing', '/ai-monitoring'].some(p => path.startsWith(p))) return 'aiops';
        if (['/executive-security', '/security-monitoring', '/ueba', '/attack-simulator', '/soc-live-feed', '/aws-connectors', '/detection-rules'].some(p => path.startsWith(p))) return 'security';
        if (['/runbooks'].some(p => path.startsWith(p))) return 'automation';
        if (['/analytics', '/reports', '/weekly-reports', '/scheduled-reports', '/tenant-schedules', '/report-builder'].some(p => path.startsWith(p))) return 'insights';
        if (['/admin', '/download', '/settings', '/integrations', '/rbac', '/kafka-pipeline', '/tenants', '/billing', '/admin-console', '/tenant-branding', '/admin/control-console', '/admin/plans', '/admin/email-templates', '/admin/leads', '/admin/automation-templates', '/admin/aws-deploy'].some(p => path.startsWith(p))) return 'enterprise';
        return 'command';
    };
    
    const activeModule = getActiveModule();
    const currentModule = MODULES[activeModule];

    // Fetch notifications
    useEffect(() => {
        const fetchNotifications = async () => {
            try {
                const res = await api.get('/alerts?status=open&limit=5');
                const alerts = res.data || [];
                setNotifications(alerts.slice(0, 5).map(a => ({
                    type: a.severity === 'critical' ? 'critical' : a.severity === 'warning' ? 'warning' : 'info',
                    title: a.title,
                    time: new Date(a.created_at).toLocaleTimeString()
                })));
            } catch (e) {
                setNotifications([]);
            }
        };
        fetchNotifications();
    }, []);

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setSearchOpen(true);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    return (
            <div className="min-h-screen bg-[#0B0E14] flex flex-col">
                {/* ==================== TOP BAR ==================== */}
                <header className="sticky top-0 z-50 bg-[#0B0E14]/95 backdrop-blur-xl border-b border-white/5">
                    <div className="flex h-12 items-center justify-between px-4">
                        {/* Logo */}
                        <Link to="/dashboard" className="flex items-center gap-2">
                            <FalconLogo size={28} />
                            <span className="font-heading font-bold text-base tracking-wide hidden md:flex items-baseline">
                                <span className="text-[#F5B841]">FALCON</span>
                                <span className="text-white">OPS</span>
                                <span className="text-[#00E0FF] text-xs ml-1">AI</span>
                            </span>
                        </Link>

                        {/* Global Search */}
                        <Button
                            variant="ghost"
                            onClick={() => setSearchOpen(true)}
                            className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-md text-white/50 text-sm"
                        >
                            <Search className="w-4 h-4" />
                            <span>Search...</span>
                            <kbd className="ml-2 px-1.5 py-0.5 bg-white/10 rounded text-[10px]">⌘K</kbd>
                        </Button>

                        {/* Right Controls */}
                        <div className="flex items-center gap-2">
                            {/* Time Range */}
                            <Select value={timeRange} onValueChange={setTimeRange}>
                                <SelectTrigger className="w-[130px] h-8 bg-white/5 border-white/10 text-xs">
                                    <Clock className="w-3 h-3 mr-1 text-white/50" />
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    {TIME_RANGES.map(t => (
                                        <SelectItem key={t.value} value={t.value} className="text-xs">
                                            {t.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {/* Environment */}
                            <Select value={environment} onValueChange={setEnvironment}>
                                <SelectTrigger className="w-[140px] h-8 bg-white/5 border-white/10 text-xs hidden lg:flex">
                                    <Globe className="w-3 h-3 mr-1 text-white/50" />
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    {ENVIRONMENTS.map(e => (
                                        <SelectItem key={e.value} value={e.value} className="text-xs">
                                            <span className={e.color}>{e.label}</span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {/* Timezone */}
                            <Select value={timezone} onValueChange={setTimezone}>
                                <SelectTrigger className="w-[110px] h-8 bg-white/5 border-white/10 text-xs hidden xl:flex" data-testid="timezone-select">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    {TIMEZONES.map(t => (
                                        <SelectItem key={t.value} value={t.value} className="text-xs">
                                            {t.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {/* Auto-refresh interval */}
                            <Select value={refreshInterval} onValueChange={setRefreshInterval}>
                                <SelectTrigger className="w-[90px] h-8 bg-white/5 border-white/10 text-xs hidden xl:flex" data-testid="refresh-interval-select">
                                    <RefreshCw className="w-3 h-3 mr-1 text-white/50" />
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent className="bg-[#0D1117] border-white/10">
                                    {REFRESH_INTERVALS.map(r => (
                                        <SelectItem key={r.value} value={r.value} className="text-xs">
                                            {r.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>

                            {/* Notifications */}
                            <NotificationsPanel 
                                open={notificationsOpen} 
                                onOpenChange={setNotificationsOpen}
                                notifications={notifications}
                            />

                            {/* Theme toggle — infrastructure only, see ThemeContext.js. Real
                                visible effect is currently limited to a handful of shadcn
                                primitives (card/dialog/dropdown/popover); most of the app is
                                still hardcoded dark literals and won't visibly change yet. */}
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={toggleTheme}
                                className="hover:bg-white/5 hidden md:flex"
                                title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                                data-testid="theme-toggle"
                            >
                                {theme === 'dark' ? <Sun className="w-5 h-5 text-white/70" /> : <Moon className="w-5 h-5 text-white/70" />}
                            </Button>

                            {/* AI Copilot */}
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setCopilotOpen(true)}
                                className="hover:bg-white/5"
                                title="AI Copilot"
                            >
                                <Bot className="w-5 h-5 text-[#00E0FF]" />
                            </Button>

                            {/* Wallboard Mode */}
                            <Button 
                                variant="ghost" 
                                size="icon" 
                                onClick={() => navigate('/wallboard')}
                                className="hover:bg-white/5 hidden lg:flex"
                                title="NOC Wallboard"
                            >
                                <Monitor className="w-5 h-5 text-white/70" />
                            </Button>

                            {/* Auto-refresh status — reflects the actual refreshInterval setting
                                above, not a page-level "data is fresh" claim (the header itself
                                fetches nothing; only pages that call useAutoRefresh() honor this). */}
                            <div
                                className={`hidden lg:flex items-center gap-1.5 px-2 py-1 rounded text-[10px] border ${
                                    refreshInterval !== 'off'
                                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                                        : 'bg-white/5 border-white/10 text-white/40'
                                }`}
                                data-testid="refresh-status-indicator"
                            >
                                <div className={`w-1.5 h-1.5 rounded-full ${refreshInterval !== 'off' ? 'bg-emerald-400 animate-pulse' : 'bg-white/30'}`} />
                                {refreshInterval !== 'off' ? 'LIVE' : 'PAUSED'}
                            </div>

                            {/* User Menu */}
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" className="flex items-center gap-2 hover:bg-white/5 h-8 px-2">
                                        <div className="w-7 h-7 rounded bg-primary/20 border border-primary/30 flex items-center justify-center">
                                            <User className="w-3.5 h-3.5 text-primary" />
                                        </div>
                                        <ChevronDown className="w-3 h-3 text-white/50 hidden sm:block" />
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-56 bg-[#0D1117] border-white/10">
                                    <div className="px-3 py-2 border-b border-white/10">
                                        <p className="text-sm font-semibold text-white">{user?.full_name}</p>
                                        <p className="text-xs text-white/50">{user?.email}</p>
                                        <Badge variant="outline" className="mt-1 text-[10px]">{user?.role}</Badge>
                                    </div>
                                    <DropdownMenuItem asChild>
                                        <Link to="/settings" className="flex items-center gap-2 cursor-pointer">
                                            <Settings className="w-4 h-4" /> Settings
                                        </Link>
                                    </DropdownMenuItem>
                                    <DropdownMenuItem asChild>
                                        <Link to="/admin?tab=api-keys" className="flex items-center gap-2 cursor-pointer">
                                            <Key className="w-4 h-4" /> API Keys
                                        </Link>
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator className="bg-white/10" />
                                    <DropdownMenuItem onClick={logout} className="text-red-400 cursor-pointer">
                                        <LogOut className="w-4 h-4 mr-2" /> Logout
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>

                            {/* Mobile Menu */}
                            <Button
                                variant="ghost"
                                size="icon"
                                className="lg:hidden"
                                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            >
                                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                            </Button>
                        </div>
                    </div>

                    {/* ==================== PRIMARY NAV BAR ==================== */}
                    <div className="hidden lg:flex items-center gap-1 px-4 py-1 border-t border-white/5 bg-[#0B0E14]/80">
                        {Object.values(MODULES).filter(m => !m.adminOnly || user?.role === 'admin').map((module) => {
                            const Icon = module.icon;
                            const isActive = activeModule === module.id;
                            return (
                                <Button
                                    key={module.id}
                                    variant="ghost"
                                    onClick={() => navigate(module.sidebar[0].path)}
                                    className={`flex items-center gap-2 px-3 py-1.5 h-8 text-xs font-medium rounded-md transition-all ${
                                        isActive
                                            ? `bg-white/10 ${module.color}`
                                            : 'text-white/60 hover:text-white hover:bg-white/5'
                                    }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {module.label}
                                </Button>
                            );
                        })}
                    </div>

                    {/* ==================== CUSTOM RANGE BAR ====================
                        Shown only when Time Range is set to "Custom". datetime-local
                        inputs are always browser-local wall-clock time — the Timezone
                        selector above only affects how returned timestamps are
                        DISPLAYED, it does not reinterpret this input. */}
                    {timeRange === 'custom' && (
                        <div className="flex items-center gap-2 px-4 py-1.5 border-t border-white/5 bg-[#0B0E14]/80 text-xs" data-testid="custom-range-bar">
                            <Calendar className="w-3.5 h-3.5 text-white/50" />
                            <span className="text-white/40">Custom range (browser-local time):</span>
                            <Input
                                type="datetime-local"
                                value={customRange.start}
                                onChange={(e) => setCustomRange((r) => ({ ...r, start: e.target.value }))}
                                className="h-7 w-[190px] bg-white/5 border-white/10 text-xs"
                                data-testid="custom-range-start"
                            />
                            <span className="text-white/40">to</span>
                            <Input
                                type="datetime-local"
                                value={customRange.end}
                                onChange={(e) => setCustomRange((r) => ({ ...r, end: e.target.value }))}
                                className="h-7 w-[190px] bg-white/5 border-white/10 text-xs"
                                data-testid="custom-range-end"
                            />
                        </div>
                    )}
                </header>

                {/* ==================== MAIN CONTENT AREA ==================== */}
                <div className="flex flex-1 overflow-hidden">
                    {/* ==================== LEFT SIDEBAR ==================== */}
                    <aside className={`hidden lg:flex flex-col border-r border-white/5 bg-[#0B0E14] transition-all duration-300 ${
                        sidebarCollapsed ? 'w-16' : 'w-56'
                    }`}>
                        {/* Module Header */}
                        <div className="p-3 border-b border-white/5">
                            <div className="flex items-center gap-2">
                                {React.createElement(currentModule.icon, { className: `w-5 h-5 ${currentModule.color}` })}
                                {!sidebarCollapsed && (
                                    <div>
                                        <h2 className={`text-sm font-semibold ${currentModule.color}`}>{currentModule.label}</h2>
                                        <p className="text-[10px] text-white/40">{currentModule.description}</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Sidebar Navigation */}
                        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
                            {currentModule.sidebar.map((item) => {
                                const Icon = item.icon;
                                const isActive = location.pathname === item.path || 
                                    (item.path.includes('?') && location.pathname + location.search === item.path);
                                return (
                                    <Link
                                        key={item.path}
                                        to={item.path}
                                        className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all ${
                                            isActive
                                                ? `bg-white/10 text-white`
                                                : 'text-white/60 hover:text-white hover:bg-white/5'
                                        }`}
                                        title={sidebarCollapsed ? item.label : undefined}
                                    >
                                        <Icon className="w-4 h-4 flex-shrink-0" />
                                        {!sidebarCollapsed && <span>{item.label}</span>}
                                    </Link>
                                );
                            })}
                        </nav>

                        {/* Collapse Toggle */}
                        <div className="p-2 border-t border-white/5">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                                className="w-full justify-center text-white/40 hover:text-white"
                            >
                                <ChevronRight className={`w-4 h-4 transition-transform ${sidebarCollapsed ? '' : 'rotate-180'}`} />
                            </Button>
                        </div>
                    </aside>

                    {/* ==================== MAIN WORKSPACE ==================== */}
                    <main className="flex-1 overflow-y-auto p-4 lg:p-6">
                        {children}
                    </main>
                </div>

                {/* Mobile Navigation */}
                {mobileMenuOpen && (
                    <div className="fixed inset-0 z-40 lg:hidden">
                        <div className="absolute inset-0 bg-black/80" onClick={() => setMobileMenuOpen(false)} />
                        <nav className="absolute left-0 top-0 bottom-0 w-64 bg-[#0B0E14] border-r border-white/10 p-4 overflow-y-auto">
                            <div className="mb-4">
                                <h3 className={`text-sm font-semibold ${currentModule.color}`}>{currentModule.label}</h3>
                            </div>
                            {currentModule.sidebar.map((item) => {
                                const Icon = item.icon;
                                return (
                                    <Link
                                        key={item.path}
                                        to={item.path}
                                        onClick={() => setMobileMenuOpen(false)}
                                        className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-white/60 hover:text-white hover:bg-white/5"
                                    >
                                        <Icon className="w-4 h-4" />
                                        {item.label}
                                    </Link>
                                );
                            })}
                            <div className="mt-4 pt-4 border-t border-white/10">
                                <p className="text-xs text-white/40 mb-2">Modules</p>
                                {Object.values(MODULES).filter(m => !m.adminOnly || user?.role === 'admin').map((module) => {
                                    const Icon = module.icon;
                                    return (
                                        <Button
                                            key={module.id}
                                            variant="ghost"
                                            onClick={() => {
                                                navigate(module.sidebar[0].path);
                                                setMobileMenuOpen(false);
                                            }}
                                            className={`w-full justify-start gap-2 text-sm ${module.color}`}
                                        >
                                            <Icon className="w-4 h-4" />
                                            {module.label}
                                        </Button>
                                    );
                                })}
                            </div>
                        </nav>
                    </div>
                )}

                {/* Dialogs */}
                <GlobalSearch open={searchOpen} onOpenChange={setSearchOpen} />
                <AICopilotPanel open={copilotOpen} onOpenChange={setCopilotOpen} />
            </div>
    );
};

export default EnterpriseLayout;
