import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { useLanguage } from '../context/LanguageContext';
import { LanguageToggle } from '../components/LanguageToggle';
import { FalconLogo } from '../components/FalconLogo';
import { InteractiveDemo } from '../components/InteractiveDemo';
import {
    Shield,
    Zap,
    Brain,
    TrendingDown,
    Clock,
    ChevronRight,
    Check,
    ArrowRight,
    AlertTriangle,
    Activity,
    Server,
    Target,
    Cpu,
    Network,
    Eye,
    BarChart3,
    Menu,
    X,
    Play,
    FileText,
    FileSpreadsheet,
    FileDown,
    Layers,
    Building,
    Calendar,
    Mail,
    Sparkles,
    LayoutDashboard,
    KeyRound,
    CreditCard,
    GitBranch,
    Radio,
    Globe,
    Lock,
    Database,
    Cloud,
} from 'lucide-react';

// Showcase of Phase 11-15 capabilities — shown on landing page before auth
const enterpriseShowcase = [
    {
        icon: Brain,
        title: 'Multi-Agent AI Monitoring',
        desc: '6 specialized LLM agents score every model call for hallucination, prompt-injection, cost & quality in real-time.',
        color: 'from-fuchsia-500/20 to-pink-500/20',
        border: 'border-fuchsia-500/30',
        tag: 'NEW',
    },
    {
        icon: Network,
        title: 'D3 Service Map + APM Traces',
        desc: 'Force-directed dependency graph, live OTLP trace ingestion, blast-radius overlays. Datadog-grade visualization.',
        color: 'from-blue-500/20 to-cyan-500/20',
        border: 'border-blue-500/30',
        tag: 'NEW',
    },
    {
        icon: GitBranch,
        title: 'N8n Automation Templates',
        desc: 'One-click push of pre-built incident workflows (alert → Slack → JIRA → PagerDuty) into your N8n instance.',
        color: 'from-orange-500/20 to-red-500/20',
        border: 'border-orange-500/30',
        tag: 'NEW',
    },
    {
        icon: Cloud,
        title: 'AWS Deploy Wizard',
        desc: 'Generate Terraform + ECR + Fargate + DocumentDB plans in 60 seconds. Zero-touch enterprise rollout.',
        color: 'from-amber-500/20 to-yellow-500/20',
        border: 'border-amber-500/30',
        tag: 'NEW',
    },
    {
        icon: FileDown,
        title: 'Branded Enterprise PDF Reports',
        desc: 'AI-generated CSO briefings with SLA charts, severity tables, tenant logo. DOCX + Excel + PDF.',
        color: 'from-orange-500/20 to-amber-500/20',
        border: 'border-orange-500/30',
        tag: 'NEW',
    },
    {
        icon: FileSpreadsheet,
        title: 'Excel / CSV / DOCX Upload',
        desc: 'Drop any alerts file — AI rebuilds a polished weekly report in the Fasah format.',
        color: 'from-emerald-500/20 to-teal-500/20',
        border: 'border-emerald-500/30',
        tag: 'NEW',
    },
    {
        icon: LayoutDashboard,
        title: 'Drag-and-Drop Dashboard',
        desc: '10 live widgets (SOC, Uptime, SLA, Threats, AI Agents). Save per-user. Datadog-style.',
        color: 'from-cyan-500/20 to-blue-500/20',
        border: 'border-cyan-500/30',
        tag: 'NEW',
    },
    {
        icon: Layers,
        title: 'Report Template Builder',
        desc: '12 drag-drop section types. Build custom weekly report layouts per tenant.',
        color: 'from-purple-500/20 to-fuchsia-500/20',
        border: 'border-purple-500/30',
        tag: 'NEW',
    },
    {
        icon: Calendar,
        title: 'Scheduled Reports (Cron)',
        desc: 'Auto-generate every Sun/Mon 9 AM. Email DOCX+Excel+PDF via Resend. Per-tenant schedules.',
        color: 'from-pink-500/20 to-rose-500/20',
        border: 'border-pink-500/30',
    },
    {
        icon: KeyRound,
        title: 'Portal OTP + Password',
        desc: 'Shareable links with expiry, password, 6-digit email OTP. Full access audit log.',
        color: 'from-red-500/20 to-orange-500/20',
        border: 'border-red-500/30',
        tag: 'NEW',
    },
    {
        icon: Building,
        title: 'Multi-Tenant Branding',
        desc: 'Per-tenant logo, colors, footer. Applied to every generated PDF automatically.',
        color: 'from-indigo-500/20 to-blue-500/20',
        border: 'border-indigo-500/30',
    },
    {
        icon: Brain,
        title: 'AI Multi-Agent System',
        desc: 'RCA, Summarizer, Healer agents using CrewAI pattern with persistent memory.',
        color: 'from-violet-500/20 to-purple-500/20',
        border: 'border-violet-500/30',
    },
    {
        icon: Radio,
        title: 'SOC Live Feed',
        desc: 'Real-time WebSocket feed of security events, threats, UEBA anomalies, attack sims.',
        color: 'from-red-500/20 to-pink-500/20',
        border: 'border-red-500/30',
    },
    {
        icon: Globe,
        title: 'Multi-Region Uptime',
        desc: 'Synthetic probes from multiple regions. WhatsApp + Email alerts on downtime.',
        color: 'from-emerald-500/20 to-green-500/20',
        border: 'border-emerald-500/30',
    },
    {
        icon: CreditCard,
        title: 'Stripe Usage Billing',
        desc: 'Datadog-style metered billing. Plan tracking, usage events, webhook sync.',
        color: 'from-purple-500/20 to-violet-500/20',
        border: 'border-purple-500/30',
    },
    {
        icon: Cloud,
        title: 'AWS-Native (ECR+Fargate)',
        desc: 'Terraform-ready. Secrets Manager, S3 reports, DocumentDB, ALB. One-command deploy.',
        color: 'from-amber-500/20 to-yellow-500/20',
        border: 'border-amber-500/30',
    },
];

