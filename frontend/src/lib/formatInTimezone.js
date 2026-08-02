// Formats an ISO timestamp in the given zone. `timezone` is the value from
// GlobalFiltersContext: 'browser' (native local formatting, no IANA zone
// passed to Intl) or any IANA zone name (e.g. 'UTC', 'Asia/Riyadh'). Uses the
// native Intl.DateTimeFormat — no new dependency (date-fns v4 has no built-in
// IANA timezone formatting).
export function formatInTimezone(isoString, timezone = 'browser', options = {}) {
    if (!isoString) return '--';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '--';

    const intlOptions = {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
        ...options,
    };
    if (timezone && timezone !== 'browser') {
        intlOptions.timeZone = timezone;
    }

    try {
        return new Intl.DateTimeFormat('en-US', intlOptions).format(date);
    } catch (e) {
        // Unknown/invalid IANA zone string — fall back to browser-local
        // rather than throwing and blanking the whole page.
        return new Intl.DateTimeFormat('en-US', { ...intlOptions, timeZone: undefined }).format(date);
    }
}

// Short zone label suitable for appending to a formatted timestamp, e.g. "14:32 UTC".
export function timezoneLabel(timezone) {
    if (!timezone || timezone === 'browser') {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    }
    return timezone;
}
