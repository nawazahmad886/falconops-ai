import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    Settings, Webhook, Cloud, Bell, Search, MessageSquare,
    Mail, Key, Shield, RefreshCw, Save, Trash2, Eye, EyeOff,
    Check, X, ChevronRight, Link, Unplug, Plug, Server,
    CheckCircle, XCircle, BarChart3, Ticket,
} from 'lucide-react';

const CATEGORY_ICONS = {
    cloud: Cloud,
    notification: Bell,
    data_source: Search,
    itsm: Ticket,
    custom: Webhook,
};

const CATEGORY_LABELS = {
    cloud: 'Cloud Security',
    notification: 'Notifications',
    data_source: 'Data Sources',
    itsm: 'ITSM',
    custom: 'Custom',
};

const CATEGORY_COLORS = {
    cloud: 'text-cyan-400',
    notification: 'text-amber-400',
    data_source: 'text-blue-400',
    itsm: 'text-purple-400',
    custom: 'text-green-400',
};

export default function IntegrationsPage() {
    const { api } = useAuth();
    const [loading, setLoading] = useState(true);
    const [catalog, setCatalog] = useState([]);
    const [configuring, setConfiguring] = useState(null);
    const [configValues, setConfigValues] = useState({});
    const [enabled, setEnabled] = useState(true);
    const [saving, setSaving] = useState(false);
    const [showPasswords, setShowPasswords] = useState({});
    const [testing, setTesting] = useState(null);
    const [filterCategory, setFilterCategory] = useState('all');

    const fetchCatalog = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/integrations/catalog');
            setCatalog(res.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchCatalog(); }, [fetchCatalog]);

    const openConfig = async (integration) => {
        setConfiguring(integration);
        setEnabled(integration.enabled || false);
        // Load existing config if configured
        if (integration.configured) {
            try {
                const res = await api.get(`/admin/integrations/${integration.id}`);
                if (res.data && !res.data.error) {
                    setConfigValues(res.data.config || {});
                    setEnabled(res.data.enabled);
                    return;
                }
            } catch (e) { /* not configured yet */ }
        }
        // Set defaults
        const defaults = {};
        integration.fields?.forEach(f => { if (f.default) defaults[f.key] = f.default; });
        setConfigValues(defaults);
    };

    const saveConfig = async () => {
        if (!configuring) return;
        setSaving(true);
        try {
            const res = await api.put(`/admin/integrations/${configuring.id}`, {
                config: configValues,
                enabled,
            });
            if (res.data?.error) {
                toast.error(res.data.error);
            } else {
                toast.success(`${configuring.name} saved successfully`);
                setConfiguring(null);
                fetchCatalog();
            }
        } catch (e) {
            toast.error('Failed to save integration');
        }
        setSaving(false);
    };

    const toggleIntegration = async (integration) => {
        try {
            await api.patch(`/admin/integrations/${integration.id}/toggle`, {
                enabled: !integration.enabled,
            });
            fetchCatalog();
            toast.success(`${integration.name} ${!integration.enabled ? 'enabled' : 'disabled'}`);
        } catch (e) { toast.error('Toggle failed'); }
    };

    const deleteIntegration = async (integration) => {
        try {
            await api.delete(`/admin/integrations/${integration.id}`);
            fetchCatalog();
            toast.success(`${integration.name} removed`);
        } catch (e) { toast.error('Delete failed'); }
    };

    const testConnection = async (integrationId) => {
        setTesting(integrationId);
        try {
            const res = await api.post(`/admin/integrations/${integrationId}/test`);
            if (res.data?.success) {
                toast.success('Connection verified');
            } else {
                toast.error(res.data?.error || 'Connection failed');
            }
        } catch (e) { toast.error('Test failed'); }
        setTesting(null);
    };

    const categories = ['all', ...new Set(catalog.map(c => c.category))];
    const filtered = filterCategory === 'all' ? catalog : catalog.filter(c => c.category === filterCategory);
    const grouped = {};
    filtered.forEach(c => {
        if (!grouped[c.category]) grouped[c.category] = [];
        grouped[c.category].push(c);
    });

    if (loading) return <div className="flex items-center justify-center h-64 text-white/40">Loading integrations...</div>;

    return (
        <div className="space-y-6" data-testid="integrations-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3" data-testid="integrations-title">
                        <Plug className="w-7 h-7 text-green-400" />
                        Integrations
                    </h1>
                    <p className="text-sm text-white/40 mt-1">Manage API keys, connectors & external service integrations</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchCatalog} className="border-white/10 text-xs">
                    <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
                </Button>
            </div>

            {/* Category Filter */}
            <div className="flex gap-1.5 flex-wrap">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setFilterCategory(cat)}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                            filterCategory === cat ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                        }`}
                        data-testid={`filter-${cat}`}
                    >
                        {cat === 'all' ? 'All' : CATEGORY_LABELS[cat] || cat}
                    </button>
                ))}
            </div>

            {/* Integrations Grid */}
            {Object.entries(grouped).map(([category, items]) => {
                const CatIcon = CATEGORY_ICONS[category] || Webhook;
                const catColor = CATEGORY_COLORS[category] || 'text-white/60';
                return (
                    <div key={category}>
                        <h3 className={`text-sm font-medium mb-3 flex items-center gap-2 ${catColor}`}>
                            <CatIcon className="w-4 h-4" /> {CATEGORY_LABELS[category] || category}
                        </h3>
                        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {items.map(item => (
                                <Card key={item.id} className={`bg-[#0D1117] border-white/5 hover:border-white/10 transition-colors ${item.enabled ? 'border-l-2 border-l-emerald-500' : ''}`} data-testid={`integration-${item.id}`}>
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between mb-3">
                                            <div>
                                                <h4 className="text-sm font-semibold text-white/90">{item.name}</h4>
                                                <p className="text-[10px] text-white/30 mt-0.5 line-clamp-1">{item.description}</p>
                                            </div>
                                            {item.configured && (
                                                <Switch
                                                    checked={item.enabled}
                                                    onCheckedChange={() => toggleIntegration(item)}
                                                    data-testid={`toggle-${item.id}`}
                                                />
                                            )}
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-1.5">
                                                {item.configured ? (
                                                    <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border text-[9px]">
                                                        <Check className="w-2.5 h-2.5 mr-0.5" /> Configured
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">
                                                        Not configured
                                                    </Badge>
                                                )}
                                            </div>
                                            <div className="flex gap-1">
                                                {item.configured && (
                                                    <>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => testConnection(item.id)} disabled={testing === item.id} data-testid={`test-${item.id}`}>
                                                            {testing === item.id ? <RefreshCw className="w-3 h-3 animate-spin text-white/40" /> : <CheckCircle className="w-3 h-3 text-emerald-400" />}
                                                        </Button>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => deleteIntegration(item)} data-testid={`delete-${item.id}`}>
                                                            <Trash2 className="w-3 h-3 text-red-400" />
                                                        </Button>
                                                    </>
                                                )}
                                                <Button size="sm" variant="ghost" className="text-xs text-white/50 h-7" onClick={() => openConfig(item)} data-testid={`config-${item.id}`}>
                                                    <Settings className="w-3 h-3 mr-1" /> {item.configured ? 'Edit' : 'Configure'}
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                );
            })}

            {/* Configure Dialog */}
            <Dialog open={!!configuring} onOpenChange={(open) => !open && setConfiguring(null)}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-lg" data-testid="config-dialog">
                    <DialogHeader>
                        <DialogTitle className="text-white flex items-center gap-2">
                            <Key className="w-5 h-5 text-amber-400" />
                            Configure {configuring?.name}
                        </DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        {configuring?.fields?.map(field => (
                            <div key={field.key} className="space-y-1.5">
                                <Label className="text-xs text-white/60">{field.label} {field.required && <span className="text-red-400">*</span>}</Label>
                                <div className="flex gap-2">
                                    <Input
                                        type={field.type === 'password' && !showPasswords[field.key] ? 'password' : 'text'}
                                        value={configValues[field.key] || ''}
                                        onChange={(e) => setConfigValues(v => ({ ...v, [field.key]: e.target.value }))}
                                        placeholder={field.default || `Enter ${field.label}`}
                                        className="bg-white/5 border-white/10 text-sm font-mono"
                                        data-testid={`field-${field.key}`}
                                    />
                                    {field.type === 'password' && (
                                        <Button
                                            size="icon"
                                            variant="ghost"
                                            onClick={() => setShowPasswords(s => ({ ...s, [field.key]: !s[field.key] }))}
                                            className="shrink-0"
                                        >
                                            {showPasswords[field.key] ? <EyeOff className="w-4 h-4 text-white/40" /> : <Eye className="w-4 h-4 text-white/40" />}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                        <div className="flex items-center justify-between pt-2">
                            <Label className="text-xs text-white/60">Enable Integration</Label>
                            <Switch checked={enabled} onCheckedChange={setEnabled} data-testid="config-enabled-toggle" />
                        </div>
                    </div>
                    <DialogFooter className="gap-2">
                        <Button variant="ghost" onClick={() => setConfiguring(null)} className="text-xs">Cancel</Button>
                        <Button onClick={saveConfig} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-xs" data-testid="config-save-btn">
                            {saving ? <RefreshCw className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1" />}
                            Save Configuration
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
