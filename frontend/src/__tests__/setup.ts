/**
 * Global test setup — mocks browser APIs not available in jsdom.
 */

// Default settings for mocks
const mockDefaults = {
  network: {
    electron_ipc_port: 5001,
    server_rest_port: 5050,
    server_websocket_port: 3000,
    client_api_port: 4000,
  },
  video: {
    video_width: 640,
    video_height: 480,
    display_width: 960,
    display_height: 720,
    frame_rate: 15,
  },
  audio: {
    sample_rate: 8196,
    audio_wait: 0.125,
    mute_by_default: false,
  },
  encryption: {
    key_length: 128,
    encrypt_scheme: 'AES',
    key_generator: 'FILE',
  },
  debug: {
    video_enabled: false,
  },
};

// Mock window.electronAPI (exposed via preload.ts contextBridge)
Object.defineProperty(window, 'electronAPI', {
  value: {
    setPeerId: jest.fn(),
    ipcListen: jest.fn(),
    ipcRemoveListener: jest.fn(),
    rendererReady: jest.fn(),
    disconnect: jest.fn(),
    toggleMute: jest.fn(),
    getSettings: jest.fn().mockResolvedValue(mockDefaults),
    saveSettings: jest.fn().mockResolvedValue({ ok: true }),
    getDefaults: jest.fn().mockResolvedValue(mockDefaults),
  },
  writable: true,
});

// Mock HTMLCanvasElement.getContext (jsdom doesn't provide canvas 2d context)
HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue({
  createImageData: jest.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
  putImageData: jest.fn(),
  getImageData: jest.fn().mockReturnValue({ data: new Uint8ClampedArray(4) }),
  drawImage: jest.fn(),
  clearRect: jest.fn(),
  fillRect: jest.fn(),
  fillText: jest.fn(),
  measureText: jest.fn().mockReturnValue({ width: 0 }),
  canvas: { width: 0, height: 0 },
}) as any;

// Mock navigator.mediaDevices.getUserMedia
Object.defineProperty(navigator, 'mediaDevices', {
  value: {
    getUserMedia: jest.fn().mockResolvedValue({
      getTracks: () => [{ stop: jest.fn() }],
    }),
  },
  writable: true,
});
