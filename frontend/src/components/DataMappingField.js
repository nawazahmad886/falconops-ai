import React from 'react';
import { Input } from './ui/input';
import { Label } from './ui/label';

/**
 * A single input-field-to-{{template}} mapping row. `upstreamNodeIds` just
 * powers a plain-text hint (autocomplete-by-typing) — the actual resolution
 * happens server-side in expression_evaluator.py's dot-path lookup, never
 * client-side.
 */
export const DataMappingField = ({ fieldName, value, onChange, upstreamNodeIds = [] }) => (
    <div className="space-y-1">
        <Label className="text-xs text-white/60">{fieldName}</Label>
        <Input
            className="h-8 text-xs bg-muted/50 font-mono"
            placeholder="{{trigger.service}} or a literal value"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            list={`upstream-nodes-${fieldName}`}
        />
        <datalist id={`upstream-nodes-${fieldName}`}>
            {upstreamNodeIds.map((id) => <option key={id} value={`{{${id}.output.}}`} />)}
        </datalist>
    </div>
);

export default DataMappingField;
