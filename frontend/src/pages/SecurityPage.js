import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
    Shield,
    Lock,
    Server,
    Eye,
    Key,
    FileCheck,
    Globe,
    Building2,
    CheckCircle2,
    ArrowRight,
    Cloud,
    Database,
    UserCheck,
} from 'lucide-react';

const securityFeatures = [
    {
        icon: Lock,
        title: 'Data Encryption',
        description: 'AES-256 encryption at rest and TLS 1.3 in transit for all data.',
    },
    {
        icon: Key,
        title: 'Access Control',
        description: 'Role-based access control (RBAC) with granular permissions.',
    },
    {
        icon: Eye,
        title: 'Audit Logging',
        description: 'Complete audit trail of all system actions and access.',
    },
    {
        icon: UserCheck,
        title: 'Authentication',
        description: 'JWT-based auth with optional SSO and MFA support.',
    },
    {
        icon: Database,
        title: 'Data Isolation',
        description: 'Multi-tenant architecture with strict data segregation.',
    },
    {
        icon: Server,
        title: 'Infrastructure Security',
        description: 'SOC 2 compliant infrastructure with regular penetration testing.',
    },
];

const deploymentOptions = [
    {
        icon: Cloud,
        title: 'Cloud Hosted',
        description: 'Fully managed SaaS deployment with 99.9% uptime SLA.',
        features: ['Automatic updates', 'Managed backups', 'Global CDN', '24/7 monitoring'],
    },
    {
        icon: Server,
        title: 'On-Premise',
        description: 'Deploy within your data center for complete data control.',
        features: ['Full data sovereignty', 'Air-gapped support', 'Custom integration', 'Local support'],
    },
    {
        icon: Building2,
        title: 'Hybrid',
        description: 'Combine cloud scalability with on-premise data residency.',
        features: ['Flexible architecture', 'Best of both worlds', 'Gradual migration', 'Cost optimization'],
    },
];

const complianceItems = [
    { name: 'ISO 27001', status: 'Roadmap', description: 'Information security management' },
    { name: 'SOC 2 Type II', status: 'Roadmap', description: 'Security & availability controls' },
    { name: 'GDPR', status: 'Compliant', description: 'Data privacy compliance' },
    { name: 'Saudi PDPL', status: 'Compliant', description: 'Saudi data protection law' },
];

export const SecurityPage = () => {
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
                            <Link to="/security" className="text-sm text-primary font-medium">Security</Link>
                            <Link to="/training" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Training</Link>
                            <Button asChild size="sm">
                                <Link to="/contact">Contact Us</Link>
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-32 pb-16 px-4 sm:px-6 lg:px-8">
                <div className="absolute inset-0 grid-pattern opacity-20" />
                <div className="relative max-w-7xl mx-auto text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
                            <Shield className="w-4 h-4" />
                            Enterprise Security
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            Security &
                            <br />
                            <span className="text-primary">Compliance</span>
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
                            Enterprise-grade security built for Saudi and GCC organizations. 
                            Your data sovereignty and compliance requirements are our priority.
                        </p>
                    </motion.div>
                </div>
            </section>

            {/* Security Features */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            Security Architecture
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Built from the ground up with security as a core principle
                        </p>
                    </div>
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {securityFeatures.map((feature, idx) => {
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

            {/* Deployment Options */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                            Deployment Options
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Flexible deployment to meet your data residency requirements
                        </p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-6">
                        {deploymentOptions.map((option, idx) => {
                            const Icon = option.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className="h-full bg-card/50 border-border/40">
                                        <CardHeader>
                                            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-2">
                                                <Icon className="w-6 h-6 text-primary" />
                                            </div>
                                            <CardTitle className="font-heading text-xl">{option.title}</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-sm text-muted-foreground mb-4">{option.description}</p>
                                            <ul className="space-y-2">
                                                {option.features.map((feature, fIdx) => (
                                                    <li key={fIdx} className="flex items-center gap-2 text-sm">
                                                        <CheckCircle2 className="w-4 h-4 text-primary" />
                                                        <span>{feature}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Compliance */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-6">
                                Compliance & Certifications
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                We are committed to meeting the highest standards of security 
                                and compliance, with a clear roadmap for international certifications.
                            </p>
                            <div className="space-y-4">
                                {complianceItems.map((item, idx) => (
                                    <div key={idx} className="flex items-start justify-between p-4 rounded-lg bg-muted/30">
                                        <div className="flex items-start gap-3">
                                            <FileCheck className="w-5 h-5 text-primary mt-0.5" />
                                            <div>
                                                <p className="font-medium">{item.name}</p>
                                                <p className="text-xs text-muted-foreground">{item.description}</p>
                                            </div>
                                        </div>
                                        <Badge variant={item.status === 'Compliant' ? 'default' : 'outline'}>
                                            {item.status}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <Card className="bg-primary/5 border-primary/20">
                            <CardContent className="p-8">
                                <Globe className="w-12 h-12 text-primary mb-4" />
                                <h3 className="font-heading font-semibold text-xl mb-4">
                                    Saudi Data Residency
                                </h3>
                                <p className="text-muted-foreground mb-6">
                                    We understand the importance of data sovereignty for Saudi enterprises. 
                                    Our platform supports local hosting options in Saudi Arabia through:
                                </p>
                                <ul className="space-y-2">
                                    {['STC Cloud', 'Mobily Cloud', 'Local Data Centers', 'AWS Middle East (Bahrain)'].map((item, idx) => (
                                        <li key={idx} className="flex items-center gap-2 text-sm">
                                            <CheckCircle2 className="w-4 h-4 text-primary" />
                                            <span>{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </section>

            {/* Enterprise Ready */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto text-center">
                    <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-12">
                        Enterprise-Ready Deployment
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        {[
                            'On-Prem Support',
                            'Cloud Deployment',
                            'Hybrid Architecture',
                            'DR Support',
                            'SLA-Backed',
                            'Dedicated Support',
                        ].map((item, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, scale: 0.9 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                                viewport={{ once: true }}
                                className="p-4 rounded-lg bg-card/50 border border-border/40"
                            >
                                <CheckCircle2 className="w-6 h-6 text-primary mx-auto mb-2" />
                                <p className="text-sm font-medium">{item}</p>
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
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                                Have Security Questions?
                            </h2>
                            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
                                Our team is ready to discuss your security requirements 
                                and provide detailed documentation.
                            </p>
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                                <Button asChild size="lg" className="glow-primary">
                                    <Link to="/contact">
                                        Contact Security Team
                                        <ArrowRight className="w-5 h-5 ml-2" />
                                    </Link>
                                </Button>
                                <Button variant="outline" size="lg">
                                    Request Security Documentation
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
                            © 2025 FalconOps AI. Security-First Monitoring.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
