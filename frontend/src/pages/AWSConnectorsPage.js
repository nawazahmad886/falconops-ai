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
    CloudCog, RefreshCw, Shield, Activity, Globe,
    Server, AlertTriangle, Network, Eye, Clock, Database,
    CheckCircle, XCircle, Settings,
} from 'lucide-react';

const SEVERITY_STYLES = {
    critical: 'bg-red-500/15 text-red-400 border-red-500/30',
    high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
};

export default function AWSConnectorsPage() {
    const { api } = useAuth();
    const [connectors, setConnectors] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('overview');
    const [ctEvents, setCtEvents] = useState([]);
    const [vpcEvents, setVpcEvents] = useState([]);
    const [fetchingEvents, setFetchingEvents] = useState(false);
    const [configForm, setConfigForm] = useState({
        connector_type: 'cloudtrail',
        aws_region: 'us-east-1',
        aws_access_key: '',
        aws_secret_key: '',
        log_group: 'vpc-flow-logs',
        enabled: true,
    });
    const [configuring, setConfiguring] = useState(false);

    const fetchConnectors = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/aws/connectors');
            setConnectors(res.data?.connectors || []);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const fetchEvents = useCallback(async () => {
        setFetchingEvents(true);
        try {
            const [ctRes, vpcRes] = await Promise.all([
                api.get('/aws/events/cloudtrail?limit=20'),
                api.get('/aws/events/vpc?limit=20'),
            ]);
            setCtEvents(ctRes.data || []);
            setVpcEvents(vpcRes.data || []);
        } catch (e) { console.error(e); }
        setFetchingEvents(false);
    }, [api]);

    const saveConfig = useCallback(async () => {
        setConfiguring(true);
        try {
            await api.post('/aws/connectors', configForm);
            await fetchConnectors();
        } catch (e) { console.error(e); }
        setConfiguring(false);
    }, [api, configForm, fetchConnectors]);

    const pollAWS = useCallback(async () => {
        setFetchingEvents(true);
        try {
            await api.post('/aws/fetch');
            await fetchEvents();
        } catch (e) { console.error(e); }
        setFetchingEvents(false);
    }, [api, fetchEvents]);

    useEffect(() => { fetchConnectors(); fetchEvents(); }, [fetchConnectors, fetchEvents]);

    const tabs = [
        { id: 'overview', label: 'Overview', icon: Eye },
        { id: 'cloudtrail', label: 'CloudTrail', icon: Shield },
        { id: 'vpc', label: 'VPC Flow Logs', icon: Network },
        { id: 'config', label: 'Configuration', icon: Settings },
    ];

    return (
        <div className="space-y-6" data-testid="aws-connectors-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-orange-500/15">
                            <CloudCog className="w-6 h-6 text-orange-400" />
                        </div>
                        AWS Connectors
                    </h1>
                    <p className="text-sm text-white/50 mt-1">CloudTrail & VPC Flow Logs ingestion</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={pollAWS} disabled={fetchingEvents} className="border-white/10 text-xs" data-testid="poll-aws-btn">
                        <RefreshCw className={`w-3 h-3 mr-1 ${fetchingEvents ? 'animate-spin' : ''}`} /> Poll AWS
                    </Button>
                </div>
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

            {/* Overview */}
            {tab === 'overview' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {connectors.map(c => (
                        <Card key={c.id} className="bg-[#0D1117] border-white/5" data-testid={`connector-${c.id}`}>
                            <CardContent className="p-5">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${c.type === 'cloudtrail' ? 'bg-orange-500/15' : 'bg-cyan-500/15'}`}>
                                            {c.type === 'cloudtrail'
                                                ? <Shield className="w-5 h-5 text-orange-400" />
                                                : <Network className="w-5 h-5 text-cyan-400" />
                                            }
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-semibold text-white">{c.name}</h3>
                                            <p className="text-xs text-white/40">Region: {c.region}</p>
                                        </div>
                                    </div>
                                    <Badge className={c.enabled ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-white/40 border-white/10'}>
                                        {c.enabled ? <CheckCircle className="w-3 h-3 mr-1" /> : <XCircle className="w-3 h-3 mr-1" />}
                                        {c.enabled ? 'Enabled' : 'Disabled'}
                                    </Badge>
                                </div>
                                <Badge variant="outline" className="text-[10px] text-white/40 border-white/10">{c.status}</Badge>
                            </CardContent>
                        </Card>
                    ))}
                    {connectors.length === 0 && !loading && (
                        <div className="col-span-2 text-center p-8 text-white/40">
                            <CloudCog className="w-8 h-8 mx-auto mb-3 opacity-40" />
                            <p>No AWS connectors configured yet.</p>
                        </div>
                    )}
                </div>
            )}

            {/* CloudTrail Events */}
            {tab === 'cloudtrail' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Shield className="w-4 h-4 text-orange-400" />
                            CloudTrail Events
                            <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{ctEvents.length} events</Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[500px] overflow-y-auto divide-y divide-white/5" data-testid="cloudtrail-events">
                            {ctEvents.length === 0 ? (
                                <div className="p-8 text-center text-white/40">
                                    <Shield className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                    <p>No CloudTrail events. Click "Poll AWS" to fetch simulated data.</p>
                                </div>
                            ) : ctEvents.map((ev, i) => {
                                const sevStyle = SEVERITY_STYLES[ev.severity] || SEVERITY_STYLES.info;
                                return (
                                    <div key={i} className="flex items-start gap-3 p-3 hover:bg-white/[0.02]" data-testid={`ct-event-${i}`}>
                                        <div className={`p-1.5 rounded ${sevStyle.split(' ')[0]}`}>
                                            <Shield className={`w-3.5 h-3.5 ${sevStyle.split(' ')[1]}`} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-white/80 truncate">{ev.message}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <Badge variant="outline" className={`text-[9px] ${sevStyle}`}>{ev.severity}</Badge>
                                                <span className="text-[10px] text-white/30">{ev.category}</span>
                                                <span className="text-[10px] text-white/30 font-mono">{ev.source_ip}</span>
                                                <span className="text-[10px] text-white/30">{ev.user}</span>
                                            </div>
                                        </div>
                                        <span className="text-[10px] text-white/25 whitespace-nowrap">{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ''}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* VPC Flow Logs */}
            {tab === 'vpc' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Network className="w-4 h-4 text-cyan-400" />
                            VPC Flow Logs
                            <Badge variant="outline" className="text-[10px] ml-2 text-white/40 border-white/10">{vpcEvents.length} events</Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="max-h-[500px] overflow-y-auto divide-y divide-white/5" data-testid="vpc-events">
                            {vpcEvents.length === 0 ? (
                                <div className="p-8 text-center text-white/40">
                                    <Network className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                    <p>No VPC Flow Log events. Click "Poll AWS" to fetch simulated data.</p>
                                </div>
                            ) : vpcEvents.map((ev, i) => {
                                const sevStyle = SEVERITY_STYLES[ev.severity] || SEVERITY_STYLES.info;
                                return (
                                    <div key={i} className="flex items-start gap-3 p-3 hover:bg-white/[0.02]" data-testid={`vpc-event-${i}`}>
                                        <div className={`p-1.5 rounded ${sevStyle.split(' ')[0]}`}>
                                            <Network className={`w-3.5 h-3.5 ${sevStyle.split(' ')[1]}`} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-white/80 truncate">{ev.message}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <Badge variant="outline" className={`text-[9px] ${sevStyle}`}>{ev.severity}</Badge>
                                                <span className="text-[10px] text-white/30 font-mono">{ev.source_ip}</span>
                                                <span className="text-[10px] text-white/30">{ev.target}</span>
                                                <Badge variant="outline" className={`text-[9px] ${ev.status === 'accept' ? 'text-emerald-400 border-emerald-500/30' : 'text-red-400 border-red-500/30'}`}>
                                                    {ev.status}
                                                </Badge>
                                            </div>
                                        </div>
                                        <span className="text-[10px] text-white/25 whitespace-nowrap">{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ''}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Configuration */}
            {tab === 'config' && (
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Settings className="w-4 h-4 text-white/60" />
                            Configure AWS Connector
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-5 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <Label className="text-xs text-white/60">Connector Type</Label>
                                <Select value={configForm.connector_type} onValueChange={v => setConfigForm(p => ({ ...p, connector_type: v }))}>
                                    <SelectTrigger className="bg-[#161B22] border-white/10 mt-1" data-testid="connector-type-select">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent className="bg-[#0D1117] border-white/10">
                                        <SelectItem value="cloudtrail">CloudTrail</SelectItem>
                                        <SelectItem value="vpc_flowlogs">VPC Flow Logs</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label className="text-xs text-white/60">AWS Region</Label>
                                <Input className="bg-[#161B22] border-white/10 mt-1" value={configForm.aws_region}
                                    onChange={e => setConfigForm(p => ({ ...p, aws_region: e.target.value }))} placeholder="us-east-1" data-testid="aws-region-input" />
                            </div>
                            <div>
                                <Label className="text-xs text-white/60">Access Key (optional for sim)</Label>
                                <Input className="bg-[#161B22] border-white/10 mt-1" type="password" value={configForm.aws_access_key}
                                    onChange={e => setConfigForm(p => ({ ...p, aws_access_key: e.target.value }))} placeholder="AKIA..." data-testid="aws-access-key-input" />
                            </div>
                            <div>
                                <Label className="text-xs text-white/60">Secret Key (optional for sim)</Label>
                                <Input className="bg-[#161B22] border-white/10 mt-1" type="password" value={configForm.aws_secret_key}
                                    onChange={e => setConfigForm(p => ({ ...p, aws_secret_key: e.target.value }))} placeholder="Secret..." data-testid="aws-secret-key-input" />
                            </div>
                        </div>
                        {configForm.connector_type === 'vpc_flowlogs' && (
                            <div>
                                <Label className="text-xs text-white/60">Log Group</Label>
                                <Input className="bg-[#161B22] border-white/10 mt-1" value={configForm.log_group}
                                    onChange={e => setConfigForm(p => ({ ...p, log_group: e.target.value }))} data-testid="log-group-input" />
                            </div>
                        )}
                        <Button onClick={saveConfig} disabled={configuring} className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="save-config-btn">
                            {configuring ? <RefreshCw className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle className="w-3 h-3 mr-1" />}
                            Save Configuration
                        </Button>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
