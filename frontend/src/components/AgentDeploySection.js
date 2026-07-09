import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import {
    Download, Terminal, Copy, CheckCircle, Server, FileCode, Settings,
    ExternalLink, ChevronDown, ChevronUp,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const CopyBlock = ({ code, label }) => {
    const [copied, setCopied] = useState(false);
    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        toast.success('Copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <div className="relative group">
            {label && <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1">{label}</p>}
            <div className="bg-black/60 rounded-lg border border-white/5 p-3 pr-10 overflow-x-auto">
                <pre className="text-xs text-cyan-300 font-mono whitespace-pre-wrap break-all">{code}</pre>
            </div>
            <button onClick={handleCopy}
                className="absolute top-2 right-2 p-1.5 rounded bg-white/5 hover:bg-white/15 text-white/40 hover:text-white transition-colors"
                data-testid={`copy-${(label || 'code').toLowerCase().replace(/\s/g, '-')}`}>
                {copied ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
        </div>
    );
};

export const AgentDeploySection = ({ instanceId, instanceName, dbType }) => {
    const [expanded, setExpanded] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const installCmd = `curl -sSf "${API_URL}/api/db-monitoring/agent/install-script?api_url=${API_URL}&db_type=${dbType || 'postgres'}&instance_id=${instanceId}" | sudo bash`;

    const quickStartCmd = `# 1. Download the agent
curl -o falcon_db_agent.py "${API_URL}/api/db-monitoring/agent/download"

# 2. Install dependencies
pip3 install requests pyyaml psycopg2-binary

# 3. Run (replace with your DB credentials)
python3 falcon_db_agent.py \\
    --api-url ${API_URL} \\
    --instance-id ${instanceId} \\
    --db-type ${dbType || 'postgres'} \\
    --host YOUR_DB_HOST \\
    --port ${dbType === 'oracle' ? '1521' : dbType === 'mysql' ? '3306' : '5432'} \\
    --user monitor \\
    --password YOUR_PASSWORD \\
    --database YOUR_DB_NAME`;

    const dryRunCmd = `python3 falcon_db_agent.py \\
    --db-type ${dbType || 'postgres'} \\
    --host YOUR_DB_HOST \\
    --user monitor \\
    --password YOUR_PASSWORD \\
    --database YOUR_DB_NAME \\
    --dry-run --once`;

    const systemdCmd = `# Enable and start the service
sudo systemctl enable falconops-db-agent
sudo systemctl start falconops-db-agent

# Check status
sudo systemctl status falconops-db-agent

# View logs
sudo journalctl -u falconops-db-agent -f`;

    const handleDownloadAgent = () => {
        window.open(`${API_URL}/api/db-monitoring/agent/download`, '_blank');
        toast.success('Agent download started');
    };

    const handleDownloadConfig = () => {
        window.open(`${API_URL}/api/db-monitoring/agent/config-template?db_type=${dbType || 'postgres'}&api_url=${API_URL}&instance_id=${instanceId}`, '_blank');
        toast.success('Config template download started');
    };

    const handleDownloadInstallScript = () => {
        window.open(`${API_URL}/api/db-monitoring/agent/install-script?api_url=${API_URL}&db_type=${dbType || 'postgres'}&instance_id=${instanceId}`, '_blank');
        toast.success('Install script download started');
    };

    return (
        <div className="space-y-4" data-testid="agent-deploy-section">
            {/* Compact header */}
            <Card className="bg-[#0a0a14] border-white/10">
                <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-cyan-500/10">
                                <Terminal className="w-5 h-5 text-cyan-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-white">Deploy Monitoring Agent</h3>
                                <p className="text-xs text-white/40">Install the FalconOps DB agent on your server to collect real metrics</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge className="text-[9px] bg-cyan-500/10 text-cyan-400 border-0">v2.0</Badge>
                            <Badge className="text-[9px] bg-purple-500/10 text-purple-400 border-0">{(dbType || 'postgres').toUpperCase()}</Badge>
                            <Button variant="ghost" size="sm" className="h-7 text-xs text-white/50" onClick={() => setExpanded(!expanded)} data-testid="toggle-deploy-section">
                                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </Button>
                        </div>
                    </div>

                    {!expanded && (
                        <div className="mt-3 flex gap-2">
                            <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 h-7 text-xs" onClick={handleDownloadAgent} data-testid="download-agent-btn">
                                <Download className="w-3 h-3 mr-1" /> Download Agent
                            </Button>
                            <Button size="sm" variant="outline" className="border-white/20 h-7 text-xs" onClick={handleDownloadConfig} data-testid="download-config-btn">
                                <Settings className="w-3 h-3 mr-1" /> Config Template
                            </Button>
                            <Button size="sm" variant="outline" className="border-white/20 h-7 text-xs" onClick={handleDownloadInstallScript} data-testid="download-install-script-btn">
                                <FileCode className="w-3 h-3 mr-1" /> Install Script
                            </Button>
                        </div>
                    )}
                </CardContent>
            </Card>

            {expanded && (
                <>
                    {/* One-liner install */}
                    <Card className="bg-[#0a0a14] border-emerald-500/10">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Server className="w-4 h-4 text-emerald-400" /> One-Line Install (Recommended)
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <p className="text-xs text-white/40">Run this on your Linux server as root. It downloads the agent, installs dependencies, and creates a systemd service.</p>
                            <CopyBlock code={installCmd} label="Run on your server" />
                            <p className="text-[10px] text-white/30">After install, edit <code className="text-cyan-400">/etc/falconops/db_agent.yaml</code> with your database credentials.</p>
                        </CardContent>
                    </Card>

                    {/* Quick Start (manual) */}
                    <Card className="bg-[#0a0a14] border-white/10">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm text-white flex items-center gap-2">
                                <Terminal className="w-4 h-4 text-cyan-400" /> Manual Quick Start
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <CopyBlock code={quickStartCmd} label="Step-by-step commands" />
                            <div className="flex gap-2">
                                <Button size="sm" className="bg-cyan-600 hover:bg-cyan-700 h-7 text-xs" onClick={handleDownloadAgent} data-testid="download-agent-btn-2">
                                    <Download className="w-3 h-3 mr-1" /> Download Agent (.py)
                                </Button>
                                <Button size="sm" variant="outline" className="border-white/20 h-7 text-xs" onClick={handleDownloadConfig} data-testid="download-config-btn-2">
                                    <Settings className="w-3 h-3 mr-1" /> Download Config (.yaml)
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Advanced section */}
                    <button onClick={() => setShowAdvanced(!showAdvanced)}
                        className="text-xs text-white/30 hover:text-white/60 transition-colors flex items-center gap-1"
                        data-testid="toggle-advanced">
                        {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />} Advanced Options
                    </button>

                    {showAdvanced && (
                        <div className="space-y-4">
                            <Card className="bg-[#0a0a14] border-white/10">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-xs text-white/50">Dry Run (Test without sending data)</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <CopyBlock code={dryRunCmd} label="Test locally" />
                                </CardContent>
                            </Card>
                            <Card className="bg-[#0a0a14] border-white/10">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-xs text-white/50">Systemd Service Management</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <CopyBlock code={systemdCmd} label="Service commands" />
                                </CardContent>
                            </Card>
                            <Card className="bg-[#0a0a14] border-white/10">
                                <CardContent className="p-4">
                                    <p className="text-xs text-white/50 font-medium mb-2">Agent Connection Info</p>
                                    <div className="grid grid-cols-2 gap-3 text-xs">
                                        <div>
                                            <Label className="text-[10px] text-white/30">API Endpoint</Label>
                                            <p className="text-white/60 font-mono">{API_URL}</p>
                                        </div>
                                        <div>
                                            <Label className="text-[10px] text-white/30">Instance ID</Label>
                                            <p className="text-white/60 font-mono">{instanceId}</p>
                                        </div>
                                        <div>
                                            <Label className="text-[10px] text-white/30">Database Type</Label>
                                            <p className="text-white/60">{(dbType || 'postgres').toUpperCase()}</p>
                                        </div>
                                        <div>
                                            <Label className="text-[10px] text-white/30">Instance Name</Label>
                                            <p className="text-white/60">{instanceName}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};
