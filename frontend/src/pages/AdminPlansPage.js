import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Textarea } from '../components/ui/textarea';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Plus, Pencil, Trash2, RefreshCw, X, CheckCircle2, Star, DollarSign, Package, Users,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const EMPTY_PLAN = {
    name: '', tagline: '', price: 0, currency: 'USD',
    billing_type: 'subscription', interval: 'month',
    features: [], max_users: 0, max_servers: 0, max_monitors: 0, max_ai_runs: 0,
    button_text: 'Get Started', stripe_price_id: '',
    is_active: true, sort_order: 0, highlight: false,
};

export default function AdminPlansPage() {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);
    const [featuresText, setFeaturesText] = useState('');
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/api/admin/plans`, { headers: authHeaders() });
            const d = await r.json();
            setPlans(d.plans || []);
        } catch {
            toast.error('Failed to load plans');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const openEdit = (plan) => {
        setEditing(plan || { ...EMPTY_PLAN });
        setFeaturesText((plan?.features || []).join('\n'));
    };

    const save = async () => {
        if (!editing.name.trim()) { toast.error('Plan name is required'); return; }
        const payload = {
            ...editing,
            features: featuresText.split('\n').map((s) => s.trim()).filter(Boolean),
            price: Number(editing.price) || 0,
            max_users: Number(editing.max_users) || 0,
            max_servers: Number(editing.max_servers) || 0,
            max_monitors: Number(editing.max_monitors) || 0,
            max_ai_runs: Number(editing.max_ai_runs) || 0,
            sort_order: Number(editing.sort_order) || 0,
        };
        setBusy(true);
        try {
            const method = payload.id ? 'PUT' : 'POST';
            const url = payload.id ? `${API}/api/admin/plans/${payload.id}` : `${API}/api/admin/plans`;
            const r = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(payload) });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`Plan ${payload.id ? 'updated' : 'created'}`);
            setEditing(null);
            load();
        } catch (e) {
            toast.error(`Save failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusy(false);
        }
    };

    const remove = async (plan) => {
        if (!window.confirm(`Delete plan "${plan.name}"?`)) return;
        try {
            const r = await fetch(`${API}/api/admin/plans/${plan.id}`, {
                method: 'DELETE', headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Plan deleted');
            load();
        } catch (e) {
            toast.error(`Delete failed: ${e.message?.slice(0, 200)}`);
        }
    };

    return (
        <div className="p-6 space-y-5" data-testid="admin-plans-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Package className="w-6 h-6 text-cyan-400" /> Plans & Pricing
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Live-edit plans shown on the public pricing page. Changes apply instantly.
                    </p>
                </div>
                <Button onClick={() => openEdit(null)} data-testid="new-plan-btn">
                    <Plus className="w-4 h-4 mr-1.5" /> New Plan
                </Button>
            </div>

            {loading ? (
                <div className="py-10 text-center"><RefreshCw className="w-5 h-5 text-white/40 animate-spin inline" /></div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {plans.map((p) => (
                        <Card key={p.id} className={`bg-black/40 border-white/10 ${p.highlight ? 'ring-1 ring-cyan-500/40' : ''}`} data-testid={`plan-card-${p.id}`}>
                            <CardContent className="p-4 space-y-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-base font-semibold text-white">{p.name}</span>
                                    <Badge className={`text-[10px] ${p.is_active ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30'} border`}>
                                        {p.is_active ? 'active' : 'inactive'}
                                    </Badge>
                                    {p.highlight && <Badge className="text-[10px] bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">popular</Badge>}
                                    <Badge className="text-[10px] bg-white/5 text-white/70 border border-white/10">{p.billing_type}</Badge>
                                </div>
                                <div className="flex items-baseline gap-1.5">
                                    <DollarSign className="w-3.5 h-3.5 text-white/50" />
                                    <span className="text-xl font-bold text-white tabular-nums">{Number(p.price).toFixed(0)}</span>
                                    {p.billing_type === 'subscription' && <span className="text-xs text-white/50">/{p.interval}</span>}
                                </div>
                                <div className="text-xs text-white/55">{p.tagline}</div>
                                <div className="text-[10px] text-white/40 flex items-center gap-3 pt-1">
                                    <span><Users className="w-3 h-3 inline mr-1" />{p.max_users} users</span>
                                    <span>{p.max_servers} servers</span>
                                    <span>{p.max_monitors} monitors</span>
                                </div>
                                <div className="flex items-center justify-end gap-1 pt-2">
                                    <Button variant="ghost" size="sm" onClick={() => openEdit(p)} data-testid={`edit-plan-${p.id}`}>
                                        <Pencil className="w-3.5 h-3.5" />
                                    </Button>
                                    <Button variant="ghost" size="sm" onClick={() => remove(p)} data-testid={`delete-plan-${p.id}`}>
                                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Edit Dialog */}
            <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
                <DialogContent className="bg-zinc-950 border-white/10 max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="plan-edit-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white">{editing?.id ? `Edit ${editing.name}` : 'New Plan'}</DialogTitle>
                        <DialogDescription className="text-white/50 text-xs">
                            Changes apply instantly to the public pricing page.
                        </DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Plan ID (slug, optional)</Label>
                                    <Input value={editing.id || ''} onChange={(e) => setEditing({ ...editing, id: e.target.value })}
                                        placeholder="auto-generated" disabled={!!editing._existing} className="bg-black/40 border-white/10 mt-1"
                                        data-testid="plan-id-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Display name</Label>
                                    <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" data-testid="plan-name-input" />
                                </div>
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Tagline</Label>
                                <Input value={editing.tagline} onChange={(e) => setEditing({ ...editing, tagline: e.target.value })}
                                    className="bg-black/40 border-white/10 mt-1" />
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Billing type</Label>
                                    <Select value={editing.billing_type} onValueChange={(v) => setEditing({ ...editing, billing_type: v })}>
                                        <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="plan-billing-type">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="free">Free</SelectItem>
                                            <SelectItem value="subscription">Subscription</SelectItem>
                                            <SelectItem value="enterprise">Enterprise</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Price (USD)</Label>
                                    <Input type="number" min="0" value={editing.price}
                                        onChange={(e) => setEditing({ ...editing, price: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" data-testid="plan-price-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Interval</Label>
                                    <Select value={editing.interval} onValueChange={(v) => setEditing({ ...editing, interval: v })}>
                                        <SelectTrigger className="bg-black/40 border-white/10 mt-1">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="month">Month</SelectItem>
                                            <SelectItem value="year">Year</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/70">Button text</Label>
                                    <Input value={editing.button_text} onChange={(e) => setEditing({ ...editing, button_text: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" data-testid="plan-button-text" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/70">Stripe price ID (optional)</Label>
                                    <Input value={editing.stripe_price_id} onChange={(e) => setEditing({ ...editing, stripe_price_id: e.target.value })}
                                        placeholder="price_xxx" className="bg-black/40 border-white/10 mt-1" />
                                </div>
                            </div>
                            <div className="grid grid-cols-4 gap-3">
                                {['max_users', 'max_servers', 'max_monitors', 'max_ai_runs'].map((field) => (
                                    <div key={field}>
                                        <Label className="text-xs text-white/70">{field.replace('max_', 'Max ')}</Label>
                                        <Input type="number" min="0" value={editing[field]}
                                            onChange={(e) => setEditing({ ...editing, [field]: e.target.value })}
                                            className="bg-black/40 border-white/10 mt-1" data-testid={`plan-${field}-input`} />
                                    </div>
                                ))}
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Features (one per line)</Label>
                                <Textarea value={featuresText} onChange={(e) => setFeaturesText(e.target.value)} rows={5}
                                    placeholder="Up to 50 monitors&#10;10 users&#10;Email + Webhook alerts"
                                    className="bg-black/40 border-white/10 mt-1 font-mono text-[12px]" data-testid="plan-features-input" />
                            </div>
                            <div className="grid grid-cols-3 gap-3 pt-2 items-center">
                                <div>
                                    <Label className="text-xs text-white/70">Sort order</Label>
                                    <Input type="number" min="0" value={editing.sort_order}
                                        onChange={(e) => setEditing({ ...editing, sort_order: e.target.value })}
                                        className="bg-black/40 border-white/10 mt-1" />
                                </div>
                                <div className="flex items-center justify-between mt-5">
                                    <Label className="text-xs text-white/70">Highlight</Label>
                                    <Switch checked={!!editing.highlight} onCheckedChange={(v) => setEditing({ ...editing, highlight: v })} data-testid="plan-highlight-switch" />
                                </div>
                                <div className="flex items-center justify-between mt-5">
                                    <Label className="text-xs text-white/70">Active</Label>
                                    <Switch checked={!!editing.is_active} onCheckedChange={(v) => setEditing({ ...editing, is_active: v })} data-testid="plan-active-switch" />
                                </div>
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEditing(null)}><X className="w-4 h-4 mr-1.5" /> Cancel</Button>
                        <Button onClick={save} disabled={busy} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="save-plan-btn">
                            {busy ? <RefreshCw className="w-4 h-4 mr-1.5 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
