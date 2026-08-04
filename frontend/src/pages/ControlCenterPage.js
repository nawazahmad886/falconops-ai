import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
    Cpu, RefreshCw, Play, Pause, ExternalLink, Activity, Database,
    Server, ScrollText, Network, Settings, ShieldCheck, AlertTriangle, WifiOff, Boxes,
    HardDriveDownload,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const JOB_KIND_LABEL = {
    asyncio_task: 'Background loop',
    start_stop_fn: 'Scheduler',
    apscheduler: 'APScheduler job',
};

function StatCard({ icon: Icon, label, value, tone }) {
    const toneCls = {
        good: 'text-emerald-300', warn: 'text-amber-300', bad: 'text-red-300', neutral: 'text-white/80',
    }[tone || 'neutral'];
    return (
        <Card className="bg-black/40 border-white/10">
            <CardContent className="p-4">
                <div className="flex items-center gap-2 text-white/40 text-xs mb-1">
                    <Icon className="w-3.5 h-3.5" /> {label}
                </div>
                <p className={`text-xl font-semibold ${toneCls}`}>{value}</p>
            </CardContent>
        </Card>
    );
}

function JobRow({ job, isAdmin, onPause, onResume, busy }) {
    const running = job.status === 'running';
    const crashed = job.status === 'crashed';
    const statusCls = crashed
        ? 'bg-red-500/15 text-red-300 border-red-500/30'
        : running
            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
            : 'bg-white/10 text-white/50 border-white/20';

    return (
        <div className="flex items-center gap-3 p-3 border-b border-white/5 last:border-0" data-testid={`job-row-${job.id}`}>
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="text-sm text-white/90">{job.label}</span>
                    <Badge className={`text-[9px] border ${statusCls}`}>{job.status}</Badge>
                </div>
                <p className="text-[11px] text-white/35">{JOB_KIND_LABEL[job.kind] || job.kind}</p>
                {job.error && <p className="text-[11px] text-red-400/80 mt-0.5">{job.error}</p>}
            </div>
            {isAdmin && (
                running ? (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onPause(job.id)} data-testid={`pause-${job.id}`}>
                        <Pause className="w-3.5 h-3.5 mr-1" /> Pause
                    </Button>
                ) : (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onResume(job.id)} data-testid={`resume-${job.id}`}>
                        <Play className="w-3.5 h-3.5 mr-1" /> Resume
                    </Button>
                )
            )}
        </div>
    );
}

const COMPONENT_STATUS_STYLE = {
    healthy: { dot: 'bg-emerald-400', text: 'text-emerald-300', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10' },
    warning: { dot: 'bg-amber-400', text: 'text-amber-300', border: 'border-amber-500/30', bg: 'bg-amber-500/10' },
    critical: { dot: 'bg-red-400', text: 'text-red-300', border: 'border-red-500/30', bg: 'bg-red-500/10' },
};

function ComponentCard({ component }) {
    const style = COMPONENT_STATUS_STYLE[component.status] || COMPONENT_STATUS_STYLE.warning;
    return (
        <div
            className={`rounded-lg border p-3 ${style.border} ${style.bg}`}
            data-testid={`component-card-${component.collection}`}
            title={component.error || undefined}
        >
            <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-white/90 truncate">{component.name}</span>
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${style.dot}`} />
            </div>
            <p className="text-[11px] text-white/40 mt-0.5 truncate">{component.description}</p>
            <div className="flex items-center justify-between mt-2 text-[10px]">
                <span className={`${style.text} uppercase tracking-wide`}>{component.status}</span>
                <span className="text-white/30">{component.latency_ms != null ? `${component.latency_ms}ms` : '—'}</span>
            </div>
            {component.error && (
                <p className="text-[10px] text-red-400/80 mt-1 truncate">{component.error}</p>
            )}
        </div>
    );
}

const SEVERITY_DOT = {
    critical: 'bg-red-400', warning: 'bg-amber-400', info: 'bg-cyan-400/60',
};

function ActivityRow({ event }) {
    return (
        <div className="flex items-start gap-2 p-2 text-[12px] border-b border-white/5 last:border-0">
            <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEVERITY_DOT[event.severity] || SEVERITY_DOT.info}`} />
            <div className="min-w-0 flex-1">
                <p className="text-white/80 truncate">{event.title}</p>
                <p className="text-white/30 text-[10px]">{event.kind} • {event.actor || 'system'} • {(event.at || '').replace('T', ' ').slice(0, 19)}</p>
            </div>
        </div>
    );
}

