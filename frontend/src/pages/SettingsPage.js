import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import {
    Settings,
    User,
    Webhook,
    Bell,
    Copy,
    Check,
    ExternalLink,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const SettingsPage = () => {
    const { user } = useAuth();
    const [copied, setCopied] = useState(false);
    const webhookUrl = `${BACKEND_URL}/api/alerts/webhook`;

    const copyWebhookUrl = () => {
        navigator.clipboard.writeText(webhookUrl);
        setCopied(true);
        toast.success('Webhook URL copied to clipboard');
        setTimeout(() => setCopied(false), 2000);
    };

    const examplePayload = {
        source: "AppDynamics",
        severity: "critical",
        title: "High CPU Usage",
        description: "CPU usage exceeded 95% threshold",
        service: "payment-service",
        host: "prod-server-01",
        metric_name: "cpu_usage",
        metric_value: 97.5,
        threshold: 95,
        tags: {
            environment: "production",
            team: "payments"
        }
    };

    return (
        <>
            <div className="space-y-6" data-testid="settings-page">
                {/* Header */}
                <div>
                    <h1 className="font-heading font-semibold text-2xl md:text-3xl flex items-center gap-2">
                        <Settings className="w-7 h-7 text-primary" />
                        Settings
                    </h1>
                    <p className="text-muted-foreground text-sm">Configure your FalconOps AI platform</p>
                </div>

                <Tabs defaultValue="profile" className="space-y-6">
                    <TabsList className="bg-muted/30 border border-border/40">
                        <TabsTrigger value="profile" data-testid="tab-profile">Profile</TabsTrigger>
                        <TabsTrigger value="webhooks" data-testid="tab-webhooks">Webhooks</TabsTrigger>
                        <TabsTrigger value="notifications" data-testid="tab-notifications">Notifications</TabsTrigger>
                    </TabsList>

                    {/* Profile Tab */}
                    <TabsContent value="profile">
                        <Card className="bg-card/50 border-border/40">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <User className="w-5 h-5 text-primary" />
                                    Profile Information
                                </CardTitle>
                                <CardDescription>Your account details</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid md:grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Full Name</Label>
                                        <Input 
                                            value={user?.full_name || ''} 
                                            disabled 
                                            className="bg-muted/50"
                                            data-testid="profile-name"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Email</Label>
                                        <Input 
                                            value={user?.email || ''} 
                                            disabled 
                                            className="bg-muted/50"
                                            data-testid="profile-email"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Organization</Label>
                                        <Input 
                                            value={user?.organization || 'Not specified'} 
                                            disabled 
                                            className="bg-muted/50"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Role</Label>
                                        <div className="flex items-center gap-2 h-10">
                                            <Badge variant="outline" className="border-primary text-primary">
                                                {user?.role || 'User'}
                                            </Badge>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Webhooks Tab */}
                    <TabsContent value="webhooks" className="space-y-6">
                        <Card className="bg-card/50 border-border/40">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Webhook className="w-5 h-5 text-primary" />
                                    Alert Webhook Endpoint
                                </CardTitle>
                                <CardDescription>
                                    Send alerts from your monitoring tools to this endpoint
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label>Webhook URL</Label>
                                    <div className="flex items-center gap-2">
                                        <Input 
                                            value={webhookUrl} 
                                            readOnly 
                                            className="bg-muted/50 font-mono text-sm"
                                            data-testid="webhook-url"
                                        />
                                        <Button 
                                            variant="outline" 
                                            size="icon"
                                            onClick={copyWebhookUrl}
                                            data-testid="copy-webhook-url"
                                        >
                                            {copied ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
                                        </Button>
                                    </div>
                                </div>

                                <Separator className="bg-border/40" />

                                <div className="space-y-3">
                                    <Label>HTTP Method</Label>
                                    <Badge>POST</Badge>
                                </div>

                                <div className="space-y-3">
                                    <Label>Example Request Payload</Label>
                                    <div className="bg-muted/50 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                                        <pre className="text-muted-foreground">
                                            {JSON.stringify(examplePayload, null, 2)}
                                        </pre>
                                    </div>
                                </div>

                                <div className="space-y-3">
                                    <Label>cURL Example</Label>
                                    <div className="bg-muted/50 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                                        <pre className="text-muted-foreground whitespace-pre-wrap">
{`curl -X POST "${webhookUrl}" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(examplePayload)}'`}
                                        </pre>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="bg-card/50 border-border/40">
                            <CardHeader>
                                <CardTitle>Supported Monitoring Tools</CardTitle>
                                <CardDescription>
                                    FalconOps AI can receive alerts from any tool that supports HTTP webhooks
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    {['AppDynamics', 'Elastic APM', 'Prometheus', 'Datadog', 'New Relic', 'Dynatrace', 'Grafana', 'PagerDuty'].map((tool) => (
                                        <div 
                                            key={tool}
                                            className="p-3 rounded-lg bg-muted/30 border border-border/40 text-center text-sm"
                                        >
                                            {tool}
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Notifications Tab */}
                    <TabsContent value="notifications">
                        <Card className="bg-card/50 border-border/40">
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Bell className="w-5 h-5 text-primary" />
                                    Notification Settings
                                </CardTitle>
                                <CardDescription>
                                    Configure how you receive alerts and notifications
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="text-center py-8 text-muted-foreground">
                                    <Bell className="w-10 h-10 mx-auto mb-2 opacity-50" />
                                    <p className="text-sm">Email notifications coming soon</p>
                                    <p className="text-xs">Configure SendGrid integration to enable email alerts</p>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </>
    );
};
