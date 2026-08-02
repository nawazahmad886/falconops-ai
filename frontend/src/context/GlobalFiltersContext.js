import React, { createContext, useContext, useState } from 'react';

const GlobalFiltersContext = createContext(null);

export const useGlobalFilters = () => {
    const context = useContext(GlobalFiltersContext);
    if (!context) {
        throw new Error('useGlobalFilters must be used within a GlobalFiltersProvider');
    }
    return context;
};

// Owns the global time range / timezone / refresh interval / environment state
// above <AppRoutes/> so it survives navigation. Previously this state lived
// inside EnterpriseLayout.js, which is re-instantiated by a fresh
// <ProtectedRoute> element tree on every route match (this app has no shared
// <Outlet/> layout route) — so it silently reset on every navigation despite
// looking "persistent" because the same component type rendered each time.
export const GlobalFiltersProvider = ({ children }) => {
    const [timeRange, setTimeRange] = useState('1h');
    const [environment, setEnvironment] = useState('all');
    // { start, end } as raw datetime-local strings — browser-local wall-clock
    // time, not timezone-aware. `timezone` below only affects how returned
    // timestamps are *displayed*, never how this input is interpreted.
    const [customRange, setCustomRange] = useState({ start: '', end: '' });
    // 'browser' | 'UTC' | an IANA zone name (e.g. 'Asia/Riyadh'). No 'server'
    // option — no backend timezone concept exists to back one; every stored/
    // returned timestamp is a UTC ISO string regardless of this setting.
    const [timezone, setTimezone] = useState('browser');
    // 'off' | milliseconds
    const [refreshInterval, setRefreshInterval] = useState('off');

    const value = {
        timeRange, setTimeRange,
        environment, setEnvironment,
        customRange, setCustomRange,
        timezone, setTimezone,
        refreshInterval, setRefreshInterval,
    };

    return <GlobalFiltersContext.Provider value={value}>{children}</GlobalFiltersContext.Provider>;
};
