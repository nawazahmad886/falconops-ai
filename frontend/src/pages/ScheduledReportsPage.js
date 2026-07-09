import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import {
    Calendar, Clock, Mail, Send, RefreshCw, Save, PlayCircle,
    CheckCircle, XCircle, AlertTriangle, Sparkles, Bell, Users,
} from 'lucide-react';

const DAYS = [
    { value: 'sun', label: 'Sun' },
    { value: 'mon', label: 'Mon' },
    { value: 'tue', label: 'Tue' },
    { value: 'wed', label: 'Wed' },
    { value: 'thu', label: 'Thu' },
    { value: 'fri', label: 'Fri' },
    { value: 'sat', label: 'Sat' },
];

export default function ScheduledReportsPage() {
    const { api } = useAuth();
    const [settings, setSettings] = useState(null);
    const [logs, setLogs] = useState([]);
    const [newRecipient, setNewRecipient] = useState('');
    const [saving, setSaving] = useState(false);
    const [triggering, setTriggering] = useState(false);
    const [loading, setLoading] = useState(true);
    const [testEmailAddr, setTestEmailAddr] = useState('');
    const [testing, setTesting] = useState(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [s, l] = await Promise.all([
                api.get('/scheduled-reports/settings'),
                api.get('/scheduled-reports/logs?limit=20'),
            ]);
            setSettings(s.data);
            setLogs(l.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const toggleDay = (d) => {
        if (!settings) return;
        const cur = settings.days_of_week || [];
        const next = cur.includes(d) ? cur.filter(x => x !== d) : [...cur, d];
        setSettings({ ...settings, days_of_week: next });
    };

    const addRecipient = () => {
        const email = newRecipient.trim();
        if (!email || !email.includes('@')) {
            toast.error('Enter a valid email');
            return;
        }
        const cur = settings.recipients || [];
        if (cur.includes(email)) {
            toast.error('Already added');
            return;
        }
        setSettings({ ...settings, recipients: [...cur, email] });
        setNewRecipient('');
    };

    const removeRecipient = (email) => {
        setSettings({ ...settings, recipients: (settings.recipients || []).filter(r => r !== email) });
    };

    const save = async () => {
        setSaving(true);
        try {
            const payload = {
                enabled: settings.enabled,
                days_of_week: settings.days_of_week,
                hour: parseInt(settings.hour, 10),
                minute: parseInt(settings.minute, 10),
                timezone: settings.timezone || 'UTC',
                period_days: parseInt(settings.period_days, 10),
                recipients: settings.recipients || [],
                sender_email: settings.sender_email,
                portal_base_url: settings.portal_base_url || '',
            };
            await api.put('/scheduled-reports/settings', payload);
            toast.success('Schedule saved & cron updated');
            await fetchAll();
        } catch (e) {
            toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
        }
        setSaving(false);
    };

    const triggerNow = async () => {
        setTriggering(true);
        try {
            const res = await api.post('/scheduled-reports/trigger', {});
            const e = res.data?.email || {};
            if (e.ok) toast.success(`Report generated + email sent to ${(res.data.recipients || []).length} recipient(s)`);
            else if (e.skipped) toast.success(`Report generated (no recipients configured)`);
            else toast.error(`Email failed: ${e.error || 'unknown'}`);
            await fetchAll();
        } catch (err) {
            toast.error(`Trigger failed: ${err.response?.data?.detail || err.message}`);
        }
        setTriggering(false);
    };

    const sendTestEmail = async () => {
        if (!testEmailAddr || !testEmailAddr.includes('@')) {
            toast.error('Enter a valid test email');
            return;
        }
        setTesting(true);
        try {
            const res = await api.post('/scheduled-reports/test-email', { to: testEmailAddr });
            if (res.data?.ok) toast.success(`Test email sent to ${testEmailAddr}`);
            else toast.error(`Test failed: ${res.data?.error}`);
        } catch (e) {
            toast.error(`Test failed: ${e.response?.data?.detail || e.message}`);
        }
        setTesting(false);
    };

    if (loading || !settings) {
        return (
            <div className="flex items-center justify-center py-20">
                <RefreshCw className="w-6 h-6 animate-spin text-white/30" />
            </div>
        );
    }

    return (
        <div className="space-y-6" data-testid="scheduled-reports-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Calendar className="w-6 h-6 text-[#F5B841]" />
                        Scheduled Reports
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Auto-generate enterprise weekly reports on a cron · Email via Resend · Attach PDF + DOCX + Excel
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button
                        onClick={triggerNow}
                        disabled={triggering}
                        className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black"
                        data-testid="trigger-now-btn"
                    >
                        {triggering ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <PlayCircle className="w-4 h-4 mr-2" />}
                        Run Now
                    </Button>
                    <Button
                        onClick={save}
                        disabled={saving}
                        className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                        data-testid="save-schedule-btn"
                    >
                        {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                        Save
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Schedule Config */}
                <Card className="bg-[#0D1117] border-white/5 lg:col-span-2">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Clock className="w-4 h-4 text-[#00E0FF]" />
                            Schedule Configuration
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        {/* Enable Switch */}
                        <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5">
                            <div>
                                <p className="text-sm text-white font-medium">Scheduler Enabled</p>
                                <p className="text-xs text-white/40">Turn off to pause all automatic runs</p>
                            </div>
                            <Switch
                                checked={settings.enabled}
                                onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
                                data-testid="enabled-switch"
                            />
                        </div>

                        {/* Days of Week */}
                        <div>
                            <Label className="text-xs text-white/60 mb-2 block">Run on (multiple allowed)</Label>
                            <div className="flex gap-2 flex-wrap">
                                {DAYS.map(d => {
                                    const active = (settings.days_of_week || []).includes(d.value);
                                    return (
                                        <button
                                            key={d.value}
                                            onClick={() => toggleDay(d.value)}
                                            className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-all ${
                                                active
                                                    ? 'bg-[#00E0FF] text-black border-[#00E0FF]'
                                                    : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
                                            }`}
                                            data-testid={`day-${d.value}`}
                                        >
                                            {d.label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Time */}
                        <div className="grid grid-cols-3 gap-3">
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Hour (0-23)</Label>
                                <Input
                                    type="number" min="0" max="23"
                                    value={settings.hour}
                                    onChange={(e) => setSettings({ ...settings, hour: e.target.value })}
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="hour-input"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Minute (0-59)</Label>
                                <Input
                                    type="number" min="0" max="59"
                                    value={settings.minute}
                                    onChange={(e) => setSettings({ ...settings, minute: e.target.value })}
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="minute-input"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Timezone</Label>
                                <Input
                                    value={settings.timezone || 'UTC'}
                                    onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                                    placeholder="UTC"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="timezone-input"
                                />
                            </div>
                        </div>

                        {/* Period + Portal URL + Sender */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Report Period (days)</Label>
                                <Input
                                    type="number" min="1" max="90"
                                    value={settings.period_days}
                                    onChange={(e) => setSettings({ ...settings, period_days: e.target.value })}
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="period-days-input"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Portal Base URL (optional)</Label>
                                <Input
                                    value={settings.portal_base_url || ''}
                                    onChange={(e) => setSettings({ ...settings, portal_base_url: e.target.value })}
                                    placeholder="https://falconops.com"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="portal-base-url-input"
                                />
                                <p className="text-[10px] text-white/30 mt-1">Prepended to share links embedded in emails</p>
                            </div>
                        </div>

                        <div>
                            <Label className="text-xs text-white/60 mb-2 block">Sender Email (Resend)</Label>
                            <Input
                                value={settings.sender_email || ''}
                                onChange={(e) => setSettings({ ...settings, sender_email: e.target.value })}
                                placeholder="onboarding@resend.dev"
                                className="bg-[#161B22] border-white/10"
                                data-testid="sender-email-input"
                            />
                            <p className="text-[10px] text-amber-400/70 mt-1 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                Using onboarding@resend.dev works only for your Resend account's verified email. Add your own domain at resend.com/domains for production.
                            </p>
                        </div>

                        {/* Recipients */}
                        <div>
                            <Label className="text-xs text-white/60 mb-2 block flex items-center gap-1">
                                <Users className="w-3 h-3" /> Recipients ({(settings.recipients || []).length})
                            </Label>
                            <div className="flex gap-2 mb-2">
                                <Input
                                    type="email"
                                    value={newRecipient}
                                    onChange={(e) => setNewRecipient(e.target.value)}
                                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRecipient(); } }}
                                    placeholder="ciso@company.com"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="new-recipient-input"
                                />
                                <Button onClick={addRecipient} variant="outline" className="border-white/10" data-testid="add-recipient-btn">
                                    Add
                                </Button>
                            </div>
                            {(settings.recipients || []).length > 0 ? (
                                <div className="flex flex-wrap gap-1.5" data-testid="recipients-list">
                                    {settings.recipients.map(r => (
                                        <Badge
                                            key={r}
                                            className="bg-[#00E0FF]/10 text-[#00E0FF] border-[#00E0FF]/30 pl-2 pr-1 py-1 flex items-center gap-1 cursor-default"
                                        >
                                            {r}
                                            <button
                                                onClick={() => removeRecipient(r)}
                                                className="ml-1 w-4 h-4 rounded-full hover:bg-red-500/30 text-red-400 flex items-center justify-center text-xs"
                                                data-testid={`remove-${r}`}
                                            >
                                                ×
                                            </button>
                                        </Badge>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-white/30 italic">No recipients. Report will be generated but not emailed.</p>
                            )}
                        </div>

                        {/* Test Email */}
                        <div className="pt-4 border-t border-white/5">
                            <Label className="text-xs text-white/60 mb-2 block flex items-center gap-1">
                                <Send className="w-3 h-3" /> Send Test Email
                            </Label>
                            <div className="flex gap-2">
                                <Input
                                    type="email"
                                    value={testEmailAddr}
                                    onChange={(e) => setTestEmailAddr(e.target.value)}
                                    placeholder="you@company.com"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="test-email-input"
                                />
                                <Button
                                    onClick={sendTestEmail}
                                    disabled={testing}
                                    variant="outline"
                                    className="border-white/10"
                                    data-testid="send-test-btn"
                                >
                                    {testing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Mail className="w-4 h-4 mr-2" />}
                                    Test
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Activity Log */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Bell className="w-4 h-4 text-[#F5B841]" />
                            Recent Runs ({logs.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {logs.length === 0 ? (
                            <div className="text-center py-8 text-white/30 text-xs">No runs yet</div>
                        ) : (
                            <div className="space-y-2 max-h-[500px] overflow-y-auto" data-testid="run-logs">
                                {logs.map((l, i) => {
                                    const ok = l.status === 'success';
                                    const detail = l.detail || {};
                                    const em = detail.email || {};
                                    const emailOK = em.ok || em.skipped;
                                    return (
                                        <div
                                            key={i}
                                            className={`p-2.5 rounded-lg border text-xs ${
                                                ok ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'
                                            }`}
                                            data-testid={`log-${i}`}
                                        >
                                            <div className="flex items-center gap-2 mb-1">
                                                {ok ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                                                <span className={ok ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'}>
                                                    {l.status}
                                                </span>
                                                <span className="text-white/30 ml-auto">
                                                    {new Date(l.timestamp).toLocaleString()}
                                                </span>
                                            </div>
                                            {detail.report_id && (
                                                <div className="text-white/60">Report: <span className="font-mono">{detail.report_id}</span></div>
                                            )}
                                            {detail.period && (
                                                <div className="text-white/40">Period: {detail.period}</div>
                                            )}
                                            {detail.total_alerts !== undefined && (
                                                <div className="text-white/40">
                                                    {detail.total_alerts} alerts · {detail.critical_count} critical
                                                </div>
                                            )}
                                            {detail.recipients?.length > 0 && (
                                                <div className="text-white/40 truncate">
                                                    ✉ {detail.recipients.join(', ')} {emailOK ? '✓' : `✗ ${em.error?.slice(0,50)}`}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Tips card */}
            <Card className="bg-gradient-to-r from-[#00E0FF]/5 to-[#F5B841]/5 border-[#00E0FF]/20">
                <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                        <Sparkles className="w-5 h-5 text-[#00E0FF] shrink-0 mt-0.5" />
                        <div className="space-y-1 text-sm">
                            <p className="text-white font-medium">How it works</p>
                            <p className="text-white/50 text-xs">
                                At each scheduled run, FalconOps auto-fetches SOC data for the last <b>{settings.period_days} days</b>,
                                runs the CSO-level AI summary, generates branded PDF + DOCX + Excel,
                                creates a 30-day public share link (auto-attached to the email),
                                and emails all recipients as attachments.
                                Every run is logged here.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
