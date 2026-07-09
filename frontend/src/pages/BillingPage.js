import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    CreditCard, CheckCircle, Zap, Shield, Crown, RefreshCw,
    ArrowRight, Clock, Users, Server, Activity, Globe,
    BarChart3, TrendingUp, DollarSign, Brain, Target,
    AlertTriangle, Wrench, ArrowUpCircle, ArrowDownCircle,
} from 'lucide-react';
import {
    AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

const PLAN_ICONS = { free: Globe, pro: Zap, enterprise: Crown };
const PLAN_COLORS = {
    free: { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/30', accent: 'bg-blue-600', stroke: '#3b82f6' },
    pro: { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/30', accent: 'bg-purple-600', stroke: '#8b5cf6' },
    enterprise: { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/30', accent: 'bg-amber-600', stroke: '#f59e0b' },
};
const AGENT_COLORS = ['#ef4444', '#f59e0b', '#22c55e'];
const STATUS_STYLES = {
    paid: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    initiated: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    pending: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
};

export default function BillingPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('overview');
    const [plans, setPlans] = useState([]);
    const [current, setCurrent] = useState(null);
    const [usage, setUsage] = useState(null);
    const [analytics, setAnalytics] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [upgrading, setUpgrading] = useState(null);
    const [polling, setPolling] = useState(false);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [pRes, cRes, uRes, aRes, tRes] = await Promise.all([
                api.get('/billing/plans'),
                api.get('/billing/current'),
                api.get('/billing/usage'),
                api.get('/billing/analytics'),
                api.get('/billing/transactions?limit=20'),
            ]);
            setPlans(pRes.data || []);
            setCurrent(cRes.data);
            setUsage(uRes.data);
            setAnalytics(aRes.data);
            setTransactions(tRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get('session_id');
        if (sessionId) {
            setPolling(true);
            let attempts = 0;
            const poll = async () => {
                try {
                    const res = await api.get(`/billing/checkout/status/${sessionId}`);
                    if (res.data?.payment_status === 'paid') { setPolling(false); window.history.replaceState({}, '', '/billing'); await fetchData(); return; }
                    if (res.data?.status === 'expired' || attempts >= 10) { setPolling(false); return; }
                } catch (e) { console.error(e); }
                attempts++;
                if (attempts < 10) setTimeout(poll, 2000);
            };
            poll();
        }
    }, [api, fetchData]);

    const upgradePlan = useCallback(async (planId) => {
        setUpgrading(planId);
        try {
            const origin = window.location.origin;
            const res = await api.post('/billing/checkout', { plan_id: planId, origin_url: origin });
            if (res.data?.url) window.location.href = res.data.url;
        } catch (e) { console.error(e); }
        setUpgrading(null);
    }, [api]);

    const downgrade = useCallback(async () => {
        if (!window.confirm('Downgrade to Free? You will lose Pro/Enterprise features.')) return;
        try { await api.post('/billing/downgrade'); await fetchData(); } catch (e) { console.error(e); }
    }, [api, fetchData]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const currentPlanId = current?.plan_id || 'free';
    const planColor = PLAN_COLORS[currentPlanId] || PLAN_COLORS.free;

    const tabs = [
        { id: 'overview', label: 'Overview', icon: BarChart3 },
        { id: 'plans', label: 'Plans', icon: Crown },
        { id: 'history', label: 'Transactions', icon: Clock },
    ];

    return (
        <div className="space-y-6" data-testid="billing-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><CreditCard className="w-6 h-6 text-purple-400" /></div>
                        Billing Dashboard
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Usage analytics, cost tracking & subscription management</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchData} disabled={loading} className="border-white/10 text-xs">
                    <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {polling && (
                <Card className="bg-blue-500/10 border-blue-500/30"><CardContent className="p-4 flex items-center gap-3"><RefreshCw className="w-4 h-4 text-blue-400 animate-spin" /><p className="text-sm text-blue-400">Processing your payment...</p></CardContent></Card>
            )}

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => { const Icon = t.icon; return (
                    <Button key={t.id} variant="ghost" size="sm" onClick={() => setTab(t.id)} className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`} data-testid={`tab-${t.id}`}>
                        <Icon className="w-3 h-3 mr-1" /> {t.label}
                    </Button>
                ); })}
            </div>

            {/* ======================== OVERVIEW TAB ======================== */}
            {tab === 'overview' && (
                <div className="space-y-4">
                    {/* Current Plan + Usage Bar */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <Card className={`bg-[#0D1117] ${planColor.border} border`}>
                            <CardContent className="p-5">
                                <div className="flex items-center gap-3 mb-3">
                                    <div className={`p-3 rounded-xl ${planColor.bg}`}>
                                        {React.createElement(PLAN_ICONS[currentPlanId] || Globe, { className: `w-6 h-6 ${planColor.text}` })}
                                    </div>
                                    <div>
                                        <p className="text-xs text-white/50">Current Plan</p>
                                        <p className={`text-xl font-bold ${planColor.text}`}>{current?.plan?.name || 'Free'}</p>
                                    </div>
                                </div>
                                <p className={`text-2xl font-bold ${planColor.text}`}>${current?.plan?.price || 0}<span className="text-xs text-white/30 font-normal">/mo</span></p>
                            </CardContent>
                        </Card>

                        {/* Usage Meter */}
                        {usage && (
                            <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                                <CardContent className="p-5">
                                    <div className="flex items-center justify-between mb-3">
                                        <p className="text-sm text-white/60">AI Agent Runs This Month</p>
                                        <Badge className={usage.usage_pct > 80 ? 'bg-red-500/15 text-red-400 border-red-500/30' : usage.usage_pct > 50 ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'}>
                                            {usage.usage_pct}%
                                        </Badge>
                                    </div>
                                    <div className="flex items-end gap-3 mb-2">
                                        <span className="text-3xl font-bold text-white" data-testid="ai-runs-used">{usage.ai_runs_used}</span>
                                        <span className="text-sm text-white/30 mb-1">/ {usage.ai_runs_limit}</span>
                                    </div>
                                    <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden mb-3">
                                        <div className={`h-full rounded-full transition-all ${usage.usage_pct > 80 ? 'bg-red-500' : usage.usage_pct > 50 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                                            style={{ width: `${Math.min(usage.usage_pct, 100)}%` }} />
                                    </div>
                                    <div className="flex justify-between text-xs text-white/40">
                                        <span>{usage.ai_runs_remaining} remaining</span>
                                        {usage.overage_runs > 0 && <span className="text-red-400">{usage.overage_runs} overage (+${usage.overage_cost})</span>}
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Key Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                            <p className="text-[10px] text-white/50 mb-1">Total Runs</p>
                            <p className="text-xl font-bold text-white">{analytics?.total_runs_this_month || 0}</p>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                            <p className="text-[10px] text-white/50 mb-1">Avg Daily</p>
                            <p className="text-xl font-bold text-cyan-400">{analytics?.avg_daily_runs || 0}</p>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                            <p className="text-[10px] text-white/50 mb-1">Projected Monthly</p>
                            <p className="text-xl font-bold text-amber-400">{analytics?.projected_monthly_runs || 0}</p>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                            <p className="text-[10px] text-white/50 mb-1">Cost/Run</p>
                            <p className="text-xl font-bold text-white">${analytics?.cost_per_run || 0}</p>
                        </CardContent></Card>
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-4">
                            <p className="text-[10px] text-white/50 mb-1">Est. Bill</p>
                            <p className="text-xl font-bold text-purple-400" data-testid="estimated-bill">${analytics?.estimated_total_bill || 0}</p>
                        </CardContent></Card>
                    </div>

                    {/* Charts Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* Daily Usage Trend */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><TrendingUp className="w-4 h-4 text-cyan-400" /> Daily AI Usage Trend</CardTitle></CardHeader>
                            <CardContent className="p-4">
                                {analytics?.daily_usage?.length > 0 ? (
                                    <ResponsiveContainer width="100%" height={220}>
                                        <AreaChart data={analytics.daily_usage}>
                                            <defs>
                                                <linearGradient id="usageGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <XAxis dataKey="date" tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} axisLine={false} tickLine={false} />
                                            <YAxis tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} axisLine={false} tickLine={false} />
                                            <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff', fontSize: 12 }} />
                                            <Area type="monotone" dataKey="ai_runs" stroke="#8b5cf6" strokeWidth={2} fill="url(#usageGrad)" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="py-12 text-center text-white/30 text-xs">No usage data yet this month</div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Agent Breakdown */}
                        <Card className="bg-[#0D1117] border-white/5">
                            <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><Brain className="w-4 h-4 text-purple-400" /> Usage by Agent</CardTitle></CardHeader>
                            <CardContent className="p-4">
                                {analytics?.agent_breakdown?.length > 0 ? (
                                    <div className="flex items-center gap-4">
                                        <ResponsiveContainer width="50%" height={180}>
                                            <PieChart>
                                                <Pie data={analytics.agent_breakdown} dataKey="runs" nameKey="agent" cx="50%" cy="50%" outerRadius={70} innerRadius={40}>
                                                    {analytics.agent_breakdown.map((_, i) => <Cell key={i} fill={AGENT_COLORS[i % AGENT_COLORS.length]} />)}
                                                </Pie>
                                                <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff', fontSize: 12 }} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                        <div className="space-y-3 flex-1">
                                            {analytics.agent_breakdown.map((a, i) => (
                                                <div key={a.agent} className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: AGENT_COLORS[i % AGENT_COLORS.length] }} />
                                                        <span className="text-xs text-white/60 capitalize">{a.agent}</span>
                                                    </div>
                                                    <div className="text-right">
                                                        <span className="text-xs font-bold text-white">{a.runs}</span>
                                                        <span className="text-[10px] text-white/30 ml-1">${a.cost}</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="py-12 text-center text-white/30 text-xs">No agent usage data</div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Cost Breakdown */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-sm flex items-center gap-2"><DollarSign className="w-4 h-4 text-emerald-400" /> Cost Breakdown</CardTitle></CardHeader>
                        <CardContent className="p-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                    <p className="text-[10px] text-white/40">Subscription</p>
                                    <p className="text-lg font-bold text-white">${analytics?.plan_cost || 0}<span className="text-xs text-white/30">/mo</span></p>
                                </div>
                                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                    <p className="text-[10px] text-white/40">AI Usage (projected)</p>
                                    <p className="text-lg font-bold text-purple-400">${analytics?.projected_monthly_cost || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                    <p className="text-[10px] text-white/40">Overage</p>
                                    <p className="text-lg font-bold text-red-400">${usage?.overage_cost || 0}</p>
                                </div>
                                <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                                    <p className="text-[10px] text-purple-400">Estimated Total</p>
                                    <p className="text-lg font-bold text-purple-400">${analytics?.estimated_total_bill || 0}<span className="text-xs text-white/30">/mo</span></p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ======================== PLANS TAB ======================== */}
            {tab === 'plans' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {plans.map(plan => {
                        const isCurrent = currentPlanId === plan.id;
                        const colors = PLAN_COLORS[plan.id] || PLAN_COLORS.free;
                        const Icon = PLAN_ICONS[plan.id] || Globe;
                        return (
                            <Card key={plan.id} className={`bg-[#0D1117] border-white/5 transition-all ${isCurrent ? `ring-1 ${colors.border}` : 'hover:border-white/15'}`} data-testid={`plan-card-${plan.id}`}>
                                <CardContent className="p-5 space-y-4">
                                    <div className="flex items-center justify-between">
                                        <div className={`p-2 rounded-lg ${colors.bg}`}><Icon className={`w-5 h-5 ${colors.text}`} /></div>
                                        {isCurrent && <Badge className={`text-[9px] ${colors.bg} ${colors.text} ${colors.border}`}>Current</Badge>}
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                                        <p className={`text-2xl font-bold ${colors.text} mt-1`}>{plan.price > 0 ? `$${plan.price}` : 'Free'}{plan.price > 0 && <span className="text-xs text-white/40 font-normal">/mo</span>}</p>
                                    </div>
                                    <div className="space-y-2 text-xs">
                                        <div className="flex items-center gap-2 text-white/60"><Activity className="w-3 h-3" /> {plan.max_monitors} Monitors</div>
                                        <div className="flex items-center gap-2 text-white/60"><Users className="w-3 h-3" /> {plan.max_users} Users</div>
                                        <div className="flex items-center gap-2 text-white/60"><Server className="w-3 h-3" /> {plan.max_servers} Servers</div>
                                        <div className="flex items-center gap-2 text-white/60"><Brain className="w-3 h-3" /> {plan.max_ai_runs} AI Runs/mo</div>
                                        <div className="flex items-center gap-2 text-white/60"><Shield className="w-3 h-3" /> {plan.features?.length || 0} Features</div>
                                    </div>
                                    <div>
                                        {isCurrent ? (
                                            plan.id !== 'free' ? <Button variant="outline" size="sm" className="w-full border-white/10 text-xs" onClick={downgrade}>Downgrade</Button> : <Button disabled size="sm" className="w-full text-xs">Current</Button>
                                        ) : plan.price > 0 ? (
                                            <Button size="sm" className={`w-full text-white text-xs ${colors.accent} hover:opacity-90`} onClick={() => upgradePlan(plan.id)} disabled={upgrading === plan.id} data-testid={`upgrade-${plan.id}`}>
                                                {upgrading === plan.id ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <ArrowRight className="w-3 h-3 mr-1" />} Upgrade
                                            </Button>
                                        ) : <Button size="sm" variant="outline" className="w-full border-white/10 text-xs" onClick={downgrade}>Switch to Free</Button>}
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* ======================== TRANSACTIONS TAB ======================== */}
            {tab === 'history' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Clock className="w-4 h-4 text-white/60" /> Payment History</CardTitle></CardHeader>
                    <CardContent className="p-0">
                        <div className="divide-y divide-white/5" data-testid="transaction-list">
                            {transactions.length === 0 ? (
                                <div className="p-8 text-center text-white/40"><CreditCard className="w-8 h-8 mx-auto mb-3 opacity-40" /><p>No transactions yet</p></div>
                            ) : transactions.map((tx, i) => (
                                <div key={tx.session_id || i} className="flex items-center justify-between p-3 hover:bg-white/[0.02]" data-testid={`tx-${i}`}>
                                    <div className="flex items-center gap-3">
                                        <div className="p-1.5 rounded bg-purple-500/10"><CreditCard className="w-3.5 h-3.5 text-purple-400" /></div>
                                        <div>
                                            <p className="text-sm text-white/80">{tx.plan_id?.charAt(0).toUpperCase() + tx.plan_id?.slice(1)} Plan</p>
                                            <p className="text-[10px] text-white/30">{tx.created_at ? new Date(tx.created_at).toLocaleString() : ''}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm font-bold text-white">${tx.amount}</span>
                                        <Badge className={STATUS_STYLES[tx.payment_status] || STATUS_STYLES.pending}>{tx.payment_status}</Badge>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
