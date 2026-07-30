import React from 'react';

// Bespoke mark for the Agentic AI Workflow module — a central Supervisor hub
// routing to four specialist agents (Copilot/Diagnoser/Forecaster/Blast-Radius),
// same "custom SVG, not a stock icon" treatment as FalconLogo.js elsewhere in this app.
export const AgenticWorkflowLogo = ({ size = 40, className = '' }) => {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={className}
        >
            <defs>
                <linearGradient id="awGrad" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#22D3EE" />
                    <stop offset="100%" stopColor="#D946EF" />
                </linearGradient>
                <radialGradient id="awGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#22D3EE" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
                </radialGradient>
            </defs>

            {/* Connection lines from the Supervisor hub to each satellite agent */}
            <g stroke="url(#awGrad)" strokeWidth="1.4" opacity="0.85">
                <line x1="32" y1="32" x2="32" y2="12" />
                <line x1="32" y1="32" x2="50" y2="24" />
                <line x1="32" y1="32" x2="50" y2="44" />
                <line x1="32" y1="32" x2="14" y2="44" />
                <line x1="32" y1="32" x2="14" y2="24" />
            </g>

            {/* Satellite agent nodes */}
            <g fill="url(#awGrad)">
                <circle cx="32" cy="12" r="4.5" />
                <circle cx="50" cy="24" r="4" />
                <circle cx="50" cy="44" r="4" />
                <circle cx="14" cy="44" r="4" />
                <circle cx="14" cy="24" r="4" />
            </g>

            {/* Supervisor hub — glow + solid core */}
            <circle cx="32" cy="32" r="14" fill="url(#awGlow)" />
            <circle cx="32" cy="32" r="8" fill="#0B0F14" stroke="url(#awGrad)" strokeWidth="1.5" />
            <circle cx="32" cy="32" r="3.5" fill="#22D3EE" />
        </svg>
    );
};

export const AgenticWorkflowLogoFull = ({ className = '' }) => (
    <div className={`flex items-center gap-3 ${className}`}>
        <AgenticWorkflowLogo size={40} />
        <span className="font-heading font-semibold text-lg tracking-wide flex items-baseline gap-1.5">
            <span className="bg-gradient-to-r from-cyan-400 to-fuchsia-400 bg-clip-text text-transparent">Agentic</span>
            <span className="text-white">AI Workflow</span>
        </span>
    </div>
);

export default AgenticWorkflowLogo;
