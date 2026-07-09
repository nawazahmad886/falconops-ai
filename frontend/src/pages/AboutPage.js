import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
    Shield,
    Zap,
    Brain,
    Target,
    Users,
    Award,
    CheckCircle2,
    ArrowRight,
    Globe,
    Building2,
    AlertTriangle,
    TrendingDown,
    DollarSign,
    Eye,
    Clock,
    User,
    Briefcase,
} from 'lucide-react';

const problemsWeSolve = [
    {
        icon: AlertTriangle,
        title: 'Alert Fatigue',
        description: 'NOC teams drowning in 500+ daily alerts, most being noise or duplicates.',
    },
    {
        icon: Clock,
        title: 'Slow Root Cause Detection',
        description: 'Hours wasted manually correlating alerts across multiple tools.',
    },
    {
        icon: DollarSign,
        title: 'High NOC Cost',
        description: 'Over-staffed teams handling repetitive tasks that AI can automate.',
    },
    {
        icon: Eye,
        title: 'Lack of Executive Visibility',
        description: 'No clear business impact metrics or intelligent reporting.',
    },
];

const values = [
    {
        icon: Target,
        title: 'Monitoring-First Architecture',
        description: 'AI layer built specifically for the monitoring domain, not generic automation.',
    },
    {
        icon: Brain,
        title: 'Domain Expertise',
        description: 'Founded by monitoring professionals with 10+ years enterprise experience.',
    },
    {
        icon: Shield,
        title: 'Enterprise-Grade',
        description: 'Architecture designed for scale, reliability, and security requirements.',
    },
    {
        icon: Globe,
        title: 'Saudi Market Specialization',
        description: 'Deep understanding of regional enterprise needs and compliance requirements.',
    },
];

const differentiators = [
    'Specialized only in Monitoring & Observability',
    'AI-driven automation approach',
    'Enterprise-scale architecture design',
    'MTTR reduction focused methodology',
    'Saudi enterprise market expertise',
    'Executive-level reporting intelligence',
];

