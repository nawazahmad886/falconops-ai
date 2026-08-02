import React, { createContext, useContext, useEffect, useState } from 'react';

const ThemeContext = createContext(null);

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};

const STORAGE_KEY = 'falconTheme';

/**
 * Infrastructure only: toggles a `light` class on <html> (dark stays the
 * default — <html> with no class — matching this app's actual look today, so
 * shipping this cannot regress current appearance for anyone who never opens
 * the toggle). Real effect is currently limited to the ~22/46 shadcn
 * components/ui/* primitives that consume the CSS custom-property tokens in
 * index.css (card, dialog, dropdown-menu, popover, etc.) — most pages use
 * hardcoded dark literal classNames (bg-black/40, bg-[#0B0E14], text-white,
 * ...) directly, thousands of occurrences across the app, and will not
 * change appearance until migrated to token-based classes in a later pass.
 */
export const ThemeProvider = ({ children }) => {
    const [theme, setThemeState] = useState(() => localStorage.getItem(STORAGE_KEY) || 'dark');

    useEffect(() => {
        document.documentElement.classList.toggle('light', theme === 'light');
    }, [theme]);

    const setTheme = (next) => {
        setThemeState(next);
        localStorage.setItem(STORAGE_KEY, next);
    };

    const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

    return (
        <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};
