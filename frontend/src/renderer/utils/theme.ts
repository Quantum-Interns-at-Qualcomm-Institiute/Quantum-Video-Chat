/**
 * theme.ts — Centralised theme persistence and DOM management.
 *
 * All theme reads/writes go through this module instead of
 * scattering ``localStorage`` calls across components.
 */

const THEME_KEY = 'qvc-theme';
const LOGO_KEY = 'qvc-logo-visible';

export type Theme = 'dark' | 'light';

/** Read the stored theme preference, defaulting to 'dark'. */
export function getStoredTheme(): Theme {
  try {
    const val = localStorage.getItem(THEME_KEY);
    if (val === 'light') return 'light';
  } catch (_) { /* storage unavailable */ }
  return 'dark';
}

/** Persist the theme preference and apply it to the document root. */
export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (_) { /* storage unavailable */ }
}

/** Read the stored logo visibility preference, defaulting to true. */
export function getLogoVisible(): boolean {
  try {
    return localStorage.getItem(LOGO_KEY) !== 'false';
  } catch (_) { return true; }
}

/** Persist the logo visibility preference. */
export function setLogoVisible(visible: boolean): void {
  try {
    localStorage.setItem(LOGO_KEY, String(visible));
  } catch (_) { /* storage unavailable */ }
}
