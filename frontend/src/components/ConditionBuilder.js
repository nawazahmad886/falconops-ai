import React from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Trash2 } from 'lucide-react';

const COMPARATORS = ['>', '<', '>=', '<=', '==', '!=', 'contains', 'not_contains'];

/**
 * Produces the structured condition JSON the backend's
 * services/workflow/expression_evaluator.py consumes:
 *   {op: 'AND'|'OR'|'NOT', terms: [...]}
 *   {op: '>'|'<'|...|'contains', left, right}
 * Never emits a free-text expression string — that's the point.
 */
export const ConditionBuilder = ({ value, onChange }) => {
    const condition = value || { op: '==', left: '', right: '' };
    const isGroup = condition.op === 'AND' || condition.op === 'OR' || condition.op === 'NOT';

    const setOp = (op) => {
        if (op === 'AND' || op === 'OR' || op === 'NOT') {
            onChange({ op, terms: condition.terms || [{ op: '==', left: '', right: '' }] });
        } else {
            onChange({ op, left: condition.left || '', right: condition.right || '' });
        }
    };

    if (isGroup) {
        const terms = condition.terms || [];
        return (
            <div className="space-y-2 border border-white/10 rounded-md p-2">
                <div className="flex items-center gap-2">
                    <Select value={condition.op} onValueChange={setOp}>
                        <SelectTrigger className="w-24 h-8 text-xs bg-muted/50"><SelectValue /></SelectTrigger>
                        <SelectContent>
                            {['AND', 'OR', 'NOT', '>', '<', '>=', '<=', '==', '!=', 'contains', 'not_contains'].map(o => (
                                <SelectItem key={o} value={o}>{o}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button size="sm" variant="outline" className="h-7 text-xs"
                        onClick={() => onChange({ ...condition, terms: [...terms, { op: '==', left: '', right: '' }] })}>
                        <Plus className="w-3 h-3 mr-1" />Term
                    </Button>
                </div>
                <div className="pl-3 space-y-2 border-l border-white/10">
                    {terms.map((term, idx) => (
                        <div key={idx} className="flex items-start gap-1">
                            <div className="flex-1"><ConditionBuilder value={term} onChange={(t) => {
                                const next = [...terms]; next[idx] = t; onChange({ ...condition, terms: next });
                            }} /></div>
                            <Button size="icon" variant="ghost" className="h-7 w-7 text-red-400"
                                onClick={() => onChange({ ...condition, terms: terms.filter((_, i) => i !== idx) })}>
                                <Trash2 className="w-3 h-3" />
                            </Button>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="flex items-center gap-1.5">
            <Input className="h-8 text-xs bg-muted/50" placeholder="{{node_id.output.field}}"
                value={condition.left || ''} onChange={(e) => onChange({ ...condition, left: e.target.value })} />
            <Select value={condition.op} onValueChange={setOp}>
                <SelectTrigger className="w-28 h-8 text-xs bg-muted/50"><SelectValue /></SelectTrigger>
                <SelectContent>
                    {['AND', 'OR', 'NOT', ...COMPARATORS].map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                </SelectContent>
            </Select>
            <Input className="h-8 text-xs bg-muted/50" placeholder="value or {{...}}"
                value={condition.right ?? ''} onChange={(e) => onChange({ ...condition, right: e.target.value })} />
        </div>
    );
};

export default ConditionBuilder;
