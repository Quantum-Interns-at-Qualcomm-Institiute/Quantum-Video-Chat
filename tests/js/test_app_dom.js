/**
 * @jest-environment jsdom
 */

/**
 * DOM rendering tests for app.js.
 *
 * Loads app.js into a jsdom environment and verifies that render()
 * produces the correct DOM structure for each UI state.
 */
import { describe, test, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP_JS_PATH = resolve(
  __dirname,
  '../../../../public/video-chat/js/app.js',
);

// Stub globals that app.js expects
function setupGlobals() {
  // Socket.IO stub
  globalThis.io = () => ({
    on: () => {},
    emit: () => {},
    disconnect: () => {},
    connected: false,
  });

  // navigator.mediaDevices stub
  Object.defineProperty(globalThis.navigator, 'mediaDevices', {
    value: {
      getUserMedia: () =>
        Promise.resolve({
          getTracks: () => [],
          getVideoTracks: () => [],
          getAudioTracks: () => [],
        }),
      enumerateDevices: () => Promise.resolve([]),
    },
    configurable: true,
  });

  // RTCPeerConnection stub
  globalThis.RTCPeerConnection = class {
    constructor() {
      this.onicecandidate = null;
      this.oniceconnectionstatechange = null;
      this.ontrack = null;
      this.ondatachannel = null;
      this.iceConnectionState = 'new';
    }
    addTrack() {}
    createOffer() { return Promise.resolve({ type: 'offer', sdp: '' }); }
    createAnswer() { return Promise.resolve({ type: 'answer', sdp: '' }); }
    setLocalDescription() { return Promise.resolve(); }
    setRemoteDescription() { return Promise.resolve(); }
    addIceCandidate() { return Promise.resolve(); }
    createDataChannel() {
      return { onopen: null, onmessage: null, onclose: null, close: () => {} };
    }
    close() {}
  };

  // Canvas context stub
  HTMLCanvasElement.prototype.getContext = function () {
    return {
      clearRect: () => {},
      fillRect: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      arc: () => {},
      stroke: () => {},
      fill: () => {},
      setLineDash: () => {},
      createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }),
      putImageData: () => {},
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
    };
  };

  // localStorage stub
  const store = {};
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
    configurable: true,
  });

  // requestAnimationFrame stub
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
}

/**
 * Load app.js into the current jsdom context.
 * Uses vm.runInThisContext so top-level var/function declarations
 * become properties of the global object (window).
 */
function loadApp() {
  let code = readFileSync(APP_JS_PATH, 'utf-8');
  // Convert top-level const/let to var so they become function-scoped
  // and accessible via our return object.
  // Only match lines at column 0 (top-level declarations).
  code = code.replace(/^(const|let) /gm, 'var ');
  // Execute inside a function that has access to window/document via jsdom.
  // Use `with(window)` is not available in strict mode, so instead we
  // execute the code as a script via the Function constructor which
  // inherits the jsdom global scope.
  const script = new Function(code + `
    return {
      state, render, toggleCamera, toggleMute, createRoom,
      leaveSession, showToast, dismissToast, formatTime, handleJoin,
    };
  `);
  return script();
}

