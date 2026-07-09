import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Check, Sparkles, ArrowRight, RefreshCw, X, Send, Star, Zap, Shield, Cpu, Package, Download,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const ICONS = {
    trial: Sparkles,
    standard: Zap,
    professional: Star,
    enterprise: Shield,
};

const PlanCard = ({ plan, onAction }) => {
    const Icon = ICONS[plan.id] || Cpu;
    const isHighlight = !!plan.highlight;
    const priceLabel = plan.billing_type === 'enterprise'
        ? 'Custom'
        : plan.billing_type === 'free'
            ? 'Free'
            : `$${Number(plan.price).toFixed(0)}`;

    return (
        <div
            className={[
                "relative flex flex-col rounded-2xl border p-7 transition-all",
                isHighlight
                    ? "border-cyan-400/60 bg-gradient-to-b from-cyan-500/[0.08] to-black/40 shadow-[0_0_60px_-12px] shadow-cyan-500/30"
                    : "border-white/10 bg-black/40 hover:border-white/20",
            ].join(' ')}
            data-testid={`plan-card-${plan.id}`}
        >
            {isHighlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-cyan-500 text-black text-[10px] font-semibold tracking-widest">
                        MOST POPULAR
                    </Badge>
                </div>
            )}
            <div className="flex items-center gap-2 mb-2">
                <Icon className={`w-5 h-5 ${isHighlight ? 'text-cyan-300' : 'text-white/60'}`} />
                <span className="text-sm uppercase tracking-widest text-white/60">{plan.name}</span>
            </div>
            <div className="flex items-baseline gap-1.5 mb-1">
                <span className="text-4xl font-bold text-white tabular-nums">{priceLabel}</span>
                {plan.billing_type === 'subscription' && (
                    <span className="text-sm text-white/50">/ {plan.interval}</span>
                )}
            </div>
            {plan.tagline && (
                <p className="text-xs text-white/55 mb-5">{plan.tagline}</p>
            )}
            <ul className="space-y-2 mb-6 flex-1">
                {(plan.features || []).map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-white/80">
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{f}</span>
                    </li>
                ))}
            </ul>
            <Button
                className={[
                    "w-full",
                    isHighlight
                        ? "bg-cyan-500 hover:bg-cyan-400 text-black"
                        : "bg-white/5 hover:bg-white/10 text-white border border-white/10",
                ].join(' ')}
                onClick={() => onAction(plan)}
                data-testid={`plan-cta-${plan.id}`}
            >
                {plan.button_text || 'Get Started'}
                <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
        </div>
    );
};

