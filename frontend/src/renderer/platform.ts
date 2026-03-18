/**
 * platform.ts — Transport abstraction layer
 *
 * Provides a browser-native implementation for settings and IPC-like
 * communication via localStorage and a simple event bus.
 */

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type SettingsData = Record<string, Record<string, string | number | boolean>>;

export type IpcCallback = (event: unknown, ...args: unknown[]) => void;

export interface PlatformAPI {
  ipcListen:         (eventName: string, callback: IpcCallback) => void;
  ipcRemoveListener: (eventName: string) => void;
  rendererReady:     () => void;
  setPeerId:         (peerId: string) => void;
  disconnect:        () => void;
  toggleMute:        () => void;
  getSettings:       () => Promise<SettingsData>;
  saveSettings:      (settings: SettingsData) => Promise<void>;
  getDefaults:       () => Promise<SettingsData>;
}

// ---------------------------------------------------------------------------
// Default settings
// ---------------------------------------------------------------------------

const SETTINGS_DEFAULTS: SettingsData = {
  network: {
    middleware_port:        5001,
    server_rest_port:       5050,
    server_websocket_port:  3000,
    client_api_port:        4000,
  },
  video: {
    video_width:    640,
    video_height:   480,
    display_width:  960,
    display_height: 720,
    frame_rate:     15,
  },
  audio: {
    sample_rate:      8196,
    audio_wait:       0.125,
    mute_by_default:  false,
  },
  encryption: {
    key_length:      128,
    encrypt_scheme:  'AES',
    key_generator:   'FILE',
  },
  debug: {
    video_enabled: false,
  },
};

// ---------------------------------------------------------------------------
// Browser implementation
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'qvc-settings';

/** Minimal event bus used to simulate IPC in a plain browser. */
const _listeners = new Map<string, IpcCallback>();

const platform: PlatformAPI = {
  ipcListen(eventName, callback) {
    _listeners.set(eventName, callback);
  },
  ipcRemoveListener(eventName) {
    _listeners.delete(eventName);
  },
  rendererReady() { /* no-op — no main process to signal */ },
  setPeerId()     { /* no-op */ },
  disconnect()    { /* no-op */ },
  toggleMute()    { /* no-op */ },

  getSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as SettingsData;
        // Merge with defaults so new keys added later are always present.
        const merged: SettingsData = {};
        for (const section of Object.keys(SETTINGS_DEFAULTS)) {
          merged[section] = { ...SETTINGS_DEFAULTS[section], ...(saved[section] ?? {}) };
        }
        return Promise.resolve(merged);
      }
    } catch { /* fall through to defaults */ }
    return Promise.resolve(JSON.parse(JSON.stringify(SETTINGS_DEFAULTS)));
  },

  saveSettings(settings) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch { /* storage unavailable — silently ignore */ }
    return Promise.resolve();
  },

  getDefaults() {
    return Promise.resolve(JSON.parse(JSON.stringify(SETTINGS_DEFAULTS)));
  },
};

export default platform;