describe('App DOM Rendering', () => {
  let app;

  beforeEach(() => {
    document.body.innerHTML = '<div id="app" class="main-screen"></div>';
    document.documentElement.setAttribute('data-theme', 'dark');
    setupGlobals();
    app = loadApp();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Lobby view (not in call)', () => {
    test('renders lobby when not connected', () => {
      app.state.connected = false;
      app.state.roomId = '';
      app.render();

      expect(document.querySelector('.lobby')).not.toBeNull();
      expect(document.querySelector('.lobby-title').textContent).toBe('QKD Video Chat');
    });

    test('join button is disabled when not connected', () => {
      app.state.connected = false;
      app.render();

      const joinBtn = document.querySelector('.lobby-btn[type="submit"]');
      expect(joinBtn.disabled).toBe(true);
    });

    test('join button is enabled when connected', () => {
      app.state.connected = true;
      app.render();

      const joinBtn = document.querySelector('.lobby-btn[type="submit"]');
      expect(joinBtn.disabled).toBe(false);
    });

    test('start session button is disabled when not connected', () => {
      app.state.connected = false;
      app.render();

      const startBtn = document.querySelector('.lobby-start-btn');
      expect(startBtn.disabled).toBe(true);
    });

    test('start session button is enabled when connected', () => {
      app.state.connected = true;
      app.render();

      const startBtn = document.querySelector('.lobby-start-btn');
      expect(startBtn.disabled).toBe(false);
    });

    test('shows waiting spinner when waitingForPeer', () => {
      app.state.connected = true;
      app.state.waitingForPeer = true;
      app.state.roomId = 'ABC12';
      app.render();

      const waiting = document.querySelector('.lobby-waiting');
      expect(waiting).not.toBeNull();
      expect(waiting.textContent).toContain('Waiting for peer');
      expect(waiting.textContent).toContain('ABC12');
    });

    test('shows self-video element', () => {
      app.state.connected = true;
      app.render();

      const selfVideo = document.getElementById('self-video');
      expect(selfVideo).not.toBeNull();
      expect(selfVideo.tagName).toBe('VIDEO');
    });

    test('shows noise canvas when camera is off', () => {
      app.state.connected = true;
      app.state.cameraOn = false;
      app.render();

      const noise = document.getElementById('noise-canvas');
      expect(noise).not.toBeNull();
      expect(document.querySelector('.noise-label').textContent).toBe('Camera Off');
    });

    test('shows connection status dot', () => {
      app.state.connected = true;
      app.render();

      const dot = document.querySelector('.conn-dot');
      expect(dot).not.toBeNull();
      expect(dot.classList.contains('conn-dot--ok')).toBe(true);
    });

    test('shows disconnected status dot when not connected', () => {
      app.state.connected = false;
      app.render();

      const dot = document.querySelector('.conn-dot');
      expect(dot.classList.contains('conn-dot--off')).toBe(true);
    });

    test('state label shows "ready" when connected', () => {
      app.state.connected = true;
      app.render();

      const label = document.querySelector('.conn-state');
      expect(label.textContent).toBe('ready');
    });

    test('state label shows "disconnected" when not connected', () => {
      app.state.connected = false;
      app.render();

      const label = document.querySelector('.conn-state');
      expect(label.textContent).toBe('disconnected');
    });

    test('media toggle buttons render correctly', () => {
      app.state.connected = true;
      app.state.cameraOn = true;
      app.state.muted = false;
      app.render();

      const mediaBtns = document.querySelectorAll('.lobby-media-btn');
      expect(mediaBtns.length).toBe(2);
      // Neither should have the --off modifier
      expect(mediaBtns[0].classList.contains('lobby-media-btn--off')).toBe(false);
      expect(mediaBtns[1].classList.contains('lobby-media-btn--off')).toBe(false);
    });

    test('camera off button has --off class', () => {
      app.state.connected = true;
      app.state.cameraOn = false;
      app.render();

      const cameraBtns = document.querySelectorAll('.lobby-media-btn');
      // First button is camera
      expect(cameraBtns[0].classList.contains('lobby-media-btn--off')).toBe(true);
    });

    test('muted button has --off class', () => {
      app.state.connected = true;
      app.state.muted = true;
      app.render();

      const mediaBtns = document.querySelectorAll('.lobby-media-btn');
      // Second button is mic
      expect(mediaBtns[1].classList.contains('lobby-media-btn--off')).toBe(true);
    });
  });

  describe('In-call view', () => {
    beforeEach(() => {
      app.state.connected = true;
      app.state.roomId = 'XYZ99';
      app.state.waitingForPeer = false;
      app.state.peerConnected = true;
    });

    test('renders incall view when in a room', () => {
      app.render();

      expect(document.querySelector('.incall')).not.toBeNull();
      expect(document.querySelector('.lobby')).toBeNull();
    });

    test('shows room code', () => {
      app.render();

      const roomLabel = document.querySelector('.incall-room');
      expect(roomLabel.textContent).toContain('XYZ99');
    });

    test('shows peer-video element', () => {
      app.render();

      const peerVideo = document.getElementById('peer-video');
      expect(peerVideo).not.toBeNull();
      expect(peerVideo.tagName).toBe('VIDEO');
    });

    test('shows self-video PIP element', () => {
      app.render();

      const selfVideo = document.getElementById('self-video');
      expect(selfVideo).not.toBeNull();
      expect(selfVideo.closest('.incall-pip')).not.toBeNull();
    });

    test('shows elapsed timer', () => {
      app.state.elapsed = 65;
      app.render();

      const timer = document.getElementById('elapsed-timer');
      expect(timer.textContent).toBe('01:05');
    });

    test('shows toolbar with camera, mic, and leave buttons', () => {
      app.render();

      const toolbar = document.querySelector('.incall-toolbar');
      expect(toolbar).not.toBeNull();

      const toolBtns = document.querySelectorAll('.incall-tool-btn');
      expect(toolBtns.length).toBe(2); // camera + mic

      const leaveBtn = document.querySelector('.incall-leave-btn');
      expect(leaveBtn).not.toBeNull();
    });

    test('camera off shows --off class on toolbar button', () => {
      app.state.cameraOn = false;
      app.render();

      const toolBtns = document.querySelectorAll('.incall-tool-btn');
      expect(toolBtns[0].classList.contains('incall-tool-btn--off')).toBe(true);
    });

    test('muted shows --off class on toolbar button', () => {
      app.state.muted = true;
      app.render();

      const toolBtns = document.querySelectorAll('.incall-tool-btn');
      expect(toolBtns[1].classList.contains('incall-tool-btn--off')).toBe(true);
    });

    test('shows quantum panel', () => {
      app.render();

      const panel = document.getElementById('quantum-panel');
      expect(panel).not.toBeNull();
    });

    test('quantum panel shows pending message when BB84 not active', () => {
      app.state.bb84Active = false;
      app.render();

      const panel = document.getElementById('quantum-panel');
      expect(panel.textContent).toContain('Encryption pending');
    });

    test('quantum panel shows QBER when BB84 is active', () => {
      app.state.bb84Active = true;
      app.state.qber = 0.035;
      app.state.qberEvent = 'normal';
      app.state.qberHistory = [{ qber: 0.035, time: Date.now() }];
      app.render();

      const panel = document.getElementById('quantum-panel');
      expect(panel.textContent).toContain('3.50%');
      expect(panel.textContent).toContain('QBER');
      expect(panel.textContent).toContain('Secure');
    });
  });

  describe('State transitions', () => {
    test('lobby → waiting → in-call → lobby lifecycle', () => {
      // Start in lobby
      app.state.connected = true;
      app.render();
      expect(document.querySelector('.lobby')).not.toBeNull();
      expect(document.querySelector('.incall')).toBeNull();

      // Create room → waiting
      app.state.waitingForPeer = true;
      app.state.roomId = 'ABC12';
      app.render();
      expect(document.querySelector('.lobby')).not.toBeNull();
      expect(document.querySelector('.lobby-waiting')).not.toBeNull();

      // Peer joins → in-call
      app.state.waitingForPeer = false;
      app.state.peerConnected = true;
      app.render();
      expect(document.querySelector('.incall')).not.toBeNull();
      expect(document.querySelector('.lobby')).toBeNull();

      // Leave → lobby
      app.state.roomId = '';
      app.state.peerConnected = false;
      app.render();
      expect(document.querySelector('.lobby')).not.toBeNull();
      expect(document.querySelector('.incall')).toBeNull();
    });
  });

  describe('Utility functions', () => {
    test('formatTime formats seconds correctly', () => {
      expect(app.formatTime(0)).toBe('00:00');
      expect(app.formatTime(59)).toBe('00:59');
      expect(app.formatTime(60)).toBe('01:00');
      expect(app.formatTime(3661)).toBe('61:01');
    });
  });

  describe('Toast notifications', () => {
    test('showToast makes toast visible', () => {
      app.render();
      app.showToast('Test message');

      const toast = document.getElementById('toast');
      expect(toast.classList.contains('toast--visible')).toBe(true);
      expect(document.getElementById('toast-msg').textContent).toBe('Test message');
    });

    test('dismissToast hides toast', () => {
      app.render();
      app.showToast('Test');
      app.dismissToast();

      const toast = document.getElementById('toast');
      expect(toast.classList.contains('toast--hidden')).toBe(true);
    });
  });
});
