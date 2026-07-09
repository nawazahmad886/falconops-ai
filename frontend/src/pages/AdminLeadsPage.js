import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Users, RefreshCw, Mail, Phone, Building2, MessageCircle, Search, Trash2, Filter, X,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const STATUS_COLORS = {
    new:        'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    contacted:  'bg-amber-500/15 text-amber-300 border-amber-500/30',
    qualified:  'bg-violet-500/15 text-violet-300 border-violet-500/30',
    won:        'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    lost:       'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
};

export default function AdminLeadsPage() {
    const [leads, setLeads] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [selected, setSelected] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (statusFilter !== 'all') params.set('status', statusFilter);
            const r = await fetch(`${API}/api/admin/leads?${params}`, { headers: authHeaders() });
            const d = await r.json();
            setLeads(d.leads || []);
            setTotal(d.total || 0);
        } catch {
            toast.error('Failed to load leads');
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => { load(); }, [load]);

    const filtered = useMemo(() => {
        if (!search.trim()) return leads;
        const q = search.toLowerCase();
        return leads.filter((l) =>
            (l.name || '').toLowerCase().includes(q) ||
            (l.email || '').toLowerCase().includes(q) ||
            (l.company || '').toLowerCase().includes(q)
        );
    }, [leads, search]);

    const updateStatus = async (lead, newStatus, notes) => {
        try {
            const r = await fetch(`${API}/api/admin/leads/${lead.id}`, {
                method: 'PUT', headers: authHeaders(),
                body: JSON.stringify({ status: newStatus, notes }),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success(`Lead → ${newStatus}`);
            load();
            if (selected) setSelected({ ...selected, status: newStatus, notes });
        } catch (e) {
            toast.error(`Update failed: ${e.message?.slice(0, 200)}`);
        }
    };

    const remove = async (lead) => {
        if (!window.confirm(`Delete lead from ${lead.name}?`)) return;
        try {
            const r = await fetch(`${API}/api/admin/leads/${lead.id}`, {
                method: 'DELETE', headers: authHeaders(),
            });
            if (!r.ok) throw new Error(await r.text());
            toast.success('Lead deleted');
            setSelected(null);
            load();
        } catch (e) {
            toast.error(`Delete failed: ${e.message?.slice(0, 200)}`);
        }
    };

    const counts = useMemo(() => {
        const c = { new: 0, contacted: 0, qualified: 0, won: 0, lost: 0 };
        leads.forEach((l) => { if (c[l.status] !== undefined) c[l.status] += 1; });
        return c;
    }, [leads]);

    return (
        <div className="p-6 space-y-5" data-testid="admin-leads-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Users className="w-6 h-6 text-cyan-400" /> Sales Leads
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        {total} total leads · pipeline view of enterprise inquiries from the pricing page.
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="refresh-leads-btn">
                    <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {/* Pipeline tiles */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {['new', 'contacted', 'qualified', 'won', 'lost'].map((s) => (
                    <Card key={s} className={`cursor-pointer ${statusFilter === s ? 'ring-1 ring-cyan-500/40' : ''} bg-black/30 border-white/10`}
                          onClick={() => setStatusFilter(statusFilter === s ? 'all' : s)}
                          data-testid={`status-tile-${s}`}>
                        <CardContent className="p-3 text-center">
                            <div className="text-[10px] uppercase tracking-widest text-white/50">{s}</div>
                            <div className={`text-2xl font-bold mt-1 tabular-nums ${STATUS_COLORS[s].split(' ')[1]}`}>{counts[s]}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Filters */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-3">
                    <div className="flex items-center gap-2 flex-wrap">
                        <Filter className="w-4 h-4 text-white/50" />
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="w-[140px] bg-black/40 border-white/10" data-testid="lead-status-filter">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All statuses</SelectItem>
                                {['new', 'contacted', 'qualified', 'won', 'lost'].map((s) =>
                                    <SelectItem key={s} value={s}>{s}</SelectItem>
                                )}
                            </SelectContent>
                        </Select>
                        <div className="relative flex-1 min-w-[200px]">
                            <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40" />
                            <Input value={search} onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search name, email, company…"
                                className="pl-8 bg-black/40 border-white/10" data-testid="lead-search-input" />
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* List */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-3">
                    {loading ? (
                        <div className="py-8 text-center"><RefreshCw className="w-5 h-5 text-white/40 animate-spin inline" /></div>
                    ) : filtered.length === 0 ? (
                        <div className="py-10 text-center text-white/40 text-sm" data-testid="no-leads">
                            <Users className="w-8 h-8 mx-auto mb-2 opacity-40" />
                            No leads to show.
                        </div>
                    ) : (
                        <div className="space-y-1.5">
                            {filtered.map((l) => (
                                <button key={l.id} onClick={() => setSelected(l)}
                                    className="w-full text-left p-3 rounded-lg border border-white/10 bg-black/30 hover:bg-white/[0.03] hover:border-white/20"
                                    data-testid={`lead-row-${l.id}`}>
                                    <div className="flex items-start justify-between gap-3 flex-wrap">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2 flex-wrap mb-0.5">
                                                <span className="text-sm font-semibold text-white truncate">{l.name}</span>
                                                <Badge className={`text-[10px] border ${STATUS_COLORS[l.status] || STATUS_COLORS.new}`}>
                                                    {l.status}
                                                </Badge>
                                                {l.plan_id && (
                                                    <Badge className="text-[10px] bg-white/5 text-white/70 border border-white/10">
                                                        {l.plan_id}
                                                    </Badge>
                                                )}
                                            </div>
                                            <div className="text-[11px] text-white/55 flex items-center gap-3 flex-wrap">
                                                <span><Mail className="w-3 h-3 inline mr-1" />{l.email}</span>
                                                {l.company && <span><Building2 className="w-3 h-3 inline mr-1" />{l.company}</span>}
                                                {l.phone && <span><Phone className="w-3 h-3 inline mr-1" />{l.phone}</span>}
                                            </div>
                                            <div className="text-[11px] text-white/65 mt-1.5 line-clamp-1">{l.message}</div>
                                        </div>
                                        <div className="text-[10px] text-white/40 shrink-0 text-right">
                                            {new Date(l.created_at).toLocaleString()}
                                        </div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Lead detail dialog */}
            <Dialog open={!!selected} onOpenChange={(v) => !v && setSelected(null)}>
                <DialogContent className="bg-zinc-950 border-white/10 max-w-xl" data-testid="lead-detail-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white">{selected?.name}</DialogTitle>
                        <DialogDescription className="text-white/50 text-xs">
                            Submitted {selected && new Date(selected.created_at).toLocaleString()}
                        </DialogDescription>
                    </DialogHeader>
                    {selected && (
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-2 text-[12px] text-white/75">
                                <div><Mail className="w-3 h-3 inline mr-1 text-white/50" /> {selected.email}</div>
                                {selected.phone && <div><Phone className="w-3 h-3 inline mr-1 text-white/50" /> {selected.phone}</div>}
                                {selected.company && <div><Building2 className="w-3 h-3 inline mr-1 text-white/50" /> {selected.company}</div>}
                                {selected.team_size && <div><Users className="w-3 h-3 inline mr-1 text-white/50" /> Team: {selected.team_size}</div>}
                            </div>
                            <div className="rounded-lg border border-white/10 bg-black/40 p-3">
                                <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1">
                                    <MessageCircle className="w-3 h-3 inline mr-1" /> Message
                                </div>
                                <div className="text-[13px] text-white/85 whitespace-pre-wrap">{selected.message}</div>
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Status</Label>
                                <Select value={selected.status}
                                    onValueChange={(v) => updateStatus(selected, v, selected.notes || '')}>
                                    <SelectTrigger className="bg-black/40 border-white/10 mt-1" data-testid="lead-status-update">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {['new', 'contacted', 'qualified', 'won', 'lost'].map((s) =>
                                            <SelectItem key={s} value={s}>{s}</SelectItem>
                                        )}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label className="text-xs text-white/70">Internal notes</Label>
                                <Textarea
                                    value={selected.notes || ''}
                                    onChange={(e) => setSelected({ ...selected, notes: e.target.value })}
                                    onBlur={() => updateStatus(selected, selected.status, selected.notes || '')}
                                    rows={3}
                                    placeholder="Followed up via email…"
                                    className="bg-black/40 border-white/10 mt-1"
                                    data-testid="lead-notes-input"
                                />
                            </div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => remove(selected)} className="text-red-400 hover:text-red-300" data-testid="delete-lead-btn">
                            <Trash2 className="w-4 h-4 mr-1.5" /> Delete
                        </Button>
                        <Button onClick={() => setSelected(null)}><X className="w-4 h-4 mr-1.5" /> Close</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
