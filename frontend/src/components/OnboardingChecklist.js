import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { CheckCircle2, Circle, X, Rocket } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

/**
 * Real, backend-driven "getting started" checklist for tenants that haven't
 * finished basic setup yet — every step's done/not-done state is a genuine
 * count against that tenant's own data (see onboarding_service.py), not a
 * scripted sequence. Renders nothing once every step is done or the user has
 * dismissed it.
 */
export function OnboardingChecklist() {
    const [status, setStatus] = useState(null);
    const [dismissing, setDismissing] = useState(false);

    useEffect(() => {
        let cancelled = false;
        fetch(`${API}/api/onboarding/status`, { headers: authHeaders() })
            .then((r) => (r.ok ? r.json() : null))
            .then((data) => { if (!cancelled) setStatus(data); })
            .catch(() => {});
        return () => { cancelled = true; };
    }, []);

    if (!status || !status.should_show) return null;

    const handleDismiss = async () => {
        setDismissing(true);
        try {
            await fetch(`${API}/api/onboarding/dismiss`, { method: 'POST', headers: authHeaders() });
        } catch (e) { /* non-critical */ }
        setStatus((s) => ({ ...s, should_show: false }));
    };

    const doneCount = status.steps.filter((s) => s.done).length;

    return (
        <Card className="bg-gradient-to-br from-cyan-500/[0.06] via-black/40 to-black/40 border-cyan-500/20" data-testid="onboarding-checklist">
            <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <Rocket className="w-4 h-4 text-cyan-400" />
                        <span className="text-sm font-semibold text-white">Getting Started</span>
                        <span className="text-[11px] text-white/40">{doneCount}/{status.steps.length} complete</span>
                    </div>
                    <Button size="sm" variant="ghost" className="h-6 w-6 p-0" disabled={dismissing} onClick={handleDismiss} data-testid="dismiss-onboarding">
                        <X className="w-3.5 h-3.5 text-white/40" />
                    </Button>
                </div>
                <div className="mt-3 space-y-1.5">
                    {status.steps.map((step) => (
                        <Link
                            key={step.id}
                            to={step.action_path}
                            className="flex items-center gap-2 text-[13px] hover:bg-white/[0.03] rounded px-2 py-1.5 -mx-2 transition-colors"
                            data-testid={`onboarding-step-${step.id}`}
                        >
                            {step.done
                                ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                                : <Circle className="w-4 h-4 text-white/25 shrink-0" />}
                            <span className={step.done ? 'text-white/40 line-through' : 'text-white/80'}>{step.label}</span>
                        </Link>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}
