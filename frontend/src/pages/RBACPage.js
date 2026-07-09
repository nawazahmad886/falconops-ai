import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
    Lock, Users, Shield, History, RefreshCw, CheckCircle,
    XCircle, Plus, Trash2, Eye, Settings, Key, ChevronRight,
} from 'lucide-react';

const PERMISSION_CATEGORIES = {
    dashboard: { label: 'Dashboard', color: 'text-amber-400' },
    monitors: { label: 'Monitoring', color: 'text-emerald-400' },
    alerts: { label: 'Alerts', color: 'text-red-400' },
    health_rules: { label: 'Health Rules', color: 'text-blue-400' },
    security: { label: 'Security', color: 'text-red-400' },
    remediation: { label: 'Remediation', color: 'text-orange-400' },
    ueba: { label: 'UEBA', color: 'text-purple-400' },
    impact: { label: 'Impact', color: 'text-cyan-400' },
    integrations: { label: 'Integrations', color: 'text-emerald-400' },
    reports: { label: 'Reports', color: 'text-blue-400' },
    users: { label: 'Users', color: 'text-amber-400' },
    rbac: { label: 'RBAC', color: 'text-red-400' },
    audit: { label: 'Audit', color: 'text-white/60' },
    topology: { label: 'Topology', color: 'text-cyan-400' },
    copilot: { label: 'AI Copilot', color: 'text-purple-400' },
    settings: { label: 'Settings', color: 'text-white/60' },
};

