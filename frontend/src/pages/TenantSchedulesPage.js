import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    Building, Calendar, Clock, Users, Save, PlayCircle, RefreshCw,
    Mail, CheckCircle, XCircle, Sparkles, AlertTriangle,
} from 'lucide-react';

const DAYS = [
    { value: 'sun', label: 'Sun' }, { value: 'mon', label: 'Mon' },
    { value: 'tue', label: 'Tue' }, { value: 'wed', label: 'Wed' },
    { value: 'thu', label: 'Thu' }, { value: 'fri', label: 'Fri' },
    { value: 'sat', label: 'Sat' },
];

export default function TenantSchedulesPage() {
    const { api } = useAuth();
    const [tenants, setTenants] = useState([]);
    const [tenantSchedules, setTenantSchedules] = useState([]);
    const [selectedId, setSelectedId] = useState('');
    const [settings, setSettings] = useState(null);
    const [logs, setLogs] = useState([]);
    const [newRecipient, setNewRecipient] = useState('');
    const [saving, setSaving] = useState(false);
    const [triggering, setTriggering] = useState(false);
    const [loading, setLoading] = useState(true);

    const fetchTenants = useCallback(async () => {
        try {
            const [tRes, sRes] = await Promise.all([
                api.get('/tenants'),
                api.get('/scheduled-reports/tenants'),
            ]);
            setTenants(tRes.data || []);
            setTenantSchedules(sRes.data || []);
            if (tRes.data?.length && !selectedId) setSelectedId(tRes.data[0].id);
        } catch (e) { console.error(e); }
    }, [api, selectedId]);

    const fetchSettings = useCallback(async (tid) => {
        if (!tid) return;
        setLoading(true);
        try {
            const [s, l] = await Promise.all([
                api.get(`/scheduled-reports/tenants/${tid}/settings`),
                api.get(`/scheduled-reports/tenants/${tid}/logs?limit=10`),
            ]);
            setSettings(s.data);
            setLogs(l.data || []);
        } catch (e) {
            toast.error(`Load failed: ${e.message}`);
        }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchTenants(); }, [fetchTenants]);
    useEffect(() => { if (selectedId) fetchSettings(selectedId); }, [selectedId, fetchSettings]);

    const toggleDay = (d) => {
        const cur = settings.days_of_week || [];
        setSettings({ ...settings, days_of_week: cur.includes(d) ? cur.filter(x => x !== d) : [...cur, d] });
    };

    const addRecipient = () => {
        if (!newRecipient.trim() || !newRecipient.includes('@')) return toast.error('Invalid email');
        const cur = settings.recipients || [];
        if (cur.includes(newRecipient)) return toast.error('Already added');
        setSettings({ ...settings, recipients: [...cur, newRecipient.trim()] });
        setNewRecipient('');
    };

    const removeRecipient = (email) => {
        setSettings({ ...settings, recipients: (settings.recipients || []).filter(r => r !== email) });
    };

    const save = async () => {
        setSaving(true);
        try {
            await api.put(`/scheduled-reports/tenants/${selectedId}/settings`, {
                enabled: settings.enabled,
                days_of_week: settings.days_of_week,
                hour: parseInt(settings.hour, 10),
                minute: parseInt(settings.minute, 10),
                timezone: settings.timezone || 'UTC',
                period_days: parseInt(settings.period_days, 10),
                recipients: settings.recipients || [],
                sender_email: settings.sender_email,
                portal_base_url: settings.portal_base_url || '',
            });
            toast.success('Tenant schedule saved');
            await fetchTenants();
        } catch (e) {
            toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
        }
        setSaving(false);
    };

    const triggerNow = async () => {
        setTriggering(true);
        try {
            const res = await api.post(`/scheduled-reports/tenants/${selectedId}/trigger`, {});
            const em = res.data?.email || {};
            if (em.ok) toast.success(`Report sent to ${(res.data.recipients || []).length} recipient(s)`);
            else if (em.skipped) toast.success('Report generated (no recipients)');
            else toast.error(`Email failed: ${em.error?.slice(0, 80)}`);
            await fetchSettings(selectedId);
        } catch (e) {
            toast.error(`Trigger failed: ${e.response?.data?.detail || e.message}`);
        }
        setTriggering(false);
    };

    const selectedTenant = tenants.find(t => t.id === selectedId);

    return (
        <div className="space-y-6" data-testid="tenant-schedules-page">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Building className="w-6 h-6 text-[#F5B841]" />
                        Per-Tenant Schedules
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Each tenant can have their own cron schedule, recipients, and sender. Overrides the global schedule.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button
                        onClick={triggerNow}
                        disabled={triggering || !settings}
                        className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black"
                        data-testid="tenant-trigger-now-btn"
                    >
                        {triggering ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <PlayCircle className="w-4 h-4 mr-2" />}
                        Run Now
                    </Button>
                    <Button
                        onClick={save}
                        disabled={saving || !settings}
                        className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                        data-testid="tenant-save-btn"
                    >
                        {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                        Save
                    </Button>
                </div>
            </div>

            {/* Tenant picker */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardContent className="pt-6 space-y-3">
                    <Label className="text-xs text-white/60 block">Select Tenant</Label>
                    <Select value={selectedId} onValueChange={setSelectedId}>
                        <SelectTrigger className="bg-[#161B22] border-white/10 max-w-md" data-testid="tenant-schedule-select">
                            <SelectValue placeholder="Choose tenant..." />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0D1117] border-white/10">
                            {tenants.map(t => {
                                const hasSchedule = tenantSchedules.some(s => s.tenant_id === t.id && s.enabled);
                                return (
                                    <SelectItem key={t.id} value={t.id}>
                                        <div className="flex items-center gap-2">
                                            <span>{t.name}</span>
                                            {hasSchedule && <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-[9px] ml-2">Active</Badge>}
                                        </div>
                                    </SelectItem>
                                );
                            })}
                        </SelectContent>
                    </Select>
                    {selectedTenant && (
                        <p className="text-xs text-white/40">
                            Plan: {selectedTenant.plan} · {selectedTenant.user_count || 0} users · Contact: {selectedTenant.contact_email || 'N/A'}
                        </p>
                    )}
                </CardContent>
            </Card>

            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <RefreshCw className="w-6 h-6 animate-spin text-white/30" />
                </div>
            ) : settings && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Settings */}
                    <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Calendar className="w-4 h-4 text-[#00E0FF]" />
                                {selectedTenant?.name} Schedule
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-5">
                            <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5">
                                <div>
                                    <p className="text-sm text-white font-medium">Per-Tenant Cron Enabled</p>
                                    <p className="text-xs text-white/40">Overrides the global default for this tenant</p>
                                </div>
                                <Switch
                                    checked={settings.enabled || false}
                                    onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
                                    data-testid="tenant-enabled-switch"
                                />
                            </div>

                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Days of Week</Label>
                                <div className="flex gap-2 flex-wrap">
                                    {DAYS.map(d => {
                                        const active = (settings.days_of_week || []).includes(d.value);
                                        return (
                                            <button
                                                key={d.value}
                                                onClick={() => toggleDay(d.value)}
                                                className={`px-3 py-1.5 rounded-md text-xs font-medium border ${
                                                    active ? 'bg-[#00E0FF] text-black border-[#00E0FF]' : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
                                                }`}
                                                data-testid={`tenant-day-${d.value}`}
                                            >
                                                {d.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 block">Hour</Label>
                                    <Input type="number" min="0" max="23" value={settings.hour}
                                        onChange={(e) => setSettings({ ...settings, hour: e.target.value })}
                                        className="bg-[#161B22] border-white/10" data-testid="tenant-hour-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 block">Minute</Label>
                                    <Input type="number" min="0" max="59" value={settings.minute}
                                        onChange={(e) => setSettings({ ...settings, minute: e.target.value })}
                                        className="bg-[#161B22] border-white/10" data-testid="tenant-minute-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 block">Timezone</Label>
                                    <Input value={settings.timezone || 'UTC'}
                                        onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                                        className="bg-[#161B22] border-white/10" data-testid="tenant-timezone-input" />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 block">Period (days)</Label>
                                    <Input type="number" min="1" max="90" value={settings.period_days}
                                        onChange={(e) => setSettings({ ...settings, period_days: e.target.value })}
                                        className="bg-[#161B22] border-white/10" data-testid="tenant-period-input" />
                                </div>
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 block">Sender Email</Label>
                                    <Input value={settings.sender_email || ''}
                                        onChange={(e) => setSettings({ ...settings, sender_email: e.target.value })}
                                        className="bg-[#161B22] border-white/10" data-testid="tenant-sender-input" />
                                </div>
                            </div>

                            <div>
                                <Label className="text-xs text-white/60 mb-2 block flex items-center gap-1">
                                    <Users className="w-3 h-3" /> Recipients ({(settings.recipients || []).length})
                                </Label>
                                <div className="flex gap-2 mb-2">
                                    <Input type="email" value={newRecipient}
                                        onChange={(e) => setNewRecipient(e.target.value)}
                                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRecipient(); } }}
                                        placeholder="tenant-admin@acme.com"
                                        className="bg-[#161B22] border-white/10"
                                        data-testid="tenant-new-recipient-input" />
                                    <Button onClick={addRecipient} variant="outline" className="border-white/10" data-testid="tenant-add-recipient-btn">Add</Button>
                                </div>
                                {(settings.recipients || []).length > 0 && (
                                    <div className="flex flex-wrap gap-1.5" data-testid="tenant-recipients-list">
                                        {settings.recipients.map(r => (
                                            <Badge key={r} className="bg-[#00E0FF]/10 text-[#00E0FF] border-[#00E0FF]/30 pl-2 pr-1 py-1 flex items-center gap-1">
                                                {r}
                                                <button onClick={() => removeRecipient(r)}
                                                    className="ml-1 w-4 h-4 rounded-full hover:bg-red-500/30 text-red-400 text-xs">×</button>
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Tenant Logs */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Mail className="w-4 h-4 text-[#F5B841]" />
                                Tenant Runs
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {logs.length === 0 ? (
                                <div className="text-center py-6 text-white/30 text-xs">No runs yet for this tenant</div>
                            ) : (
                                <div className="space-y-2 max-h-[500px] overflow-y-auto" data-testid="tenant-run-logs">
                                    {logs.map((l, i) => {
                                        const ok = l.status === 'success';
                                        const d = l.detail || {};
                                        return (
                                            <div key={i}
                                                className={`p-2 rounded-lg border text-xs ${
                                                    ok ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'
                                                }`}>
                                                <div className="flex items-center gap-2 mb-1">
                                                    {ok ? <CheckCircle className="w-3 h-3 text-emerald-400" /> : <XCircle className="w-3 h-3 text-red-400" />}
                                                    <span className={ok ? 'text-emerald-400' : 'text-red-400'}>{l.status}</span>
                                                    <span className="text-white/30 ml-auto">{new Date(l.timestamp).toLocaleString()}</span>
                                                </div>
                                                {d.report_id && <div className="text-white/50 font-mono text-[10px]">{d.report_id}</div>}
                                                {d.total_alerts !== undefined && (
                                                    <div className="text-white/40">{d.total_alerts} alerts · {d.critical_count} critical</div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Global schedule info */}
            <Card className="bg-gradient-to-r from-[#00E0FF]/5 to-[#F5B841]/5 border-[#00E0FF]/20">
                <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                        <Sparkles className="w-5 h-5 text-[#00E0FF] shrink-0 mt-0.5" />
                        <div className="text-sm space-y-1">
                            <p className="text-white font-medium">Multi-schedule model</p>
                            <p className="text-white/50 text-xs">
                                The <b>global schedule</b> (Scheduled Reports page) runs one report using SOC-wide data.
                                Each <b>tenant schedule</b> runs separately with that tenant's branding applied to the PDF and its own recipients.
                                Disable a tenant's schedule to remove its cron without losing settings.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
