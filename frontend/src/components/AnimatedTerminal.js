import React, { useEffect, useState, useRef } from 'react';
import { CheckCircle2 } from 'lucide-react';

/**
 * Animated terminal demo — auto-types a sequence of lines, then settles.
 * Pure CSS + React state — no extra deps.
 *
 * Props:
 *   lines: [{ prompt: '$', text: '...', delayMs?: number, classify?: 'cmd'|'log'|'ok'|'err' }]
 *   loop: boolean — restart from top after a pause (default true)
 *   typingSpeedMs: ms per character (default 18)
 *   pauseBetweenLinesMs: ms pause after each line (default 280)
 *   onComplete: optional callback when full sequence is done
 */
export default function AnimatedTerminal({
    lines = [],
    loop = true,
    typingSpeedMs = 18,
    pauseBetweenLinesMs = 280,
    onComplete,
}) {
    const [lineIdx, setLineIdx] = useState(0);
    const [charIdx, setCharIdx] = useState(0);
    const [doneLines, setDoneLines] = useState([]);
    const timerRef = useRef(null);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (lineIdx >= lines.length) {
            if (onComplete) onComplete();
            if (loop) {
                timerRef.current = setTimeout(() => {
                    setLineIdx(0);
                    setCharIdx(0);
                    setDoneLines([]);
                }, 2400);
            }
            return () => clearTimeout(timerRef.current);
        }
        const cur = lines[lineIdx];
        const text = cur.text || '';
        if (charIdx < text.length) {
            timerRef.current = setTimeout(
                () => setCharIdx(charIdx + 1),
                cur.delayMs || typingSpeedMs
            );
        } else {
            timerRef.current = setTimeout(() => {
                setDoneLines((prev) => [...prev, cur]);
                setLineIdx(lineIdx + 1);
                setCharIdx(0);
            }, cur.pauseAfterMs || pauseBetweenLinesMs);
        }
        return () => clearTimeout(timerRef.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lineIdx, charIdx, lines]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [doneLines, charIdx]);

    const classColor = (c) => {
        switch (c) {
            case 'cmd': return 'text-white/90';
            case 'log': return 'text-white/55';
            case 'ok':  return 'text-emerald-300';
            case 'err': return 'text-red-300';
            case 'info': return 'text-cyan-300';
            default: return 'text-white/70';
        }
    };

    const renderLine = (l, key, isLive) => {
        const text = isLive ? l.text.slice(0, charIdx) : l.text;
        return (
            <div key={key} className="flex items-start gap-2 leading-relaxed">
                {l.prompt && (
                    <span className="text-cyan-400 select-none shrink-0">{l.prompt}</span>
                )}
                <span className={classColor(l.classify || 'log')}>
                    {text}
                    {isLive && <span className="inline-block w-2 h-3.5 bg-cyan-300/70 ml-0.5 animate-pulse" />}
                </span>
                {!isLive && l.classify === 'ok' && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 ml-1 mt-0.5 shrink-0" />
                )}
            </div>
        );
    };

    return (
        <div className="rounded-xl border border-white/10 bg-black/80 shadow-2xl overflow-hidden" data-testid="animated-terminal">
            {/* Mac-style window chrome */}
            <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900 border-b border-white/10">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                <span className="ml-2 text-[10px] uppercase tracking-widest text-white/40 font-mono">
                    falconops apm shell
                </span>
            </div>
            <div
                ref={scrollRef}
                className="px-4 py-4 font-mono text-[12.5px] min-h-[280px] max-h-[420px] overflow-y-auto space-y-1.5"
                style={{
                    backgroundImage: 'radial-gradient(circle at 30% 0%, rgba(6,182,212,0.07), transparent 60%)',
                }}
            >
                {doneLines.map((l, i) => renderLine(l, `d-${i}`, false))}
                {lineIdx < lines.length && renderLine(lines[lineIdx], 'live', true)}
            </div>
        </div>
    );
}
