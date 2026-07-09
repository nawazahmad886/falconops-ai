import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
    Brain,
    Zap,
    ArrowRight,
    CheckCircle2,
    Workflow,
    MessageSquare,
    BarChart3,
    Bell,
    Target,
    Sparkles,
    Layers,
    GitBranch,
    TrendingUp,
    Shield,
} from 'lucide-react';

const features = [
    {
        icon: Layers,
        title: 'Alert Clustering',
        description: 'Automatically groups related alerts into incidents, reducing noise by up to 70%.',
    },
    {
        icon: Target,
        title: 'Root Cause Pattern Learning',
        description: 'AI learns from historical incidents to identify root causes faster.',
    },
    {
        icon: BarChart3,
        title: 'Executive Summaries',
        description: 'Auto-generated business impact reports for leadership visibility.',
    },
    {
        icon: Workflow,
        title: 'Ticket Automation',
        description: 'Automatic ticket creation with enriched context and suggested actions.',
    },
    {
        icon: MessageSquare,
        title: 'NOC Copilot Chat',
        description: 'Conversational AI assistant for incident investigation and resolution.',
    },
    {
        icon: Sparkles,
        title: 'Intelligent Alerting',
        description: 'Context-aware notifications with severity adjustment and deduplication.',
    },
];

const roadmap = [
    {
        phase: 'Phase 1',
        title: 'Correlation & Analysis',
        status: 'Live',
        features: ['Alert correlation', 'AI root cause analysis', 'Incident clustering', 'Executive dashboards'],
    },
    {
        phase: 'Phase 2',
        title: 'Prediction & Prevention',
        status: 'Q2 2025',
        features: ['Anomaly detection', 'Predictive alerting', 'Capacity forecasting', 'SLA risk prediction'],
    },
    {
        phase: 'Phase 3',
        title: 'Auto-Remediation',
        status: 'Q4 2025',
        features: ['Automated runbooks', 'Self-healing workflows', 'Change correlation', 'Closed-loop automation'],
    },
];

