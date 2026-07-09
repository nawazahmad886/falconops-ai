import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { toast } from 'sonner';
import { Radar, Key, Copy, Download, CheckCircle, Container, Boxes, TerminalSquare } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const FEATURES = [
    'Auto-discovers Node.js, Python, Java, Go & .NET services',
    'Logs: /var/log, Docker & Kubernetes pods (filtered, batched, gzip)',
    'Metrics: host CPU/mem/disk/net + per-service process stats',
    'Traces: built-in OTLP receiver — zero app code changes',
    'App metrics derived from traces: req rate, error rate, p95/p99',
    'Smart sampling + disk buffer with retry (offline-safe)',
    '< 2% CPU, < 100MB RAM · single ~7MB static binary',
];

export const OneAgentCard = () => {
    const [apiKey, setApiKey] = useState('');
    const [keyName, setKeyName] = useState('');
    const [generating, setGenerating] = useState(false);

    const generateKey = async () => {
        setGenerating(true);
        try {
            const r = await fetch(`${API_URL}/api/oneagent/keys`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
                },
                body: JSON.stringify({ name: keyName || 'oneagent-key' }),
            });
            if (!r.ok) throw new Error(r.status === 403 ? 'Admin access required' : 'Failed');
            const data = await r.json();
            setApiKey(data.key);
            toast.success('API key generated — copy it now, it is shown only once');
        } catch (e) {
            toast.error(e.message || 'Key generation failed');
        } finally {
            setGenerating(false);
        }
    };

    const installCmd = `curl -sL ${API_URL}/api/oneagent/install.sh | FALCONOPS_API_KEY=${apiKey || '<API_KEY>'} FALCONOPS_BACKEND_URL=${API_URL} sudo -E bash`;
    const dockerCmd = `docker run -d --name falconops-oneagent -e FALCONOPS_API_KEY=${apiKey || '<API_KEY>'} -e FALCONOPS_BACKEND_URL=${API_URL} -v /proc:/host/proc:ro -e HOST_PROC=/host/proc -v /var/log:/var/log:ro --pid=host --network=host falconops/oneagent:latest`;

    const copy = (text, label) => {
        navigator.clipboard.writeText(text);
        toast.success(`${label} copied`);
    };

    const download = (path, filename) => {
        const a = document.createElement('a');
        a.href = `${API_URL}${path}`;
        a.download = filename;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
    };

    return (
        <Card className="bg-gradient-to-br from-[#0a0a0a] to-cyan-950/20 border-cyan-500/30 mb-6" data-testid="oneagent-card">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-cyan-500/15">
                            <Radar className="w-6 h-6 text-cyan-300" />
                        </div>
                        <div>
                            <CardTitle className="text-white text-lg flex items-center gap-2">
                                FalconOpsAI OneAgent
                                <Badge className="bg-cyan-500/20 text-cyan-300 border-cyan-500/30 text-[10px]">NEW</Badge>
                                <Badge variant="outline" className="text-[10px] border-white/20 text-white/50">v1.0.0 · Go</Badge>
                            </CardTitle>
                            <CardDescription className="text-xs mt-0.5">
                                Universal observability agent — one binary for logs, metrics & traces. Linux, Docker, Kubernetes. SaaS & on-prem.
                            </CardDescription>
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-200 h-8 text-xs"
                            onClick={() => download('/api/oneagent/download/binary?arch=amd64', 'falconops-oneagent-linux-amd64')}
                            data-testid="oneagent-download-amd64">
                            <Download className="w-3.5 h-3.5 mr-1" /> Linux x86_64
                        </Button>
                        <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-200 h-8 text-xs"
                            onClick={() => download('/api/oneagent/download/binary?arch=arm64', 'falconops-oneagent-linux-arm64')}
                            data-testid="oneagent-download-arm64">
                            <Download className="w-3.5 h-3.5 mr-1" /> Linux ARM64
                        </Button>
                        <Button size="sm" variant="outline" className="border-white/15 text-white/60 h-8 text-xs"
                            onClick={() => download('/api/oneagent/download/source', 'falconops-oneagent-src.tar.gz')}
                            data-testid="oneagent-download-source">
                            <Download className="w-3.5 h-3.5 mr-1" /> Source
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-0">
                <div className="p-3 bg-white/[0.03] rounded-lg space-y-1.5">
                    <h4 className="text-xs font-medium text-white/70 uppercase tracking-wider">Capabilities</h4>
                    <ul className="space-y-1">
                        {FEATURES.map((f, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs text-white/55">
                                <CheckCircle className="w-3 h-3 mt-0.5 shrink-0 text-cyan-400" /> {f}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="space-y-3">
                    <div className="p-3 bg-white/[0.03] rounded-lg space-y-2">
                        <h4 className="text-xs font-medium text-white/70 uppercase tracking-wider flex items-center gap-1.5">
                            <Key className="w-3.5 h-3.5 text-amber-300" /> 1 · Generate Agent API Key
                        </h4>
                        {apiKey ? (
                            <div className="flex items-center gap-2">
                                <code data-testid="oneagent-api-key" className="flex-1 text-[11px] font-mono text-emerald-300 bg-black/50 border border-emerald-500/20 rounded px-2 py-1.5 truncate">{apiKey}</code>
                                <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => copy(apiKey, 'API key')}>
                                    <Copy className="w-3.5 h-3.5" />
                                </Button>
                            </div>
                        ) : (
                            <div className="flex gap-2">
                                <Input value={keyName} onChange={e => setKeyName(e.target.value)}
                                    placeholder="key name (e.g. prod-cluster)"
                                    className="h-8 text-xs bg-white/5 border-white/15 text-white"
                                    data-testid="oneagent-key-name-input" />
                                <Button size="sm" className="h-8 text-xs bg-amber-500/20 border border-amber-500/40 text-amber-200 hover:bg-amber-500/30"
                                    onClick={generateKey} disabled={generating} data-testid="oneagent-generate-key-btn">
                                    {generating ? 'Generating…' : 'Generate Key'}
                                </Button>
                            </div>
                        )}
                    </div>
                    <div className="p-3 bg-white/[0.03] rounded-lg space-y-2">
                        <h4 className="text-xs font-medium text-white/70 uppercase tracking-wider flex items-center gap-1.5">
                            <TerminalSquare className="w-3.5 h-3.5 text-cyan-300" /> 2 · Install (Linux / systemd)
                        </h4>
                        <div className="relative group">
                            <pre className="p-2 bg-black/60 border border-white/5 rounded text-[10px] text-white/50 whitespace-pre-wrap break-all font-mono">{installCmd}</pre>
                            <Button size="sm" variant="ghost" className="absolute top-1 right-1 h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                                onClick={() => copy(installCmd, 'Install command')} data-testid="oneagent-copy-install">
                                <Copy className="w-3 h-3" />
                            </Button>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-white/35">
                            <button className="flex items-center gap-1 hover:text-white/70" onClick={() => copy(dockerCmd, 'Docker command')}>
                                <Container className="w-3 h-3" /> Copy Docker run
                            </button>
                            <span className="flex items-center gap-1">
                                <Boxes className="w-3 h-3" /> K8s DaemonSet included in source bundle
                            </span>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
