import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
    Brain,
    Sparkles,
    AlertTriangle,
    CheckCircle,
    Clock,
    TrendingUp,
    Shield,
    Zap,
    RefreshCw,
    ChevronDown,
    ChevronUp,
    Target,
    Lightbulb,
    Activity,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const AIInsightsPanel = ({ incident, analysis, onAnalyze, isAnalyzing }) => {
    const [expanded, setExpanded] = useState(true);
    const [activeTab, setActiveTab] = useState('summary');

    if (!incident) return null;

    // Support both new format (with success flag) and old flat format
    const hasAnalysis = analysis && (analysis.success || analysis.root_cause);
    const investigation = analysis?.investigation || analysis?.full_report || {};
    
    // Handle old flat format - map to expected structure
    const rcaAnalysis = investigation.root_cause_analysis || {
        primary_cause: analysis?.root_cause,
        confidence_score: analysis?.confidence_score,
        evidence: analysis?.investigation_steps?.slice(0, 3),
        timeline: [],
        contributing_factors: []
    };
    const recommendations = investigation.recommendations || {
        immediate_actions: analysis?.suggested_actions?.slice(0, 3),
        short_term_fixes: analysis?.suggested_actions?.slice(3, 5),
        long_term_prevention: []
    };
    const riskAssessment = investigation.risk_assessment || {
        current_risk: analysis?.risk_level,
        escalation_needed: analysis?.escalation_needed,
        estimated_resolution: analysis?.estimated_resolution_time
    };

    const getConfidenceColor = (score) => {
        if (score >= 80) return 'text-green-400';
        if (score >= 60) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getRiskColor = (risk) => {
        switch (risk?.toLowerCase()) {
            case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30';
            case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
            case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30';
            default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    return (
        <Card className="bg-gradient-to-br from-purple-500/5 via-cyan-500/5 to-transparent border-purple-500/20 rounded-sm overflow-hidden">
            <CardHeader className="pb-2 border-b border-white/5">
                <div className="flex items-center justify-between">
                    <CardTitle className="font-heading text-sm font-bold uppercase tracking-wider flex items-center gap-2">
                        <Brain className="w-5 h-5 text-purple-400" />
                        <span className="text-white">AI Insights</span>
                        <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 text-[10px] uppercase">
                            GPT-5.2
                        </Badge>
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        {!hasAnalysis && (
                            <Button
                                onClick={onAnalyze}
                                disabled={isAnalyzing}
                                size="sm"
                                className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 border border-purple-500/30 rounded-sm"
                            >
                                {isAnalyzing ? (
                                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Sparkles className="w-4 h-4 mr-2" />
                                )}
                                {isAnalyzing ? 'Analyzing...' : 'Run AI Analysis'}
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpanded(!expanded)}
                            className="text-white/50 hover:text-white"
                        >
                            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                    >
                        <CardContent className="pt-4">
                            {!hasAnalysis ? (
                                <div className="text-center py-8">
                                    <Brain className="w-12 h-12 text-purple-400/30 mx-auto mb-4" />
                                    <p className="text-white/50 text-sm">
                                        Click "Run AI Analysis" to get intelligent insights about this incident
                                    </p>
                                    <p className="text-white/30 text-xs mt-2">
                                        AI will analyze patterns, identify root causes, and suggest remediation steps
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {/* Tab Navigation */}
                                    <div className="flex gap-2 border-b border-white/5 pb-2">
                                        {['summary', 'rca', 'actions', 'timeline'].map((tab) => (
                                            <button
                                                key={tab}
                                                onClick={() => setActiveTab(tab)}
                                                className={`px-3 py-1.5 text-xs uppercase tracking-wider font-mono rounded-sm transition-colors ${
                                                    activeTab === tab
                                                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                                                        : 'text-white/50 hover:text-white hover:bg-white/5'
                                                }`}
                                            >
                                                {tab}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Summary Tab */}
                                    {activeTab === 'summary' && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            {/* Executive Summary */}
                                            {(investigation.executive_summary || analysis?.impact_assessment) && (
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Lightbulb className="w-4 h-4 text-primary" />
                                                        <span className="text-xs text-white/50 uppercase tracking-wider font-mono">Executive Summary</span>
                                                    </div>
                                                    <p className="text-white/80 text-sm leading-relaxed">
                                                        {investigation.executive_summary || analysis?.impact_assessment}
                                                    </p>
                                                </div>
                                            )}

                                            {/* Risk Assessment */}
                                            <div className="grid grid-cols-3 gap-3">
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="text-xs text-white/50 uppercase tracking-wider font-mono mb-1">Current Risk</div>
                                                    <Badge className={`${getRiskColor(riskAssessment.current_risk)} text-sm px-2 py-0.5`}>
                                                        {riskAssessment.current_risk || 'Unknown'}
                                                    </Badge>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="text-xs text-white/50 uppercase tracking-wider font-mono mb-1">Confidence</div>
                                                    <span className={`text-lg font-bold ${getConfidenceColor(rcaAnalysis.confidence_score || 0)}`}>
                                                        {rcaAnalysis.confidence_score || 0}%
                                                    </span>
                                                </div>
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="text-xs text-white/50 uppercase tracking-wider font-mono mb-1">Est. Resolution</div>
                                                    <span className="text-white/80 text-sm">
                                                        {riskAssessment.estimated_resolution || 'N/A'}
                                                    </span>
                                                </div>
                                            </div>
                                        </motion.div>
                                    )}

                                    {/* RCA Tab */}
                                    {activeTab === 'rca' && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            {/* Primary Cause */}
                                            <div className="p-3 bg-red-500/10 rounded-sm border border-red-500/20">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <Target className="w-4 h-4 text-red-400" />
                                                    <span className="text-xs text-red-400 uppercase tracking-wider font-mono">Root Cause</span>
                                                </div>
                                                <p className="text-white font-medium">
                                                    {rcaAnalysis.primary_cause || 'Analysis in progress...'}
                                                </p>
                                            </div>

                                            {/* Evidence */}
                                            {rcaAnalysis.evidence && rcaAnalysis.evidence.length > 0 && (
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Shield className="w-4 h-4 text-cyan-400" />
                                                        <span className="text-xs text-white/50 uppercase tracking-wider font-mono">Evidence</span>
                                                    </div>
                                                    <ul className="space-y-1">
                                                        {rcaAnalysis.evidence.map((item, i) => (
                                                            <li key={i} className="text-white/70 text-sm flex items-start gap-2">
                                                                <CheckCircle className="w-3 h-3 text-cyan-400 mt-1 flex-shrink-0" />
                                                                {item}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* Contributing Factors */}
                                            {rcaAnalysis.contributing_factors && rcaAnalysis.contributing_factors.length > 0 && (
                                                <div className="p-3 bg-white/5 rounded-sm border border-white/10">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <AlertTriangle className="w-4 h-4 text-yellow-400" />
                                                        <span className="text-xs text-white/50 uppercase tracking-wider font-mono">Contributing Factors</span>
                                                    </div>
                                                    <ul className="space-y-1">
                                                        {rcaAnalysis.contributing_factors.map((factor, i) => (
                                                            <li key={i} className="text-white/70 text-sm flex items-start gap-2">
                                                                <Zap className="w-3 h-3 text-yellow-400 mt-1 flex-shrink-0" />
                                                                {factor}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </motion.div>
                                    )}

                                    {/* Actions Tab */}
                                    {activeTab === 'actions' && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            {/* Immediate Actions */}
                                            {recommendations.immediate_actions && recommendations.immediate_actions.length > 0 && (
                                                <div className="p-3 bg-red-500/10 rounded-sm border border-red-500/20">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Zap className="w-4 h-4 text-red-400" />
                                                        <span className="text-xs text-red-400 uppercase tracking-wider font-mono">Immediate Actions</span>
                                                    </div>
                                                    <ul className="space-y-2">
                                                        {recommendations.immediate_actions.map((action, i) => (
                                                            <li key={i} className="text-white/80 text-sm flex items-start gap-2 p-2 bg-red-500/5 rounded-sm">
                                                                <span className="text-red-400 font-mono text-xs">{i + 1}.</span>
                                                                {action}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* Short-term Fixes */}
                                            {recommendations.short_term_fixes && recommendations.short_term_fixes.length > 0 && (
                                                <div className="p-3 bg-yellow-500/10 rounded-sm border border-yellow-500/20">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Clock className="w-4 h-4 text-yellow-400" />
                                                        <span className="text-xs text-yellow-400 uppercase tracking-wider font-mono">Short-term Fixes</span>
                                                    </div>
                                                    <ul className="space-y-1">
                                                        {recommendations.short_term_fixes.map((fix, i) => (
                                                            <li key={i} className="text-white/70 text-sm flex items-start gap-2">
                                                                <TrendingUp className="w-3 h-3 text-yellow-400 mt-1 flex-shrink-0" />
                                                                {fix}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* Long-term Prevention */}
                                            {recommendations.long_term_prevention && recommendations.long_term_prevention.length > 0 && (
                                                <div className="p-3 bg-green-500/10 rounded-sm border border-green-500/20">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <Shield className="w-4 h-4 text-green-400" />
                                                        <span className="text-xs text-green-400 uppercase tracking-wider font-mono">Long-term Prevention</span>
                                                    </div>
                                                    <ul className="space-y-1">
                                                        {recommendations.long_term_prevention.map((item, i) => (
                                                            <li key={i} className="text-white/70 text-sm flex items-start gap-2">
                                                                <CheckCircle className="w-3 h-3 text-green-400 mt-1 flex-shrink-0" />
                                                                {item}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </motion.div>
                                    )}

                                    {/* Timeline Tab */}
                                    {activeTab === 'timeline' && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            {rcaAnalysis.timeline && rcaAnalysis.timeline.length > 0 ? (
                                                <div className="relative pl-4 border-l-2 border-cyan-500/30 space-y-4">
                                                    {rcaAnalysis.timeline.map((event, i) => (
                                                        <div key={i} className="relative">
                                                            <div className="absolute -left-[21px] w-3 h-3 bg-cyan-500 rounded-full border-2 border-[#0a0a0a]" />
                                                            <div className="p-3 bg-white/5 rounded-sm border border-white/10 ml-2">
                                                                <div className="flex items-center gap-2 mb-1">
                                                                    <Activity className="w-3 h-3 text-cyan-400" />
                                                                    <span className="text-xs text-cyan-400 font-mono">Event {i + 1}</span>
                                                                </div>
                                                                <p className="text-white/80 text-sm">{event}</p>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="text-center py-8 text-white/50 text-sm">
                                                    No timeline data available
                                                </div>
                                            )}
                                        </motion.div>
                                    )}

                                    {/* Analysis Timestamp */}
                                    <div className="pt-2 border-t border-white/5">
                                        <p className="text-white/30 text-xs font-mono">
                                            Analysis generated: {analysis?.timestamp ? new Date(analysis.timestamp).toLocaleString() : 'N/A'}
                                        </p>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </motion.div>
                )}
            </AnimatePresence>
        </Card>
    );
};

export default AIInsightsPanel;
