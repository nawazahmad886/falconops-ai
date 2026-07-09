import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    Mail,
    Phone,
    MapPin,
    Send,
    Loader2,
    MessageSquare,
    Calendar,
    Building2,
} from 'lucide-react';

const services = [
    'Monitoring Health Audit',
    'SolarWinds Deployment',
    'AppDynamics Implementation',
    'Dynatrace Setup',
    'Managed Monitoring Services',
    'AI Automation Platform',
    'Training Programs',
    'Other',
];

export const ContactPage = () => {
    const [loading, setLoading] = useState(false);
    // Detect ?intent=demo from URL → switches the page into "Schedule a Live Demo" mode
    const intent = (() => {
        try { return new URLSearchParams(window.location.search).get('intent') || ''; }
        catch { return ''; }
    })();
    const isDemoIntent = intent === 'demo';
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        company: '',
        phone: '',
        service: isDemoIntent ? 'AI Automation Platform' : '',
        message: isDemoIntent
            ? "I'd like to schedule a 30-minute live demo of FalconOps AI. Please share available slots."
            : '',
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.name.trim() || !formData.email.trim() || !formData.message.trim()) {
            toast.error('Name, email, and message are required');
            return;
        }
        setLoading(true);
        try {
            const API = process.env.REACT_APP_BACKEND_URL || '';
            // Backend ContactRequest ignores unknown fields; fold `service` into the message
            const messageBody = formData.service
                ? `[Service interest: ${formData.service}]\n\n${formData.message}`
                : formData.message;
            const r = await fetch(`${API}/api/contact`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: formData.name,
                    email: formData.email,
                    company: formData.company,
                    phone: formData.phone,
                    message: messageBody,
                    source: isDemoIntent ? 'demo_request_page' : 'contact_page',
                    plan_id: isDemoIntent ? 'demo' : '',
                }),
            });
            if (!r.ok) {
                const txt = await r.text();
                throw new Error(txt.slice(0, 200));
            }
            toast.success(
                isDemoIntent
                    ? 'Demo request received — we will email you available slots within 1 business day.'
                    : 'Thank you! Our team will contact you within 24 hours.'
            );
            setFormData({
                name: '', email: '', company: '', phone: '',
                service: isDemoIntent ? 'AI Automation Platform' : '',
                message: '',
            });
        } catch (err) {
            toast.error(`Submission failed: ${err.message || 'Please try again later'}`);
        } finally {
            setLoading(false);
        }
    };

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
                            <Link to="/training" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Training</Link>
                            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Login</Link>
                            <Button asChild size="sm" variant="outline">
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
                            {isDemoIntent ? <Calendar className="w-4 h-4" /> : <MessageSquare className="w-4 h-4" />}
                            {isDemoIntent ? 'Schedule a Live Demo' : 'Get In Touch'}
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            {isDemoIntent ? (
                                <>See FalconOps<br /><span className="text-primary">In Action</span></>
                            ) : (
                                <>Let's Transform<br /><span className="text-primary">Your Monitoring</span></>
                            )}
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                            {isDemoIntent
                                ? 'Book a 30-minute personalized walkthrough of our AIOps, APM, and SOC capabilities. We tailor every demo to your stack.'
                                : 'Ready to reduce alert noise and optimize your IT operations? Contact us for a free monitoring health assessment.'}
                        </p>
                    </motion.div>
                </div>
            </section>

            {/* Contact Form & Info */}
            <section className="py-16 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-3 gap-8">
                        {/* Contact Info */}
                        <div className="space-y-6">
                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                                            <Mail className="w-6 h-6 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Email</p>
                                            <p className="font-medium">contact@falconapps.com</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                                            <Phone className="w-6 h-6 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Phone</p>
                                            <p className="font-medium">+966 XX XXX XXXX</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="bg-card/50 border-border/40">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                                            <MapPin className="w-6 h-6 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Location</p>
                                            <p className="font-medium">Riyadh, Saudi Arabia</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="bg-primary/5 border-primary/20">
                                <CardContent className="p-6">
                                    <Calendar className="w-8 h-8 text-primary mb-3" />
                                    <h3 className="font-heading font-medium text-lg mb-2">
                                        Schedule a Consultation
                                    </h3>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Book a free 30-minute consultation to discuss your 
                                        monitoring challenges.
                                    </p>
                                    <Button variant="outline" className="w-full">
                                        Book a Call
                                    </Button>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Contact Form */}
                        <div className="lg:col-span-2">
                            <Card className="bg-card/50 border-border/40">
                                <CardHeader>
                                    <CardTitle className="font-heading text-2xl">Send Us a Message</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <form onSubmit={handleSubmit} className="space-y-6">
                                        <div className="grid md:grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label htmlFor="name">Full Name *</Label>
                                                <Input
                                                    id="name"
                                                    value={formData.name}
                                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                                    placeholder="Ahmed Al-Rashid"
                                                    required
                                                    className="bg-muted/50"
                                                    data-testid="contact-name"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label htmlFor="email">Email *</Label>
                                                <Input
                                                    id="email"
                                                    type="email"
                                                    value={formData.email}
                                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                                    placeholder="ahmed@company.com"
                                                    required
                                                    className="bg-muted/50"
                                                    data-testid="contact-email"
                                                />
                                            </div>
                                        </div>

                                        <div className="grid md:grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label htmlFor="company">Company</Label>
                                                <Input
                                                    id="company"
                                                    value={formData.company}
                                                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                                                    placeholder="Saudi Telecom"
                                                    className="bg-muted/50"
                                                    data-testid="contact-company"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label htmlFor="phone">Phone</Label>
                                                <Input
                                                    id="phone"
                                                    value={formData.phone}
                                                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                                    placeholder="+966 XX XXX XXXX"
                                                    className="bg-muted/50"
                                                    data-testid="contact-phone"
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor="service">Service Interested In</Label>
                                            <Select
                                                value={formData.service}
                                                onValueChange={(value) => setFormData({ ...formData, service: value })}
                                            >
                                                <SelectTrigger className="bg-muted/50" data-testid="contact-service">
                                                    <SelectValue placeholder="Select a service" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {services.map((service) => (
                                                        <SelectItem key={service} value={service}>
                                                            {service}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="space-y-2">
                                            <Label htmlFor="message">Message *</Label>
                                            <Textarea
                                                id="message"
                                                value={formData.message}
                                                onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                                                placeholder="Tell us about your monitoring challenges and what you're looking to achieve..."
                                                rows={5}
                                                required
                                                className="bg-muted/50"
                                                data-testid="contact-message"
                                            />
                                        </div>

                                        <Button 
                                            type="submit" 
                                            className="w-full glow-primary" 
                                            disabled={loading}
                                            data-testid="contact-submit"
                                        >
                                            {loading ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <>
                                                    Send Message
                                                    <Send className="w-4 h-4 ml-2" />
                                                </>
                                            )}
                                        </Button>
                                    </form>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </div>
            </section>

            {/* Enterprise Section */}
            <section className="py-16 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-4xl mx-auto text-center">
                    <Building2 className="w-12 h-12 text-primary mx-auto mb-4" />
                    <h2 className="font-heading font-semibold text-2xl md:text-3xl mb-4">
                        Enterprise Inquiries
                    </h2>
                    <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
                        For large-scale deployments, on-premise solutions, or custom enterprise 
                        requirements, our team is ready to discuss tailored solutions.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Button asChild size="lg">
                            <Link to="/services">View Enterprise Services</Link>
                        </Button>
                        <Button variant="outline" size="lg">
                            Request Custom Quote
                        </Button>
                    </div>
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
                            © 2025 FalconOps AI. Beyond Monitoring. Into Automation.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