export const AIPlatformPage = () => {
    return (
        <div className="min-h-screen bg-background noise">
            {/* Navigation */}
            <header className="fixed top-0 left-0 right-0 z-50 glass-strong">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        <Link to="/" className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                                <span className="text-primary font-heading font-bold text-xl">F</span>
                            </div>
                            <span className="font-heading font-semibold text-xl tracking-tight">
                                FALCON<span className="text-primary">APPS</span>
                            </span>
                        </Link>
                        <nav className="hidden md:flex items-center gap-6">
                            <Link to="/about" className="text-sm text-muted-foreground hover:text-foreground transition-colors">About</Link>
                            <Link to="/services" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Services</Link>
                            <Link to="/ai-platform" className="text-sm text-primary font-medium">AI Platform</Link>
                            <Link to="/training" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Training</Link>
                            <Button asChild size="sm">
                                <Link to="/contact">Contact Us</Link>
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8 overflow-hidden">
                <div className="absolute inset-0 grid-pattern opacity-20" />
                <div 
                    className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] rounded-full"
                    style={{ background: 'radial-gradient(circle, rgba(56, 189, 248, 0.15) 0%, transparent 70%)' }}
                />
                <div className="relative max-w-7xl mx-auto text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
                            <Brain className="w-4 h-4" />
                            Autonomous Monitoring AI
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            AI That Understands
                            <br />
                            <span className="text-primary">Your Monitoring</span>
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-3xl mx-auto mb-8">
                            Purpose-built AI for enterprise monitoring. Not generic automation — 
                            domain-specific intelligence that reduces alert noise by 70% and 
                            accelerates root cause detection by 60%.
                        </p>
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Button asChild size="lg" className="glow-primary">
                                <Link to="/register">
                                    Start Free Trial
                                    <ArrowRight className="w-5 h-5 ml-2" />
                                </Link>
                            </Button>
                            <Button variant="outline" size="lg" asChild>
                                <Link to="/contact">Request Demo</Link>
                            </Button>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Architecture Diagram */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            How It Works
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Enterprise-grade architecture designed for scale and reliability
                        </p>
                    </div>
                    
                    {/* Flow Diagram */}
                    <div className="max-w-5xl mx-auto">
                        <div className="grid grid-cols-1 md:grid-cols-6 gap-4 items-center">
                            {[
                                { icon: Bell, label: 'Monitoring Tools', sub: 'AppD, Dynatrace, ELK' },
                                { icon: GitBranch, label: 'Webhook Ingestion', sub: 'Real-time capture' },
                                { icon: Brain, label: 'AI Engine', sub: 'GPT-5.2 Analysis' },
                                { icon: Layers, label: 'Correlation Layer', sub: 'Pattern matching' },
                                { icon: BarChart3, label: 'Dashboard', sub: 'Real-time insights' },
                                { icon: TrendingUp, label: 'Executive Report', sub: 'Business impact' },
                            ].map((step, idx) => {
                                const Icon = step.icon;
                                return (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, scale: 0.9 }}
                                        whileInView={{ opacity: 1, scale: 1 }}
                                        transition={{ duration: 0.3, delay: idx * 0.1 }}
                                        viewport={{ once: true }}
                                        className="relative"
                                    >
                                        <Card className="bg-card/50 border-border/40 text-center">
                                            <CardContent className="p-4">
                                                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mx-auto mb-2">
                                                    <Icon className="w-5 h-5 text-primary" />
                                                </div>
                                                <p className="font-medium text-sm">{step.label}</p>
                                                <p className="text-xs text-muted-foreground">{step.sub}</p>
                                            </CardContent>
                                        </Card>
                                        {idx < 5 && (
                                            <div className="hidden md:block absolute top-1/2 -right-2 transform -translate-y-1/2 z-10">
                                                <ArrowRight className="w-4 h-4 text-primary" />
                                            </div>
                                        )}
                                    </motion.div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Grid */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            AI Capabilities
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Purpose-built features for enterprise monitoring automation
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature, idx) => {
                            const Icon = feature.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className="h-full bg-card/50 border-border/40 hover:border-primary/50 transition-colors">
                                        <CardContent className="p-6">
                                            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                                                <Icon className="w-6 h-6 text-primary" />
                                            </div>
                                            <h3 className="font-heading font-medium text-lg mb-2">{feature.title}</h3>
                                            <p className="text-sm text-muted-foreground">{feature.description}</p>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Roadmap */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            Product Roadmap
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Our vision for autonomous IT operations
                        </p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-6">
                        {roadmap.map((phase, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.4, delay: idx * 0.1 }}
                                viewport={{ once: true }}
                            >
                                <Card className={`h-full ${idx === 0 ? 'border-primary bg-primary/5' : 'bg-card/50 border-border/40'}`}>
                                    <CardHeader>
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="font-mono text-xs text-muted-foreground">{phase.phase}</span>
                                            <Badge variant={idx === 0 ? 'default' : 'outline'}>
                                                {phase.status}
                                            </Badge>
                                        </div>
                                        <CardTitle className="font-heading text-xl">{phase.title}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <ul className="space-y-2">
                                            {phase.features.map((feature, fIdx) => (
                                                <li key={fIdx} className="flex items-center gap-2 text-sm">
                                                    <CheckCircle2 className={`w-4 h-4 ${idx === 0 ? 'text-primary' : 'text-muted-foreground'}`} />
                                                    <span className={idx === 0 ? '' : 'text-muted-foreground'}>{feature}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Metrics */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-5xl mx-auto">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                        {[
                            { value: '70%', label: 'Alert Noise Reduction' },
                            { value: '60%', label: 'Faster MTTR' },
                            { value: '< 30s', label: 'RCA Generation' },
                            { value: '24/7', label: 'AI Monitoring' },
                        ].map((stat, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, scale: 0.9 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.3, delay: idx * 0.1 }}
                                viewport={{ once: true }}
                            >
                                <p className="font-heading font-bold text-4xl md:text-5xl text-primary mb-2">
                                    {stat.value}
                                </p>
                                <p className="text-sm text-muted-foreground">{stat.label}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-4xl mx-auto text-center">
                    <Card className="bg-primary/5 border-primary/20 p-8 sm:p-12">
                        <CardContent className="p-0">
                            <Brain className="w-12 h-12 text-primary mx-auto mb-4" />
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                                Ready to Experience AI-Powered Monitoring?
                            </h2>
                            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
                                Start your 14-day free trial or schedule a demo to see 
                                how FalconOps AI can transform your NOC operations.
                            </p>
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                                <Button asChild size="lg" className="glow-primary">
                                    <Link to="/register">
                                        Start Free Trial
                                        <ArrowRight className="w-5 h-5 ml-2" />
                                    </Link>
                                </Button>
                                <Button variant="outline" size="lg" asChild>
                                    <Link to="/contact">Schedule Demo</Link>
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-border/40 py-12 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                                <span className="text-primary font-heading font-bold">F</span>
                            </div>
                            <span className="font-heading font-semibold tracking-tight">
                                FALCON<span className="text-primary">APPS</span>
                            </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            © 2025 FalconOps AI. Autonomous Monitoring Intelligence.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