const stats = [
    { value: '73%', label: 'Noise Reduction', icon: TrendingDown },
    { value: '60%', label: 'Faster MTTR', icon: Clock },
    { value: '99.9%', label: 'SLA Compliance', icon: Target },
    { value: '24/7', label: 'AI Vigilance', icon: Eye },
];

const features = [
    {
        icon: Brain,
        title: 'AI ROOT CAUSE ANALYSIS',
        description: 'LLM-powered deep analysis identifies root causes in seconds. Automated incident correlation and blast radius calculation.',
        accent: 'cyan',
    },
    {
        icon: Zap,
        title: 'INTELLIGENT CORRELATION',
        description: 'Multi-algorithm anomaly detection with smart event deduplication and topology-aware correlation reduces noise by 80%.',
        accent: 'gold',
    },
    {
        icon: Activity,
        title: 'MTTR ACCELERATION',
        description: 'Automated runbooks, AI-suggested remediation, and one-click execution cuts mean time to resolution by 60%.',
        accent: 'cyan',
    },
    {
        icon: Shield,
        title: 'SLA PROTECTION',
        description: 'Predictive capacity forecasting and early warning system prevents SLA breaches before they happen.',
        accent: 'gold',
    },
];

const coreCapabilities = [
    {
        icon: Brain, title: 'Core AIOps Hub', path: '/core-aiops',
        description: 'Unified command center with drill-down into all 12 AI capabilities. System health ring, pipeline status, and one-click access.',
        stat: '12 AI Layers', color: 'from-cyan-500/20 to-blue-500/20', border: 'border-cyan-500/20',
    },
    {
        icon: Zap, title: 'Anomaly Detection', path: '/aiops-brain',
        description: 'Z-score, EWMA, Isolation Forest, Dynamic Thresholds, and Seasonal Decomposition - 5 algorithms running in parallel.',
        stat: '5 Algorithms', color: 'from-purple-500/20 to-violet-500/20', border: 'border-purple-500/20',
    },
    {
        icon: AlertTriangle, title: 'Alert Engine', path: '/alert-engine',
        description: 'Centralized alert management with severity routing, auto-escalation, deduplication, and real-time severity distribution.',
        stat: 'Real-time', color: 'from-red-500/20 to-orange-500/20', border: 'border-red-500/20',
    },
    {
        icon: Target, title: 'Incident Management', path: '/incident-engine',
        description: 'Full lifecycle tracking with auto-correlation, war room collaboration, and MTTR analytics per service.',
        stat: 'Full Lifecycle', color: 'from-amber-500/20 to-yellow-500/20', border: 'border-amber-500/20',
    },
    {
        icon: Eye, title: 'NOC Dashboard', path: '/noc-dashboard',
        description: 'Enterprise NOC overview with infrastructure fleet grid, application health monitoring, and live alert feed.',
        stat: '3 Views', color: 'from-teal-500/20 to-emerald-500/20', border: 'border-teal-500/20',
    },
    {
        icon: BarChart3, title: 'AI Event Analyzer', path: '/event-analyzer',
        description: 'Upload event files or receive webhooks for AI-powered pattern detection, root cause analysis, and knowledge learning.',
        stat: 'LLM-Powered', color: 'from-indigo-500/20 to-blue-500/20', border: 'border-indigo-500/20',
    },
];

const enterpriseFeatures = [
    {
        icon: BarChart3, title: 'Executive Reports',
        description: 'Multi-sheet Excel and PDF reports with severity charts, heatmaps, timeline analysis, and client branding.',
        stat: 'Excel + PDF',
    },
    {
        icon: Clock, title: 'Automated Scheduling',
        description: 'Configure daily, weekly, or monthly report delivery to stakeholders with custom branding and email subjects.',
        stat: 'Auto-Send',
    },
    {
        icon: Server, title: 'Monitoring Agent',
        description: 'Lightweight FalconOps agent collects CPU, memory, disk, and network metrics with one-command install.',
        stat: 'Self-Install',
    },
    {
        icon: Network, title: 'Service Topology',
        description: 'Visual dependency mapping with real-time health overlays, traceroute analysis, and blast radius visualization.',
        stat: 'Auto-Discovery',
    },
    {
        icon: Cpu, title: 'Capacity Prediction',
        description: 'Linear regression forecasting for CPU, memory, and disk with exhaustion date prediction per server.',
        stat: 'Predictive',
    },
    {
        icon: Activity, title: 'Runbook Automation',
        description: 'Step-by-step automated playbooks with templates, scheduling, approval workflows, and execution history.',
        stat: 'No-Code',
    },
];

const integrations = [
    { name: 'AppDynamics', icon: Server },
    { name: 'Dynatrace', icon: Cpu },
    { name: 'Elastic Stack', icon: BarChart3 },
    { name: 'Prometheus', icon: Activity },
    { name: 'SolarWinds', icon: Network },
    { name: 'Site24x7', icon: Eye },
];

const pricing = [
    {
        name: 'TRIAL',
        price: 'Free',
        period: '14 days',
        description: 'Perfect for evaluation',
        features: [
            'Up to 3 users',
            '5 servers monitored',
            '10 uptime monitors',
            'Basic monitoring',
            'Dashboard access',
            'Email support',
        ],
        cta: 'Start Free Trial',
        popular: false,
    },
    {
        name: 'STANDARD',
        price: '$299',
        period: '/month',
        description: 'For small teams',
        features: [
            'Up to 10 users',
            '25 servers monitored',
            '50 uptime monitors',
            'Reports & API access',
            'Email alerting',
            'Priority support',
        ],
        cta: 'Get Started',
        popular: false,
    },
    {
        name: 'PROFESSIONAL',
        price: '$799',
        period: '/month',
        description: 'For growing organizations',
        features: [
            'Up to 50 users',
            '100 servers monitored',
            '200 uptime monitors',
            'APM & Network Topology',
            'Runbook automation',
            'AI Root Cause Analysis',
        ],
        cta: 'Get Started',
        popular: true,
    },
    {
        name: 'ENTERPRISE',
        price: 'Custom',
        period: '',
        description: 'For large enterprises',
        features: [
            'Unlimited users & servers',
            'On-premise deployment',
            'AI Copilot & Multi-tenancy',
            'SSO & Audit logs',
            'Custom integrations',
            'White-label option',
            'Dedicated success manager',
        ],
        cta: 'Contact Sales',
        popular: false,
    },
];

