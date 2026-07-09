import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Building, Users, Plus, RefreshCw, Shield, Settings, BarChart3,
    Server, Activity, AlertTriangle, Trash2, UserPlus, Eye,
    CheckCircle, XCircle, Globe, Database,
} from 'lucide-react';

const PLAN_STYLES = {
    starter: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    professional: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    enterprise: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
};

export default function TenantsPage() {
    const { api } = useAuth();
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [selectedTenant, setSelectedTenant] = useState(null);
    const [tenantStats, setTenantStats] = useState(null);
    const [tenantUsers, setTenantUsers] = useState([]);
    const [form, setForm] = useState({ name: '', domain: '', contact_email: '', plan: 'starter', max_users: '10', max_servers: '50', max_monitors: '100' });
    const [userForm, setUserForm] = useState({ email: '', full_name: '', password: '', role: 'user' });
    const [showAddUser, setShowAddUser] = useState(false);

    const fetchTenants = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/tenants');
            setTenants(res.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchTenantDetails = useCallback(async (tenantId) => {
        try {
            const [sRes, uRes] = await Promise.all([
                api.get(`/tenants/${tenantId}/stats`),
                api.get(`/tenants/${tenantId}/users`),
            ]);
            setTenantStats(sRes.data);
            setTenantUsers(uRes.data || []);
        } catch (e) { console.error(e); }
    }, [api]);

    const createTenant = useCallback(async () => {
        try {
            await api.post('/tenants', {
                ...form,
                max_users: parseInt(form.max_users),
                max_servers: parseInt(form.max_servers),
                max_monitors: parseInt(form.max_monitors),
            });
            setShowCreate(false);
            setForm({ name: '', domain: '', contact_email: '', plan: 'starter', max_users: '10', max_servers: '50', max_monitors: '100' });
            await fetchTenants();
        } catch (e) { console.error(e); }
    }, [api, form, fetchTenants]);

    const deleteTenant = useCallback(async (id) => {
        if (!window.confirm('Delete this tenant and ALL associated data?')) return;
        try {
            await api.delete(`/tenants/${id}`);
            setSelectedTenant(null);
            await fetchTenants();
        } catch (e) { console.error(e); }
    }, [api, fetchTenants]);

    const addUser = useCallback(async () => {
        if (!selectedTenant) return;
        try {
            await api.post(`/tenants/${selectedTenant}/users`, userForm);
            setShowAddUser(false);
            setUserForm({ email: '', full_name: '', password: '', role: 'user' });
            await fetchTenantDetails(selectedTenant);
        } catch (e) { console.error(e); }
    }, [api, selectedTenant, userForm, fetchTenantDetails]);

    const deleteUser = useCallback(async (userId) => {
        if (!selectedTenant) return;
        try {
            await api.delete(`/tenants/${selectedTenant}/users/${userId}`);
            await fetchTenantDetails(selectedTenant);
        } catch (e) { console.error(e); }
    }, [api, selectedTenant, fetchTenantDetails]);

    useEffect(() => { fetchTenants(); }, [fetchTenants]);
    useEffect(() => { if (selectedTenant) fetchTenantDetails(selectedTenant); }, [selectedTenant, fetchTenantDetails]);

    return (
        <div className="space-y-6" data-testid="tenants-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/15"><Building className="w-6 h-6 text-amber-400" /></div>
                        Multi-Tenant Management
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Manage organizations, users, and data isolation</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchTenants} disabled={loading} className="border-white/10 text-xs">
                        <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => setShowCreate(!showCreate)} className="bg-amber-600 hover:bg-amber-700 text-white text-xs" data-testid="create-tenant-btn">
                        <Plus className="w-3 h-3 mr-1" /> New Tenant
                    </Button>
                </div>
            </div>

            {/* Create Tenant Form */}
            {showCreate && (
                <Card className="bg-[#0D1117] border-white/5" data-testid="create-tenant-form">
                    <CardHeader className="pb-3 border-b border-white/5"><CardTitle className="text-base flex items-center gap-2"><Plus className="w-4 h-4 text-amber-400" /> New Tenant</CardTitle></CardHeader>
                    <CardContent className="p-4 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div><Label className="text-xs text-white/60">Organization Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Acme Corp" data-testid="tenant-name-input" /></div>
                            <div><Label className="text-xs text-white/60">Domain</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.domain} onChange={e => setForm(p => ({ ...p, domain: e.target.value }))} placeholder="acme.com" /></div>
                            <div><Label className="text-xs text-white/60">Contact Email</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={form.contact_email} onChange={e => setForm(p => ({ ...p, contact_email: e.target.value }))} placeholder="admin@acme.com" /></div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div><Label className="text-xs text-white/60">Plan</Label>
                                <Select value={form.plan} onValueChange={v => setForm(p => ({ ...p, plan: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="starter">Starter</SelectItem><SelectItem value="professional">Professional</SelectItem><SelectItem value="enterprise">Enterprise</SelectItem></SelectContent>
                                </Select>
                            </div>
                            <div><Label className="text-xs text-white/60">Max Users</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.max_users} onChange={e => setForm(p => ({ ...p, max_users: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Max Servers</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.max_servers} onChange={e => setForm(p => ({ ...p, max_servers: e.target.value }))} /></div>
                            <div><Label className="text-xs text-white/60">Max Monitors</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="number" value={form.max_monitors} onChange={e => setForm(p => ({ ...p, max_monitors: e.target.value }))} /></div>
                        </div>
                        <Button onClick={createTenant} disabled={!form.name} className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="submit-tenant-btn"><CheckCircle className="w-3 h-3 mr-1" /> Create Tenant</Button>
                    </CardContent>
                </Card>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Tenant List */}
                <div className="lg:col-span-1 space-y-3">
                    <h2 className="text-sm font-semibold text-white/60">Organizations ({tenants.length})</h2>
                    {tenants.map(t => {
                        const planStyle = PLAN_STYLES[t.plan] || PLAN_STYLES.starter;
                        return (
                            <Card key={t.id} className={`bg-[#0D1117] border-white/5 cursor-pointer transition-all hover:border-white/15 ${selectedTenant === t.id ? 'ring-1 ring-amber-500/30' : ''}`}
                                onClick={() => setSelectedTenant(selectedTenant === t.id ? null : t.id)} data-testid={`tenant-card-${t.id}`}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <h3 className="text-sm font-semibold text-white">{t.name}</h3>
                                        <Badge className={`text-[9px] ${planStyle}`}>{t.plan}</Badge>
                                    </div>
                                    <div className="flex items-center gap-3 text-[10px] text-white/40">
                                        <span><Users className="w-3 h-3 inline mr-0.5" />{t.user_count || 0}</span>
                                        <span><Server className="w-3 h-3 inline mr-0.5" />{t.server_count || 0}</span>
                                        <span><Activity className="w-3 h-3 inline mr-0.5" />{t.monitor_count || 0}</span>
                                    </div>
                                    {t.domain && <p className="text-[10px] text-white/30 mt-1">{t.domain}</p>}
                                </CardContent>
                            </Card>
                        );
                    })}
                    {tenants.length === 0 && !loading && (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-6 text-center text-white/40">
                            <Building className="w-6 h-6 mx-auto mb-2 opacity-40" /><p className="text-xs">No tenants yet</p>
                        </CardContent></Card>
                    )}
                </div>

                {/* Tenant Details */}
                <div className="lg:col-span-2 space-y-4">
                    {selectedTenant && tenantStats ? (
                        <>
                            {/* Usage Stats */}
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-3 border-b border-white/5">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-base flex items-center gap-2"><BarChart3 className="w-4 h-4 text-amber-400" /> {tenantStats.tenant_name} Usage</CardTitle>
                                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteTenant(selectedTenant)} title="Delete Tenant"><Trash2 className="w-3 h-3 text-red-400" /></Button>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-4">
                                    <div className="grid grid-cols-3 gap-4">
                                        {['users', 'servers', 'monitors'].map(key => {
                                            const u = tenantStats.usage?.[key] || { current: 0, max: 0 };
                                            const pct = u.max > 0 ? Math.round((u.current / u.max) * 100) : 0;
                                            return (
                                                <div key={key}>
                                                    <p className="text-xs text-white/50 capitalize mb-1">{key}</p>
                                                    <p className="text-sm font-bold text-white">{u.current} / {u.max}</p>
                                                    <div className="w-full h-1.5 bg-white/5 rounded-full mt-1 overflow-hidden">
                                                        <div className={`h-full rounded-full ${pct > 80 ? 'bg-red-400' : pct > 50 ? 'bg-amber-400' : 'bg-emerald-400'}`} style={{ width: `${pct}%` }} />
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Tenant Users */}
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardHeader className="pb-3 border-b border-white/5">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-base flex items-center gap-2"><Users className="w-4 h-4 text-blue-400" /> Users</CardTitle>
                                        <Button size="sm" variant="outline" onClick={() => setShowAddUser(!showAddUser)} className="border-white/10 text-xs" data-testid="add-user-btn"><UserPlus className="w-3 h-3 mr-1" /> Add User</Button>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-0">
                                    {showAddUser && (
                                        <div className="p-4 border-b border-white/5 space-y-3">
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                                <div><Label className="text-xs text-white/60">Email</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={userForm.email} onChange={e => setUserForm(p => ({ ...p, email: e.target.value }))} data-testid="user-email-input" /></div>
                                                <div><Label className="text-xs text-white/60">Full Name</Label><Input className="bg-[#161B22] border-white/10 mt-1" value={userForm.full_name} onChange={e => setUserForm(p => ({ ...p, full_name: e.target.value }))} /></div>
                                                <div><Label className="text-xs text-white/60">Password</Label><Input className="bg-[#161B22] border-white/10 mt-1" type="password" value={userForm.password} onChange={e => setUserForm(p => ({ ...p, password: e.target.value }))} /></div>
                                                <div><Label className="text-xs text-white/60">Role</Label>
                                                    <Select value={userForm.role} onValueChange={v => setUserForm(p => ({ ...p, role: v }))}>
                                                        <SelectTrigger className="bg-[#161B22] border-white/10 mt-1"><SelectValue /></SelectTrigger>
                                                        <SelectContent className="bg-[#0D1117] border-white/10"><SelectItem value="admin">Admin</SelectItem><SelectItem value="user">User</SelectItem><SelectItem value="viewer">Viewer</SelectItem></SelectContent>
                                                    </Select>
                                                </div>
                                            </div>
                                            <Button size="sm" onClick={addUser} disabled={!userForm.email || !userForm.full_name || !userForm.password} className="bg-blue-600 hover:bg-blue-700 text-white text-xs" data-testid="submit-user-btn"><CheckCircle className="w-3 h-3 mr-1" /> Add</Button>
                                        </div>
                                    )}
                                    <div className="divide-y divide-white/5" data-testid="user-list">
                                        {tenantUsers.length === 0 ? (
                                            <div className="p-6 text-center text-white/40 text-xs">No users in this tenant</div>
                                        ) : tenantUsers.map(u => (
                                            <div key={u.id} className="flex items-center justify-between p-3 hover:bg-white/[0.02]" data-testid={`user-row-${u.id}`}>
                                                <div className="flex items-center gap-3">
                                                    <div className="p-1.5 rounded bg-blue-500/10"><Users className="w-3.5 h-3.5 text-blue-400" /></div>
                                                    <div>
                                                        <p className="text-sm text-white/80">{u.full_name}</p>
                                                        <p className="text-[10px] text-white/30">{u.email}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="text-[9px] text-white/40 border-white/10">{u.role}</Badge>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => deleteUser(u.id)}><Trash2 className="w-3 h-3 text-red-400/50" /></Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card className="bg-[#0D1117] border-white/5"><CardContent className="p-12 text-center text-white/40">
                            <Building className="w-10 h-10 mx-auto mb-3 opacity-30" />
                            <p>Select a tenant to view details</p>
                        </CardContent></Card>
                    )}
                </div>
            </div>
        </div>
    );
}
