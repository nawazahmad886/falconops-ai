import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
    Workflow, RefreshCw, Activity, Database, Server,
    CheckCircle, Clock, Layers, BarChart3, Zap,
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell,
} from 'recharts';

const PIE_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6'];

export default function KafkaPipelinePage() {
    const { api } = useAuth();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [producing, setProducing] = useState(false);

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/kafka/stats');
            setStats(res.data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [api]);

    const produceTestEvent = useCallback(async (topic) => {
        setProducing(true);
        try {
            await api.post('/kafka/produce', {
                topic,
                event: {
                    type: 'test_event',
                    message: `Test event on ${topic}`,
                    severity: 'info',
                    source: 'ui_test',
                    timestamp: new Date().toISOString(),
                },
            });
            await fetchStats();
        } catch (e) { console.error(e); }
        setProducing(false);
    }, [api, fetchStats]);

    useEffect(() => { fetchStats(); }, [fetchStats]);

    const topicData = stats?.by_topic?.map(t => ({
        name: t.topic.split('.').pop(),
        count: t.count,
    })) || [];

    return (
        <div className="space-y-6" data-testid="kafka-pipeline-page">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15">
                            <Workflow className="w-6 h-6 text-purple-400" />
                        </div>
                        Kafka Pipeline
                    </h1>
                    <p className="text-sm text-white/50 mt-1">Event streaming pipeline with Kafka / MongoDB fallback</p>
                </div>
                <Button variant="outline" size="sm" onClick={fetchStats} disabled={loading} className="border-white/10 text-xs" data-testid="refresh-stats-btn">
                    <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </Button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-purple-500/15"><Workflow className="w-4 h-4 text-purple-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Mode</p>
                            <p className="text-sm font-bold text-white capitalize" data-testid="pipeline-mode">{stats?.mode?.replace('_', ' ') || '...'}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/15"><BarChart3 className="w-4 h-4 text-blue-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Total Events</p>
                            <p className="text-lg font-bold text-white" data-testid="total-events">{stats?.total_events ?? 0}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-amber-500/15"><Clock className="w-4 h-4 text-amber-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Pending</p>
                            <p className="text-lg font-bold text-amber-400" data-testid="pending-events">{stats?.pending ?? 0}</p>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-[#0D1117] border-white/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-500/15"><CheckCircle className="w-4 h-4 text-emerald-400" /></div>
                        <div>
                            <p className="text-xs text-white/50">Processed</p>
                            <p className="text-lg font-bold text-emerald-400" data-testid="processed-events">{stats?.processed ?? 0}</p>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Topic Breakdown Chart */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Layers className="w-4 h-4 text-purple-400" />
                            Events by Topic
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4">
                        {topicData.length > 0 ? (
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={topicData}>
                                    <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                    <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} axisLine={false} />
                                    <Tooltip contentStyle={{ background: '#161B22', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff' }} />
                                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="text-center py-12 text-white/40">
                                <Layers className="w-8 h-8 mx-auto mb-3 opacity-40" />
                                <p>No topic data yet. Produce test events to see the breakdown.</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Topic Configuration */}
                <Card className="bg-[#0D1117] border-white/5">
                    <CardHeader className="pb-3 border-b border-white/5">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Zap className="w-4 h-4 text-amber-400" />
                            Configured Topics
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 divide-y divide-white/5">
                        {stats?.topics ? Object.entries(stats.topics).map(([key, topicName]) => (
                            <div key={key} className="flex items-center justify-between p-3 hover:bg-white/[0.02]" data-testid={`topic-${key}`}>
                                <div className="flex items-center gap-3">
                                    <div className="p-1.5 rounded bg-purple-500/10">
                                        <Layers className="w-3.5 h-3.5 text-purple-400" />
                                    </div>
                                    <div>
                                        <p className="text-sm text-white/80">{key}</p>
                                        <p className="text-[10px] text-white/30 font-mono">{topicName}</p>
                                    </div>
                                </div>
                                <Button variant="outline" size="sm" onClick={() => produceTestEvent(key)}
                                    disabled={producing} className="border-white/10 text-xs" data-testid={`produce-${key}`}>
                                    <Zap className="w-3 h-3 mr-1" /> Test
                                </Button>
                            </div>
                        )) : (
                            <div className="p-8 text-center text-white/40">No topics configured</div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Kafka Status */}
            <Card className="bg-[#0D1117] border-white/5">
                <CardContent className="p-4 flex items-center gap-4">
                    <Badge className={stats?.kafka_available
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }>
                        {stats?.kafka_available ? 'Kafka Available' : 'Kafka Not Installed'}
                    </Badge>
                    <span className="text-xs text-white/40">
                        {stats?.mode === 'mongodb_fallback'
                            ? 'Using MongoDB as event queue fallback. Install aiokafka for native Kafka support.'
                            : 'Connected to Kafka cluster.'
                        }
                    </span>
                </CardContent>
            </Card>
        </div>
    );
}
