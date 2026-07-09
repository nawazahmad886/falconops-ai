import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    Cloud, CheckCircle2, AlertTriangle, Copy, RefreshCw, Lock, ServerCog, Sparkles, ChevronRight,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const headers = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

export default function AWSDeployWizardPage() {
    const [health, setHealth] = useState(null);
    const [conn, setConn] = useState(null);
    const [cfg, setCfg] = useState({
        aws_region: 'us-east-1',
        aws_account_id: '',
        ecr_repo_backend: 'falconops-backend',
        ecr_repo_frontend: 'falconops-frontend',
        ecs_cluster: 'falconops-prod',
        ecs_service_backend: 'falconops-backend-svc',
        ecs_service_frontend: 'falconops-frontend-svc',
        s3_reports_bucket: 'falconops-reports-prod',
        image_tag: 'latest',
        docker_build_target: 'production',
    });
    const [creds, setCreds] = useState({ aws_access_key_id: '', aws_secret_access_key: '' });
    const [plan, setPlan] = useState(null);
    const [testing, setTesting] = useState(false);
    const [planning, setPlanning] = useState(false);
    const [done, setDone] = useState({});

    useEffect(() => {
        (async () => {
            try {
                const r = await fetch(`${API}/api/deploy/aws/health`, { headers: headers() });
                if (r.ok) setHealth(await r.json());
            } catch {
                /* ignore */
            }
        })();
    }, []);

    const testConnection = async () => {
        setTesting(true);
        setConn(null);
        try {
            const r = await fetch(`${API}/api/deploy/aws/test-connection`, {
                method: 'POST',
                headers: headers(),
                body: JSON.stringify({
                    aws_region: cfg.aws_region,
                    aws_access_key_id: creds.aws_access_key_id || null,
                    aws_secret_access_key: creds.aws_secret_access_key || null,
                }),
            });
            const d = await r.json();
            setConn(d);
            d.ok ? toast.success('AWS connection OK') : toast.error('AWS connection failed');
        } catch (e) {
            setConn({ ok: false, error: e.message });
            toast.error('Connection test failed');
        } finally {
            setTesting(false);
        }
    };

    const buildPlan = async () => {
        setPlanning(true);
        try {
            const r = await fetch(`${API}/api/deploy/aws/plan`, {
                method: 'POST',
                headers: headers(),
                body: JSON.stringify(cfg),
            });
            if (!r.ok) throw new Error(await r.text());
            const d = await r.json();
            setPlan(d);
            toast.success(`Deployment plan ready — ${d.phases.length} phases`);
        } catch (e) {
            toast.error('Plan generation failed');
        } finally {
            setPlanning(false);
        }
    };

    const copyCmds = async (cmds) => {
        await navigator.clipboard.writeText(cmds.join('\n'));
        toast.success('Commands copied to clipboard');
    };

    const allCmds = () => {
        if (!plan) return '';
        const parts = [`#!/bin/bash\nset -euo pipefail\n\n# FalconOps AWS Deployment — auto-generated\n`];
        for (const p of plan.phases) {
            parts.push(`\n# ─── ${p.title} ───`);
            parts.push(`# ${p.blurb}`);
            parts.push(...p.commands);
        }
        return parts.join('\n');
    };

    return (
        <div className="p-6 space-y-5 max-w-6xl" data-testid="aws-deploy-wizard">
            <div>
                <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                    <Cloud className="w-6 h-6 text-orange-400" />
                    AWS Production Deployment Wizard
                </h1>
                <p className="text-sm text-white/55 mt-1">
                    Generates copy-paste bash commands to deploy FalconOps to ECS Fargate with S3 reports, terraform-managed infra, and zero-downtime rollouts.
                </p>
            </div>

            {/* Environment health strip */}
            {health && (
                <div className="grid md:grid-cols-4 gap-3">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-3 flex items-center gap-2.5">
                            {health.tooling.aws_cli ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-white/40">AWS CLI</div>
                                <div className={`text-xs ${health.tooling.aws_cli ? 'text-emerald-300' : 'text-amber-300'}`}>
                                    {health.tooling.aws_cli ? 'available' : 'install on operator machine'}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-3 flex items-center gap-2.5">
                            {health.tooling.terraform ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-white/40">Terraform</div>
                                <div className={`text-xs ${health.tooling.terraform ? 'text-emerald-300' : 'text-amber-300'}`}>
                                    {health.tooling.terraform ? 'available' : 'install on operator machine'}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-3 flex items-center gap-2.5">
                            {health.infra_dir_present ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-white/40">infra/</div>
                                <div className="text-xs text-white/70">{health.infra_dir_present ? 'present' : 'missing'}</div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-3 flex items-center gap-2.5">
                            <ServerCog className="w-4 h-4 text-cyan-400" />
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-white/40">Storage Backend</div>
                                <div className="text-xs text-cyan-300">{health.env.STORAGE_BACKEND}</div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            <Tabs defaultValue="config" className="space-y-4">
                <TabsList className="bg-black/40 border border-white/10">
                    <TabsTrigger value="config" data-testid="tab-config">1. Config</TabsTrigger>
                    <TabsTrigger value="test" data-testid="tab-test">2. Test Connection</TabsTrigger>
                    <TabsTrigger value="plan" data-testid="tab-plan">3. Deployment Plan</TabsTrigger>
                </TabsList>

                <TabsContent value="config">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-5 space-y-3">
                            <div className="text-sm font-semibold text-white">Deployment configuration</div>
                            <div className="grid md:grid-cols-2 gap-3 text-[12px]">
                                {Object.entries(cfg).map(([k, v]) => (
                                    <div key={k} className="space-y-1">
                                        <Label className="text-white/55 capitalize">{k.replace(/_/g, ' ')}</Label>
                                        <Input
                                            value={v}
                                            onChange={(e) => setCfg({ ...cfg, [k]: e.target.value })}
                                            className="bg-black/40 border-white/10 text-sm h-8"
                                            data-testid={`cfg-${k}`}
                                        />
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="test">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-5 space-y-3">
                            <div className="text-sm font-semibold text-white flex items-center gap-2">
                                <Lock className="w-4 h-4 text-amber-300" /> AWS connectivity sanity-check
                            </div>
                            <p className="text-[12px] text-white/55">
                                Runs <code className="text-white/80">aws sts get-caller-identity</code> from the FalconOps backend. If aws-cli isn't installed
                                in the backend container, you'll see a clear "operator must install awscli" message — and that's fine; the
                                commands generated here are meant for the operator's laptop.
                            </p>
                            <div className="grid md:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-white/55 text-[11px]">AWS Access Key ID (optional)</Label>
                                    <Input
                                        type="password"
                                        value={creds.aws_access_key_id}
                                        onChange={(e) => setCreds({ ...creds, aws_access_key_id: e.target.value })}
                                        className="bg-black/40 border-white/10 text-sm font-mono"
                                        placeholder="leave blank to use server-side creds"
                                        data-testid="access-key-input"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-white/55 text-[11px]">AWS Secret Access Key (optional)</Label>
                                    <Input
                                        type="password"
                                        value={creds.aws_secret_access_key}
                                        onChange={(e) => setCreds({ ...creds, aws_secret_access_key: e.target.value })}
                                        className="bg-black/40 border-white/10 text-sm font-mono"
                                        placeholder="not stored — only used for this test"
                                        data-testid="secret-key-input"
                                    />
                                </div>
                            </div>
                            <Button onClick={testConnection} disabled={testing} className="bg-amber-500/[0.15] border border-amber-500/40 text-amber-200" data-testid="test-conn-btn">
                                {testing ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
                                Test Connection
                            </Button>
                            {conn && (
                                <div className={`p-3 rounded-lg border text-[12px] mt-2 ${conn.ok ? 'border-emerald-500/30 bg-emerald-500/[0.05] text-emerald-200' : 'border-red-500/30 bg-red-500/[0.05] text-red-200'}`} data-testid="conn-result">
                                    {conn.ok ? (
                                        <>
                                            <CheckCircle2 className="w-4 h-4 inline mr-1.5" />
                                            <span className="font-mono whitespace-pre-wrap">{conn.identity}</span>
                                        </>
                                    ) : (
                                        <>
                                            <AlertTriangle className="w-4 h-4 inline mr-1.5" />
                                            <div>{conn.error || conn.stderr}</div>
                                            {conn.hint && <pre className="text-[11px] mt-2 whitespace-pre-wrap text-white/60">{conn.hint}</pre>}
                                        </>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="plan">
                    <Card className="bg-black/40 border-white/10">
                        <CardContent className="p-5 space-y-4">
                            <div className="flex items-center gap-2">
                                <Button onClick={buildPlan} disabled={planning} className="bg-orange-500/[0.15] border border-orange-500/40 text-orange-200" data-testid="build-plan-btn">
                                    {planning ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Cloud className="w-3.5 h-3.5 mr-1.5" />}
                                    Generate Deployment Plan
                                </Button>
                                {plan && (
                                    <Button variant="outline" onClick={() => navigator.clipboard.writeText(allCmds()).then(() => toast.success('Full deploy.sh copied'))} className="border-white/15 text-white/80 text-[11px]" data-testid="copy-all-btn">
                                        <Copy className="w-3.5 h-3.5 mr-1.5" /> Copy full deploy.sh
                                    </Button>
                                )}
                            </div>
                            {plan && (
                                <ScrollArea className="h-[60vh] pr-3">
                                    <div className="space-y-3">
                                        {plan.phases.map((p) => (
                                            <Card key={p.id} className={`bg-[#0a0a0a] border ${p.destructive ? 'border-red-500/30' : done[p.id] ? 'border-emerald-500/30' : 'border-white/10'}`} data-testid={`phase-${p.id}`}>
                                                <CardContent className="p-4 space-y-2">
                                                    <div className="flex items-start justify-between gap-3">
                                                        <div>
                                                            <div className="text-sm font-semibold text-white flex items-center gap-2">
                                                                {done[p.id] ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <ChevronRight className="w-4 h-4 text-white/40" />}
                                                                {p.title}
                                                                {p.destructive && <Badge className="text-[9px] bg-red-500/15 text-red-300 border border-red-500/30">irreversible</Badge>}
                                                            </div>
                                                            <p className="text-[11px] text-white/55 mt-1">{p.blurb}</p>
                                                        </div>
                                                        <div className="flex items-center gap-1.5 shrink-0">
                                                            <Button size="sm" variant="ghost" onClick={() => copyCmds(p.commands)} className="text-cyan-300 h-7 px-2 text-[11px]" data-testid={`copy-${p.id}`}>
                                                                <Copy className="w-3 h-3 mr-1" /> Copy
                                                            </Button>
                                                            <Button size="sm" variant="ghost" onClick={() => setDone({ ...done, [p.id]: !done[p.id] })} className={`h-7 px-2 text-[11px] ${done[p.id] ? 'text-emerald-300' : 'text-white/50'}`} data-testid={`done-${p.id}`}>
                                                                {done[p.id] ? <CheckCircle2 className="w-3 h-3 mr-1" /> : <CheckCircle2 className="w-3 h-3 mr-1 opacity-30" />}
                                                                {done[p.id] ? 'Done' : 'Mark Done'}
                                                            </Button>
                                                        </div>
                                                    </div>
                                                    <pre className="text-[11px] text-white/80 bg-black/60 p-3 rounded-lg border border-white/5 overflow-x-auto whitespace-pre-wrap font-mono">
                                                        {p.commands.join('\n')}
                                                    </pre>
                                                </CardContent>
                                            </Card>
                                        ))}

                                        <Card className="bg-cyan-500/[0.05] border-cyan-500/30">
                                            <CardContent className="p-4 space-y-2">
                                                <div className="text-sm font-semibold text-cyan-200">Post-flip environment</div>
                                                <pre className="text-[11px] text-white/85 bg-black/60 p-2 rounded font-mono">
{JSON.stringify(plan.post_flip_env, null, 2)}
                                                </pre>
                                                <div className="text-sm font-semibold text-cyan-200 mt-2">Rollback (one-line)</div>
                                                <pre className="text-[11px] text-white/85 bg-black/60 p-2 rounded font-mono whitespace-pre-wrap">{plan.rollback_command}</pre>
                                            </CardContent>
                                        </Card>
                                    </div>
                                </ScrollArea>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
