import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
    GraduationCap,
    Clock,
    Users,
    CheckCircle2,
    ArrowRight,
    Server,
    Activity,
    Brain,
    Shield,
    Award,
    BookOpen,
    Laptop,
} from 'lucide-react';

const trainingPrograms = [
    {
        id: 'solarwinds',
        name: 'SolarWinds Administration',
        duration: '3-5 Days',
        level: 'Intermediate to Advanced',
        icon: Server,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
        description: 'Comprehensive training on SolarWinds Orion platform administration, configuration, and optimization.',
        modules: [
            'Platform Architecture & Components',
            'Installation & Initial Configuration',
            'Node & Application Monitoring Setup',
            'Alert Management & Escalation',
            'Custom Reports & Dashboards',
            'Performance Tuning & Optimization',
            'High Availability Configuration',
            'Troubleshooting & Best Practices',
        ],
        outcomes: [
            'Deploy and configure SolarWinds Orion',
            'Design effective monitoring strategies',
            'Create custom alerts and dashboards',
            'Optimize performance and scalability',
        ],
    },
    {
        id: 'appdynamics',
        name: 'AppDynamics Administration & Development',
        duration: '4-5 Days',
        level: 'Intermediate to Advanced',
        icon: Activity,
        color: 'text-blue-500',
        bgColor: 'bg-blue-500/10',
        description: 'Deep dive into AppDynamics APM platform for both administrators and developers.',
        modules: [
            'Controller Architecture & Setup',
            'Agent Deployment (Java, .NET, Node.js)',
            'Business Transaction Configuration',
            'Health Rules & Baseline Management',
            'Dashboard Creation & Analytics',
            'End User Monitoring (EUM)',
            'Synthetic Monitoring Setup',
            'API Integration & Automation',
        ],
        outcomes: [
            'Deploy and manage AppDynamics agents',
            'Configure business transactions',
            'Create effective health rules',
            'Build executive dashboards',
        ],
    },
    {
        id: 'dynatrace',
        name: 'Dynatrace Operator Training',
        duration: '3-4 Days',
        level: 'Beginner to Intermediate',
        icon: Brain,
        color: 'text-green-500',
        bgColor: 'bg-green-500/10',
        description: 'Learn to leverage Dynatrace\'s AI-powered observability platform for modern applications.',
        modules: [
            'OneAgent Deployment Strategies',
            'Davis AI Configuration & Tuning',
            'Cloud-Native Monitoring (K8s, Docker)',
            'Real User Monitoring Setup',
            'Problem Detection & Root Cause',
            'Custom Metrics & Extensions',
            'SLO Management',
            'Integration & Automation',
        ],
        outcomes: [
            'Deploy OneAgent across environments',
            'Leverage Davis AI for root cause',
            'Monitor cloud-native applications',
            'Create SLOs and reporting',
        ],
    },
    {
        id: 'noc',
        name: 'NOC Best Practices',
        duration: '2-3 Days',
        level: 'All Levels',
        icon: Shield,
        color: 'text-purple-500',
        bgColor: 'bg-purple-500/10',
        description: 'Essential training for NOC teams on operational excellence, incident management, and best practices.',
        modules: [
            'NOC Operations Framework',
            'Alert Triage & Prioritization',
            'Incident Management Process',
            'Escalation Procedures',
            'Communication Best Practices',
            'Runbook Development',
            'MTTR Optimization',
            'Continuous Improvement',
        ],
        outcomes: [
            'Implement effective NOC processes',
            'Reduce MTTR significantly',
            'Improve incident communication',
            'Build operational runbooks',
        ],
    },
    {
        id: 'aiops',
        name: 'AI for IT Operations Workshop',
        duration: '2 Days',
        level: 'Intermediate',
        icon: Brain,
        color: 'text-primary',
        bgColor: 'bg-primary/10',
        description: 'Understand how to leverage AI and automation in modern IT operations.',
        modules: [
            'Introduction to AIOps',
            'Alert Correlation Strategies',
            'Machine Learning for IT',
            'Anomaly Detection Techniques',
            'Automated Remediation',
            'Building AI Workflows',
            'FalconOps AI Platform Deep Dive',
            'Implementation Roadmap',
        ],
        outcomes: [
            'Understand AIOps fundamentals',
            'Design AI automation workflows',
            'Implement intelligent alerting',
            'Plan AIOps transformation',
        ],
    },
];

const deliveryMethods = [
    {
        icon: Laptop,
        title: 'Virtual Instructor-Led',
        description: 'Live online sessions with our expert trainers',
    },
    {
        icon: Users,
        title: 'On-Site Training',
        description: 'We come to your location for hands-on training',
    },
    {
        icon: BookOpen,
        title: 'Custom Workshops',
        description: 'Tailored programs for your specific needs',
    },
];