export const AboutPage = () => {
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
                            <Link to="/about" className="text-sm text-primary font-medium">About</Link>
                            <Link to="/services" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Services</Link>
                            <Link to="/training" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Training</Link>
                            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Login</Link>
                            <Button asChild size="sm">
                                <Link to="/contact">Contact Us</Link>
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8">
                <div className="absolute inset-0 grid-pattern opacity-20" />
                <div className="relative max-w-7xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                        className="max-w-3xl"
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
                            <Building2 className="w-4 h-4" />
                            About FalconOps AI
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            Saudi's AI-Driven
                            <br />
                            <span className="text-primary">Observability Specialist</span>
                        </h1>
                        <p className="text-lg text-muted-foreground mb-8">
                            We are a specialized observability and AI-driven monitoring company focused exclusively 
                            on enterprise monitoring architecture, optimization, and intelligent automation.
                        </p>
                    </motion.div>
                </div>
            </section>

            {/* Problem We Solve */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-destructive/5">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            The Problem We Solve
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Enterprise NOC teams face critical operational challenges that impact business performance
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {problemsWeSolve.map((problem, idx) => {
                            const Icon = problem.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className="h-full bg-card/50 border-destructive/20 hover:border-destructive/40 transition-colors">
                                        <CardContent className="p-6">
                                            <div className="w-12 h-12 rounded-lg bg-destructive/10 flex items-center justify-center mb-4">
                                                <Icon className="w-6 h-6 text-destructive" />
                                            </div>
                                            <h3 className="font-heading font-medium text-lg mb-2">{problem.title}</h3>
                                            <p className="text-sm text-muted-foreground">{problem.description}</p>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Who We Are */}
            <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-6">Who We Are</h2>
                            <p className="text-muted-foreground mb-6">
                                With deep expertise across leading platforms including SolarWinds, AppDynamics, 
                                and Dynatrace, we help organizations transform reactive IT environments into 
                                proactive, intelligent operations ecosystems.
                            </p>
                            <p className="text-muted-foreground mb-6">
                                Our mission is to eliminate alert noise, reduce MTTR, and build AI-powered 
                                autonomous monitoring environments for modern enterprises across Saudi Arabia 
                                and the GCC region.
                            </p>
                            <div className="flex items-center gap-4">
                                <Button asChild>
                                    <Link to="/services">
                                        Explore Our Services
                                        <ArrowRight className="w-4 h-4 ml-2" />
                                    </Link>
                                </Button>
                            </div>
                        </div>
                        <div className="relative">
                            <img 
                                src="https://customer-assets.emergentagent.com/job_enterprise-noc-ai/artifacts/52xdbpyb_Image.jpg"
                                alt="AI-Powered Business Intelligence"
                                className="rounded-xl border border-border/40"
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* Our Values */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">Our Core Values</h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            What sets us apart in the enterprise monitoring landscape
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {values.map((value, idx) => {
                            const Icon = value.icon;
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
                                            <h3 className="font-heading font-medium text-lg mb-2">{value.title}</h3>
                                            <p className="text-sm text-muted-foreground">{value.description}</p>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Why Choose Us */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-6">
                                Why Choose FalconOps AI
                            </h2>
                            <p className="text-muted-foreground mb-8">
                                We're not a generic IT services company. We are specialized, focused, 
                                and expert-driven in enterprise observability solutions.
                            </p>
                            <ul className="space-y-4">
                                {differentiators.map((item, idx) => (
                                    <li key={idx} className="flex items-start gap-3">
                                        <CheckCircle2 className="w-5 h-5 text-primary mt-0.5 shrink-0" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <Card className="bg-primary/5 border-primary/20">
                            <CardContent className="p-8">
                                <Award className="w-12 h-12 text-accent mb-4" />
                                <h3 className="font-heading font-semibold text-2xl mb-4">Our Promise</h3>
                                <p className="text-muted-foreground mb-6">
                                    From Monitoring to Autonomous Operations. We transform reactive IT 
                                    environments into intelligent, self-healing ecosystems.
                                </p>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="text-center p-4 rounded-lg bg-background/50">
                                        <p className="font-heading font-bold text-3xl text-primary">70%</p>
                                        <p className="text-xs text-muted-foreground">Noise Reduction</p>
                                    </div>
                                    <div className="text-center p-4 rounded-lg bg-background/50">
                                        <p className="font-heading font-bold text-3xl text-primary">60%</p>
                                        <p className="text-xs text-muted-foreground">MTTR Improvement</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </section>

            {/* Founder Section */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-medium mb-4">
                                <User className="w-3 h-3" />
                                Founder-Led Company
                            </div>
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-6">
                                Led By Enterprise Expertise
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                FalconOps AI is founded by a monitoring professional with over 10 years of 
                                hands-on experience in enterprise observability, NOC operations, and 
                                large-scale monitoring architecture.
                            </p>
                            <div className="space-y-3 mb-6">
                                {[
                                    'AppDynamics, Dynatrace & SolarWinds expertise',
                                    'ELK Stack, Prometheus & Grafana deployments',
                                    'Enterprise NOC transformation projects',
                                    'Large-scale infrastructure monitoring',
                                    'Saudi enterprise market experience',
                                ].map((item, idx) => (
                                    <div key={idx} className="flex items-center gap-2 text-sm">
                                        <Briefcase className="w-4 h-4 text-primary" />
                                        <span>{item}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-8">
                                <div className="flex items-center gap-4 mb-6">
                                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                                        <User className="w-10 h-10 text-primary" />
                                    </div>
                                    <div>
                                        <h3 className="font-heading font-semibold text-xl">Founder & Principal Architect</h3>
                                        <p className="text-sm text-muted-foreground">10+ Years in Enterprise Monitoring</p>
                                    </div>
                                </div>
                                <blockquote className="border-l-2 border-primary pl-4 text-muted-foreground italic">
                                    "I've spent a decade watching NOC teams struggle with alert fatigue and 
                                    manual correlation. FalconOps AI was built to solve the problems I saw 
                                    every day in enterprise environments."
                                </blockquote>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </section>

            {/* Industries */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto text-center">
                    <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">Industries We Serve</h2>
                    <p className="text-muted-foreground mb-12 max-w-2xl mx-auto">
                        Trusted by enterprise organizations across critical sectors
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        {['Government', 'Banking & Finance', 'Telecom', 'Oil & Gas', 'Healthcare', 'Enterprise'].map((industry, idx) => (
                            <div 
                                key={idx}
                                className="p-4 rounded-lg bg-card/50 border border-border/40 text-center"
                            >
                                <p className="text-sm font-medium">{industry}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-4xl mx-auto text-center">
                    <Card className="bg-primary/5 border-primary/20 p-8 sm:p-12">
                        <CardContent className="p-0">
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                                Ready to Transform Your Monitoring?
                            </h2>
                            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
                                Let's discuss how we can help optimize your enterprise monitoring 
                                environment and reduce operational overhead.
                            </p>
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                                <Button asChild size="lg" className="glow-primary">
                                    <Link to="/contact">
                                        Request Monitoring Audit
                                        <ArrowRight className="w-5 h-5 ml-2" />
                                    </Link>
                                </Button>
                                <Button variant="outline" size="lg" asChild>
                                    <Link to="/services">View Our Services</Link>
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
                            © 2025 FalconOps AI. Intelligent Observability for Modern Enterprises.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
