import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    BarChart3,
    RefreshCw,
    TrendingDown,
    TrendingUp,
    Clock,
    AlertTriangle,
    CheckCircle2,
    Activity,
} from 'lucide-react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
} from 'recharts';

const COLORS = ['hsl(199, 89%, 58%)', 'hsl(160, 84%, 39%)', 'hsl(43, 74%, 52%)', 'hsl(0, 84%, 60%)'];

export const AnalyticsPage = () => {
    const { api } = useAuth();
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchAnalytics = async () => {
        setLoading(true);
        try {
            const response = await api.get('/analytics/dashboard');
            setAnalytics(response.data);
        } catch (error) {
            toast.error('Failed to fetch analytics');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAnalytics();
    }, []);

    const formatMTTR = (seconds) => {
        if (!seconds) return '0m';
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return `${(seconds / 3600).toFixed(1)}h`;
    };

    const severityData = analytics?.alerts_by_severity 
        ? Object.entries(analytics.alerts_by_severity).map(([name, value]) => ({ name, value }))
        : [];

    const serviceData = analytics?.alerts_by_service
        ? Object.entries(analytics.alerts_by_service).map(([name, value]) => ({ name, value })).slice(0, 8)
        : [];

    if (loading) {
        return (
            <>
                <div className="flex items-center justify-center h-[60vh]">
                    <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                </div>
            </>
        );
    }

    return (
        <>
            <div className="space-y-6" data-testid="analytics-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 className="font-heading font-semibold text-2xl md:text-3xl flex items-center gap-2">
                            <BarChart3 className="w-7 h-7 text-primary" />
                            Analytics
                        </h1>
                        <p className="text-muted-foreground text-sm">Performance metrics and operational insights</p>
                    </div>
                    <Button onClick={fetchAnalytics} variant="outline" size="sm">
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="bg-card/50 border-border/40">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Total Alerts</p>
                                <AlertTriangle className="w-5 h-5 text-warning" />
                            </div>
                            <p className="font-heading font-bold text-3xl" data-testid="total-alerts">
                                {analytics?.total_alerts || 0}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {analytics?.open_alerts || 0} open
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-card/50 border-border/40">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Total Incidents</p>
                                <Activity className="w-5 h-5 text-primary" />
                            </div>
                            <p className="font-heading font-bold text-3xl" data-testid="total-incidents">
                                {analytics?.total_incidents || 0}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                                {analytics?.open_incidents || 0} active
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="bg-card/50 border-border/40">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Avg MTTR</p>
                                <Clock className="w-5 h-5 text-info" />
                            </div>
                            <p className="font-heading font-bold text-3xl" data-testid="analytics-mttr">
                                {formatMTTR(analytics?.avg_mttr_seconds)}
                            </p>
                            <div className="flex items-center gap-1 mt-1">
                                <TrendingDown className="w-3 h-3 text-success" />
                                <p className="text-xs text-success">Improving</p>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-card/50 border-border/40">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">SLA Compliance</p>
                                <CheckCircle2 className="w-5 h-5 text-success" />
                            </div>
                            <p className="font-heading font-bold text-3xl" data-testid="analytics-sla">
                                {analytics?.sla_compliance || 100}%
                            </p>
                            <div className="flex items-center gap-1 mt-1">
                                <TrendingUp className="w-3 h-3 text-success" />
                                <p className="text-xs text-success">On target</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Charts Row */}
                <div className="grid lg:grid-cols-2 gap-6">
                    {/* Incidents Trend */}
                    <Card className="bg-card/50 border-border/40">
                        <CardHeader className="pb-2">
                            <CardTitle className="font-heading text-lg">Incidents Over Time</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-[300px]">
                                {analytics?.incidents_trend?.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={analytics.incidents_trend}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                            <XAxis 
                                                dataKey="date" 
                                                stroke="rgba(255,255,255,0.5)" 
                                                fontSize={12}
                                                tickFormatter={(val) => val?.slice(5) || ''}
                                            />
                                            <YAxis stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                            <Tooltip 
                                                contentStyle={{ 
                                                    backgroundColor: 'hsl(0 0% 4%)', 
                                                    border: '1px solid hsl(0 0% 15%)',
                                                    borderRadius: '8px'
                                                }}
                                            />
                                            <Line 
                                                type="monotone" 
                                                dataKey="count" 
                                                stroke="hsl(199 89% 58%)" 
                                                strokeWidth={2}
                                                dot={{ fill: 'hsl(199 89% 58%)' }}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-muted-foreground">
                                        <p className="text-sm">No trend data available</p>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Alerts by Severity Pie */}
                    <Card className="bg-card/50 border-border/40">
                        <CardHeader className="pb-2">
                            <CardTitle className="font-heading text-lg">Alerts by Severity</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-[300px]">
                                {severityData.length > 0 ? (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={severityData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={60}
                                                outerRadius={100}
                                                paddingAngle={5}
                                                dataKey="value"
                                            >
                                                {severityData.map((entry, index) => (
                                                    <Cell 
                                                        key={`cell-${index}`} 
                                                        fill={
                                                            entry.name === 'critical' ? 'hsl(0 84% 60%)' :
                                                            entry.name === 'warning' ? 'hsl(38 92% 50%)' :
                                                            'hsl(217 91% 60%)'
                                                        } 
                                                    />
                                                ))}
                                            </Pie>
                                            <Tooltip 
                                                contentStyle={{ 
                                                    backgroundColor: 'hsl(0 0% 4%)', 
                                                    border: '1px solid hsl(0 0% 15%)',
                                                    borderRadius: '8px'
                                                }}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-muted-foreground">
                                        <p className="text-sm">No severity data available</p>
                                    </div>
                                )}
                            </div>
                            <div className="flex items-center justify-center gap-6 mt-4">
                                {severityData.map((entry, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <div 
                                            className="w-3 h-3 rounded-full"
                                            style={{ 
                                                backgroundColor: entry.name === 'critical' ? 'hsl(0 84% 60%)' :
                                                    entry.name === 'warning' ? 'hsl(38 92% 50%)' :
                                                    'hsl(217 91% 60%)'
                                            }}
                                        />
                                        <span className="text-sm text-muted-foreground capitalize">{entry.name}</span>
                                        <span className="text-sm font-mono">{entry.value}</span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Alerts by Service */}
                <Card className="bg-card/50 border-border/40">
                    <CardHeader className="pb-2">
                        <CardTitle className="font-heading text-lg">Alerts by Service</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px]">
                            {serviceData.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={serviceData} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                        <XAxis type="number" stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                        <YAxis 
                                            dataKey="name" 
                                            type="category" 
                                            stroke="rgba(255,255,255,0.5)" 
                                            fontSize={12} 
                                            width={120}
                                            tickFormatter={(val) => val?.length > 15 ? val.slice(0, 15) + '...' : val}
                                        />
                                        <Tooltip 
                                            contentStyle={{ 
                                                backgroundColor: 'hsl(0 0% 4%)', 
                                                border: '1px solid hsl(0 0% 15%)',
                                                borderRadius: '8px'
                                            }}
                                        />
                                        <Bar 
                                            dataKey="value" 
                                            fill="hsl(199 89% 58%)"
                                            radius={[0, 4, 4, 0]}
                                        />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="flex items-center justify-center h-full text-muted-foreground">
                                    <p className="text-sm">No service data available</p>
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </>
    );
};
