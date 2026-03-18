import { useState, useEffect } from 'react';
import './Settings.css';

const STORAGE_KEY = 'qvc-settings';

export interface AppSettings {
  darkMode: boolean;
  muted: boolean;
  hideCamera: boolean;
}

const defaults: AppSettings = {
  darkMode: true,
  muted: false,
  hideCamera: false,
};

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaults, ...JSON.parse(raw) };
  } catch (_) { /* ignore */ }
  return { ...defaults };
}

function saveSettings(s: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

interface SettingsProps {
  onClose: () => void;
}

export default function Settings({ onClose }: SettingsProps) {
  const [settings, setSettings] = useState<AppSettings>(loadSettings);

  // Persist whenever settings change
  useEffect(() => {
    saveSettings(settings);
    document.documentElement.setAttribute('data-theme', settings.darkMode ? 'dark' : 'light');
  }, [settings]);

  const toggle = (key: keyof AppSettings) =>
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>Settings</h2>
          <button className="settings-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="settings-body">
          <ToggleRow
            label="Dark Mode"
            checked={settings.darkMode}
            onChange={() => toggle('darkMode')}
          />
          <ToggleRow
            label="Mute Microphone"
            checked={settings.muted}
            onChange={() => toggle('muted')}
          />
          <ToggleRow
            label="Hide Camera by Default"
            checked={settings.hideCamera}
            onChange={() => toggle('hideCamera')}
          />
        </div>
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="settings-row">
      <span className="settings-label">{label}</span>
      <div
        className={`settings-toggle ${checked ? 'on' : 'off'}`}
        onClick={onChange}
        role="switch"
        aria-checked={checked}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onChange()}
      >
        <div className="settings-toggle-knob" />
      </div>
    </label>
  );
}
