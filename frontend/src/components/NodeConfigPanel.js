import React from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { X } from 'lucide-react';
import { ConditionBuilder } from './ConditionBuilder';
import { DataMappingField } from './DataMappingField';
import { NODE_TYPE_ICON } from './WorkflowCanvasEditor';

const AGENT_TYPES = new Set(['agent', 'planner', 'ai_decision', 'synthesizer', 'judge']);
const TOOL_TYPES = new Set([
    'data_elasticsearch', 'data_apm', 'data_sql', 'data_metrics', 'data_logs', 'data_http', 'data_rag_search', 'data_memory',
    'action_restart_pod', 'action_scale_service', 'action_create_ticket', 'action_send_email', 'action_send_teams',
    'action_send_slack', 'action_create_incident', 'health_check', 'slo_check',
]);

/**
 * Side panel bound to the selected node. Dispatches on node.data.nodeType
 * to the right config fields rather than a separate file per node type —
 * the field SET differs by type, but the underlying form primitives
 * (agent/tool picker, condition builder, data-mapping row) are shared.
 */
export const NodeConfigPanel = ({ node, upstreamNodeIds, agentCatalog, toolCatalog, onChange, onClose }) => {
    if (!node) return null;
    const nodeType = node.data.nodeType;
    const config = node.data.config || {};
    const dataMapping = node.data.data_mapping || {};
    const Icon = NODE_TYPE_ICON[nodeType];

    const setConfig = (patch) => onChange({ config: { ...config, ...patch } });
    const setLabel = (label) => onChange({ label });
    const setMapping = (field, value) => onChange({ data_mapping: { ...dataMapping, [field]: value } });

    return (
        <div className="w-80 shrink-0 border-l border-white/10 bg-[#0D1117] p-4 space-y-4 overflow-y-auto" data-testid="node-config-panel">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {Icon && <Icon className="w-4 h-4 text-white/70" />}
                    <span className="text-sm font-semibold text-white">{nodeType}</span>
                </div>
                <Button size="icon" variant="ghost" onClick={onClose}><X className="w-4 h-4" /></Button>
            </div>

            <div className="space-y-1">
                <Label className="text-xs text-white/60">Label</Label>
                <Input className="h-8 text-xs bg-muted/50" value={node.data.label || ''} onChange={(e) => setLabel(e.target.value)} />
            </div>

            {AGENT_TYPES.has(nodeType) && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Agent</Label>
                    <Select value={config.agent_id || ''} onValueChange={(v) => setConfig({ agent_id: v })}>
                        <SelectTrigger className="h-8 text-xs bg-muted/50"><SelectValue placeholder="Select agent..." /></SelectTrigger>
                        <SelectContent>
                            {(agentCatalog || []).map((a) => (
                                <SelectItem key={a.agent_id} value={a.agent_id}>
                                    {a.name}{a.is_rased_wrapper ? ' (RASED)' : ''}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}

            {TOOL_TYPES.has(nodeType) && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Tool</Label>
                    <Select value={config.tool_id || ''} onValueChange={(v) => setConfig({ tool_id: v })}>
                        <SelectTrigger className="h-8 text-xs bg-muted/50"><SelectValue placeholder="Select tool..." /></SelectTrigger>
                        <SelectContent>
                            {(toolCatalog || []).map((t) => (
                                <SelectItem key={t.tool_id} value={t.tool_id}>{t.name} ({t.risk_tier})</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {!config.tool_id && (
                        <p className="text-[10px] text-amber-400/80">No tool bound — this node will fail at execution time until configured.</p>
                    )}
                </div>
            )}

            {(nodeType === 'condition') && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Condition</Label>
                    <ConditionBuilder value={config.condition} onChange={(c) => setConfig({ condition: c })} />
                </div>
            )}

            {nodeType === 'switch' && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Cases (value : condition)</Label>
                    {(config.cases || []).map((c, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                            <Input className="h-8 w-20 text-xs bg-muted/50" placeholder="value" value={c.value || ''}
                                onChange={(e) => { const next = [...config.cases]; next[idx] = { ...c, value: e.target.value }; setConfig({ cases: next }); }} />
                            <div className="flex-1"><ConditionBuilder value={c.condition} onChange={(cond) => { const next = [...config.cases]; next[idx] = { ...c, condition: cond }; setConfig({ cases: next }); }} /></div>
                        </div>
                    ))}
                    <Button size="sm" variant="outline" className="h-7 text-xs"
                        onClick={() => setConfig({ cases: [...(config.cases || []), { value: '', condition: { op: '==', left: '', right: '' } }] })}>
                        + Case
                    </Button>
                </div>
            )}

            {nodeType === 'loop' && (
                <div className="space-y-2">
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Body node IDs (comma-separated)</Label>
                        <Input className="h-8 text-xs bg-muted/50" value={(config.body_node_ids || []).join(',')}
                            onChange={(e) => setConfig({ body_node_ids: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Max iterations (hard cap 25)</Label>
                        <Input type="number" className="h-8 text-xs bg-muted/50" value={config.max_iterations ?? 3}
                            onChange={(e) => setConfig({ max_iterations: Number(e.target.value) })} />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Termination condition</Label>
                        <ConditionBuilder value={config.termination_condition} onChange={(c) => setConfig({ termination_condition: c })} />
                    </div>
                </div>
            )}

            {nodeType === 'wait' && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Seconds (capped at 300)</Label>
                    <Input type="number" className="h-8 text-xs bg-muted/50" value={config.seconds ?? 5}
                        onChange={(e) => setConfig({ seconds: Number(e.target.value) })} />
                </div>
            )}

            {nodeType === 'human_approval' && (
                <div className="space-y-2">
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Title</Label>
                        <Input className="h-8 text-xs bg-muted/50" value={config.title || ''} onChange={(e) => setConfig({ title: e.target.value })} />
                    </div>
                    <div className="space-y-1">
                        <Label className="text-xs text-white/60">Risk tier</Label>
                        <Select value={config.risk_tier || 'GUARDED'} onValueChange={(v) => setConfig({ risk_tier: v })}>
                            <SelectTrigger className="h-8 text-xs bg-muted/50"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                {['SAFE', 'GUARDED', 'DESTRUCTIVE'].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>
                    <p className="text-[10px] text-white/40">Approve/reject requires 'remediation.approve_destructive' by default — the same permission RASED's own DESTRUCTIVE-tier actions require.</p>
                </div>
            )}

            {nodeType === 'risk_check' && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Block at or above</Label>
                    <Select value={config.block_at_or_above || 'DESTRUCTIVE'} onValueChange={(v) => setConfig({ block_at_or_above: v })}>
                        <SelectTrigger className="h-8 text-xs bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            {['SAFE', 'GUARDED', 'DESTRUCTIVE'].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                        </SelectContent>
                    </Select>
                </div>
            )}

            {nodeType === 'permission_check' && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Required permission</Label>
                    <Input className="h-8 text-xs bg-muted/50" placeholder="e.g. remediation.approve_destructive"
                        value={config.required_permission || ''} onChange={(e) => setConfig({ required_permission: e.target.value })} />
                </div>
            )}

            {nodeType === 'action_run_workflow' && (
                <div className="space-y-1">
                    <Label className="text-xs text-white/60">Sub-workflow ID</Label>
                    <Input className="h-8 text-xs bg-muted/50" value={config.workflow_id || ''} onChange={(e) => setConfig({ workflow_id: e.target.value })} />
                </div>
            )}

            <div className="space-y-2 border-t border-white/10 pt-3">
                <Label className="text-xs text-white/60">Retry (optional)</Label>
                <div className="flex gap-1">
                    <Input type="number" placeholder="max attempts" className="h-8 text-xs bg-muted/50"
                        value={config.retry?.max_attempts ?? ''} onChange={(e) => setConfig({ retry: { ...(config.retry || {}), max_attempts: Number(e.target.value) || undefined } })} />
                    <Input type="number" placeholder="backoff (s)" className="h-8 text-xs bg-muted/50"
                        value={config.retry?.backoff_seconds ?? ''} onChange={(e) => setConfig({ retry: { ...(config.retry || {}), backoff_seconds: Number(e.target.value) || undefined } })} />
                </div>
                <Label className="text-xs text-white/60">Timeout seconds (optional)</Label>
                <Input type="number" className="h-8 text-xs bg-muted/50" value={config.timeout_seconds ?? ''}
                    onChange={(e) => setConfig({ timeout_seconds: Number(e.target.value) || undefined })} />
            </div>

            {upstreamNodeIds?.length > 0 && (
                <div className="space-y-2 border-t border-white/10 pt-3">
                    <Label className="text-xs text-white/60">Data Mapping</Label>
                    <p className="text-[10px] text-white/40">Maps upstream node outputs into this node's input, e.g. service = {'{{trigger.service}}'}</p>
                    <DataMappingField fieldName="service" value={dataMapping.service} onChange={(v) => setMapping('service', v)} upstreamNodeIds={upstreamNodeIds} />
                    <DataMappingField fieldName="query" value={dataMapping.query} onChange={(v) => setMapping('query', v)} upstreamNodeIds={upstreamNodeIds} />
                </div>
            )}
        </div>
    );
};

export default NodeConfigPanel;
