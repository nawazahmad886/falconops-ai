import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { FalconLogo } from '../components/FalconLogo';
import {
    Lock, Shield, FileText, FileSpreadsheet, FileDown, Bot, Gauge, Clock,
    Activity, AlertTriangle, CheckCircle, RefreshCw, Calendar, XCircle,
    Mail, KeyRound,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const SEV = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};

export default function PublicPortalPage() {
    const { token } = useParams();
    const [meta, setMeta] = useState(null);
    const [report, setReport] = useState(null);
    const [password, setPassword] = useState('');
    const [email, setEmail] = useState('');
    const [otpCode, setOtpCode] = useState('');
    const [otpRequested, setOtpRequested] = useState(false);
    const [otpCooldown, setOtpCooldown] = useState(0);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const fetchMeta = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${BACKEND_URL}/api/portal/${token}/meta`);
            const data = await res.json();
            setMeta(data);
            if (!data.valid) setError(data.reason || 'Invalid link');
            // Auto-fetch only when no gates at all
            if (data.valid && !data.password_protected && !data.require_otp) {
                await unlockReport('', '', '');
            }
        } catch (e) {
            setError('Failed to load link');
        }
        setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    const unlockReport = async (pw, em, code) => {
        setSubmitting(true);
        setError(null);
        try {
            const res = await fetch(`${BACKEND_URL}/api/portal/${token}/view`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: pw, email: em || null, otp: code || null }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || 'Access denied');
                setReport(null);
            } else {
                setReport(data.report);
                toast.success('Report unlocked');
            }
        } catch (e) {
            setError(`Error: ${e.message}`);
        }
        setSubmitting(false);
    };

    const requestOtp = async () => {
        if (!email || !email.includes('@')) {
            setError('Please enter a valid email');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const res = await fetch(`${BACKEND_URL}/api/portal/${token}/request-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || 'OTP request failed');
            } else {
                setOtpRequested(true);
                setOtpCooldown(60);
                toast.success(`Code sent to ${email}`);
            }
        } catch (e) {
            setError(`Error: ${e.message}`);
        }
        setSubmitting(false);
    };

    useEffect(() => { fetchMeta(); }, [fetchMeta]);

    // OTP cooldown timer (re-send gated)
    useEffect(() => {
        if (otpCooldown <= 0) return;
        const t = setTimeout(() => setOtpCooldown(otpCooldown - 1), 1000);
        return () => clearTimeout(t);
    }, [otpCooldown]);

    const downloadFile = async (fmt) => {
        try {
            const res = await fetch(`${BACKEND_URL}/api/portal/${token}/download/${fmt}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password, email: email || null, otp: otpCode || null }),
            });
            if (!res.ok) {
                const d = await res.json();
                toast.error(d.detail || `Download failed`);
                return;
            }
            const blob = await res.blob();
            const ext = fmt === 'excel' ? 'xlsx' : fmt;
            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(blob);
            link.download = `FalconOps_Report_${report.report_id}.${ext}`;
            link.click();
            window.URL.revokeObjectURL(link.href);
            toast.success(`${fmt.toUpperCase()} downloaded`);
        } catch (e) {
            toast.error(`Download failed: ${e.message}`);
        }
    };

    // Loading state
    if (loading) {
        return (
            <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center">
                <RefreshCw className="w-8 h-8 animate-spin text-[#00E0FF]" />
            </div>
        );
    }

    // Invalid / expired / revoked
    if (!meta?.valid) {
        const icon = meta?.reason === 'expired' ? Clock : meta?.reason === 'revoked' ? XCircle : AlertTriangle;
        const Icon = icon;
        const title = meta?.reason === 'expired' ? 'Link Expired' : meta?.reason === 'revoked' ? 'Link Revoked' : 'Invalid Link';
        const desc = meta?.reason === 'expired' ? 'This shared report link has passed its expiration date.'
            : meta?.reason === 'revoked' ? 'This link has been revoked by its creator.'
            : 'The link you are trying to access is invalid.';
        return (
            <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center p-4" data-testid="portal-invalid">
                <Card className="bg-[#0D1117] border-white/10 max-w-md w-full">
                    <CardContent className="pt-8 pb-8 text-center">
                        <div className="w-14 h-14 rounded-full bg-red-500/15 border border-red-500/30 mx-auto flex items-center justify-center mb-4">
                            <Icon className="w-7 h-7 text-red-400" />
                        </div>
                        <h2 className="text-xl font-semibold text-white mb-2">{title}</h2>
                        <p className="text-sm text-white/50">{desc}</p>
                        <p className="text-xs text-white/30 mt-4">Contact the sender for a new link.</p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // Gate screens (password and/or OTP)
    if ((meta.password_protected || meta.require_otp) && !report) {
        const needPassword = meta.password_protected;
        const needOtp = meta.require_otp;

        const submitAll = () => {
            if (needOtp && !otpRequested) {
                requestOtp();
                return;
            }
            unlockReport(password, email, otpCode);
        };

        return (
            <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center p-4" data-testid="portal-password-gate">
                <Card className="bg-[#0D1117] border-white/10 max-w-md w-full">
                    <CardHeader className="text-center pb-3">
                        <FalconLogo size={40} className="mx-auto mb-2" />
                        <CardTitle className="text-lg">Protected Report</CardTitle>
                        <p className="text-xs text-white/50 mt-1">
                            {needPassword && needOtp ? 'Enter password and verify your email to continue'
                                : needPassword ? 'Enter the access password to continue'
                                : 'Verify your email to continue'}
                        </p>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {needPassword && (
                            <div>
                                <Label className="text-xs text-white/60 mb-2 flex items-center gap-1">
                                    <Lock className="w-3 h-3" /> Password
                                </Label>
                                <Input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="Enter password"
                                    className="bg-[#161B22] border-white/10"
                                    autoFocus
                                    data-testid="portal-password-input"
                                />
                            </div>
                        )}

                        {needOtp && (
                            <>
                                <div>
                                    <Label className="text-xs text-white/60 mb-2 flex items-center gap-1">
                                        <Mail className="w-3 h-3" /> Email
                                    </Label>
                                    <Input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="you@company.com"
                                        className="bg-[#161B22] border-white/10"
                                        disabled={otpRequested}
                                        data-testid="portal-email-input"
                                    />
                                </div>

                                {otpRequested && (
                                    <div>
                                        <Label className="text-xs text-white/60 mb-2 flex items-center justify-between">
                                            <span className="flex items-center gap-1"><KeyRound className="w-3 h-3" /> 6-digit code</span>
                                            <span className="text-[10px] text-white/30">Sent to {email}</span>
                                        </Label>
                                        <Input
                                            type="text"
                                            inputMode="numeric"
                                            maxLength={6}
                                            value={otpCode}
                                            onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                            placeholder="000000"
                                            className="bg-[#161B22] border-white/10 font-mono text-center text-xl tracking-[0.5em]"
                                            autoFocus
                                            data-testid="portal-otp-input"
                                        />
                                        <div className="flex items-center justify-between mt-2">
                                            <p className="text-[10px] text-white/30">Code expires in 10 min</p>
                                            <button
                                                onClick={requestOtp}
                                                disabled={otpCooldown > 0 || submitting}
                                                className="text-[11px] text-[#00E0FF] hover:underline disabled:text-white/30 disabled:no-underline"
                                                data-testid="portal-resend-otp"
                                            >
                                                {otpCooldown > 0 ? `Resend in ${otpCooldown}s` : 'Resend code'}
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </>
                        )}

                        {error && (
                            <div className="text-xs text-red-400 flex items-center gap-1 p-2 rounded bg-red-500/10 border border-red-500/20" data-testid="portal-error">
                                <AlertTriangle className="w-3 h-3" /> {error}
                            </div>
                        )}

                        <Button
                            onClick={submitAll}
                            disabled={submitting || (needPassword && !password) || (needOtp && otpRequested && otpCode.length < 6)}
                            className="w-full bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                            data-testid="portal-unlock-btn"
                        >
                            {submitting ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Shield className="w-4 h-4 mr-2" />}
                            {needOtp && !otpRequested ? 'Send OTP' : 'Unlock Report'}
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // Report view
    if (!report) return null;

    return (
        <div className="min-h-screen bg-[#0B0E14]" data-testid="portal-report-view">
            {/* Header */}
            <header className="sticky top-0 z-10 bg-[#0B0E14]/95 backdrop-blur-xl border-b border-white/5">
                <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <FalconLogo size={28} />
                        <div>
                            <div className="font-heading font-bold text-sm tracking-wide">
                                <span className="text-[#F5B841]">FALCON</span>
                                <span className="text-white">OPS</span>
                                <span className="text-[#00E0FF] text-[10px] ml-1">AI</span>
                            </div>
                            <div className="text-[10px] text-white/30">Shared Report Portal</div>
                        </div>
                    </div>
                    <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-[10px]">
                        <CheckCircle className="w-3 h-3 mr-1" /> Verified
                    </Badge>
                </div>
            </header>

            {/* Report body */}
            <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
                {/* Title */}
                <div>
                    <h1 className="text-2xl font-bold text-white">Weekly SOC &amp; AIOps Report</h1>
                    <p className="text-sm text-white/50 mt-1">
                        Period: <b>{report.period || 'N/A'}</b> · Report ID: <span className="font-mono">{report.report_id}</span>
                    </p>
                </div>

                {/* KPI banner */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <KPI label="Total Alerts" value={report.total_alerts} icon={Activity} color="text-white" />
                    <KPI label="Critical" value={report.critical_count} icon={AlertTriangle} color="text-red-400" bg="bg-red-500/10 border-red-500/20" />
                    <KPI label="Warning" value={report.warning_count} icon={AlertTriangle} color="text-amber-400" bg="bg-amber-500/10 border-amber-500/20" />
                    <KPI label="Occurrences" value={report.total_occurrences || 0} icon={Activity} color="text-blue-400" bg="bg-blue-500/10 border-blue-500/20" />
                </div>

                {/* SLA banner */}
                {report.sla_metrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="portal-sla">
                        <KPI label="Risk Posture" value={report.sla_metrics.risk_posture} icon={Shield}
                             color={report.sla_metrics.risk_posture === 'High' ? 'text-red-400' : report.sla_metrics.risk_posture === 'Medium' ? 'text-amber-400' : 'text-emerald-400'} />
                        <KPI label="SLA Uptime" value={`${report.sla_metrics.uptime_pct?.toFixed(2)}%`} icon={Gauge} color="text-[#00E0FF]" />
                        <KPI label="MTTR" value={`${report.sla_metrics.mttr_minutes} min`} icon={Clock} color="text-purple-400" />
                        <KPI label="Compliance" value={report.sla_metrics.sla_compliance} icon={CheckCircle} color="text-white" />
                    </div>
                )}

                {/* Downloads */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="pt-6">
                        <div className="flex items-center gap-3 flex-wrap">
                            {report.has_pdf && (
                                <Button
                                    onClick={() => downloadFile('pdf')}
                                    className="bg-gradient-to-r from-[#00E0FF] to-[#F5B841] text-black hover:opacity-90 font-semibold"
                                    data-testid="portal-download-pdf"
                                >
                                    <FileDown className="w-4 h-4 mr-2" /> Download Enterprise PDF
                                </Button>
                            )}
                            <Button
                                onClick={() => downloadFile('docx')}
                                variant="outline"
                                className="border-[#00E0FF]/30 text-[#00E0FF] hover:bg-[#00E0FF]/10"
                                data-testid="portal-download-docx"
                            >
                                <FileText className="w-4 h-4 mr-2" /> DOCX
                            </Button>
                            <Button
                                onClick={() => downloadFile('excel')}
                                variant="outline"
                                className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                                data-testid="portal-download-excel"
                            >
                                <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* AI Summary */}
                {report.ai_summary && (
                    <Card className="bg-gradient-to-br from-[#00E0FF]/5 to-purple-500/5 border-[#00E0FF]/20">
                        <CardHeader>
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Bot className="w-4 h-4 text-[#00E0FF]" />
                                AI Executive Summary
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-white/80 whitespace-pre-wrap leading-relaxed" data-testid="portal-ai-summary">
                                {report.ai_summary}
                            </p>
                        </CardContent>
                    </Card>
                )}

                {/* Alerts */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-[#F5B841]" />
                            Alert Details (Top 20)
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead className="bg-white/5 text-white/50">
                                    <tr>
                                        <th className="text-left p-2">Rule</th>
                                        <th className="text-left p-2">Severity</th>
                                        <th className="text-left p-2">Count</th>
                                        <th className="text-left p-2">Summary</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(report.alerts || []).map((a, i) => (
                                        <tr key={i} className="border-t border-white/5">
                                            <td className="p-2 text-white/80">{a.rule_name}</td>
                                            <td className="p-2"><Badge className={SEV[a.severity] || SEV.info}>{a.severity}</Badge></td>
                                            <td className="p-2 text-white/60">{a.count}</td>
                                            <td className="p-2 text-white/50 truncate max-w-md">{a.summary}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>

                {/* Footer */}
                <div className="text-center py-6 text-[11px] text-white/30 border-t border-white/5">
                    <p>{report.branding?.footer_text || 'Confidential — FalconOps AI Report'}</p>
                    <p className="mt-1">Generated {new Date(report.created_at).toLocaleString()} · Powered by FalconOps AI</p>
                </div>
            </div>
        </div>
    );
}

const KPI = ({ label, value, icon: Icon, color = 'text-white', bg = 'bg-white/[0.03] border-white/5' }) => (
    <div className={`p-3 rounded-lg border ${bg}`}>
        <div className="flex items-center gap-1.5">
            <Icon className={`w-3 h-3 ${color} opacity-70`} />
            <p className={`text-[10px] uppercase ${color} opacity-60`}>{label}</p>
        </div>
        <p className={`text-xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
);