export default function ControlCenterPage() {
    const { isAdmin } = useAuth();
    const [overview, setOverview] = useState(null);
    const [components, setComponents] = useState([]);
    const [jobs, setJobs] = useState([]);
    const [activity, setActivity] = useState([]);
    const [dependencies, setDependencies] = useState(null);
    const [backupStatus, setBackupStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [busyJob, setBusyJob] = useState(null);
    const [backupRunning, setBackupRunning] = useState(false);
    // Backend-unreachable resilience: keep the last successfully fetched data
    // on screen (stale-but-informative) instead of blanking the page, and
    // surface a clear banner with when it was last confirmed live.
    const [backendUnreachable, setBackendUnreachable] = useState(false);
    const [lastUpdated, setLastUpdated] = useState(null);

    const fetchAll = useCallback(async () => {
        try {
            const [ovRes, compRes, jobsRes, activityRes, depsRes, backupRes] = await Promise.all([
                fetch(`${API}/api/control-center/overview`, { headers: authHeaders() }),
                fetch(`${API}/api/control-center/components`, { headers: authHeaders() }),
                fetch(`${API}/api/control-center/jobs`, { headers: authHeaders() }),
                fetch(`${API}/api/control-center/activity?limit=60`, { headers: authHeaders() }),
                fetch(`${API}/api/control-center/dependencies`, { headers: authHeaders() }),
                fetch(`${API}/api/backup/status`, { headers: authHeaders() }),
            ]);
            // Any of these resolving (even 401/500, i.e. a real HTTP response) means the
            // backend process itself is reachable — only a network-level failure (thrown
            // exception below) means it's actually down.
            if (ovRes.ok) setOverview(await ovRes.json());
            if (compRes.ok) setComponents((await compRes.json()).components || []);
            if (jobsRes.ok) setJobs((await jobsRes.json()).jobs || []);
            if (activityRes.ok) setActivity((await activityRes.json()).events || []);
            if (depsRes.ok) setDependencies(await depsRes.json());
            if (backupRes.ok) setBackupStatus(await backupRes.json());
            setBackendUnreachable(false);
            setLastUpdated(new Date());
        } catch (e) {
            // fetch() only throws on network failure (DNS, connection refused, timeout) —
            // exactly "backend unreachable". Keep whatever data is already in state so the
            // page stays informative instead of going blank.
            setBackendUnreachable(true);
            toast.error('Backend unreachable — showing last known status');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 20000);
        return () => clearInterval(interval);
    }, [fetchAll]);

    const handlePause = async (jobId) => {
        setBusyJob(jobId);
        try {
            const r = await fetch(`${API}/api/control-center/jobs/${encodeURIComponent(jobId)}/pause`, { method: 'POST', headers: authHeaders() });
            const result = await r.json();
            if (!r.ok || result.ok === false) throw new Error(result.error || await r.text());
            toast.success(`Paused ${jobId}`);
            fetchAll();
        } catch (e) {
            toast.error(`Pause failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusyJob(null);
        }
    };

    const handleResume = async (jobId) => {
        setBusyJob(jobId);
        try {
            const r = await fetch(`${API}/api/control-center/jobs/${encodeURIComponent(jobId)}/resume`, { method: 'POST', headers: authHeaders() });
            const result = await r.json();
            if (!r.ok || result.ok === false) throw new Error(result.error || await r.text());
            toast.success(`Resumed ${jobId}`);
            fetchAll();
        } catch (e) {
            toast.error(`Resume failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBusyJob(null);
        }
    };

    const handleRunBackup = async () => {
        setBackupRunning(true);
        try {
            const r = await fetch(`${API}/api/backup/run`, { method: 'POST', headers: authHeaders() });
            const result = await r.json();
            if (!r.ok || result.ok === false) throw new Error(result.error || 'backup failed');
            toast.success(`Backup completed (${result.size_bytes ? Math.round(result.size_bytes / 1024 / 1024) + 'MB' : ''})`);
            fetchAll();
        } catch (e) {
            toast.error(`Backup failed: ${e.message?.slice(0, 200)}`);
        } finally {
            setBackupRunning(false);
        }
    };

    const mongoOk = overview?.mongo?.status === 'healthy' || overview?.mongo?.connected === true;

    return (
        <div className="p-6 space-y-4 max-w-[1500px] mx-auto" data-testid="control-center-page">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <Cpu className="w-6 h-6 text-cyan-400" /> Platform Control Center
                    </h1>
                    <p className="text-sm text-white/50 mt-1">
                        FalconOps is one backend process, not a fleet of independent microservices — this console reflects
                        that honestly. Real health status throughout; pause/resume controls the background jobs that
                        genuinely are independent, safely-restartable loops inside this process.
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading} data-testid="refresh-control-center">
                    <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {backendUnreachable && (
                <div
                    className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-300"
                    data-testid="backend-unreachable-banner"
                >
                    <WifiOff className="w-4 h-4 shrink-0" />
                    <span>
                        Backend unreachable — showing last known status
                        {lastUpdated ? ` as of ${lastUpdated.toLocaleTimeString()}` : ''}. Retrying every 20s.
                    </span>
                </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                <StatCard icon={Server} label="Version" value={overview?.version || '—'} />
                <StatCard icon={Activity} label="Process Uptime" value={overview?.process?.uptime_human || overview?.process?.uptime || '—'} />
                <StatCard icon={Database} label="MongoDB" value={mongoOk ? 'Connected' : 'Check'} tone={mongoOk ? 'good' : 'warn'} />
                <StatCard icon={ShieldCheck} label="Services Healthy" value={overview ? `${overview.services_healthy}/${overview.services_total}` : '—'} tone="good" />
                <StatCard icon={AlertTriangle} label="Services Warning/Critical" value={overview ? `${(overview.services_warning || 0) + (overview.services_critical || 0)}` : '—'} tone={(overview?.services_warning || overview?.services_critical) ? (overview?.services_critical ? 'bad' : 'warn') : 'good'} />
                <StatCard icon={Cpu} label="CPU" value={overview?.resources?.cpu_percent != null ? `${overview.resources.cpu_percent}%` : '—'} />
            </div>

            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white">
                        <Boxes className="w-4 h-4 text-cyan-400" /> Application Components
                    </CardTitle>
                    <p className="text-[11px] text-white/40">
                        Real per-component status — green is a fast successful check, amber is a slow one, red is a failed one. Never fabricated.
                    </p>
                </CardHeader>
                <CardContent className="p-4">
                    {components.length === 0 ? (
                        <div className="text-xs text-white/40">Loading…</div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                            {components.map((c) => (
                                <ComponentCard key={c.collection} component={c} />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card className="bg-black/40 border-white/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2 text-white">
                            <Activity className="w-4 h-4 text-cyan-400" /> Background Jobs
                        </CardTitle>
                        <p className="text-[11px] text-white/40">
                            {isAdmin
                                ? 'Real pause/resume — these are independent loops inside this one process, not separate services. A watchdog auto-restarts crashed jobs (bounded retries; whole-process crashes are already handled by the container restart policy).'
                                : 'Read-only — admin role required to pause/resume.'}
                        </p>
                    </CardHeader>
                    <CardContent className="p-0 max-h-[420px] overflow-y-auto">
                        {jobs.length === 0 && <div className="p-4 text-xs text-white/40">Loading…</div>}
                        {jobs.map((job) => (
                            <JobRow key={job.id} job={job} isAdmin={isAdmin} onPause={handlePause} onResume={handleResume} busy={busyJob === job.id} />
                        ))}
                    </CardContent>
                </Card>

                <Card className="bg-black/40 border-white/10">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2 text-white">
                            <ScrollText className="w-4 h-4 text-white/60" /> Unified Activity Timeline
                        </CardTitle>
                        <p className="text-[11px] text-white/40">Aggregated from agentic decisions, remediation, config changes, security audit, integrations, reports, runbooks, platform events, and job auto-restarts.</p>
                    </CardHeader>
                    <CardContent className="p-0 max-h-[420px] overflow-y-auto">
                        {activity.length === 0 && <div className="p-4 text-xs text-white/40">No recent activity.</div>}
                        {activity.map((event, i) => <ActivityRow key={i} event={event} />)}
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2 flex-row items-center justify-between space-y-0">
                    <div>
                        <CardTitle className="text-sm flex items-center gap-2 text-white">
                            <HardDriveDownload className="w-4 h-4 text-emerald-400" /> Database Backups
                        </CardTitle>
                        <p className="text-[11px] text-white/40 mt-1">
                            Real scheduled mongodump — creates the backup, doesn't restore. Restore stays the documented manual mongorestore procedure (see Admin Guide).
                        </p>
                    </div>
                    {isAdmin && (
                        <Button size="sm" variant="outline" disabled={backupRunning} onClick={handleRunBackup} data-testid="run-backup-now">
                            <HardDriveDownload className={`w-3.5 h-3.5 mr-1.5 ${backupRunning ? 'animate-pulse' : ''}`} /> {backupRunning ? 'Running…' : 'Run Backup Now'}
                        </Button>
                    )}
                </CardHeader>
                <CardContent className="p-4">
                    {!backupStatus ? (
                        <div className="text-xs text-white/40">Loading…</div>
                    ) : !backupStatus.configured ? (
                        <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded p-2">
                            mongodump is not installed on this host — the scheduler is running but every attempt fails. See backup_service.py / Dockerfile.
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[12px]">
                            <div>
                                <p className="text-white/40 text-[10px] uppercase">Last Attempt</p>
                                <p className={backupStatus.last_attempt?.ok ? 'text-emerald-300' : 'text-red-300'}>
                                    {backupStatus.last_attempt ? (backupStatus.last_attempt.ok ? 'Succeeded' : 'Failed') : 'None yet'}
                                </p>
                            </div>
                            <div>
                                <p className="text-white/40 text-[10px] uppercase">When</p>
                                <p className="text-white/70">{(backupStatus.last_attempt?.started_at || '').replace('T', ' ').slice(0, 19) || '—'}</p>
                            </div>
                            <div>
                                <p className="text-white/40 text-[10px] uppercase">Interval</p>
                                <p className="text-white/70">Every {backupStatus.interval_hours}h · keep last {backupStatus.retention_count}</p>
                            </div>
                            <div>
                                <p className="text-white/40 text-[10px] uppercase">Location</p>
                                <p className="text-white/70 truncate" title={backupStatus.backup_dir}>{backupStatus.backup_dir}</p>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card className="bg-black/40 border-white/10">
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-white">
                        <Network className="w-4 h-4 text-violet-400" /> Internal Deployment Map
                    </CardTitle>
                    <p className="text-[11px] text-white/40">
                        FalconOps's own deployment shape (from docker-compose.yml) — not the monitored-service topology, see link below.
                    </p>
                </CardHeader>
                <CardContent className="p-4">
                    <div className="flex flex-wrap gap-2">
                        {(dependencies?.nodes || []).map((node) => (
                            <Badge key={node.id} className="text-[11px] bg-white/5 border border-white/15 text-white/70 px-3 py-1.5">
                                {node.label}
                            </Badge>
                        ))}
                    </div>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Link to="/admin/control-console" className="block">
                    <Card className="bg-black/40 border-white/10 hover:border-cyan-500/30 transition-colors">
                        <CardContent className="p-4 flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/90 flex items-center gap-1.5"><Settings className="w-4 h-4" /> Configuration</p>
                                <p className="text-[11px] text-white/40 mt-0.5">Feature flags, limits, AI model config</p>
                            </div>
                            <ExternalLink className="w-3.5 h-3.5 text-white/30" />
                        </CardContent>
                    </Card>
                </Link>
                <Link to="/topology" className="block">
                    <Card className="bg-black/40 border-white/10 hover:border-cyan-500/30 transition-colors">
                        <CardContent className="p-4 flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/90 flex items-center gap-1.5"><Network className="w-4 h-4" /> Service Topology</p>
                                <p className="text-[11px] text-white/40 mt-0.5">Monitored-service dependency graph</p>
                            </div>
                            <ExternalLink className="w-3.5 h-3.5 text-white/30" />
                        </CardContent>
                    </Card>
                </Link>
                <Link to="/self-monitoring" className="block">
                    <Card className="bg-black/40 border-white/10 hover:border-cyan-500/30 transition-colors">
                        <CardContent className="p-4 flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/90 flex items-center gap-1.5"><Activity className="w-4 h-4" /> Full Diagnostics</p>
                                <p className="text-[11px] text-white/40 mt-0.5">Detailed resource/process/DB health</p>
                            </div>
                            <ExternalLink className="w-3.5 h-3.5 text-white/30" />
                        </CardContent>
                    </Card>
                </Link>
            </div>
        </div>
    );
}
