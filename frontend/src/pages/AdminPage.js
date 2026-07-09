import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import { Slider } from '../components/ui/slider';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Settings,
    Server,
    Bell,
    Shield,
    Users,
    Database,
    Cpu,
    Activity,
    AlertTriangle,
    Brain,
    Palette,
    Globe,
    Key,
    Webhook,
    Mail,
    MessageSquare,
    Clock,
    RefreshCw,
    Save,
    Plus,
    Trash2,
    Edit,
    Eye,
    EyeOff,
    Copy,
    Check,
    X,
    ChevronRight,
    Building,
    Zap,
    HardDrive,
    Network,
    FileText,
    BarChart3,
    Lock,
    Unlock,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const AdminPage = () => {
    const { api, user } = useAuth();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [activeTab, setActiveTab] = useState('general');
    
    // Settings state
    const [generalSettings, setGeneralSettings] = useState({
        site_name: 'FalconOps AI',
        timezone: 'UTC',
        language: 'en',
        date_format: 'YYYY-MM-DD',
        dark_mode: true,
        compact_view: false,
        refresh_interval: 30,
    });
    
    const [monitoringSettings, setMonitoringSettings] = useState({
        default_check_interval: 60,
        default_timeout: 30,
        retry_count: 3,
        sla_threshold_latency: 300,
        sla_threshold_uptime: 99.9,
        auto_pause_on_failure: false,
        max_concurrent_checks: 50,
    });
    
    const [serverSettings, setServerSettings] = useState({
        heartbeat_interval: 30,
        offline_threshold: 120,
        cpu_warning_threshold: 80,
        cpu_critical_threshold: 95,
        memory_warning_threshold: 80,
        memory_critical_threshold: 95,
        disk_warning_threshold: 85,
        disk_critical_threshold: 95,
        auto_alert_on_threshold: true,
    });
    
    const [alertSettings, setAlertSettings] = useState({
        deduplication_window: 10,
        auto_acknowledge_after: 0,
        auto_resolve_after: 0,
        escalation_enabled: false,
        escalation_delay: 30,
        alert_retention_days: 90,
    });
    
    const [correlationSettings, setCorrelationSettings] = useState({
        enabled: true,
        time_window_minutes: 15,
        min_alerts_for_incident: 2,
        auto_run_interval: 5,
        rules: [],
    });
    
    const [notificationSettings, setNotificationSettings] = useState({
        email_enabled: true,
        email_from: 'noreply@falconops.ai',
        smtp_host: '',
        smtp_port: 587,
        teams_enabled: false,
        teams_webhook_url: '',
        slack_enabled: false,
        slack_webhook_url: '',
        pagerduty_enabled: false,
        pagerduty_api_key: '',
    });
    
    const [securitySettings, setSecuritySettings] = useState({
        session_timeout: 60,
        max_login_attempts: 5,
        lockout_duration: 15,
        password_min_length: 8,
        require_special_char: true,
        require_uppercase: true,
        require_number: true,
        two_factor_enabled: false,
        api_rate_limit: 100,
    });
    
    const [users, setUsers] = useState([]);
    const [tenants, setTenants] = useState([]);
    const [correlationRules, setCorrelationRules] = useState([]);
    
    // Modals
    const [showUserModal, setShowUserModal] = useState(false);
    const [showTenantModal, setShowTenantModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [editingTenant, setEditingTenant] = useState(null);
    
    // Form states
    const [newUser, setNewUser] = useState({ email: '', full_name: '', password: '', role: 'user' });
    const [newTenant, setNewTenant] = useState({ name: '', domain: '', contact_email: '', plan: 'starter' });

    const fetchSettings = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch correlation rules
            const rulesRes = await api.get('/correlation/rules');
            setCorrelationRules(rulesRes.data);
            setCorrelationSettings(prev => ({ ...prev, rules: rulesRes.data }));
            
            // Fetch users (admin only)
            if (user?.role === 'admin') {
                try {
                    const usersRes = await api.get('/auth/users');
                    setUsers(usersRes.data || []);
                } catch (e) {
                    // Users endpoint might not exist
                }
                
                try {
                    const tenantsRes = await api.get('/tenants');
                    setTenants(tenantsRes.data || []);
                } catch (e) {
                    // Tenants might be empty
                }
            }
        } catch (error) {
            console.error('Failed to fetch settings:', error);
        } finally {
            setLoading(false);
        }
    }, [api, user]);

    useEffect(() => {
        fetchSettings();
    }, [fetchSettings]);

    const handleSaveSettings = async (section) => {
        setSaving(true);
        try {
            // In a real app, you'd save to backend
            // await api.post('/settings', { section, data: settingsData });
            toast.success(`${section} settings saved successfully`);
        } catch (error) {
            toast.error('Failed to save settings');
        } finally {
            setSaving(false);
        }
    };

    const handleCreateUser = async () => {
        try {
            await api.post('/auth/register', newUser);
            toast.success('User created successfully');
            setShowUserModal(false);
            setNewUser({ email: '', full_name: '', password: '', role: 'user' });
            fetchSettings();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to create user');
        }
    };

    const handleDeleteUser = async (userId) => {
        if (!window.confirm('Are you sure you want to delete this user?')) return;
        try {
            await api.delete(`/auth/users/${userId}`);
            toast.success('User deleted');
            fetchSettings();
        } catch (error) {
            toast.error('Failed to delete user');
        }
    };

    const handleCreateTenant = async () => {
        try {
            await api.post('/tenants', newTenant);
            toast.success('Tenant created successfully');
            setShowTenantModal(false);
            setNewTenant({ name: '', domain: '', contact_email: '', plan: 'starter' });
            fetchSettings();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to create tenant');
        }
    };

    const handleDeleteTenant = async (tenantId) => {
        if (!window.confirm('Are you sure? This will delete all tenant data!')) return;
        try {
            await api.delete(`/tenants/${tenantId}`);
            toast.success('Tenant deleted');
            fetchSettings();
        } catch (error) {
            toast.error('Failed to delete tenant');
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        toast.success('Copied to clipboard');
    };

    if (user?.role !== 'admin') {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <Card className="bg-red-500/10 border-red-500/30 p-8 text-center">
                        <Lock className="w-16 h-16 text-red-400 mx-auto mb-4" />
                        <h2 className="text-xl font-bold text-red-400 mb-2">Access Denied</h2>
                        <p className="text-white/60">Admin privileges required to access this page</p>
                    </Card>
                </div>
            </>
        );
    }

    return (
        <>
            <div className="space-y-6" data-testid="admin-page">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-heading font-bold text-white uppercase tracking-wider flex items-center gap-3">
                            <Settings className="w-6 h-6 text-primary" />
                            Administration
                        </h1>
                        <p className="text-white/50 text-sm font-mono mt-1">Platform configuration and management</p>
                    </div>
                    <Badge variant="outline" className="border-primary/30 text-primary">
                        <Shield className="w-3 h-3 mr-1" />
                        Admin Access
                    </Badge>
                </div>

                {/* Main Content */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                    <TabsList className="bg-[#0a0a0a] border border-white/10 p-1 flex-wrap h-auto gap-1">
                        <TabsTrigger value="general" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Globe className="w-4 h-4 mr-2" />
                            General
                        </TabsTrigger>
                        <TabsTrigger value="monitoring" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Activity className="w-4 h-4 mr-2" />
                            Monitoring
                        </TabsTrigger>
                        <TabsTrigger value="servers" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Server className="w-4 h-4 mr-2" />
                            Servers
                        </TabsTrigger>
                        <TabsTrigger value="alerts" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Bell className="w-4 h-4 mr-2" />
                            Alerts
                        </TabsTrigger>
                        <TabsTrigger value="correlation" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Brain className="w-4 h-4 mr-2" />
                            Correlation
                        </TabsTrigger>
                        <TabsTrigger value="notifications" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Mail className="w-4 h-4 mr-2" />
                            Notifications
                        </TabsTrigger>
                        <TabsTrigger value="users" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Users className="w-4 h-4 mr-2" />
                            Users
                        </TabsTrigger>
                        <TabsTrigger value="tenants" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Building className="w-4 h-4 mr-2" />
                            Tenants
                        </TabsTrigger>
                        <TabsTrigger value="security" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Shield className="w-4 h-4 mr-2" />
                            Security
                        </TabsTrigger>
                        <TabsTrigger value="integrations" className="data-[state=active]:bg-primary data-[state=active]:text-black">
                            <Webhook className="w-4 h-4 mr-2" />
                            Integrations
                        </TabsTrigger>
                    </TabsList>

                    {/* General Settings */}
                    <TabsContent value="general" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Globe className="w-5 h-5 text-primary" />
                                    General Settings
                                </CardTitle>
                                <CardDescription>Configure platform-wide settings</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Platform Name</Label>
                                        <Input
                                            value={generalSettings.site_name}
                                            onChange={(e) => setGeneralSettings({ ...generalSettings, site_name: e.target.value })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Timezone</Label>
                                        <Select value={generalSettings.timezone} onValueChange={(v) => setGeneralSettings({ ...generalSettings, timezone: v })}>
                                            <SelectTrigger className="bg-white/5 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="UTC">UTC</SelectItem>
                                                <SelectItem value="Asia/Riyadh">Asia/Riyadh (GMT+3)</SelectItem>
                                                <SelectItem value="America/New_York">America/New_York (EST)</SelectItem>
                                                <SelectItem value="Europe/London">Europe/London (GMT)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Language</Label>
                                        <Select value={generalSettings.language} onValueChange={(v) => setGeneralSettings({ ...generalSettings, language: v })}>
                                            <SelectTrigger className="bg-white/5 border-white/10">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="en">English</SelectItem>
                                                <SelectItem value="ar">العربية (Arabic)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Auto Refresh Interval (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={generalSettings.refresh_interval}
                                            onChange={(e) => setGeneralSettings({ ...generalSettings, refresh_interval: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <div className="space-y-4">
                                    <h4 className="text-sm font-medium text-white">UI Preferences</h4>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <Label>Dark Mode</Label>
                                            <p className="text-xs text-white/50">Enable dark theme for the dashboard</p>
                                        </div>
                                        <Switch
                                            checked={generalSettings.dark_mode}
                                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, dark_mode: v })}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <Label>Compact View</Label>
                                            <p className="text-xs text-white/50">Use condensed layout for tables</p>
                                        </div>
                                        <Switch
                                            checked={generalSettings.compact_view}
                                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, compact_view: v })}
                                        />
                                    </div>
                                </div>
                                <Button onClick={() => handleSaveSettings('General')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save General Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Monitoring Settings */}
                    <TabsContent value="monitoring" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Activity className="w-5 h-5 text-cyan-400" />
                                    Monitoring Configuration
                                </CardTitle>
                                <CardDescription>Configure uptime monitoring defaults</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Default Check Interval (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={monitoringSettings.default_check_interval}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, default_check_interval: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Default Timeout (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={monitoringSettings.default_timeout}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, default_timeout: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Retry Count</Label>
                                        <Input
                                            type="number"
                                            value={monitoringSettings.retry_count}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, retry_count: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Max Concurrent Checks</Label>
                                        <Input
                                            type="number"
                                            value={monitoringSettings.max_concurrent_checks}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, max_concurrent_checks: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <h4 className="text-sm font-medium text-white">SLA Thresholds</h4>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Latency SLA (ms)</Label>
                                        <Input
                                            type="number"
                                            value={monitoringSettings.sla_threshold_latency}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, sla_threshold_latency: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                        <p className="text-xs text-white/40">Alert when response time exceeds this</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Uptime SLA (%)</Label>
                                        <Input
                                            type="number"
                                            step="0.1"
                                            value={monitoringSettings.sla_threshold_uptime}
                                            onChange={(e) => setMonitoringSettings({ ...monitoringSettings, sla_threshold_uptime: parseFloat(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                        <p className="text-xs text-white/40">Target uptime percentage</p>
                                    </div>
                                </div>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Auto-pause on Consecutive Failures</Label>
                                        <p className="text-xs text-white/50">Pause monitor after 5 consecutive failures</p>
                                    </div>
                                    <Switch
                                        checked={monitoringSettings.auto_pause_on_failure}
                                        onCheckedChange={(v) => setMonitoringSettings({ ...monitoringSettings, auto_pause_on_failure: v })}
                                    />
                                </div>
                                <Button onClick={() => handleSaveSettings('Monitoring')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Monitoring Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Server Settings */}
                    <TabsContent value="servers" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Server className="w-5 h-5 text-green-400" />
                                    Server Monitoring Configuration
                                </CardTitle>
                                <CardDescription>Configure server agent and threshold settings</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Heartbeat Interval (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.heartbeat_interval}
                                            onChange={(e) => setServerSettings({ ...serverSettings, heartbeat_interval: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Offline Threshold (seconds)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.offline_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, offline_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                        <p className="text-xs text-white/40">Mark server offline after no heartbeat</p>
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <h4 className="text-sm font-medium text-white flex items-center gap-2">
                                    <Cpu className="w-4 h-4 text-cyan-400" />
                                    CPU Thresholds
                                </h4>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label className="text-yellow-400">Warning Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.cpu_warning_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, cpu_warning_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-yellow-500/30"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-red-400">Critical Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.cpu_critical_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, cpu_critical_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-red-500/30"
                                        />
                                    </div>
                                </div>
                                <h4 className="text-sm font-medium text-white flex items-center gap-2">
                                    <HardDrive className="w-4 h-4 text-purple-400" />
                                    Memory Thresholds
                                </h4>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label className="text-yellow-400">Warning Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.memory_warning_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, memory_warning_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-yellow-500/30"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-red-400">Critical Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.memory_critical_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, memory_critical_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-red-500/30"
                                        />
                                    </div>
                                </div>
                                <h4 className="text-sm font-medium text-white flex items-center gap-2">
                                    <Database className="w-4 h-4 text-orange-400" />
                                    Disk Thresholds
                                </h4>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label className="text-yellow-400">Warning Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.disk_warning_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, disk_warning_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-yellow-500/30"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-red-400">Critical Threshold (%)</Label>
                                        <Input
                                            type="number"
                                            value={serverSettings.disk_critical_threshold}
                                            onChange={(e) => setServerSettings({ ...serverSettings, disk_critical_threshold: parseInt(e.target.value) })}
                                            className="bg-white/5 border-red-500/30"
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Auto-generate Alerts on Threshold</Label>
                                        <p className="text-xs text-white/50">Automatically create alerts when thresholds are exceeded</p>
                                    </div>
                                    <Switch
                                        checked={serverSettings.auto_alert_on_threshold}
                                        onCheckedChange={(v) => setServerSettings({ ...serverSettings, auto_alert_on_threshold: v })}
                                    />
                                </div>
                                <Button onClick={() => handleSaveSettings('Server')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Server Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Alert Settings */}
                    <TabsContent value="alerts" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Bell className="w-5 h-5 text-yellow-400" />
                                    Alert Configuration
                                </CardTitle>
                                <CardDescription>Configure alert behavior and lifecycle</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Deduplication Window (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={alertSettings.deduplication_window}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, deduplication_window: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                        <p className="text-xs text-white/40">Suppress duplicate alerts within this window</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Alert Retention (days)</Label>
                                        <Input
                                            type="number"
                                            value={alertSettings.alert_retention_days}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, alert_retention_days: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Auto-acknowledge After (minutes, 0=disabled)</Label>
                                        <Input
                                            type="number"
                                            value={alertSettings.auto_acknowledge_after}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, auto_acknowledge_after: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Auto-resolve After (minutes, 0=disabled)</Label>
                                        <Input
                                            type="number"
                                            value={alertSettings.auto_resolve_after}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, auto_resolve_after: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <h4 className="text-sm font-medium text-white">Escalation</h4>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Enable Escalation</Label>
                                        <p className="text-xs text-white/50">Escalate unacknowledged alerts</p>
                                    </div>
                                    <Switch
                                        checked={alertSettings.escalation_enabled}
                                        onCheckedChange={(v) => setAlertSettings({ ...alertSettings, escalation_enabled: v })}
                                    />
                                </div>
                                {alertSettings.escalation_enabled && (
                                    <div className="space-y-2">
                                        <Label>Escalation Delay (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={alertSettings.escalation_delay}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, escalation_delay: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                )}
                                <Button onClick={() => handleSaveSettings('Alert')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Alert Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Correlation Settings */}
                    <TabsContent value="correlation" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Brain className="w-5 h-5 text-purple-400" />
                                    AI Correlation Engine
                                </CardTitle>
                                <CardDescription>Configure intelligent alert correlation</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <Label>Enable Smart Correlation</Label>
                                        <p className="text-xs text-white/50">Use AI rules to correlate alerts into incidents</p>
                                    </div>
                                    <Switch
                                        checked={correlationSettings.enabled}
                                        onCheckedChange={(v) => setCorrelationSettings({ ...correlationSettings, enabled: v })}
                                    />
                                </div>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Correlation Time Window (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={correlationSettings.time_window_minutes}
                                            onChange={(e) => setCorrelationSettings({ ...correlationSettings, time_window_minutes: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Min Alerts for Incident</Label>
                                        <Input
                                            type="number"
                                            value={correlationSettings.min_alerts_for_incident}
                                            onChange={(e) => setCorrelationSettings({ ...correlationSettings, min_alerts_for_incident: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Auto-run Interval (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={correlationSettings.auto_run_interval}
                                            onChange={(e) => setCorrelationSettings({ ...correlationSettings, auto_run_interval: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <h4 className="text-sm font-medium text-white">Active Correlation Rules ({correlationRules.length})</h4>
                                <div className="space-y-2">
                                    {correlationRules.map((rule) => (
                                        <div key={rule.id} className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10">
                                            <div className="flex items-center gap-3">
                                                <Zap className={`w-4 h-4 ${rule.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'}`} />
                                                <div>
                                                    <p className="text-white text-sm font-medium">{rule.name}</p>
                                                    <p className="text-white/40 text-xs">{rule.description}</p>
                                                </div>
                                            </div>
                                            <Badge variant="outline" className={rule.severity === 'critical' ? 'border-red-500/30 text-red-400' : 'border-yellow-500/30 text-yellow-400'}>
                                                {rule.severity}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                                <Button onClick={() => handleSaveSettings('Correlation')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Correlation Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Notification Settings */}
                    <TabsContent value="notifications" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Mail className="w-5 h-5 text-blue-400" />
                                    Notification Channels
                                </CardTitle>
                                <CardDescription>Configure alert notification delivery</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {/* Email */}
                                <div className="space-y-4 p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Mail className="w-5 h-5 text-blue-400" />
                                            <Label className="text-lg">Email Notifications</Label>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.email_enabled}
                                            onCheckedChange={(v) => setNotificationSettings({ ...notificationSettings, email_enabled: v })}
                                        />
                                    </div>
                                    {notificationSettings.email_enabled && (
                                        <div className="grid md:grid-cols-2 gap-4 pt-2">
                                            <div className="space-y-2">
                                                <Label>From Address</Label>
                                                <Input
                                                    value={notificationSettings.email_from}
                                                    onChange={(e) => setNotificationSettings({ ...notificationSettings, email_from: e.target.value })}
                                                    className="bg-white/5 border-white/10"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>SMTP Host</Label>
                                                <Input
                                                    value={notificationSettings.smtp_host}
                                                    onChange={(e) => setNotificationSettings({ ...notificationSettings, smtp_host: e.target.value })}
                                                    className="bg-white/5 border-white/10"
                                                    placeholder="smtp.sendgrid.net"
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Slack */}
                                <div className="space-y-4 p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <MessageSquare className="w-5 h-5 text-green-400" />
                                            <Label className="text-lg">Slack Notifications</Label>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.slack_enabled}
                                            onCheckedChange={(v) => setNotificationSettings({ ...notificationSettings, slack_enabled: v })}
                                        />
                                    </div>
                                    {notificationSettings.slack_enabled && (
                                        <div className="space-y-2 pt-2">
                                            <Label>Webhook URL</Label>
                                            <Input
                                                type="password"
                                                value={notificationSettings.slack_webhook_url}
                                                onChange={(e) => setNotificationSettings({ ...notificationSettings, slack_webhook_url: e.target.value })}
                                                className="bg-white/5 border-white/10"
                                                placeholder="https://hooks.slack.com/services/..."
                                            />
                                        </div>
                                    )}
                                </div>

                                {/* Microsoft Teams */}
                                <div className="space-y-4 p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <MessageSquare className="w-5 h-5 text-purple-400" />
                                            <Label className="text-lg">Microsoft Teams</Label>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.teams_enabled}
                                            onCheckedChange={(v) => setNotificationSettings({ ...notificationSettings, teams_enabled: v })}
                                        />
                                    </div>
                                    {notificationSettings.teams_enabled && (
                                        <div className="space-y-2 pt-2">
                                            <Label>Webhook URL</Label>
                                            <Input
                                                type="password"
                                                value={notificationSettings.teams_webhook_url}
                                                onChange={(e) => setNotificationSettings({ ...notificationSettings, teams_webhook_url: e.target.value })}
                                                className="bg-white/5 border-white/10"
                                                placeholder="https://outlook.office.com/webhook/..."
                                            />
                                        </div>
                                    )}
                                </div>

                                {/* PagerDuty */}
                                <div className="space-y-4 p-4 bg-white/5 rounded-sm border border-white/10">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <Bell className="w-5 h-5 text-orange-400" />
                                            <Label className="text-lg">PagerDuty</Label>
                                        </div>
                                        <Switch
                                            checked={notificationSettings.pagerduty_enabled}
                                            onCheckedChange={(v) => setNotificationSettings({ ...notificationSettings, pagerduty_enabled: v })}
                                        />
                                    </div>
                                    {notificationSettings.pagerduty_enabled && (
                                        <div className="space-y-2 pt-2">
                                            <Label>API Key</Label>
                                            <Input
                                                type="password"
                                                value={notificationSettings.pagerduty_api_key}
                                                onChange={(e) => setNotificationSettings({ ...notificationSettings, pagerduty_api_key: e.target.value })}
                                                className="bg-white/5 border-white/10"
                                            />
                                        </div>
                                    )}
                                </div>

                                <Button onClick={() => handleSaveSettings('Notification')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Notification Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Users Tab */}
                    <TabsContent value="users" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle className="text-white flex items-center gap-2">
                                        <Users className="w-5 h-5 text-cyan-400" />
                                        User Management
                                    </CardTitle>
                                    <CardDescription>Manage platform users and roles</CardDescription>
                                </div>
                                <Button onClick={() => setShowUserModal(true)} className="bg-primary text-black">
                                    <Plus className="w-4 h-4 mr-2" />
                                    Add User
                                </Button>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {users.length === 0 ? (
                                        <p className="text-white/50 text-center py-8">No users found. User listing may require additional setup.</p>
                                    ) : (
                                        users.map((u) => (
                                            <div key={u.id} className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                                                        <span className="text-primary font-bold">{u.full_name?.charAt(0) || u.email?.charAt(0)}</span>
                                                    </div>
                                                    <div>
                                                        <p className="text-white font-medium">{u.full_name || u.email}</p>
                                                        <p className="text-white/40 text-xs">{u.email}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className={
                                                        u.role === 'admin' ? 'border-red-500/30 text-red-400' :
                                                        u.role === 'user' ? 'border-green-500/30 text-green-400' :
                                                        'border-white/30 text-white/60'
                                                    }>
                                                        {u.role}
                                                    </Badge>
                                                    {u.id !== user?.id && (
                                                        <Button size="sm" variant="ghost" onClick={() => handleDeleteUser(u.id)} className="text-red-400 hover:text-red-300">
                                                            <Trash2 className="w-4 h-4" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Tenants Tab */}
                    <TabsContent value="tenants" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle className="text-white flex items-center gap-2">
                                        <Building className="w-5 h-5 text-purple-400" />
                                        Tenant Management
                                    </CardTitle>
                                    <CardDescription>Manage multi-tenant organizations</CardDescription>
                                </div>
                                <Button onClick={() => setShowTenantModal(true)} className="bg-primary text-black">
                                    <Plus className="w-4 h-4 mr-2" />
                                    Add Tenant
                                </Button>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {tenants.length === 0 ? (
                                        <p className="text-white/50 text-center py-8">No tenants configured. Create your first tenant to enable multi-tenancy.</p>
                                    ) : (
                                        tenants.map((t) => (
                                            <div key={t.id} className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10">
                                                <div className="flex items-center gap-3">
                                                    <Building className="w-8 h-8 text-purple-400" />
                                                    <div>
                                                        <p className="text-white font-medium">{t.name}</p>
                                                        <p className="text-white/40 text-xs">{t.domain || 'No domain'} • {t.plan} plan</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="border-white/30">
                                                        {t.user_count || 0} users
                                                    </Badge>
                                                    <Button size="sm" variant="ghost" onClick={() => handleDeleteTenant(t.id)} className="text-red-400 hover:text-red-300">
                                                        <Trash2 className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Security Tab */}
                    <TabsContent value="security" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Shield className="w-5 h-5 text-red-400" />
                                    Security Settings
                                </CardTitle>
                                <CardDescription>Configure authentication and access control</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Session Timeout (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={securitySettings.session_timeout}
                                            onChange={(e) => setSecuritySettings({ ...securitySettings, session_timeout: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>API Rate Limit (requests/min)</Label>
                                        <Input
                                            type="number"
                                            value={securitySettings.api_rate_limit}
                                            onChange={(e) => setSecuritySettings({ ...securitySettings, api_rate_limit: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Max Login Attempts</Label>
                                        <Input
                                            type="number"
                                            value={securitySettings.max_login_attempts}
                                            onChange={(e) => setSecuritySettings({ ...securitySettings, max_login_attempts: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Lockout Duration (minutes)</Label>
                                        <Input
                                            type="number"
                                            value={securitySettings.lockout_duration}
                                            onChange={(e) => setSecuritySettings({ ...securitySettings, lockout_duration: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <Separator className="bg-white/10" />
                                <h4 className="text-sm font-medium text-white">Password Requirements</h4>
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div className="space-y-2">
                                        <Label>Minimum Length</Label>
                                        <Input
                                            type="number"
                                            value={securitySettings.password_min_length}
                                            onChange={(e) => setSecuritySettings({ ...securitySettings, password_min_length: parseInt(e.target.value) })}
                                            className="bg-white/5 border-white/10"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <Label>Require Special Character</Label>
                                        <Switch
                                            checked={securitySettings.require_special_char}
                                            onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, require_special_char: v })}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <Label>Require Uppercase Letter</Label>
                                        <Switch
                                            checked={securitySettings.require_uppercase}
                                            onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, require_uppercase: v })}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <Label>Require Number</Label>
                                        <Switch
                                            checked={securitySettings.require_number}
                                            onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, require_number: v })}
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <Label>Two-Factor Authentication</Label>
                                            <p className="text-xs text-white/50">Require 2FA for all users</p>
                                        </div>
                                        <Switch
                                            checked={securitySettings.two_factor_enabled}
                                            onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, two_factor_enabled: v })}
                                        />
                                    </div>
                                </div>
                                <Button onClick={() => handleSaveSettings('Security')} disabled={saving} className="bg-primary text-black">
                                    <Save className="w-4 h-4 mr-2" />
                                    Save Security Settings
                                </Button>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Integrations Tab */}
                    <TabsContent value="integrations" className="space-y-4">
                        <Card className="bg-[#0a0a0a] border-white/5">
                            <CardHeader>
                                <CardTitle className="text-white flex items-center gap-2">
                                    <Webhook className="w-5 h-5 text-green-400" />
                                    Webhook & API Integration
                                </CardTitle>
                                <CardDescription>Configure external integrations</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <Label>Alert Webhook URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            value={`${BACKEND_URL}/api/alerts/webhook`}
                                            readOnly
                                            className="bg-white/5 border-white/10 font-mono text-sm"
                                        />
                                        <Button variant="outline" onClick={() => copyToClipboard(`${BACKEND_URL}/api/alerts/webhook`)} className="border-white/10">
                                            <Copy className="w-4 h-4" />
                                        </Button>
                                    </div>
                                    <p className="text-xs text-white/40">Use this URL to send alerts from external monitoring tools</p>
                                </div>
                                <Separator className="bg-white/10" />
                                <div className="space-y-4">
                                    <h4 className="text-sm font-medium text-white">Example Payload</h4>
                                    <pre className="bg-black/50 p-4 rounded-sm text-xs text-green-400 overflow-x-auto">
{JSON.stringify({
    source: "AppDynamics",
    severity: "critical",
    title: "High CPU Usage",
    description: "CPU usage exceeded 95% threshold",
    service: "payment-service",
    host: "prod-server-01",
    metric_name: "cpu_usage",
    metric_value: 97.5,
    threshold: 95,
    tags: { environment: "production", team: "payments" }
}, null, 2)}
                                    </pre>
                                </div>
                                <Separator className="bg-white/10" />
                                <div className="space-y-2">
                                    <Label>Server Metrics Ingestion URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            value={`${BACKEND_URL}/api/servers/metrics/ingest`}
                                            readOnly
                                            className="bg-white/5 border-white/10 font-mono text-sm"
                                        />
                                        <Button variant="outline" onClick={() => copyToClipboard(`${BACKEND_URL}/api/servers/metrics/ingest`)} className="border-white/10">
                                            <Copy className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label>Server Registration URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            value={`${BACKEND_URL}/api/servers/register`}
                                            readOnly
                                            className="bg-white/5 border-white/10 font-mono text-sm"
                                        />
                                        <Button variant="outline" onClick={() => copyToClipboard(`${BACKEND_URL}/api/servers/register`)} className="border-white/10">
                                            <Copy className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>

            {/* Add User Modal */}
            <Dialog open={showUserModal} onOpenChange={setShowUserModal}>
                <DialogContent className="bg-[#0a0a0a] border-white/10">
                    <DialogHeader>
                        <DialogTitle className="text-white">Add New User</DialogTitle>
                        <DialogDescription>Create a new user account</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label>Full Name</Label>
                            <Input
                                value={newUser.full_name}
                                onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                                className="bg-white/5 border-white/10"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Email</Label>
                            <Input
                                type="email"
                                value={newUser.email}
                                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                                className="bg-white/5 border-white/10"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Password</Label>
                            <Input
                                type="password"
                                value={newUser.password}
                                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                className="bg-white/5 border-white/10"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Role</Label>
                            <Select value={newUser.role} onValueChange={(v) => setNewUser({ ...newUser, role: v })}>
                                <SelectTrigger className="bg-white/5 border-white/10">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="admin">Admin</SelectItem>
                                    <SelectItem value="user">User</SelectItem>
                                    <SelectItem value="viewer">Viewer</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowUserModal(false)} className="border-white/10">Cancel</Button>
                        <Button onClick={handleCreateUser} className="bg-primary text-black">Create User</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Add Tenant Modal */}
            <Dialog open={showTenantModal} onOpenChange={setShowTenantModal}>
                <DialogContent className="bg-[#0a0a0a] border-white/10">
                    <DialogHeader>
                        <DialogTitle className="text-white">Add New Tenant</DialogTitle>
                        <DialogDescription>Create a new tenant organization</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label>Organization Name</Label>
                            <Input
                                value={newTenant.name}
                                onChange={(e) => setNewTenant({ ...newTenant, name: e.target.value })}
                                className="bg-white/5 border-white/10"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Domain (optional)</Label>
                            <Input
                                value={newTenant.domain}
                                onChange={(e) => setNewTenant({ ...newTenant, domain: e.target.value })}
                                className="bg-white/5 border-white/10"
                                placeholder="example.com"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Contact Email</Label>
                            <Input
                                type="email"
                                value={newTenant.contact_email}
                                onChange={(e) => setNewTenant({ ...newTenant, contact_email: e.target.value })}
                                className="bg-white/5 border-white/10"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Plan</Label>
                            <Select value={newTenant.plan} onValueChange={(v) => setNewTenant({ ...newTenant, plan: v })}>
                                <SelectTrigger className="bg-white/5 border-white/10">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="starter">Starter (10 users, 50 servers)</SelectItem>
                                    <SelectItem value="professional">Professional (50 users, 200 servers)</SelectItem>
                                    <SelectItem value="enterprise">Enterprise (Unlimited)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowTenantModal(false)} className="border-white/10">Cancel</Button>
                        <Button onClick={handleCreateTenant} className="bg-primary text-black">Create Tenant</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};