export const TrainingPage = () => {
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
                            <Link to="/training" className="text-sm text-primary font-medium">Training</Link>
                            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Login</Link>
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
                            <GraduationCap className="w-4 h-4" />
                            Professional Training Programs
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            Monitoring &
                            <br />
                            <span className="text-primary">Observability Training</span>
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-3xl mx-auto mb-8">
                            Expert-led training programs on enterprise monitoring platforms. 
                            From SolarWinds to AI-powered operations.
                        </p>
                    </motion.div>
                </div>
            </section>

            {/* Delivery Methods */}
            <section className="py-12 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="grid md:grid-cols-3 gap-6">
                        {deliveryMethods.map((method, idx) => {
                            const Icon = method.icon;
                            return (
                                <Card key={idx} className="bg-card/50 border-border/40">
                                    <CardContent className="p-6 text-center">
                                        <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mx-auto mb-4">
                                            <Icon className="w-6 h-6 text-primary" />
                                        </div>
                                        <h3 className="font-heading font-medium text-lg mb-2">{method.title}</h3>
                                        <p className="text-sm text-muted-foreground">{method.description}</p>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Training Programs */}
            <section className="py-16 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-2xl md:text-3xl mb-4">
                            Training Programs
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Comprehensive courses designed for IT professionals and monitoring teams
                        </p>
                    </div>

                    <div className="space-y-8">
                        {trainingPrograms.map((program, idx) => {
                            const Icon = program.icon;
                            return (
                                <motion.div
                                    key={program.id}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.05 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className="bg-card/50 border-border/40 hover:border-primary/30 transition-colors" data-testid={`training-${program.id}`}>
                                        <CardHeader>
                                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                                <div className="flex items-center gap-4">
                                                    <div className={`w-14 h-14 rounded-xl ${program.bgColor} flex items-center justify-center`}>
                                                        <Icon className={`w-7 h-7 ${program.color}`} />
                                                    </div>
                                                    <div>
                                                        <CardTitle className="font-heading text-xl">{program.name}</CardTitle>
                                                        <CardDescription className="flex items-center gap-4 mt-1">
                                                            <span className="flex items-center gap-1">
                                                                <Clock className="w-4 h-4" />
                                                                {program.duration}
                                                            </span>
                                                            <Badge variant="outline">{program.level}</Badge>
                                                        </CardDescription>
                                                    </div>
                                                </div>
                                                <Button asChild>
                                                    <Link to="/contact">
                                                        Enquire Now
                                                        <ArrowRight className="w-4 h-4 ml-2" />
                                                    </Link>
                                                </Button>
                                            </div>
                                        </CardHeader>
                                        <CardContent className="space-y-6">
                                            <p className="text-muted-foreground">{program.description}</p>
                                            
                                            <div className="grid lg:grid-cols-2 gap-6">
                                                {/* Modules */}
                                                <div>
                                                    <h4 className="font-heading font-medium text-sm uppercase tracking-wider text-muted-foreground mb-3">
                                                        Course Modules
                                                    </h4>
                                                    <div className="grid grid-cols-1 gap-2">
                                                        {program.modules.map((module, mIdx) => (
                                                            <div key={mIdx} className="flex items-center gap-2 text-sm">
                                                                <span className="text-primary font-mono">{String(mIdx + 1).padStart(2, '0')}.</span>
                                                                <span>{module}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                {/* Outcomes */}
                                                <div>
                                                    <h4 className="font-heading font-medium text-sm uppercase tracking-wider text-muted-foreground mb-3">
                                                        Learning Outcomes
                                                    </h4>
                                                    <div className="space-y-2">
                                                        {program.outcomes.map((outcome, oIdx) => (
                                                            <div key={oIdx} className="flex items-start gap-2">
                                                                <CheckCircle2 className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                                                                <span className="text-sm">{outcome}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Certification */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div>
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-6">
                                Professional Certification
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                Upon successful completion of our training programs, participants receive 
                                a FalconOps AI Professional Certificate recognizing their expertise in 
                                enterprise monitoring and observability.
                            </p>
                            <ul className="space-y-3">
                                {[
                                    'Hands-on practical exercises',
                                    'Real-world scenario training',
                                    'Post-training support access',
                                    'Certificate of completion',
                                ].map((item, idx) => (
                                    <li key={idx} className="flex items-center gap-3">
                                        <CheckCircle2 className="w-5 h-5 text-primary" />
                                        <span>{item}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="p-8 text-center">
                                <Award className="w-16 h-16 text-accent mx-auto mb-4" />
                                <h3 className="font-heading font-semibold text-xl mb-2">
                                    FalconOps AI Certified Professional
                                </h3>
                                <p className="text-sm text-muted-foreground mb-6">
                                    Demonstrate your expertise in enterprise monitoring
                                </p>
                                <div className="flex flex-wrap justify-center gap-2">
                                    <Badge variant="outline">Monitoring Expert</Badge>
                                    <Badge variant="outline">APM Specialist</Badge>
                                    <Badge variant="outline">NOC Professional</Badge>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-4xl mx-auto text-center">
                    <Card className="bg-primary/5 border-primary/20 p-8 sm:p-12">
                        <CardContent className="p-0">
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                                Ready to Upskill Your Team?
                            </h2>
                            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
                                Contact us to discuss custom training programs tailored to your 
                                organization's needs and schedule.
                            </p>
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                                <Button asChild size="lg" className="glow-primary">
                                    <Link to="/contact">
                                        Request Training Quote
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
                            © 2025 FalconOps AI. Transforming NOC with AI.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
