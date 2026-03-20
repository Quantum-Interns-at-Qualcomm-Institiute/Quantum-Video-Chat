/**
 * QKD Video Chat — Vanilla JS frontend.
 *
 * Replaces the React app with a single-file JS frontend served by Flask.
 * Connects to the middleware Socket.IO server on the same origin.
 */

/* ── SVG Icons ──────────────────────────────────────────────────────────── */
const ICONS = {
  cameraOn: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><rect x="2" y="5" width="14" height="14"/><path d="M16 10l6-3v10l-6-3"/><circle cx="7" cy="9" r="1" fill="currentColor" stroke="none"/></svg>`,
  cameraOff: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><rect x="2" y="5" width="14" height="14"/><path d="M16 10l6-3v10l-6-3"/><line x1="2" y1="3" x2="22" y2="21" stroke-width="2"/></svg>`,
  micOn: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><rect x="8" y="2" width="8" height="12" rx="0"/><path d="M4 10v1a8 8 0 0016 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
  micOff: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><rect x="8" y="2" width="8" height="12" rx="0"/><path d="M4 10v1a8 8 0 0016 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/><line x1="2" y1="3" x2="22" y2="21" stroke-width="2"/></svg>`,
  phoneOff: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><path d="M10.68 13.31a16 16 0 003.41 2.6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 004.05.7 2 2 0 011.98 2v3.5a2 2 0 01-2.18 2A19.79 19.79 0 013.07 4.18 2 2 0 015.07 2H8.6a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L9.58 9.91"/><line x1="2" y1="2" x2="22" y2="22" stroke-width="2"/></svg>`,
  check: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square"><polyline points="20 6 9 17 4 12"/></svg>`,
  sun: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
  moon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/></svg>`,
  image: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"><rect x="3" y="3" width="18" height="18"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
};

/* ── State ──────────────────────────────────────────────────────────────── */
const state = {
  middlewareConnected: false,
  serverConnected: false,
  userId: '',
  roomId: '',
  waitingForPeer: false,
  cameraOn: true,
  muted: false,
  cameras: [],
  selectedCamera: 0,
  audioDevices: [],
  selectedAudio: 0,
  errorMessage: '',
  elapsed: 0,
  registrationEmitted: false,
  // BB84 quantum metrics
  qber: null,
  qberEvent: null,
  qberHistory: [],
  bb84Active: false,
  eavesdropperEnabled: false,
};

let elapsedInterval = null;
let noiseRaf = null;
let socket = null;

/* ── Backend Connect Widget ──────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  var el = document.getElementById('backend-connect');
  if (el && window.UIKit && UIKit.initConnect) {
    window.backendConnect = UIKit.initConnect(el, {
      service: 'qvc',
      defaultHost: 'localhost',
      defaultPort: 5002,
      label: 'Backend',
      onConnect: function(info) {
        // Reinit socket with new URL
        if (socket) { socket.disconnect(); }
        initSocket(info.url);
      }
    });
  }
});

/* ── Socket.IO ──────────────────────────────────────────────────────────── */
function initSocket(url) {
  socket = io(url || (typeof MIDDLEWARE_URL !== "undefined" ? MIDDLEWARE_URL : window.location.origin), {
    autoConnect: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 20,
  });

  socket.on('connect', () => {
    state.middlewareConnected = true;
    if (window.backendConnect) window.backendConnect.setStatus('connected');
    render();
  });

  socket.on('disconnect', () => {
    state.middlewareConnected = false;
    state.serverConnected = false;
    if (window.backendConnect) window.backendConnect.setStatus('disconnected');
    render();
  });

  socket.on('welcome', (cfg) => {
    state.middlewareConnected = true;
    state.registrationEmitted = false;
    if (cfg && cfg.host) {
      const hostEl = document.getElementById('server-host');
      const portEl = document.getElementById('server-port');
      if (hostEl) hostEl.value = cfg.host;
      if (portEl) portEl.value = cfg.port || 5050;
    }
    if (cfg && cfg.isLocal) {
      connectToServer(cfg.host, cfg.port);
    }
    render();
  });

  socket.on('server-connected', () => {
    state.serverConnected = true;
    state.errorMessage = '';
    if (!state.registrationEmitted) {
      state.registrationEmitted = true;
      socket.emit('create_user');
    }
    render();
  });

  socket.on('server-error', (msg) => {
    state.serverConnected = false;
    showToast(msg || 'Connection failed.');
    render();
  });

  socket.on('user-registered', (data) => {
    state.userId = data.user_id || data;
    render();
  });

  socket.on('waiting-for-peer', () => {
    state.waitingForPeer = true;
    render();
  });

  socket.on('room-id', (roomId) => {
    state.roomId = roomId;
    state.waitingForPeer = false;
    state.elapsed = 0;
    startElapsedTimer();
    render();
  });

  socket.on('peer-disconnected', () => {
    leaveSession();
    showToast('Peer disconnected.');
  });

  socket.on('frame', (data) => {
    if (data.self) {
      drawOnCanvas(document.getElementById('self-canvas'), data);
    } else {
      drawOnCanvas(document.getElementById('peer-canvas'), data);
    }
  });

  socket.on('audio-frame', () => {
    // Audio playback not yet implemented in browser
  });

  socket.on('qber-update', (data) => {
    state.bb84Active = true;
    state.qber = data.qber;
    state.qberEvent = data.event;
    state.qberHistory.push({
      time: Date.now(),
      qber: data.qber,
      event: data.event,
    });
    // Keep last 50 data points
    if (state.qberHistory.length > 50) state.qberHistory.shift();
    renderQuantumPanel();
  });

  socket.on('camera-list', (cameras) => {
    state.cameras = cameras;
    render();
  });

  socket.on('audio-device-list', (devices) => {
    state.audioDevices = devices;
    render();
  });

  socket.connect();
}

/* ── Actions ────────────────────────────────────────────────────────────── */
function connectToServer(host, port) {
  socket.emit('configure_server', { host, port: parseInt(port, 10) });
}

function toggleCamera() {
  state.cameraOn = !state.cameraOn;
  socket.emit('toggle_camera', { enabled: state.cameraOn });
  render();
}

function toggleMute() {
  state.muted = !state.muted;
  socket.emit('toggle_mute', { muted: state.muted });
  render();
}

function selectCamera(index) {
  state.selectedCamera = index;
  socket.emit('select_camera', { device: index });
}

function selectAudio(index) {
  state.selectedAudio = index;
  socket.emit('select_audio', { device: index });
}

function joinRoom(peerId) {
  socket.emit('join_room', { peer_id: peerId || null });
}

function leaveSession() {
  socket.emit('leave_room');
  state.roomId = '';
  state.waitingForPeer = false;
  state.elapsed = 0;
  if (elapsedInterval) { clearInterval(elapsedInterval); elapsedInterval = null; }
  render();
}

function startElapsedTimer() {
  if (elapsedInterval) clearInterval(elapsedInterval);
  elapsedInterval = setInterval(() => {
    state.elapsed++;
    const el = document.getElementById('elapsed-timer');
    if (el) el.textContent = formatTime(state.elapsed);
  }, 1000);
}

function formatTime(secs) {
  const m = Math.floor(secs / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

/* ── Canvas rendering ───────────────────────────────────────────────────── */
function toRGBA(raw) {
  if (Array.isArray(raw) && Array.isArray(raw[0]) && Array.isArray(raw[0][0])) {
    const flat = [];
    for (const row of raw) {
      for (const px of row) {
        flat.push(px[2], px[1], px[0], 255); // BGR → RGBA
      }
    }
    return new Uint8ClampedArray(flat);
  }
  const arr = raw.flat ? raw.flat(Infinity) : Array.from(raw);
  return new Uint8ClampedArray(arr);
}

function drawOnCanvas(canvas, data) {
  if (!canvas) return;
  canvas.width = data.width;
  canvas.height = data.height;
  const ctx = canvas.getContext('2d');
  ctx.putImageData(new ImageData(toRGBA(data.frame), data.width, data.height), 0, 0);
}

/* ── Noise canvas ───────────────────────────────────────────────────────── */
function startNoise(canvas) {
  if (!canvas) return;
  const w = 160;
  const h = Math.round(160 * (9 / 16));
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  const imageData = ctx.createImageData(w, h);
  const buf = imageData.data;

  function draw() {
    for (let i = 0; i < buf.length; i += 4) {
      const v = (Math.random() * 200 + 30) | 0;
      buf[i] = v; buf[i + 1] = v; buf[i + 2] = v; buf[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
    noiseRaf = requestAnimationFrame(draw);
  }
  draw();
}

function stopNoise() {
  if (noiseRaf) { cancelAnimationFrame(noiseRaf); noiseRaf = null; }
}

/* ── Toast ──────────────────────────────────────────────────────────────── */
let toastTimer = null;

function showToast(msg) {
  state.errorMessage = msg;
  const el = document.getElementById('toast');
  const msgEl = document.getElementById('toast-msg');
  if (!el || !msgEl) return;
  msgEl.textContent = msg;
  el.className = 'toast toast--visible';
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.className = 'toast toast--hidden';
    setTimeout(() => { state.errorMessage = ''; }, 300);
  }, 5000);
}

function dismissToast() {
  const el = document.getElementById('toast');
  if (el) el.className = 'toast toast--hidden';
  if (toastTimer) clearTimeout(toastTimer);
  setTimeout(() => { state.errorMessage = ''; }, 300);
}

/* ── Theme ──────────────────────────────────────────────────────────────── */
function getTheme() {
  return localStorage.getItem('qvc-theme') || 'dark';
}

function setTheme(theme) {
  localStorage.setItem('qvc-theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  setTheme(next);
  render();
}

function getLogoVisible() {
  const v = localStorage.getItem('qvc-logo-visible');
  return v === null ? true : v === 'true';
}

function toggleLogo() {
  const next = !getLogoVisible();
  localStorage.setItem('qvc-logo-visible', String(next));
  render();
}

/* ── Render ─────────────────────────────────────────────────────────────── */
function render() {
  const app = document.getElementById('app');
  if (!app) return;

  const inCall = !!state.roomId;

  // Determine state label
  let stateLabel = 'idle';
  if (state.roomId) stateLabel = 'in session';
  else if (state.waitingForPeer) stateLabel = 'waiting';
  else if (state.serverConnected) stateLabel = 'ready';

  const mwDotClass = state.middlewareConnected ? 'conn-dot--ok' : 'conn-dot--off';
  const srvDotClass = state.serverConnected ? 'conn-dot--ok' :
    state.middlewareConnected ? 'conn-dot--idle' : 'conn-dot--off';

  const isDark = getTheme() === 'dark';
  const logoVisible = getLogoVisible();
  const isConnected = state.serverConnected;

  let html = '';

  // Toast (always present)
  html += `<div id="toast" class="toast toast--hidden" onclick="dismissToast()">
    <span id="toast-msg" class="toast-message"></span>
    <span class="toast-dismiss">&times;</span>
  </div>`;

  if (!inCall) {
    // ── Header + Lobby ──
    html += `<div class="header">
      <div class="header-left">
        ${logoVisible ? '<img id="logo" src="/static/logo.png" alt="UCSD Logo">' : ''}
      </div>
      <div class="header-right">
        <div class="conn-status">
          <span class="conn-dot ${mwDotClass}" title="${state.middlewareConnected ? 'Middleware connected' : 'Middleware disconnected'}"></span>
          <span class="conn-label">middleware</span>
          <span class="conn-sep">&middot;</span>
          <span class="conn-dot ${srvDotClass}" title="${state.serverConnected ? 'QKD server connected' : 'QKD server not connected'}"></span>
          <span class="conn-label">server</span>
          <span class="conn-sep">&middot;</span>
          <span class="conn-state conn-state--${stateLabel.replace(/\s/g, '-')}">${stateLabel}</span>
        </div>
        <button class="header-theme-btn" onclick="toggleLogo()" title="${logoVisible ? 'Hide logo' : 'Show logo'}">${ICONS.image}</button>
        <button class="header-theme-btn" onclick="toggleTheme()" title="${isDark ? 'Light mode' : 'Dark mode'}">${isDark ? ICONS.sun : ICONS.moon}</button>
      </div>
    </div>`;

    html += `<div class="main-body"><div class="lobby">`;

    // Self preview
    html += `<div class="lobby-preview">
      <canvas id="self-canvas" class="lobby-preview-canvas"></canvas>
      ${!state.cameraOn ? `<div class="noise-canvas-wrapper"><canvas id="noise-canvas" class="noise-canvas"></canvas><span class="noise-label">Camera Off</span></div>` : ''}
    </div>`;

    html += `<h2 class="lobby-title">QKD Video Chat</h2>`;

    // Server connect form
    html += `<form class="lobby-form" onsubmit="handleConnect(event)">
      <label for="server-host" class="lobby-label">Server</label>
      <div class="lobby-server-inputs">
        <input id="server-host" type="text" class="lobby-input lobby-input--host" placeholder="192.168.x.x" value="${document.getElementById('server-host')?.value || '192.168.1.28'}" spellcheck="false" autocomplete="off">
        <span class="lobby-colon">:</span>
        <input id="server-port" type="number" class="lobby-input lobby-input--port" placeholder="5050" value="${document.getElementById('server-port')?.value || '5050'}" min="1" max="65535">
      </div>
      <button type="submit" class="lobby-btn lobby-connect-btn ${isConnected ? 'lobby-connect-btn--connected' : ''}">${isConnected ? ICONS.check + ' Connected' : 'Connect'}</button>
    </form>`;

    html += `<div class="lobby-divider"></div>`;

    // Room join form
    html += `<form class="lobby-form" onsubmit="handleJoin(event)">
      <label for="join-room-id" class="lobby-label">Room ID</label>
      <input id="join-room-id" type="text" class="lobby-input lobby-input--room" placeholder="Enter code or leave blank" ${!isConnected ? 'disabled' : ''} spellcheck="false" autocomplete="off" value="${document.getElementById('join-room-id')?.value || ''}">
      <button type="submit" class="lobby-btn" ${!isConnected ? 'disabled' : ''}>Join</button>
    </form>`;

    // Start session button
    html += `<button type="button" class="lobby-btn lobby-start-btn" onclick="joinRoom()" ${!isConnected || state.waitingForPeer ? 'disabled' : ''}>${state.waitingForPeer ? 'Waiting for peer...' : 'Start Session'}</button>`;

    // Waiting indicator
    if (state.waitingForPeer) {
      html += `<div class="lobby-waiting">
        <span class="lobby-waiting-spinner"></span>
        <span>Waiting for peer to join...</span>
        ${state.userId ? `<span class="lobby-user-id">Your ID: <strong>${state.userId}</strong></span>` : ''}
      </div>`;
    }

    // Media toggles
    html += `<div class="lobby-media">
      <button class="lobby-media-btn ${state.cameraOn ? '' : 'lobby-media-btn--off'}" type="button" onclick="toggleCamera()" title="${state.cameraOn ? 'Turn camera off' : 'Turn camera on'}">
        ${state.cameraOn ? ICONS.cameraOn : ICONS.cameraOff}
      </button>
      <button class="lobby-media-btn ${state.muted ? 'lobby-media-btn--off' : ''}" type="button" onclick="toggleMute()" title="${state.muted ? 'Unmute microphone' : 'Mute microphone'}">
        ${state.muted ? ICONS.micOff : ICONS.micOn}
      </button>
    </div>`;

    // Camera picker
    if (state.cameras.length > 0) {
      html += `<div class="lobby-device-row">
        <label for="camera-select" class="lobby-label">Camera</label>
        <select id="camera-select" class="lobby-select" onchange="selectCamera(Number(this.value))">
          ${state.cameras.map(c => `<option value="${c.index}" ${c.index === state.selectedCamera ? 'selected' : ''}>${c.label}</option>`).join('')}
        </select>
      </div>`;
    }

    // Audio picker
    if (state.audioDevices.length > 0) {
      html += `<div class="lobby-device-row">
        <label for="audio-select" class="lobby-label">Mic</label>
        <select id="audio-select" class="lobby-select" onchange="selectAudio(Number(this.value))">
          ${state.audioDevices.map(d => `<option value="${d.index}" ${d.index === state.selectedAudio ? 'selected' : ''}>${d.label}</option>`).join('')}
        </select>
      </div>`;
    }

    html += `</div></div>`;

  } else {
    // ── InCall ──
    html += `<div class="incall">
      <div class="incall-video-area">
        <canvas id="peer-canvas" class="incall-peer-canvas"></canvas>
        <div class="incall-peer-noise">
          <div class="noise-canvas-wrapper">
            <canvas id="peer-noise-canvas" class="noise-canvas"></canvas>
            <span class="noise-label">Waiting for video...</span>
          </div>
        </div>
        <div class="incall-pip">
          <canvas id="self-canvas" class="incall-pip-canvas"></canvas>
          ${!state.cameraOn ? `<div class="incall-pip-off">${ICONS.cameraOff}</div>` : ''}
        </div>
      </div>
      <div class="incall-info">
        <span class="incall-room">Room: <strong>${state.roomId}</strong></span>
        <span class="incall-timer" id="elapsed-timer">${formatTime(state.elapsed)}</span>
      </div>
      <div id="quantum-panel" class="quantum-panel"></div>
      <div class="incall-toolbar">
        <div class="incall-toolbar-center">
          <button class="incall-tool-btn ${state.cameraOn ? '' : 'incall-tool-btn--off'}" onclick="toggleCamera()" title="${state.cameraOn ? 'Turn camera off' : 'Turn camera on'}">
            ${state.cameraOn ? ICONS.cameraOn : ICONS.cameraOff}
            <span class="incall-tool-label">${state.cameraOn ? 'Camera' : 'Camera Off'}</span>
          </button>
          <button class="incall-tool-btn ${state.muted ? 'incall-tool-btn--off' : ''}" onclick="toggleMute()" title="${state.muted ? 'Unmute microphone' : 'Mute microphone'}">
            ${state.muted ? ICONS.micOff : ICONS.micOn}
            <span class="incall-tool-label">${state.muted ? 'Muted' : 'Mic'}</span>
          </button>
        </div>
        <button class="incall-leave-btn" onclick="leaveSession()" title="Leave session">
          ${ICONS.phoneOff}
          <span class="incall-tool-label">Leave</span>
        </button>
      </div>
    </div>`;
  }

  // Preserve input values before re-render
  const hostVal = document.getElementById('server-host')?.value;
  const portVal = document.getElementById('server-port')?.value;
  const joinVal = document.getElementById('join-room-id')?.value;

  app.innerHTML = html;

  // Restore input values
  if (!inCall) {
    const h = document.getElementById('server-host');
    const p = document.getElementById('server-port');
    const j = document.getElementById('join-room-id');
    if (h && hostVal) h.value = hostVal;
    if (p && portVal) p.value = portVal;
    if (j && joinVal) j.value = joinVal;
  }

  // Start noise canvases
  stopNoise();
  if (!inCall && !state.cameraOn) {
    startNoise(document.getElementById('noise-canvas'));
  }
  if (inCall) {
    startNoise(document.getElementById('peer-noise-canvas'));
    renderQuantumPanel();
  }

  // Request device lists
  if (socket && socket.connected) {
    socket.emit('list_cameras');
    socket.emit('list_audio_devices');
  }
}

/* ── Quantum Dashboard Panel ───────────────────────────────────────────── */
function renderQuantumPanel() {
  const panel = document.getElementById('quantum-panel');
  if (!panel) return;

  if (!state.bb84Active) {
    panel.innerHTML = '<div class="qd-inactive">Classical key mode</div>';
    return;
  }

  const qber = state.qber;
  const qberPct = qber !== null ? (qber * 100).toFixed(2) : '--';
  const event = state.qberEvent || 'unknown';

  // Status classification
  let statusClass = 'qd-status--normal';
  let statusLabel = 'Secure';
  if (event === 'intrusion_detected') {
    statusClass = 'qd-status--danger';
    statusLabel = 'INTRUSION';
  } else if (event === 'warning') {
    statusClass = 'qd-status--warning';
    statusLabel = 'Warning';
  } else if (event === 'key_generation_failed') {
    statusClass = 'qd-status--warning';
    statusLabel = 'Key Failed';
  }

  let html = `
    <div class="qd-header">
      <span class="qd-title">BB84 Quantum Channel</span>
      <span class="qd-badge ${statusClass}">${statusLabel}</span>
    </div>
    <div class="qd-metrics">
      <div class="qd-metric">
        <span class="qd-metric-value ${qber > 0.11 ? 'qd-metric--danger' : qber > 0.05 ? 'qd-metric--warning' : ''}">${qberPct}%</span>
        <span class="qd-metric-label">QBER</span>
      </div>
      <div class="qd-metric">
        <span class="qd-metric-value">${state.qberHistory.length}</span>
        <span class="qd-metric-label">Rounds</span>
      </div>
      <div class="qd-metric">
        <span class="qd-metric-value">11%</span>
        <span class="qd-metric-label">Threshold</span>
      </div>
    </div>
    <canvas id="qber-chart" class="qd-chart" width="280" height="80"></canvas>
    <button class="qd-eve-btn ${state.eavesdropperEnabled ? 'qd-eve-btn--active' : ''}"
            onclick="toggleEavesdropper()" title="Simulate eavesdropper (Eve)">
      ${state.eavesdropperEnabled ? 'Disable Eve' : 'Simulate Eve'}
    </button>
  `;
  panel.innerHTML = html;

  // Draw QBER chart
  drawQBERChart();
}

function drawQBERChart() {
  const canvas = document.getElementById('qber-chart');
  if (!canvas || state.qberHistory.length < 2) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = 'rgba(0,0,0,0.2)';
  ctx.fillRect(0, 0, w, h);

  // Threshold line at 11%
  const thresholdY = h - (0.11 / 0.35) * h;
  ctx.strokeStyle = 'rgba(255,80,80,0.5)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(0, thresholdY);
  ctx.lineTo(w, thresholdY);
  ctx.stroke();
  ctx.setLineDash([]);

  // QBER line
  const points = state.qberHistory;
  const step = w / Math.max(points.length - 1, 1);

  ctx.strokeStyle = '#4fc3f7';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < points.length; i++) {
    const x = i * step;
    const y = h - (points[i].qber / 0.35) * h;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Mark intrusion points
  for (let i = 0; i < points.length; i++) {
    if (points[i].event === 'intrusion_detected') {
      const x = i * step;
      const y = h - (points[i].qber / 0.35) * h;
      ctx.fillStyle = '#ff5252';
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function toggleEavesdropper() {
  state.eavesdropperEnabled = !state.eavesdropperEnabled;
  // Send to server admin API
  const serverHost = document.getElementById('server-host')?.value || 'localhost';
  const serverPort = document.getElementById('server-port')?.value || '5050';
  const url = `http://${serverHost}:${serverPort}/admin/quantum/eavesdropper`;
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: state.eavesdropperEnabled }),
  }).then(r => r.json()).then(data => {
    showToast(`Eavesdropper ${data.eavesdropper}`);
    renderQuantumPanel();
  }).catch(() => {
    showToast('Could not toggle eavesdropper');
    state.eavesdropperEnabled = !state.eavesdropperEnabled;
  });
  renderQuantumPanel();
}

/* ── Form handlers ──────────────────────────────────────────────────────── */
function handleConnect(e) {
  e.preventDefault();
  const host = document.getElementById('server-host').value;
  const port = document.getElementById('server-port').value;
  if (!host) { showToast('Please enter a server address.'); return; }
  connectToServer(host, port);
}

function handleJoin(e) {
  e.preventDefault();
  const id = document.getElementById('join-room-id').value.trim();
  if (id && !/^[a-zA-Z0-9]{5}$/.test(id)) {
    showToast('Room ID must be exactly 5 alphanumeric characters.');
    return;
  }
  joinRoom(id || null);
}

/* ── Init ───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Apply stored theme
  setTheme(getTheme());

  // Initial render
  render();

  // Connect socket
  initSocket();
});
