import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    Building, Palette, Upload, Save, RefreshCw, Image as ImageIcon,
    Sparkles, CheckCircle,
} from 'lucide-react';

export default function TenantBrandingPage() {
    const { api, user } = useAuth();
    const [tenants, setTenants] = useState([]);
    const [selectedId, setSelectedId] = useState('');
    const [branding, setBranding] = useState({
        primary_color: '#00E0FF',
        secondary_color: '#F5B841',
        footer_text: '',
        has_logo: false,
        company_name: '',
    });
    const [logoPreview, setLogoPreview] = useState(null);
    const [logoBase64, setLogoBase64] = useState('');
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(false);
    const fileRef = useRef(null);

    const fetchTenants = useCallback(async () => {
        try {
            const res = await api.get('/tenants');
            setTenants(res.data || []);
            if (res.data?.length && !selectedId) {
                setSelectedId(res.data[0].id);
            }
        } catch (e) {
            toast.error(`Failed to load tenants: ${e.response?.data?.detail || e.message}`);
        }
    }, [api, selectedId]);

    const fetchBranding = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        try {
            const res = await api.get(`/tenants/${id}/branding`);
            setBranding(res.data);
            setLogoPreview(null);
            setLogoBase64('');
        } catch (e) {
            toast.error(`Failed to load branding: ${e.message}`);
        }
        setLoading(false);
    }, [api]);

    useEffect(() => { fetchTenants(); }, [fetchTenants]);
    useEffect(() => { if (selectedId) fetchBranding(selectedId); }, [selectedId, fetchBranding]);

    const onLogoChange = (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        if (!f.type.startsWith('image/')) {
            toast.error('Please select an image file');
            return;
        }
        if (f.size > 2 * 1024 * 1024) {
            toast.error('Logo must be under 2MB');
            return;
        }
        const reader = new FileReader();
        reader.onload = (ev) => {
            setLogoPreview(ev.target.result);
            setLogoBase64(ev.target.result);
        };
        reader.readAsDataURL(f);
    };

    const saveBranding = async () => {
        if (!selectedId) return;
        setSaving(true);
        try {
            const payload = {
                primary_color: branding.primary_color,
                secondary_color: branding.secondary_color,
                footer_text: branding.footer_text,
            };
            if (logoBase64) payload.logo_base64 = logoBase64;
            await api.put(`/tenants/${selectedId}/branding`, payload);
            toast.success('Branding saved');
            await fetchBranding(selectedId);
        } catch (e) {
            toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
        }
        setSaving(false);
    };

    return (
        <div className="space-y-6" data-testid="tenant-branding-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Palette className="w-6 h-6 text-[#F5B841]" />
                        Tenant Branding
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        Customize enterprise PDF reports with your logo, colors, and footer. Applied to all generated reports for this tenant.
                    </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => fetchBranding(selectedId)} disabled={loading}>
                    <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Reload
                </Button>
            </div>

            {/* Tenant Selector */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardContent className="pt-6">
                    <Label className="text-xs text-white/60 mb-2 block">Select Tenant</Label>
                    <Select value={selectedId} onValueChange={setSelectedId}>
                        <SelectTrigger className="bg-[#161B22] border-white/10 max-w-md" data-testid="tenant-select">
                            <SelectValue placeholder="Choose a tenant..." />
                        </SelectTrigger>
                        <SelectContent className="bg-[#0D1117] border-white/10">
                            {tenants.map(t => (
                                <SelectItem key={t.id} value={t.id}>
                                    {t.name} · {t.plan}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </CardContent>
            </Card>

            {selectedId && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Branding Form */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Building className="w-4 h-4 text-[#00E0FF]" />
                                {branding.company_name || 'Branding'}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Logo Upload */}
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Company Logo</Label>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept="image/png,image/jpeg,image/svg+xml"
                                    onChange={onLogoChange}
                                    className="hidden"
                                    data-testid="logo-file-input"
                                />
                                <div className="flex items-center gap-3">
                                    <Button
                                        variant="outline"
                                        onClick={() => fileRef.current?.click()}
                                        className="border-white/10"
                                        data-testid="upload-logo-btn"
                                    >
                                        <Upload className="w-4 h-4 mr-2" /> Choose Logo
                                    </Button>
                                    {branding.has_logo && !logoPreview && (
                                        <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
                                            <CheckCircle className="w-3 h-3 mr-1" /> Logo uploaded
                                        </Badge>
                                    )}
                                    {logoPreview && (
                                        <Badge className="bg-[#00E0FF]/15 text-[#00E0FF] border-[#00E0FF]/30">
                                            <Sparkles className="w-3 h-3 mr-1" /> New logo staged
                                        </Badge>
                                    )}
                                </div>
                                <p className="text-[10px] text-white/30 mt-1">PNG/JPG/SVG · max 2MB · used at top-left of PDF</p>
                            </div>

                            {/* Primary Color */}
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Primary Color</Label>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="color"
                                        value={branding.primary_color || '#00E0FF'}
                                        onChange={(e) => setBranding({...branding, primary_color: e.target.value})}
                                        className="w-10 h-10 rounded border border-white/10 bg-transparent cursor-pointer"
                                        data-testid="primary-color-picker"
                                    />
                                    <Input
                                        value={branding.primary_color || ''}
                                        onChange={(e) => setBranding({...branding, primary_color: e.target.value})}
                                        className="bg-[#161B22] border-white/10 font-mono text-sm"
                                        placeholder="#00E0FF"
                                        data-testid="primary-color-input"
                                    />
                                </div>
                            </div>

                            {/* Secondary Color */}
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Secondary Color</Label>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="color"
                                        value={branding.secondary_color || '#F5B841'}
                                        onChange={(e) => setBranding({...branding, secondary_color: e.target.value})}
                                        className="w-10 h-10 rounded border border-white/10 bg-transparent cursor-pointer"
                                        data-testid="secondary-color-picker"
                                    />
                                    <Input
                                        value={branding.secondary_color || ''}
                                        onChange={(e) => setBranding({...branding, secondary_color: e.target.value})}
                                        className="bg-[#161B22] border-white/10 font-mono text-sm"
                                        placeholder="#F5B841"
                                        data-testid="secondary-color-input"
                                    />
                                </div>
                            </div>

                            {/* Footer Text */}
                            <div>
                                <Label className="text-xs text-white/60 mb-2 block">Footer Text</Label>
                                <Input
                                    value={branding.footer_text || ''}
                                    onChange={(e) => setBranding({...branding, footer_text: e.target.value})}
                                    placeholder="Confidential - ACME SOC Report"
                                    className="bg-[#161B22] border-white/10"
                                    data-testid="footer-text-input"
                                />
                            </div>

                            <Button
                                onClick={saveBranding}
                                disabled={saving}
                                className="w-full bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                                data-testid="save-branding-btn"
                            >
                                {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                                Save Branding
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Preview */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-[#F5B841]" />
                                PDF Preview
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Mock PDF preview card */}
                            <div className="bg-white rounded-lg p-6 text-black min-h-[400px] shadow-2xl" data-testid="pdf-preview">
                                {logoPreview ? (
                                    <img src={logoPreview} alt="logo" className="h-12 mb-3 object-contain" />
                                ) : branding.has_logo ? (
                                    <div className="h-12 mb-3 flex items-center text-gray-400 text-xs">
                                        <ImageIcon className="w-4 h-4 mr-1" /> Saved logo
                                    </div>
                                ) : (
                                    <div className="h-12 mb-3 flex items-center text-gray-300 text-xs border border-dashed border-gray-300 rounded px-2">
                                        No logo
                                    </div>
                                )}
                                <h2 className="text-xl font-bold" style={{ color: '#0B0E14' }}>
                                    {branding.company_name || 'ACME'} · Weekly SOC &amp; AIOps Report
                                </h2>
                                <p className="text-xs text-gray-500 mt-1 mb-4">
                                    Reporting Period: 13 Apr – 20 Apr 2026 · Generated: {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC
                                </p>

                                <div
                                    className="grid grid-cols-4 gap-2 text-center text-white rounded"
                                    style={{ backgroundColor: '#0B0E14' }}
                                >
                                    {['Risk', 'Uptime', 'MTTR', 'Threats'].map(h => (
                                        <div key={h} className="py-2 text-[10px] font-semibold">{h}</div>
                                    ))}
                                </div>
                                <div className="grid grid-cols-4 gap-2 text-center bg-gray-50 text-lg font-bold rounded-b">
                                    <div className="py-2 text-green-600">Low</div>
                                    <div className="py-2">99.98%</div>
                                    <div className="py-2">12 min</div>
                                    <div className="py-2">3</div>
                                </div>

                                <h3
                                    className="font-bold mt-4 mb-2"
                                    style={{ color: branding.primary_color }}
                                >
                                    Executive Summary
                                </h3>
                                <p className="text-xs text-gray-700 leading-relaxed">
                                    AI-generated CSO briefing appears here with business impact, key incidents, risk posture, SLA compliance, and leadership recommendations.
                                </p>

                                <h3
                                    className="font-bold mt-4 mb-2"
                                    style={{ color: branding.primary_color }}
                                >
                                    SLA &amp; Operations Metrics
                                </h3>
                                <div className="text-xs text-gray-600 border rounded">
                                    <div className="flex justify-between px-2 py-1 border-b" style={{ backgroundColor: branding.primary_color, color: 'white' }}>
                                        <span className="font-semibold">Metric</span><span className="font-semibold">Value</span>
                                    </div>
                                    <div className="flex justify-between px-2 py-1 border-b"><span>Uptime %</span><span className="font-mono">99.98%</span></div>
                                    <div className="flex justify-between px-2 py-1 border-b bg-gray-50"><span>MTTR</span><span className="font-mono">12 min</span></div>
                                    <div className="flex justify-between px-2 py-1"><span>Incidents</span><span className="font-mono">5</span></div>
                                </div>

                                <p className="text-center text-[9px] text-gray-400 mt-6 border-t pt-2">
                                    {branding.footer_text || 'Confidential – SOC Report'}
                                </p>
                            </div>
                            <p className="text-[10px] text-white/30 mt-3 text-center">
                                Live preview · Actual PDF includes charts, severity-coded tables, and page numbers
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
