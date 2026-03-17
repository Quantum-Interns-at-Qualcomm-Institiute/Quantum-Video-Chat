/**
 * platform.ts — Transport abstraction layer
 *
 * Components import from this module instead of touching `window.electronAPI`
 * directly.  When running inside Electron the real IPC bridge is used.  When
 * running in a plain browser (dev preview, tests) a lightweight browser-native
 * implementation is used instead so no Electron dependency is required.
 */

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type SettingsData = Record<string, Record<string, string | number | boolean>>;

/** Callback signature used by ipcListen — mirrors Electron's IpcRendererEvent shape. */
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
// Default settings (mirrors SETTINGS_DEFAULTS in main/main.ts)
// ---------------------------------------------------------------------------

const SETTINGS_DEFAULTS: SettingsData = {
  network: {
    electron_ipc_port:      5001,
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

const browserPlatform: PlatformAPI = {
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

// ---------------------------------------------------------------------------
// Electron implementation (thin wrapper over the contextBridge global)
// ---------------------------------------------------------------------------

const electronPlatform: PlatformAPI = {
  ipcListen:         (e, cb)  => window.electronAPI.ipcListen(e, cb),
  ipcRemoveListener: (e)      => window.electronAPI.ipcRemoveListener(e),
  rendererReady:     ()       => window.electronAPI.rendererReady(),
  setPeerId:         (id)     => window.electronAPI.setPeerId(id),
  disconnect:        ()       => window.electronAPI.disconnect(),
  toggleMute:        ()       => window.electronAPI.toggleMute(),
  getSettings:       ()       => window.electronAPI.getSettings(),
  saveSettings:      (s)      => window.electronAPI.saveSettings(s),
  getDefaults:       ()       => window.electronAPI.getDefaults(),
};

// ---------------------------------------------------------------------------
// Export the right implementation for the current runtime
// ---------------------------------------------------------------------------

const platform: PlatformAPI =
  typeof window !== 'undefined' && window.electronAPI
    ? electronPlatform
    : browserPlatform;

export default platform;