export default function RBACPage() {
    const { api } = useAuth();
    const [tab, setTab] = useState('roles');
    const [roles, setRoles] = useState([]);
    const [permissions, setPermissions] = useState([]);
    const [auditLogs, setAuditLogs] = useState({ logs: [], total: 0 });
    const [auditStats, setAuditStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedRole, setSelectedRole] = useState(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [rRes, pRes] = await Promise.all([
                api.get('/rbac/roles'),
                api.get('/rbac/permissions'),
            ]);
            setRoles(rRes.data || []);
            setPermissions(pRes.data || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchAudit = useCallback(async () => {
        try {
            const [lRes, sRes] = await Promise.all([
                api.get('/rbac/audit?limit=50'),
                api.get('/rbac/audit/stats'),
            ]);
            setAuditLogs(lRes.data || { logs: [], total: 0 });
            setAuditStats(sRes.data);
        } catch (e) { console.error(e); }
    }, [api]);

    useEffect(() => { fetchData(); fetchAudit(); }, [fetchData, fetchAudit]);

    const tabs = [
        { id: 'roles', label: 'Roles', icon: Shield },
        { id: 'permissions', label: 'Permissions', icon: Key },
        { id: 'audit', label: 'Audit Logs', icon: History },
    ];

    const groupedPerms = permissions.reduce((acc, p) => {
        const cat = p.key.split('.')[0];
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(p);
        return acc;
    }, {});

    return (
        <div className="space-y-6" data-testid="rbac-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-red-500/15">
                            <Lock className="w-6 h-6 text-red-400" />
                        </div>
                        Access Control
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Role-based access control & audit logs</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => { fetchData(); fetchAudit(); }} disabled={loading} className="border-white/10 text-xs" data-testid="refresh-rbac-btn">
                    <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-white/5 pb-1">
                {tabs.map(t => {
                    const Icon = t.icon;
                    return (
                        <Button key={t.id} variant="ghost" size="sm"
                            onClick={() => setTab(t.id)}
                            className={`text-xs ${tab === t.id ? 'bg-white/10 text-white' : 'text-white/50'}`}
                            data-testid={`tab-${t.id}`}>
                            <Icon className="w-3 h-3 mr-1" /> {t.label}
                        </Button>
                    );
                })}
            </div>

            {/* Roles Tab */}
            {tab === 'roles' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {roles.map(role => (
                        <Card key={role.role_id} className={`bg-[#0D1117] border-white/5 cursor-pointer transition-all hover:border-white/15 ${selectedRole === role.role_id ? 'ring-1 ring-red-500/30' : ''}`}
                            onClick={() => setSelectedRole(selectedRole === role.role_id ? null : role.role_id)}
                            data-testid={`role-card-${role.role_id}`}>
                            <CardContent className="p-5">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-red-500/10">
                                            <Shield className="w-5 h-5 text-red-400" />
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-semibold text-white">{role.name}</h3>
                                            <p className="text-[10px] text-white/40">{role.description}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {role.is_system && <Badge variant="outline" className="text-[9px] text-white/30 border-white/10">System</Badge>}
                                        <Badge className="bg-blue-500/15 text-blue-400 border-blue-500/30 text-[10px]">
                                            {role.permissions?.length || 0} perms
                                        </Badge>
                                    </div>
                                </div>
                                {selectedRole === role.role_id && (
                                    <div className="mt-3 pt-3 border-t border-white/5">
                                        <p className="text-xs text-white/50 mb-2">Permissions:</p>
                                        <div className="flex flex-wrap gap-1">
                                            {role.permissions?.map(p => (
                                                <Badge key={p} variant="outline" className="text-[9px] text-white/40 border-white/10">{p}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Permissions Tab */}
            {tab === 'permissions' && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(groupedPerms).map(([cat, perms]) => {
                        const catInfo = PERMISSION_CATEGORIES[cat] || { label: cat, color: 'text-white/60' };
                        return (
                            <Card key={cat} className="bg-[#0D1117] border-white/5" data-testid={`perm-group-${cat}`}>
                                <CardHeader className="pb-2">
                                    <CardTitle className={`text-sm ${catInfo.color}`}>{catInfo.label}</CardTitle>
                                </CardHeader>
                                <CardContent className="p-3 pt-0 space-y-1">
                                    {perms.map(p => (
                                        <div key={p.key} className="flex items-center gap-2 p-1.5 rounded hover:bg-white/[0.02]">
                                            <Key className="w-3 h-3 text-white/20" />
                                            <div>
                                                <p className="text-xs text-white/70 font-mono">{p.key}</p>
                                                <p className="text-[10px] text-white/30">{p.description}</p>
                                            </div>
                                        </div>
                                    ))}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Audit Tab */}
            {tab === 'audit' && (
                <div className="space-y-4">
                    {/* Audit Stats */}
                    {auditStats && (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardContent className="p-4">
                                    <p className="text-xs text-white/50">Total Events (24h)</p>
                                    <p className="text-xl font-bold text-white" data-testid="audit-total">{auditStats.total_events}</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardContent className="p-4">
                                    <p className="text-xs text-white/50">Top User</p>
                                    <p className="text-sm font-bold text-white">{auditStats.top_users?.[0]?.user || 'N/A'}</p>
                                </CardContent>
                            </Card>
                            <Card className="bg-[#0D1117] border-white/5">
                                <CardContent className="p-4">
                                    <p className="text-xs text-white/50">Top Action</p>
                                    <p className="text-sm font-bold text-white">{auditStats.top_actions?.[0]?.action || 'N/A'}</p>
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {/* Audit Logs Table */}
                    <Card className="bg-[#0D1117] border-white/5">
                        <CardHeader className="pb-3 border-b border-white/5">
                            <CardTitle className="text-base flex items-center gap-2">
                                <History className="w-4 h-4 text-white/60" />
                                Audit Trail
                                <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{auditLogs.total} records</Badge>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="max-h-[500px] overflow-y-auto divide-y divide-white/5" data-testid="audit-log-list">
                                {auditLogs.logs?.length === 0 ? (
                                    <div className="p-8 text-center text-white/40">
                                        <History className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                        <p>No audit logs yet. Actions will be recorded here.</p>
                                    </div>
                                ) : auditLogs.logs?.map((log, i) => (
                                    <div key={log.id || i} className="flex items-start gap-3 p-3 hover:bg-white/[0.02]" data-testid={`audit-log-${i}`}>
                                        <div className={`p-1.5 rounded ${log.status === 'success' ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                                            {log.status === 'success'
                                                ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                                                : <XCircle className="w-3.5 h-3.5 text-red-400" />
                                            }
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-white/80">{log.action}</span>
                                                <Badge variant="outline" className="text-[9px] text-white/40 border-white/10">{log.resource}</Badge>
                                            </div>
                                            <p className="text-xs text-white/40 mt-0.5">{log.user_email} ({log.user_role})</p>
                                            {log.detail && <p className="text-[10px] text-white/30 mt-0.5 truncate">{log.detail}</p>}
                                        </div>
                                        <span className="text-[10px] text-white/25 whitespace-nowrap">
                                            {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