const ContactModal = ({ open, plan, onClose }) => {
    const [form, setForm] = useState({
        name: '', email: '', company: '', phone: '', team_size: '', message: '',
    });
    const [busy, setBusy] = useState(false);
    const [done, setDone] = useState(false);

    useEffect(() => {
        if (open) {
            setForm({
                name: '', email: '', company: '', phone: '', team_size: '',
                message: plan?.id === 'enterprise'
                    ? `We're interested in the FalconOps Enterprise plan for our team.`
                    : '',
            });
            setDone(false);
        }
    }, [open, plan]);

    const submit = async () => {
        if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
            toast.error('Name, email, and message are required');
            return;
        }
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/contact`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...form,
                    plan_id: plan?.id || '',
                    source: 'pricing_page',
                }),
            });
            if (!r.ok) {
                const txt = await r.text();
                throw new Error(txt);
            }
            setDone(true);
            toast.success("Thanks! We'll be in touch within 1 business day.");
        } catch (e) {
            toast.error(`Submission failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
            <DialogContent className="bg-zinc-950 border-white/10 max-w-lg" data-testid="contact-modal">
                <DialogHeader>
                    <DialogTitle className="text-white">
                        {plan?.id === 'enterprise' ? 'Talk to Sales' : `Contact us about ${plan?.name || 'FalconOps'}`}
                    </DialogTitle>
                    <DialogDescription className="text-white/50 text-xs">
                        We respond within 1 business day. Your message lands directly with our team.
                    </DialogDescription>
                </DialogHeader>
                {done ? (
                    <div className="py-6 text-center" data-testid="contact-success">
                        <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto mb-3">
                            <Check className="w-6 h-6 text-emerald-400" />
                        </div>
                        <h3 className="text-base font-semibold text-white">Message received!</h3>
                        <p className="text-xs text-white/60 mt-1">A confirmation email is on its way to {form.email}.</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="text-xs text-white/70">Full name *</Label>
                                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                                    placeholder="Alex Johnson" className="bg-black/40 border-white/10 mt-1"
                                    data-testid="contact-name-input" />
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Work email *</Label>
                                <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                                    placeholder="alex@acme.com" type="email" className="bg-black/40 border-white/10 mt-1"
                                    data-testid="contact-email-input" />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="text-xs text-white/70">Company</Label>
                                <Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })}
                                    placeholder="Acme Corp" className="bg-black/40 border-white/10 mt-1"
                                    data-testid="contact-company-input" />
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Team size</Label>
                                <Input value={form.team_size} onChange={(e) => setForm({ ...form, team_size: e.target.value })}
                                    placeholder="10–50 engineers" className="bg-black/40 border-white/10 mt-1"
                                    data-testid="contact-teamsize-input" />
                            </div>
                        </div>
                        <div>
                            <Label className="text-xs text-white/70">Message *</Label>
                            <Textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                                placeholder="Tell us about your observability needs…" rows={4}
                                className="bg-black/40 border-white/10 mt-1" data-testid="contact-message-input" />
                        </div>
                    </div>
                )}
                <DialogFooter>
                    {done ? (
                        <Button onClick={onClose} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="contact-close-btn">
                            Done
                        </Button>
                    ) : (
                        <>
                            <Button variant="outline" onClick={onClose}><X className="w-4 h-4 mr-1.5" /> Cancel</Button>
                            <Button onClick={submit} disabled={busy} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="contact-submit-btn">
                                {busy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Send className="w-4 h-4 mr-1.5" />}
                                Send message
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

export default function PricingPage() {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [contactPlan, setContactPlan] = useState(null);

    useEffect(() => {
        fetch(`${API}/api/pricing/plans`)
            .then((r) => r.json())
            .then((d) => setPlans(d.plans || []))
            .catch(() => toast.error('Failed to load plans'))
            .finally(() => setLoading(false));
    }, []);

    // If user landed from "Contact Sales" CTA → auto-open the Enterprise contact modal
    useEffect(() => {
        if (!plans.length) return;
        try {
            const params = new URLSearchParams(window.location.search);
            const target = params.get('contact');
            if (target) {
                const match = plans.find((p) => p.id === target) || plans.find((p) => p.id === 'enterprise');
                if (match) setContactPlan(match);
            }
        } catch (_e) {
            // no-op
        }
    }, [plans]);

    const handleAction = (plan) => {
        // Landing page never processes payments directly — it captures intent and routes
        // the user into the onboarding funnel.
        if (plan.billing_type === 'enterprise') {
            setContactPlan(plan);
            return;
        }
        // Free / trial / paid plans all funnel through signup with ?plan=<id>
        window.location.href = `/signup?plan=${encodeURIComponent(plan.id)}`;
    };

    return (
        <div className="min-h-screen bg-zinc-950 text-white" data-testid="pricing-page">
            {/* Hero */}
            <div className="max-w-6xl mx-auto px-6 pt-24 pb-12 text-center">
                <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/30 mb-4">
                    Transparent pricing · No surprises
                </Badge>
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-4">
                    Observability, AIOps & APM
                    <br />
                    <span className="bg-gradient-to-r from-cyan-300 to-violet-300 bg-clip-text text-transparent">
                        priced for every team
                    </span>
                </h1>
                <p className="text-base sm:text-lg text-white/60 max-w-2xl mx-auto">
                    From a free trial to enterprise on-prem — FalconOps scales with you.
                    Pick a plan, switch anytime, no lock-in.
                </p>
            </div>

            {/* Plans */}
            <div className="max-w-7xl mx-auto px-6 pb-24">
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <RefreshCw className="w-6 h-6 text-white/40 animate-spin" />
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5" data-testid="plans-grid">
                        {plans.map((p) => (
                            <PlanCard key={p.id} plan={p} onAction={handleAction} />
                        ))}
                    </div>
                )}

                {/* FAQ-style strip */}
                <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                        { t: 'Cancel any time', d: 'No long-term commitments. Downgrade or cancel in one click.' },
                        { t: 'Air-gapped deployment', d: 'Enterprise plan ships a fully on-prem package with Helm + Podman support.' },
                        { t: 'No credit card for trial', d: 'Start with the free trial — explore every feature for 14 days.' },
                    ].map((x, i) => (
                        <Card key={i} className="bg-black/30 border-white/10">
                            <CardContent className="p-5">
                                <div className="text-sm font-semibold text-white">{x.t}</div>
                                <div className="text-[12px] text-white/55 mt-1">{x.d}</div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>

            <ContactModal
                open={!!contactPlan}
                plan={contactPlan}
                onClose={() => setContactPlan(null)}
            />

            {/* On-prem bundle CTA — gated lead capture */}
            <BundleRequestSection />
        </div>
    );
}

const BundleRequestSection = () => {
    const [open, setOpen] = useState(false);
    const [form, setForm] = useState({ name: '', email: '', company: '', use_case: '', team_size: '' });
    const [busy, setBusy] = useState(false);
    const [done, setDone] = useState(false);

    const submit = async () => {
        if (!form.name.trim() || !form.email.trim()) {
            toast.error('Name and email are required');
            return;
        }
        setBusy(true);
        try {
            const r = await fetch(`${API}/api/licenses/request-bundle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form),
            });
            if (!r.ok) throw new Error(await r.text());
            setDone(true);
            toast.success('Download link sent — check your inbox.');
        } catch (e) {
            toast.error(`Request failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusy(false);
        }
    };

    return (
        <>
            <div className="max-w-7xl mx-auto px-6 pb-24" data-testid="bundle-cta-section">
                <Card className="bg-gradient-to-br from-violet-500/[0.08] via-black/40 to-black/40 border-violet-500/30">
                    <CardContent className="p-7 flex flex-col md:flex-row items-center gap-5">
                        <div className="flex items-center gap-3 shrink-0">
                            <div className="w-12 h-12 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center">
                                <Package className="w-6 h-6 text-violet-300" />
                            </div>
                            <div className="hidden md:block w-px h-12 bg-white/10" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-base font-semibold text-white">Run FalconOps on your own infrastructure</div>
                            <p className="text-[12px] text-white/60 mt-1">
                                Air-gapped Docker / Podman / Helm-chart bundle. Request a secure download link and we'll email you instructions in seconds.
                            </p>
                        </div>
                        <Button
                            onClick={() => setOpen(true)}
                            className="bg-violet-500 hover:bg-violet-400 text-white shrink-0"
                            data-testid="bundle-request-btn"
                        >
                            <Download className="w-4 h-4 mr-1.5" /> Request on-prem bundle
                        </Button>
                    </CardContent>
                </Card>
            </div>

            <Dialog open={open} onOpenChange={(v) => { if (!v) { setOpen(false); setDone(false); } }}>
                <DialogContent className="bg-zinc-950 border-white/10 max-w-lg" data-testid="bundle-request-modal">
                    <DialogHeader>
                        <DialogTitle className="text-white">Get your on-prem bundle</DialogTitle>
                        <DialogDescription className="text-white/50 text-xs">
                            We'll email a secure one-time download link valid for 7 days.
                        </DialogDescription>
                    </DialogHeader>
                    {done ? (
                        <div className="py-6 text-center" data-testid="bundle-success">
                            <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto mb-3">
                                <Check className="w-6 h-6 text-emerald-400" />
                            </div>
                            <h3 className="text-base font-semibold text-white">Check your inbox</h3>
                            <p className="text-xs text-white/60 mt-1">A download link is on its way to {form.email}.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Full name *</Label>
                                    <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                                        placeholder="Alex Johnson" className="bg-black/40 border-white/10 mt-1" data-testid="bundle-name-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Work email *</Label>
                                    <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                                        placeholder="alex@acme.com" type="email" className="bg-black/40 border-white/10 mt-1" data-testid="bundle-email-input" />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Company</Label>
                                    <Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" data-testid="bundle-company-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Team size</Label>
                                    <Input value={form.team_size} onChange={(e) => setForm({ ...form, team_size: e.target.value })}
                                        placeholder="50+" className="bg-black/40 border-white/10 mt-1" />
                                </div>
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">What are you evaluating?</Label>
                                <Textarea value={form.use_case} onChange={(e) => setForm({ ...form, use_case: e.target.value })}
                                    rows={3} placeholder="Air-gapped trial on RHEL 9 cluster…"
                                    className="bg-black/40 border-white/10 mt-1" data-testid="bundle-usecase-input" />
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        {done ? (
                            <Button onClick={() => { setOpen(false); setDone(false); }} className="bg-cyan-500 text-black hover:bg-cyan-400">Done</Button>
                        ) : (
                            <>
                                <Button variant="outline" onClick={() => setOpen(false)}><X className="w-4 h-4 mr-1.5" /> Cancel</Button>
                                <Button onClick={submit} disabled={busy} className="bg-violet-500 hover:bg-violet-400 text-white" data-testid="bundle-submit-btn">
                                    {busy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <Send className="w-4 h-4 mr-1.5" />}
                                    Email me the link
                                </Button>
                            </>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};
