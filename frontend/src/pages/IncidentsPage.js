import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '../components/ui/dialog';
import { toast } from 'sonner';
import {
    AlertTriangle,
    Brain,
    CheckCircle2,
    Clock,
    RefreshCw,
    ChevronRight,
    Sparkles,
    Target,
    Lightbulb,
    TrendingUp,
    AlertCircle,
} from 'lucide-react';
import { AIInsightsPanel } from '../components/AIInsightsPanel';
import AIOpsDiagnosePanel from '../components/AIOpsDiagnosePanel';
import { Brain as BrainIcon } from 'lucide-react';

const severityColors = {
    critical: 'bg-destructive text-destructive-foreground',
    warning: 'bg-warning text-black',
    info: 'bg-info text-white',
};

const statusColors = {
    open: 'border-destructive text-destructive',
    investigating: 'border-warning text-warning',
    resolved: 'border-success text-success',
};

export const IncidentsPage = () => {
    const { api } = useAuth();
    const [incidents, setIncidents] = useState([]);
    const [selectedIncident, setSelectedIncident] = useState(null);
    const [loading, setLoading] = useState(true);
    const [analyzing, setAnalyzing] = useState(false);
    const [correlating, setCorrelating] = useState(false);
    const [correlationStats, setCorrelationStats] = useState(null);
    const [diagnoseService, setDiagnoseService] = useState(null);

    const fetchIncidents = async () => {
        setLoading(true);
        try {
            const [incidentsRes, statsRes] = await Promise.all([
                api.get('/incidents?limit=50'),
                api.get('/incidents/correlation-stats').catch(() => ({ data: null }))
            ]);
            setIncidents(incidentsRes.data);
            if (statsRes.data) {
                setCorrelationStats(statsRes.data);
            }
        } catch (error) {
            toast.error('Failed to fetch incidents');
        } finally {
            setLoading(false);
        }
    };

    const handleSmartCorrelate = async () => {
        setCorrelating(true);
        try {
            const response = await api.post('/incidents/smart-correlate');
            if (response.data.incidents_created > 0) {
                toast.success(`Smart correlation created ${response.data.incidents_created} incident(s)`);
            } else {
                toast.info('No new incidents to create from current alerts');
            }
            fetchIncidents();
        } catch (error) {
            toast.error('Failed to run smart correlation');
        } finally {
            setCorrelating(false);
        }
    };

    useEffect(() => {
        fetchIncidents();
    }, []);

    const handleStatusChange = async (incidentId, newStatus) => {
        try {
            await api.patch(`/incidents/${incidentId}/status?status=${newStatus}`);
            toast.success(`Incident marked as ${newStatus}`);
            fetchIncidents();
            if (selectedIncident?.id === incidentId) {
                setSelectedIncident({ ...selectedIncident, status: newStatus });
            }
        } catch (error) {
            toast.error('Failed to update incident status');
        }
    };

    const handleTriggerAnalysis = async (incidentId) => {
        setAnalyzing(true);
        try {
            await api.post(`/incidents/${incidentId}/analyze`);
            toast.success('AI analysis triggered. Results will appear shortly.');
            // Poll for results
            setTimeout(async () => {
                const res = await api.get(`/incidents/${incidentId}`);
                setSelectedIncident(res.data);
                setAnalyzing(false);
            }, 5000);
        } catch (error) {
            toast.error('Failed to trigger AI analysis');
            setAnalyzing(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const formatMTTR = (seconds) => {
        if (!seconds) return '--';
        if (seconds < 60) return `${Math.round(seconds)} seconds`;
        if (seconds < 3600) return `${Math.round(seconds / 60)} minutes`;
        return `${(seconds / 3600).toFixed(1)} hours`;
    };

    return (
        <>
            <div className="space-y-6" data-testid="incidents-page">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 className="font-heading font-semibold text-2xl md:text-3xl flex items-center gap-2">
                            <AlertTriangle className="w-7 h-7 text-warning" />
                            Incidents
                        </h1>
                        <p className="text-muted-foreground text-sm">AI-correlated incident clusters with root cause analysis</p>
                        {correlationStats && (
                            <p className="text-xs text-muted-foreground mt-1">
                                {correlationStats.correlation_rules_count} correlation rules active • {correlationStats.total_incidents} total incidents
                            </p>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <Button 
                            onClick={handleSmartCorrelate} 
                            variant="default" 
                            size="sm" 
                            disabled={correlating}
                            data-testid="smart-correlate-btn"
                            className="bg-primary hover:bg-primary/90"
                        >
                            {correlating ? (
                                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Brain className="w-4 h-4 mr-2" />
                            )}
                            Smart Correlate
                        </Button>
                        <Button onClick={fetchIncidents} variant="outline" size="sm" data-testid="refresh-incidents-btn">
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>
                </div>

                {/* Incidents List */}
                <div className="grid gap-4">
                    {loading ? (
                        <div className="flex items-center justify-center py-20">
                            <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                        </div>
                    ) : incidents.length === 0 ? (
                        <Card className="bg-card/50 border-border/40">
                            <CardContent className="py-20 text-center text-muted-foreground">
                                <CheckCircle2 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p className="text-lg font-medium">No incidents</p>
                                <p className="text-sm">Incidents are automatically created when correlated alerts are detected</p>
                            </CardContent>
                        </Card>
                    ) : (
                        incidents.map((incident) => (
                            <Card 
                                key={incident.id} 
                                className={`bg-card/50 border-border/40 hover:border-primary/30 transition-colors cursor-pointer ${
                                    incident.status === 'open' ? 'border-l-4 border-l-destructive' :
                                    incident.status === 'investigating' ? 'border-l-4 border-l-warning' : ''
                                }`}
                                onClick={() => setSelectedIncident(incident)}
                                data-testid={`incident-${incident.id}`}
                            >
                                <CardContent className="p-4">
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Badge className={severityColors[incident.severity]}>
                                                    {incident.severity}
                                                </Badge>
                                                <Badge variant="outline" className={statusColors[incident.status]}>
                                                    {incident.status}
                                                </Badge>
                                                {incident.ai_analysis && (
                                                    <Badge variant="outline" className="border-primary text-primary">
                                                        <Brain className="w-3 h-3 mr-1" />
                                                        AI Analyzed
                                                    </Badge>
                                                )}
                                            </div>
                                            <h3 className="font-medium text-lg mb-1 truncate">{incident.title}</h3>
                                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                                <span className="font-mono">{incident.service}</span>
                                                <span>•</span>
                                                <span>{incident.alert_count} alerts</span>
                                                <span>•</span>
                                                <span className="flex items-center gap-1">
                                                    <Clock className="w-3 h-3" />
                                                    {formatDate(incident.created_at)}
                                                </span>
                                            </div>
                                            {incident.root_cause && (
                                                <p className="mt-2 text-sm text-muted-foreground line-clamp-1">
                                                    <strong className="text-foreground">Root Cause:</strong> {incident.root_cause}
                                                </p>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                                            {incident.service && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => setDiagnoseService(incident.service)}
                                                    className="bg-violet-500/[0.08] hover:bg-violet-500/[0.16] border border-violet-500/30 text-violet-200 text-[11px] h-7 px-2"
                                                    data-testid={`diagnose-incident-${incident.id}`}
                                                    title={`AI Diagnose ${incident.service}`}
                                                >
                                                    <BrainIcon className="w-3.5 h-3.5 mr-1" />
                                                    Diagnose
                                                </Button>
                                            )}
                                            <ChevronRight className="w-5 h-5 text-muted-foreground" />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </div>

                {/* AI Diagnose Panel (renders when user clicks Diagnose on any incident) */}
                {diagnoseService && (
                    <AIOpsDiagnosePanel
                        service={diagnoseService}
                        hours={24}
                        onClose={() => setDiagnoseService(null)}
                    />
                )}

                {/* Incident Detail Dialog */}
                <Dialog open={!!selectedIncident} onOpenChange={() => setSelectedIncident(null)}>
                    <DialogContent className="max-w-3xl max-h-[90vh] bg-card border-border">
                        {selectedIncident && (
                            <>
                                <DialogHeader>
                                    <DialogTitle className="font-heading text-xl flex items-center gap-2">
                                        <AlertTriangle className="w-5 h-5 text-warning" />
                                        Incident Details
                                    </DialogTitle>
                                </DialogHeader>
                                <ScrollArea className="max-h-[70vh] pr-4">
                                    <div className="space-y-6">
                                        {/* Header Info */}
                                        <div>
                                            <div className="flex items-center gap-2 mb-3">
                                                <Badge className={severityColors[selectedIncident.severity]}>
                                                    {selectedIncident.severity}
                                                </Badge>
                                                <Badge variant="outline" className={statusColors[selectedIncident.status]}>
                                                    {selectedIncident.status}
                                                </Badge>
                                            </div>
                                            <h2 className="text-lg font-medium mb-2">{selectedIncident.title}</h2>
                                            <div className="grid grid-cols-2 gap-4 text-sm">
                                                <div>
                                                    <p className="text-muted-foreground">Service</p>
                                                    <p className="font-mono">{selectedIncident.service}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">Alert Count</p>
                                                    <p>{selectedIncident.alert_count}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">Created</p>
                                                    <p>{formatDate(selectedIncident.created_at)}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">MTTR</p>
                                                    <p>{formatMTTR(selectedIncident.mttr_seconds)}</p>
                                                </div>
                                            </div>
                                        </div>

                                        <Separator className="bg-border/40" />

                                        {/* AI Insights Panel */}
                                        <AIInsightsPanel
                                            incident={selectedIncident}
                                            analysis={selectedIncident.ai_analysis}
                                            onAnalyze={() => handleTriggerAnalysis(selectedIncident.id)}
                                            isAnalyzing={analyzing}
                                        />

                                        <Separator className="bg-border/40" />

                                        {/* Actions */}
                                        <div className="flex items-center gap-3">
                                            {selectedIncident.status !== 'investigating' && selectedIncident.status !== 'resolved' && (
                                                <Button
                                                    variant="outline"
                                                    onClick={() => handleStatusChange(selectedIncident.id, 'investigating')}
                                                    data-testid="mark-investigating"
                                                >
                                                    <AlertCircle className="w-4 h-4 mr-2" />
                                                    Mark Investigating
                                                </Button>
                                            )}
                                            {selectedIncident.status !== 'resolved' && (
                                                <Button
                                                    onClick={() => handleStatusChange(selectedIncident.id, 'resolved')}
                                                    data-testid="resolve-incident"
                                                >
                                                    <CheckCircle2 className="w-4 h-4 mr-2" />
                                                    Resolve Incident
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </ScrollArea>
                            </>
                        )}
                    </DialogContent>
                </Dialog>
            </div>
        </>
    );
};
