import React from 'react';

export const FalconLogo = ({ size = 40, className = '' }) => {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={className}
        >
            {/* Shield outline (subtle) */}
            <path
                d="M32 4L8 14V30C8 44.36 18.08 57.36 32 61C45.92 57.36 56 44.36 56 30V14L32 4Z"
                stroke="rgba(255,255,255,0.1)"
                strokeWidth="1"
                fill="none"
            />
            
            {/* Falcon head - geometric angular design */}
            <g>
                {/* Main head shape */}
                <path
                    d="M32 12L22 24L24 32L32 28L40 32L42 24L32 12Z"
                    fill="#F5B841"
                    opacity="0.9"
                />
                
                {/* Beak */}
                <path
                    d="M32 28L28 36L32 42L36 36L32 28Z"
                    fill="#F5B841"
                />
                
                {/* Left eye */}
                <circle cx="27" cy="22" r="2" fill="#0B0F14" />
                <circle cx="27.5" cy="21.5" r="0.8" fill="#00E0FF" />
                
                {/* Right eye */}
                <circle cx="37" cy="22" r="2" fill="#0B0F14" />
                <circle cx="36.5" cy="21.5" r="0.8" fill="#00E0FF" />
                
                {/* Left wing with circuit pattern */}
                <path
                    d="M22 24L12 32L14 44L24 38L24 32L22 24Z"
                    fill="#F5B841"
                    opacity="0.7"
                />
                
                {/* Right wing with circuit pattern */}
                <path
                    d="M42 24L52 32L50 44L40 38L40 32L42 24Z"
                    fill="#F5B841"
                    opacity="0.7"
                />
                
                {/* AI Circuit patterns - Left wing */}
                <g stroke="#00E0FF" strokeWidth="1" opacity="0.8">
                    <line x1="16" y1="34" x2="20" y2="34" />
                    <line x1="20" y1="34" x2="20" y2="38" />
                    <circle cx="16" cy="34" r="1.5" fill="#00E0FF" />
                    <circle cx="20" cy="38" r="1" fill="#00E0FF" />
                    <line x1="14" y1="40" x2="18" y2="36" />
                    <circle cx="14" cy="40" r="1" fill="#00E0FF" />
                </g>
                
                {/* AI Circuit patterns - Right wing */}
                <g stroke="#00E0FF" strokeWidth="1" opacity="0.8">
                    <line x1="48" y1="34" x2="44" y2="34" />
                    <line x1="44" y1="34" x2="44" y2="38" />
                    <circle cx="48" cy="34" r="1.5" fill="#00E0FF" />
                    <circle cx="44" cy="38" r="1" fill="#00E0FF" />
                    <line x1="50" y1="40" x2="46" y2="36" />
                    <circle cx="50" cy="40" r="1" fill="#00E0FF" />
                </g>
                
                {/* Center chest circuit */}
                <g stroke="#00E0FF" strokeWidth="0.8" opacity="0.6">
                    <line x1="32" y1="44" x2="32" y2="50" />
                    <line x1="28" y1="48" x2="36" y2="48" />
                    <circle cx="32" cy="50" r="1.5" fill="#00E0FF" />
                    <circle cx="28" cy="48" r="1" fill="#00E0FF" />
                    <circle cx="36" cy="48" r="1" fill="#00E0FF" />
                </g>
            </g>
        </svg>
    );
};

export const FalconLogoFull = ({ className = '' }) => {
    return (
        <div className={`flex items-center gap-3 ${className}`}>
            <FalconLogo size={40} />
            <span className="font-heading font-semibold text-lg tracking-wide flex items-baseline gap-0.5">
                <span className="text-[#F5B841]">FALCON</span>
                <span className="text-white">OPS</span>
                <span className="text-[#00E0FF] text-sm ml-1">AI</span>
            </span>
        </div>
    );
};

export const FalconLogoCompact = ({ size = 32, className = '' }) => {
    return (
        <div className={`flex items-center justify-center ${className}`}>
            <FalconLogo size={size} />
        </div>
    );
};

export default FalconLogo;
