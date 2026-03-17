import { useState, useEffect } from 'react';

const STORAGE_KEY = 'qvc-theme';

export default function ThemeToggle() {
    const [theme, setTheme] = useState<'dark' | 'light'>(() => {
        return (localStorage.getItem(STORAGE_KEY) as 'dark' | 'light') || 'dark';
    });

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_KEY, theme);
    }, [theme]);

    const isDark = theme === 'dark';

    return (
        <label className="checkbox-label">
            <span>Dark mode</span>
            <input
                type="checkbox"
                className="settings-checkbox"
                checked={isDark}
                onChange={() => setTheme(isDark ? 'light' : 'dark')}
            />
        </label>
    );
}
