import { useGlobalFilters } from '../context/GlobalFiltersContext';

// Mirrors EnterpriseLayout.js's TIME_RANGES value set exactly (5m/15m/1h/6h/
// 24h/7d/30d/custom) — kept here rather than imported to avoid a layout->hook
// dependency; if TIME_RANGES ever changes, update both.
const RANGE_HOURS = {
    '5m': 5 / 60,
    '15m': 15 / 60,
    '1h': 1,
    '6h': 6,
    '24h': 24,
    '7d': 24 * 7,
    '30d': 24 * 30,
};

/**
 * Reads the global timeRange/customRange and returns a ready-to-use window:
 * { hours, startTime, endTime, isCustom }. hours is always a whole number
 * (ceil'd) for endpoints that take an hour count; startTime/endTime are UTC
 * ISO strings for endpoints that take an explicit window.
 *
 * Replaces each page's own ad-hoc time-range state/math. Also fixes a
 * pre-existing bug: the old TimeFilter.js TIME_FILTERS' 'custom' entry has
 * hours: null, so getTimeFilterHours('custom') silently fell back to 24h in
 * every one of its consumers — "Custom Range" never actually worked before.
 */
export function useTimeRangeParams() {
    const { timeRange, customRange } = useGlobalFilters();

    const isCustom = timeRange === 'custom';
    const now = new Date();

    if (isCustom && customRange.start && customRange.end) {
        const start = new Date(customRange.start);
        const end = new Date(customRange.end);
        const hours = Math.max(1, Math.ceil((end - start) / (1000 * 60 * 60)));
        return { hours, startTime: start.toISOString(), endTime: end.toISOString(), isCustom: true };
    }

    // Custom selected but no range entered yet (or invalid) — honest 24h
    // fallback, same default every other range effectively has, not a silent
    // wrong-but-plausible-looking custom window.
    const hours = isCustom ? 24 : (RANGE_HOURS[timeRange] || 24);
    const start = new Date(now.getTime() - hours * 60 * 60 * 1000);
    return {
        hours: Math.max(1, Math.ceil(hours)),
        startTime: start.toISOString(),
        endTime: now.toISOString(),
        isCustom,
    };
}