export const LandingPage = () => {
    const { language, isRTL } = useLanguage();
    const navigate = useNavigate();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [scrolled, setScrolled] = useState(false);

    // Map landing-page plan names → backend pricing plan ids used by /signup?plan=<id>
    const PLAN_ID_MAP = {
        TRIAL: 'trial',
        STANDARD: 'standard',
        PROFESSIONAL: 'professional',
        ENTERPRISE: 'enterprise',
    };

    const handlePlanCTA = (plan) => {
        const planId = PLAN_ID_MAP[plan.name] || 'trial';
        if (planId === 'enterprise') {
            // Enterprise → dedicated sales page (Pricing has built-in contact modal)
            navigate('/pricing?contact=enterprise');
            return;
        }
        // All other plans → signup funnel with plan pre-selected → routes into /billing after signup
        navigate(`/signup?plan=${encodeURIComponent(planId)}`);
    };

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 50);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <div className={`min-h-screen bg-[#0B0F14] ${isRTL ? 'rtl' : 'ltr'}`}>
            {/* Scanline effect */}
            <div className="scanline" />
            
            {/* Navigation */}
            <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? 'glass-strong' : ''}`}>
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16 lg:h-20">
                        <Link to="/" className="flex items-center gap-3" data-testid="logo-link">
                            <FalconLogo size={40} />
                            <span className="font-heading font-semibold text-xl tracking-wide flex items-baseline gap-0.5">
                                <span className="text-[#F5B841]">FALCON</span>
                                <span className="text-white">OPS</span>
                                <span className="text-[#00E0FF] text-sm ml-1">AI</span>
                            </span>
                        </Link>
                        
                        {/* Desktop Nav */}
                        <nav className="hidden lg:flex items-center gap-8">
                            <Link to="/about" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'من نحن' : 'About'}
                            </Link>
                            <Link to="/services" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'الخدمات' : 'Services'}
                            </Link>
                            <Link to="/ai-platform" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'المنصة' : 'Platform'}
                            </Link>
                            <Link to="/security" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'الأمان' : 'Security'}
                            </Link>
                            <Link to="/pricing" data-testid="nav-pricing-link" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'الأسعار' : 'Pricing'}
                            </Link>
                            <Link to="/login" data-testid="login-link" className="text-sm text-white/60 hover:text-white uppercase tracking-wider font-medium transition-colors">
                                {language === 'ar' ? 'دخول' : 'Login'}
                            </Link>
                            <LanguageToggle />
                            <Button asChild data-testid="get-started-btn" className="bg-[#F5B841] text-black hover:bg-[#F5B841]/90 font-bold uppercase tracking-wider rounded-lg px-6">
                                <Link to="/register">{language === 'ar' ? 'ابدأ الآن' : 'Get Started'}</Link>
                            </Button>
                        </nav>

                        {/* Mobile Nav */}
                        <div className="flex items-center gap-3 lg:hidden">
                            <LanguageToggle />
                            <button
                                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                                className="p-2 text-white/70 hover:text-white"
                                data-testid="mobile-menu-btn"
                            >
                                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Mobile Menu */}
                {mobileMenuOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="lg:hidden glass-strong border-t border-white/10"
                    >
                        <div className="px-4 py-4 space-y-3">
                            <Link to="/about" className="block py-2 text-white/70 hover:text-white uppercase tracking-wider text-sm">About</Link>
                            <Link to="/services" className="block py-2 text-white/70 hover:text-white uppercase tracking-wider text-sm">Services</Link>
                            <Link to="/ai-platform" className="block py-2 text-white/70 hover:text-white uppercase tracking-wider text-sm">Platform</Link>
                            <Link to="/pricing" className="block py-2 text-white/70 hover:text-white uppercase tracking-wider text-sm" data-testid="mobile-pricing-link">Pricing</Link>
                            <Link to="/login" className="block py-2 text-white/70 hover:text-white uppercase tracking-wider text-sm">Login</Link>
                            <Button asChild className="w-full bg-[#F5B841] text-black font-bold uppercase tracking-wider rounded-lg">
                                <Link to="/register">Get Started</Link>
                            </Button>
                        </div>
                    </motion.div>
                )}
            </header>

            {/* Hero Section */}
            <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
                {/* Background */}
                <div className="absolute inset-0">
                    {/* Hero image with overlay */}
                    <div 
                        className="absolute inset-0 bg-cover bg-center opacity-30"
                        style={{ 
                            backgroundImage: 'url(https://images.unsplash.com/photo-1663900108404-a05e8bf82cda?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzd8MHwxfHNlYXJjaHwxfHxmdXR1cmlzdGljJTIwc2F1ZGklMjBhcmFiaWElMjBjaXR5JTIwbmlnaHQlMjBza3lsaW5lfGVufDB8fHx8MTc3MTg4Njk1NXww&ixlib=rb-4.1.0&q=85)'
                        }}
                    />
                    {/* Grid overlay */}
                    <div className="absolute inset-0 obsidian-grid opacity-50" />
                    {/* Gradient overlays */}
                    <div className="absolute inset-0 bg-gradient-to-b from-[#0B0F14] via-transparent to-[#0B0F14]" />
                    <div className="absolute top-0 left-0 w-1/2 h-full bg-gradient-to-r from-[#0B0F14] to-transparent" />
                    {/* Gold glow accent */}
                    <div 
                        className="absolute top-1/4 right-1/4 w-[600px] h-[600px] rounded-full blur-3xl opacity-20"
                        style={{ background: 'radial-gradient(circle, rgba(245, 184, 65, 0.4) 0%, transparent 70%)' }}
                    />
                    {/* Cyan glow accent */}
                    <div 
                        className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] rounded-full blur-3xl opacity-15"
                        style={{ background: 'radial-gradient(circle, rgba(0, 224, 255, 0.4) 0%, transparent 70%)' }}
                    />
                </div>

                <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
                    <div className="grid lg:grid-cols-12 gap-12 lg:gap-8 items-center">
                        {/* Left Content */}
                        <motion.div
                            initial={{ opacity: 0, x: -40 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.6 }}
                            className="lg:col-span-7"
                        >
                            {/* Badge */}
                            <div className="inline-flex items-center gap-2 px-4 py-2 mb-8 border border-[#00E0FF]/30 bg-[#00E0FF]/5 rounded-lg">
                                <div className="live-dot" />
                                <span className="text-[#00E0FF] text-sm font-mono uppercase tracking-wider">
                                    {language === 'ar' ? 'ذكاء اصطناعي للعمليات' : 'AI-Powered Operations'}
                                </span>
                            </div>

                            {/* Headline */}
                            <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl xl:text-7xl tracking-tight uppercase leading-[0.9] mb-6">
                                {language === 'ar' ? (
                                    <>
                                        <span className="text-white">تقليل ضوضاء التنبيهات</span>
                                        <br />
                                        <span className="text-[#F5B841]">بنسبة 73%</span>
                                    </>
                                ) : (
                                    <>
                                        <span className="text-white">Intelligent</span>
                                        <br />
                                        <span className="text-white">Monitoring.</span>
                                        <br />
                                        <span className="text-[#00E0FF]">Autonomous</span>
                                        <span className="text-[#F5B841]"> Ops.</span>
                                    </>
                                )}
                            </h1>

                            <p className="text-lg text-white/60 mb-8 max-w-xl leading-relaxed">
                                {language === 'ar' 
                                    ? 'طبقة الذكاء الاصطناعي للحوادث التي تعمل فوق أدوات المراقبة الحالية لديك. ربط ذكي للتنبيهات، وتحليل السبب الجذري، والحل التلقائي.'
                                    : 'Enterprise AI-Driven Availability & AIOps Platform. Smart alert correlation, AI root cause analysis, and autonomous incident resolution.'}
                            </p>

                            {/* CTA Buttons */}
                            <div className="flex flex-col sm:flex-row gap-4 mb-12">
                                <Button 
                                    asChild 
                                    size="lg" 
                                    data-testid="hero-cta-btn" 
                                    className="bg-[#F5B841] text-black hover:bg-[#F5B841]/90 font-bold uppercase tracking-wider rounded-lg px-8 h-14"
                                >
                                    <Link to="/register">
                                        {language === 'ar' ? 'ابدأ التجربة المجانية' : 'Start Free Trial'}
                                        <ArrowRight className={`w-5 h-5 ${isRTL ? 'mr-2 rotate-180' : 'ml-2'}`} />
                                    </Link>
                                </Button>
                                <Button 
                                    variant="outline" 
                                    size="lg" 
                                    asChild
                                    className="border-cyan-500/30 hover:bg-cyan-500/10 text-cyan-400 uppercase tracking-wider rounded-sm px-8 h-14"
                                >
                                    <a href="#demo">
                                        <Play className={`w-5 h-5 ${isRTL ? 'ml-2' : 'mr-2'}`} />
                                        {language === 'ar' ? 'جرب العرض' : 'Try Live Demo'}
                                    </a>
                                </Button>
                            </div>

                            {/* Trust indicators */}
                            <div className="flex flex-wrap items-center gap-6 text-sm text-white/40">
                                <div className="flex items-center gap-2">
                                    <Shield className="w-4 h-4 text-primary" />
                                    <span className="uppercase tracking-wider">{language === 'ar' ? 'أمان المؤسسات' : 'Enterprise Security'}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Server className="w-4 h-4 text-cyan-400" />
                                    <span className="uppercase tracking-wider">{language === 'ar' ? 'نشر محلي' : 'On-Premise Ready'}</span>
                                </div>
                            </div>
                        </motion.div>

                        {/* Right - Dashboard Preview */}
                        <motion.div
                            initial={{ opacity: 0, x: 40 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.6, delay: 0.2 }}
                            className="lg:col-span-5 hidden lg:block"
                        >
                            <div className="relative">
                                {/* Glow behind */}
                                <div className="absolute -inset-4 bg-gradient-to-r from-primary/20 via-cyan-500/10 to-primary/20 rounded-sm blur-2xl opacity-50" />
                                
                                {/* Dashboard card */}
                                <div className="relative bg-black/60 backdrop-blur-xl border border-white/10 rounded-sm overflow-hidden">
                                    {/* Browser chrome */}
                                    <div className="flex items-center gap-2 px-4 py-3 bg-black/50 border-b border-white/10">
                                        <div className="flex gap-1.5">
                                            <div className="w-3 h-3 rounded-full bg-red-500/60" />
                                            <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                                            <div className="w-3 h-3 rounded-full bg-green-500/60" />
                                        </div>
                                        <div className="flex-1 text-center">
                                            <span className="text-xs text-white/40 font-mono">falconapps.com/dashboard</span>
                                        </div>
                                    </div>

                                    {/* Dashboard content */}
                                    <div className="p-4 space-y-4">
                                        {/* Stats row */}
                                        <div className="grid grid-cols-4 gap-2">
                                            {[
                                                { label: 'ALERTS', value: '12', color: 'text-red-400' },
                                                { label: 'INCIDENTS', value: '3', color: 'text-yellow-400' },
                                                { label: 'MTTR', value: '14m', color: 'text-cyan-400' },
                                                { label: 'SLA', value: '99.2%', color: 'text-green-400' },
                                            ].map((stat, i) => (
                                                <div key={i} className="p-2 bg-white/5 border border-white/5 rounded-sm">
                                                    <p className="text-[10px] text-white/40 font-mono uppercase">{stat.label}</p>
                                                    <p className={`font-heading font-bold text-lg ${stat.color}`}>{stat.value}</p>
                                                </div>
                                            ))}
                                        </div>

                                        {/* AI Analysis card */}
                                        <div className="p-3 bg-cyan-500/5 border border-cyan-500/20 rounded-sm">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-sm bg-cyan-500/20 flex items-center justify-center">
                                                    <Brain className="w-5 h-5 text-cyan-400" />
                                                </div>
                                                <div className="flex-1">
                                                    <p className="text-sm font-medium text-white">Payment Service - CPU Saturation</p>
                                                    <p className="text-xs text-white/50">Confidence: 94% • 12s detection</p>
                                                </div>
                                                <div className="px-2 py-1 bg-cyan-500/20 text-cyan-400 text-xs font-mono uppercase rounded-sm">
                                                    AI
                                                </div>
                                            </div>
                                        </div>

                                        {/* Alert list */}
                                        <div className="space-y-2">
                                            {[
                                                { severity: 'critical', title: 'High CPU on payment-svc', time: '2m' },
                                                { severity: 'warning', title: 'Memory spike on api-gw', time: '5m' },
                                                { severity: 'info', title: 'Deployment completed', time: '12m' },
                                            ].map((alert, i) => (
                                                <div key={i} className="flex items-center justify-between p-2 bg-white/5 rounded-sm">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-2 h-2 rounded-full ${
                                                            alert.severity === 'critical' ? 'bg-red-500 animate-pulse' :
                                                            alert.severity === 'warning' ? 'bg-yellow-500' : 'bg-cyan-500'
                                                        }`} />
                                                        <span className="text-xs text-white/80">{alert.title}</span>
                                                    </div>
                                                    <span className="text-[10px] text-white/40 font-mono">{alert.time}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* Floating badge */}
                                <div className="absolute -bottom-4 -left-4 px-4 py-3 bg-black/80 backdrop-blur-xl border border-green-500/30 rounded-sm">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-sm bg-green-500/20 flex items-center justify-center">
                                            <TrendingDown className="w-5 h-5 text-green-400" />
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-white/40 uppercase tracking-wider">Noise Reduced</p>
                                            <p className="font-heading font-bold text-xl text-green-400">-73%</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                </div>

                {/* Scroll indicator */}
                <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
                    <motion.div
                        animate={{ y: [0, 8, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        className="w-6 h-10 rounded-full border border-white/20 flex items-start justify-center p-2"
                    >
                        <div className="w-1 h-2 bg-white/40 rounded-full" />
                    </motion.div>
                </div>
            </section>

            {/* Stats Section */}
            <section className="relative py-20 border-y border-white/10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
                        {stats.map((stat, idx) => {
                            const Icon = stat.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                    className="text-center lg:text-left"
                                >
                                    <div className="inline-flex items-center justify-center lg:justify-start gap-3 mb-3">
                                        <div className="w-12 h-12 rounded-sm bg-primary/10 border border-primary/20 flex items-center justify-center">
                                            <Icon className="w-6 h-6 text-primary" />
                                        </div>
                                    </div>
                                    <p className="font-heading font-bold text-4xl lg:text-5xl text-white mb-1">{stat.value}</p>
                                    <p className="text-sm text-white/50 uppercase tracking-wider">{stat.label}</p>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Interactive Demo Section */}
            <section id="demo" className="py-24 relative bg-[#050505]">
                <div className="absolute inset-0 obsidian-grid opacity-20" />
                <div 
                    className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] rounded-full blur-3xl opacity-10"
                    style={{ background: 'radial-gradient(circle, rgba(0, 224, 255, 0.4) 0%, transparent 70%)' }}
                />
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
                    <div className="mb-12">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            className="text-center"
                        >
                            <div className="inline-flex items-center gap-2 px-4 py-2 mb-6 border border-cyan-500/30 bg-cyan-500/5 rounded-lg">
                                <Play className="w-4 h-4 text-cyan-400" />
                                <span className="text-cyan-400 text-sm font-mono uppercase tracking-wider">
                                    {language === 'ar' ? 'عرض تفاعلي' : 'Interactive Demo'}
                                </span>
                            </div>
                            <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-4">
                                {language === 'ar' ? 'شاهد المنصة في العمل' : 'See It In Action'}
                            </h2>
                            <p className="text-white/50 max-w-2xl mx-auto">
                                {language === 'ar' 
                                    ? 'جرب منصة FalconOps AI مع بيانات محاكاة حية. شاهد كيف يقوم الذكاء الاصطناعي بتحليل وربط التنبيهات في الوقت الفعلي.'
                                    : 'Experience FalconOps AI with live simulated data. Watch how AI analyzes and correlates alerts in real-time.'}
                            </p>
                        </motion.div>
                    </div>

                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        viewport={{ once: true }}
                    >
                        <InteractiveDemo />
                    </motion.div>

                    {/* CTA after demo */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.4 }}
                        viewport={{ once: true }}
                        className="mt-12 text-center"
                    >
                        <p className="text-white/50 mb-6">
                            {language === 'ar' ? 'هل أعجبك ما رأيت؟ ابدأ تجربتك المجانية الآن.' : 'Like what you see? Start your free trial today.'}
                        </p>
                        <div className="flex items-center justify-center gap-4">
                            <Button 
                                asChild 
                                className="bg-[#F5B841] text-black hover:bg-[#F5B841]/90 font-bold uppercase tracking-wider rounded-sm px-8"
                            >
                                <Link to="/register">
                                    {language === 'ar' ? 'ابدأ التجربة المجانية' : 'Start Free Trial'}
                                    <ArrowRight className="w-4 h-4 ml-2" />
                                </Link>
                            </Button>
                            <Button 
                                variant="outline"
                                asChild
                                className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-sm px-8"
                            >
                                <Link to="/login">
                                    {language === 'ar' ? 'تسجيل الدخول' : 'Login to Dashboard'}
                                </Link>
                            </Button>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Features Section */}
            <section className="py-24 relative">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="mb-16">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                        >
                            <p className="text-primary font-mono text-sm uppercase tracking-wider mb-4">// CAPABILITIES</p>
                            <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-4">
                                {language === 'ar' ? 'ذكاء مؤسسي' : 'Enterprise Intelligence'}
                            </h2>
                            <p className="text-white/50 max-w-2xl">
                                {language === 'ar' 
                                    ? 'مُصمم لفرق NOC التي تتطلب الموثوقية والسرعة والرؤى القابلة للتنفيذ.'
                                    : 'Built for NOC teams who demand reliability, speed, and actionable insights.'}
                            </p>
                        </motion.div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-6">
                        {features.map((feature, idx) => {
                            const Icon = feature.icon;
                            const isCyan = feature.accent === 'cyan';
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className={`bg-[#0a0a0a] border-white/5 hover:border-${isCyan ? 'cyan-500' : 'primary'}/30 transition-all duration-300 h-full group rounded-sm`}>
                                        <CardContent className="p-8">
                                            <div className={`w-14 h-14 rounded-sm ${isCyan ? 'bg-cyan-500/10 border-cyan-500/20' : 'bg-primary/10 border-primary/20'} border flex items-center justify-center mb-6 group-hover:scale-110 transition-transform`}>
                                                <Icon className={`w-7 h-7 ${isCyan ? 'text-cyan-400' : 'text-primary'}`} />
                                            </div>
                                            <h3 className="font-heading font-bold text-xl text-white uppercase tracking-wider mb-3">
                                                {feature.title}
                                            </h3>
                                            <p className="text-white/50 leading-relaxed">
                                                {feature.description}
                                            </p>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Enterprise Showcase — Phase 11-15 features */}
            <section id="enterprise-showcase" className="py-24 relative border-t border-white/10" data-testid="enterprise-showcase">
                <div className="absolute inset-0 obsidian-grid opacity-20" />
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
                    <div className="mb-14 text-center md:text-left">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                        >
                            <p className="text-[#F5B841] font-mono text-sm uppercase tracking-wider mb-4">
                                // ENTERPRISE READY · V2026.02
                            </p>
                            <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-4">
                                {language === 'ar' ? 'منصة متكاملة للأمن والعمليات' : 'The Full SaaS Stack for SOC + AIOps'}
                            </h2>
                            <p className="text-white/50 max-w-2xl text-base md:text-lg">
                                {language === 'ar'
                                    ? 'تقارير بتنسيق Fasah، تسليم بريد إلكتروني مجدول، لوحات تحكم مخصصة، وبوابة عميل آمنة.'
                                    : 'From Fasah-format PDF reports to scheduled email delivery, drag-drop dashboards, and secure client portals — everything you need to ship enterprise observability.'}
                            </p>
                        </motion.div>
                    </div>

                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {enterpriseShowcase.map((f, idx) => {
                            const Icon = f.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.35, delay: (idx % 4) * 0.05 }}
                                    viewport={{ once: true }}
                                    className={`relative h-full p-5 bg-[#0a0a0a] border ${f.border} hover:border-white/40 rounded-sm group cursor-pointer overflow-hidden`}
                                    data-testid={`showcase-card-${idx}`}
                                >
                                    {/* Animated corner accent */}
                                    <div className={`absolute -top-10 -right-10 w-24 h-24 rounded-full bg-gradient-to-br ${f.color} blur-2xl opacity-50 group-hover:opacity-100 transition-opacity`} />
                                    {f.tag && (
                                        <span className="absolute top-2 right-2 text-[9px] font-mono uppercase tracking-wider text-[#F5B841] bg-[#F5B841]/10 border border-[#F5B841]/30 px-1.5 py-0.5 rounded-sm">
                                            {f.tag}
                                        </span>
                                    )}
                                    <div className={`w-10 h-10 rounded-sm bg-gradient-to-br ${f.color} border ${f.border} flex items-center justify-center mb-3 group-hover:scale-110 transition-transform`}>
                                        <Icon className="w-5 h-5 text-white" />
                                    </div>
                                    <h3 className="font-heading font-bold text-sm text-white uppercase tracking-wider mb-2 leading-tight">
                                        {f.title}
                                    </h3>
                                    <p className="text-white/50 text-xs leading-relaxed">
                                        {f.desc}
                                    </p>
                                </motion.div>
                            );
                        })}
                    </div>

                    <motion.div
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        className="mt-10 flex flex-wrap items-center justify-center gap-3"
                    >
                        <Link to="/register">
                            <Button className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black font-bold uppercase tracking-wider" data-testid="showcase-cta-register">
                                <ArrowRight className="w-4 h-4 mr-2" /> Start Free Trial
                            </Button>
                        </Link>
                        <a href="#demo">
                            <Button variant="outline" className="border-white/20 text-white hover:bg-white/10 uppercase tracking-wider" data-testid="showcase-cta-demo">
                                <Play className="w-4 h-4 mr-2" /> Watch Demo
                            </Button>
                        </a>
                        <Link to="/pricing">
                            <Button variant="ghost" className="text-white/70 hover:text-white uppercase tracking-wider text-xs" data-testid="showcase-cta-pricing">
                                View pricing →
                            </Button>
                        </Link>
                    </motion.div>
                </div>
            </section>

            {/* Core AI Capabilities Section */}
            <section className="py-24 relative bg-[#050505]">
                <div className="absolute inset-0 obsidian-grid opacity-30" />
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
                    <div className="mb-16">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                        >
                            <p className="text-cyan-400 font-mono text-sm uppercase tracking-wider mb-4">// CORE AI CAPABILITIES</p>
                            <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-4">
                                {language === 'ar' ? '6 طبقات ذكاء' : '6-Layer AIOps Brain'}
                            </h2>
                            <p className="text-white/50 max-w-2xl">
                                {language === 'ar' 
                                    ? 'من استيعاب البيانات إلى الأتمتة المستقلة - كل طبقة تجعل عملياتك أكثر ذكاءً.'
                                    : 'From data ingestion to autonomous remediation - each layer makes your operations smarter.'}
                            </p>
                        </motion.div>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {coreCapabilities.map((cap, idx) => {
                            const Icon = cap.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.08 }}
                                    viewport={{ once: true }}
                                >
                                    <div className={`h-full p-6 bg-[#0a0a0a] border ${cap.border} hover:border-white/30 rounded-sm transition-all duration-300 group cursor-pointer`}>
                                        <div className="flex items-start gap-4">
                                            <div className={`w-12 h-12 rounded-sm bg-gradient-to-br ${cap.color} border ${cap.border} flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform`}>
                                                <Icon className="w-6 h-6 text-white" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="font-heading font-bold text-sm text-white uppercase tracking-wider mb-2">
                                                    {cap.title}
                                                </h3>
                                                <p className="text-white/50 text-sm leading-relaxed mb-3">
                                                    {cap.description}
                                                </p>
                                                <div className="inline-flex items-center gap-2 px-2 py-1 bg-white/5 rounded-sm">
                                                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                                                    <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">{cap.stat}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </div>

                    {/* Enterprise Features Grid */}
                    <div className="mt-16">
                        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
                            <p className="text-[#F5B841] font-mono text-sm uppercase tracking-wider mb-4">// ENTERPRISE FEATURES</p>
                            <h3 className="font-heading font-bold text-2xl md:text-3xl uppercase tracking-tight text-white mb-8">
                                {language === 'ar' ? 'أدوات مؤسسية' : 'Built for Enterprise'}
                            </h3>
                        </motion.div>

                        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {enterpriseFeatures.map((feat, idx) => {
                                const Icon = feat.icon;
                                return (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, y: 15 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.3, delay: idx * 0.06 }}
                                        viewport={{ once: true }}
                                    >
                                        <div className="flex items-center gap-3 p-4 bg-[#0a0a0a] border border-white/5 hover:border-white/20 rounded-sm transition-all group">
                                            <div className="w-10 h-10 rounded-sm bg-[#F5B841]/10 border border-[#F5B841]/20 flex items-center justify-center shrink-0">
                                                <Icon className="w-5 h-5 text-[#F5B841]" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between">
                                                    <h4 className="text-sm font-bold text-white uppercase tracking-wider">{feat.title}</h4>
                                                    <span className="text-[10px] font-mono text-[#F5B841] uppercase ml-2">{feat.stat}</span>
                                                </div>
                                                <p className="text-white/40 text-xs leading-relaxed mt-1">{feat.description}</p>
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })}
                        </div>
                    </div>

                    {/* On-Premise Banner */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.5 }}
                        viewport={{ once: true }}
                        className="mt-12"
                    >
                        <div className="p-8 bg-gradient-to-r from-primary/5 via-transparent to-cyan-500/5 border border-white/10 rounded-sm">
                            <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
                                <div className="flex items-center gap-4">
                                    <div className="w-14 h-14 rounded-sm bg-primary/10 border border-primary/20 flex items-center justify-center">
                                        <Shield className="w-7 h-7 text-primary" />
                                    </div>
                                    <div>
                                        <h3 className="font-heading font-bold text-lg text-white uppercase tracking-wider mb-1">
                                            {language === 'ar' ? 'جاهز للنشر المحلي' : 'Multi-Tenant & On-Premise Ready'}
                                        </h3>
                                        <p className="text-white/50 text-sm">
                                            {language === 'ar' 
                                                ? 'عزل كامل للبيانات مع دعم متعدد المستأجرين ونشر Docker.'
                                                : 'Full data isolation with multi-tenancy support, monitoring agents, and Docker deployment.'}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 flex-wrap">
                                    <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-sm">
                                        <Server className="w-4 h-4 text-emerald-400" />
                                        <span className="text-xs text-emerald-400 font-mono uppercase">Self-Hosted</span>
                                    </div>
                                    <div className="flex items-center gap-2 px-3 py-1.5 bg-cyan-500/10 border border-cyan-500/20 rounded-sm">
                                        <Brain className="w-4 h-4 text-cyan-400" />
                                        <span className="text-xs text-cyan-400 font-mono uppercase">Multi-Tenant</span>
                                    </div>
                                    <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-sm">
                                        <Eye className="w-4 h-4 text-purple-400" />
                                        <span className="text-xs text-purple-400 font-mono uppercase">Monitoring Agent</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Integrations */}
            <section className="py-20 border-y border-white/10 bg-[#0a0a0a]">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-12">
                        <p className="text-cyan-400 font-mono text-sm uppercase tracking-wider mb-4">// INTEGRATIONS</p>
                        <h2 className="font-heading font-bold text-2xl md:text-4xl uppercase tracking-tight text-white">
                            {language === 'ar' ? 'يعمل مع أدواتك' : 'Works With Your Stack'}
                        </h2>
                    </div>
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                        {integrations.map((integration, idx) => {
                            const Icon = integration.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, scale: 0.9 }}
                                    whileInView={{ opacity: 1, scale: 1 }}
                                    transition={{ duration: 0.3, delay: idx * 0.05 }}
                                    viewport={{ once: true }}
                                    className="p-6 bg-white/5 border border-white/5 rounded-sm hover:border-primary/30 transition-colors text-center group"
                                >
                                    <Icon className="w-8 h-8 text-white/40 group-hover:text-primary mx-auto mb-3 transition-colors" />
                                    <p className="text-xs text-white/60 font-mono uppercase tracking-wider">{integration.name}</p>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Pricing Section */}
            <section id="pricing" className="py-24 relative">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="text-center mb-16">
                        <p className="text-primary font-mono text-sm uppercase tracking-wider mb-4">// PRICING</p>
                        <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-4">
                            {language === 'ar' ? 'تسعير بسيط وشفاف' : 'Simple, Transparent Pricing'}
                        </h2>
                        <p className="text-white/50">
                            {language === 'ar' ? '14 يوم تجربة مجانية. لا حاجة لبطاقة ائتمان.' : '14-day free trial. No credit card required.'}
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {pricing.map((plan, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.4, delay: idx * 0.1 }}
                                viewport={{ once: true }}
                            >
                                <Card 
                                    className={`h-full relative rounded-sm ${
                                        plan.popular 
                                            ? 'border-primary bg-primary/5' 
                                            : 'border-white/10 bg-[#0a0a0a]'
                                    }`}
                                >
                                    {plan.popular && (
                                        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                            <div className="px-4 py-1 bg-primary text-black text-xs font-bold uppercase tracking-wider rounded-sm">
                                                Most Popular
                                            </div>
                                        </div>
                                    )}
                                    <CardContent className="p-8">
                                        <h3 className="font-heading font-bold text-xl text-white uppercase tracking-wider mb-1">{plan.name}</h3>
                                        <p className="text-sm text-white/50 mb-6">{plan.description}</p>
                                        <div className="mb-6">
                                            <span className="font-heading font-bold text-4xl text-white">{plan.price}</span>
                                            <span className="text-white/50">{plan.period}</span>
                                        </div>
                                        <ul className="space-y-3 mb-8">
                                            {plan.features.map((feature, fIdx) => (
                                                <li key={fIdx} className="flex items-start gap-3 text-sm text-white/70">
                                                    <Check className={`w-4 h-4 mt-0.5 shrink-0 ${plan.popular ? 'text-primary' : 'text-cyan-400'}`} />
                                                    <span>{feature}</span>
                                                </li>
                                            ))}
                                        </ul>
                                        <Button 
                                            className={`w-full rounded-sm uppercase tracking-wider font-bold ${
                                                plan.popular 
                                                    ? 'bg-primary text-black hover:bg-primary/90 glow-primary' 
                                                    : 'border border-white/20 bg-transparent hover:bg-white/5 text-white'
                                            }`}
                                            variant={plan.popular ? 'default' : 'outline'}
                                            onClick={() => handlePlanCTA(plan)}
                                            data-testid={`pricing-${plan.name.toLowerCase()}-btn`}
                                        >
                                            {plan.cta}
                                        </Button>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-24 relative border-t border-white/10">
                <div className="absolute inset-0 obsidian-grid opacity-30" />
                <div 
                    className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full blur-3xl opacity-20"
                    style={{ background: 'radial-gradient(circle, rgba(212, 175, 55, 0.4) 0%, transparent 70%)' }}
                />
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative">
                    <div className="text-center">
                        <h2 className="font-heading font-bold text-3xl md:text-5xl uppercase tracking-tight text-white mb-6">
                            {language === 'ar' ? 'جاهز لتحويل مركز العمليات الخاص بك؟' : 'Ready to Transform Your NOC?'}
                        </h2>
                        <p className="text-white/50 mb-10 max-w-xl mx-auto">
                            {language === 'ar' 
                                ? 'انضم إلى فرق المؤسسات عبر المملكة العربية السعودية ودول الخليج الذين يثقون في FalconOps AI لإدارة الحوادث الذكية.'
                                : 'Join enterprise teams across Saudi Arabia and GCC who trust FalconOps AI for intelligent incident management.'}
                        </p>
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Button 
                                asChild 
                                size="lg" 
                                className="bg-[#F5B841] text-black hover:bg-[#F5B841]/90 font-bold uppercase tracking-wider rounded-lg px-10 h-14"
                            >
                                <Link to="/register">
                                    {language === 'ar' ? 'ابدأ التجربة المجانية' : 'Start Free Trial'}
                                    <ArrowRight className="w-5 h-5 ml-2" />
                                </Link>
                            </Button>
                            <Button 
                                variant="outline" 
                                size="lg"
                                asChild
                                className="border-white/20 hover:bg-white/5 text-white uppercase tracking-wider rounded-lg px-10 h-14"
                                data-testid="schedule-demo-btn"
                            >
                                <Link to="/contact?intent=demo">
                                    <Calendar className={`w-5 h-5 ${isRTL ? 'ml-2' : 'mr-2'}`} />
                                    {language === 'ar' ? 'جدولة عرض' : 'Schedule Demo'}
                                </Link>
                            </Button>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-white/10 py-12 bg-[#0B0F14]">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <FalconLogo size={32} />
                            <span className="font-heading font-semibold tracking-wide flex items-baseline gap-0.5">
                                <span className="text-[#F5B841]">FALCON</span>
                                <span className="text-white">OPS</span>
                                <span className="text-[#00E0FF] text-sm ml-1">AI</span>
                            </span>
                        </div>
                        <div className="flex items-center gap-8 text-sm text-white/40">
                            <Link to="/about" className="hover:text-white transition-colors">About</Link>
                            <Link to="/services" className="hover:text-white transition-colors">Services</Link>
                            <Link to="/security" className="hover:text-white transition-colors">Security</Link>
                            <Link to="/contact" className="hover:text-white transition-colors">Contact</Link>
                        </div>
                        <div className="text-center md:text-right">
                            <p className="text-sm text-white/60 mb-1">
                                {language === 'ar' ? 'ذكاء الحوادث المدعوم بالذكاء الاصطناعي' : 'Enterprise AIOps & Availability Intelligence'}
                            </p>
                            <p className="text-xs text-white/40">
                                © 2026 FalconOps Technologies
                            </p>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
};
