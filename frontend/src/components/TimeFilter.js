import React, { useState, useEffect } from 'react';
import { Clock, Filter, Calendar } from 'lucide-react';
import { Input } from './ui/input';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

// Time filter options
export const TIME_FILTERS = [
    { label: 'Last 5 Minutes', value: '5m', hours: 0.083 },
    { label: 'Last 15 Minutes', value: '15m', hours: 0.25 },
    { label: 'Last 1 Hour', value: '1h', hours: 1 },
    { label: 'Last 6 Hours', value: '6h', hours: 6 },
    { label: 'Last 24 Hours', value: '24h', hours: 24 },
    { label: 'Last 7 Days', value: '7d', hours: 168 },
    { label: 'Custom', value: 'custom', hours: null },
];

// Format timestamp helper
export const formatTimestamp = (timestamp) => {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    });
};

export const formatRelativeTime = (timestamp) => {
    if (!timestamp) return '--';
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    return `${diffDay}d ago`;
};

export const getTimeFilterHours = (timeFilter) => {
    const filter = TIME_FILTERS.find(f => f.value === timeFilter);
    return filter?.hours || 24;
};

// Global Timestamp Header Component
export const GlobalTimestampHeader = ({ 
    timeFilter, 
    setTimeFilter, 
    customStartDate,
    setCustomStartDate,
    customEndDate,
    setCustomEndDate,
    showCustomDatePicker,
    setShowCustomDatePicker 
}) => {
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const handleTimeFilterChange = (value) => {
        setTimeFilter(value);
        if (value === 'custom') {
            setShowCustomDatePicker(true);
        } else {
            setShowCustomDatePicker(false);
        }
    };

    return (
        <div className="flex items-center justify-between bg-[#0a0a0a] border border-white/5 rounded-sm p-3 mb-6">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-cyan-400" />
                    <span className="font-mono text-sm text-white/70">Current Time:</span>
                    <span className="font-mono text-sm text-white" data-testid="current-timestamp">
                        {currentTime.toLocaleString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                            hour12: false,
                        })} UTC
                    </span>
                </div>
            </div>
            <div className="flex items-center gap-3">
                <Filter className="w-4 h-4 text-white/50" />
                <Select value={timeFilter} onValueChange={handleTimeFilterChange}>
                    <SelectTrigger className="w-[180px] bg-black/50 border-white/10 rounded-sm text-white text-xs" data-testid="time-filter-select">
                        <SelectValue placeholder="Select time range" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0a0a0a] border-white/10">
                        {TIME_FILTERS.map((filter) => (
                            <SelectItem key={filter.value} value={filter.value}>
                                {filter.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {showCustomDatePicker && (
                    <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-white/50" />
                        <Input
                            type="datetime-local"
                            value={customStartDate}
                            onChange={(e) => setCustomStartDate(e.target.value)}
                            className="bg-black/50 border-white/10 rounded-sm text-white text-xs w-[180px]"
                            data-testid="custom-start-date"
                        />
                        <span className="text-white/50">to</span>
                        <Input
                            type="datetime-local"
                            value={customEndDate}
                            onChange={(e) => setCustomEndDate(e.target.value)}
                            className="bg-black/50 border-white/10 rounded-sm text-white text-xs w-[180px]"
                            data-testid="custom-end-date"
                        />
                    </div>
                )}
            </div>
        </div>
    );
};
