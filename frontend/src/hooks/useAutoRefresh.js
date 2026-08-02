import { useEffect, useRef } from 'react';
import { useGlobalFilters } from '../context/GlobalFiltersContext';

/**
 * Calls `callback` on the globally-selected refresh interval (from the header's
 * Refresh Interval selector). No-ops when the interval is 'off'. Pages that
 * already have their own push mechanism (e.g. ProblemsPage.js's WebSocket live
 * feed) should NOT use this — layering polling on top of a live feed is
 * redundant load, not a real freshness improvement.
 */
export function useAutoRefresh(callback) {
    const { refreshInterval } = useGlobalFilters();
    const callbackRef = useRef(callback);
    callbackRef.current = callback;

    useEffect(() => {
        if (refreshInterval === 'off') return undefined;
        const ms = Number(refreshInterval);
        if (!ms || Number.isNaN(ms)) return undefined;
        const id = setInterval(() => callbackRef.current(), ms);
        return () => clearInterval(id);
    }, [refreshInterval]);
}
