# Quantum Video Chat

---

## Architecture Overview

The system has three layers that work together:

```
┌─────────────────────────────────────────────────────────────────┐
│                     ELECTRON APP (Desktop)                      │
│  ┌──────────────────────┐        ┌─────────────────────────┐   │
│  │  Main Process        │◄─IPC──►│  Renderer (React)       │   │
│  │  main.ts             │        │  Start / Join / Session │   │
│  │  Socket.IO IPC :5001 │        └─────────────────────────┘   │
│  └──────────┬───────────┘                                       │
└─────────────┼───────────────────────────────────────────────────┘
              │ Socket.IO
              ▼
┌─────────────────────────┐        ┌──────────────────────────────┐
│  Python Middleware       │──REST─►│  Python Backend Server       │
│  video_chat.py           │        │  api.py                      │
│                          │        │  REST  :5000                 │
│  Client (orchestrator)   │◄─REST─│  WebSocket :3000             │
│  ClientAPI    :4000      │        │  UserManager / User[]        │
│  SocketClient (WS)       │◄══WS══│  SocketAPI (/video /audio)   │
│  AV + Encryption         │        └──────────────────────────────┘
└─────────────────────────┘
```

---

## Components

### Backend Server (`server/`)

Manages user registration and brokers peer connections.

| File | Purpose |
|------|---------|
| `api.py` | `ServerAPI` (REST :5000) and `SocketAPI` (WebSocket :3000) |
| `server.py` | `Server` — user lifecycle and peer connection logic |
| `utils/user_manager.py` | `UserManager` with in-memory `DictUserStorage` |
| `utils/user.py` | `User` — state machine (IDLE → AWAITING → CONNECTED) |
| `utils/av.py` | `VideoClientNamespace`, `AudioClientNamespace` — H.264/audio streaming |
| `utils/encryption.py` | `AESEncryption`, `XOREncryption`, `DebugEncryption`; `KeyGeneratorFactory` |
| `exceptions.py` | `InvalidState`, `IdentityMismatch` |
| `custom_logging.py` | Centralised file + console logging |

**REST API:**
- `POST /create_user` → `{ user_id }`
- `POST /peer_connection` → `{ peer_id, socket_endpoint }` — starts WebSocket, contacts peer

### Python Middleware (`frontend/src/middleware/`)

Runs alongside the Electron app, handling peer connections and AV streaming.

| File | Purpose |
|------|---------|
| `video_chat.py` | Entry point — connects to Electron IPC and drives the `Client` |
| `client/client.py` | `Client` (main orchestrator) + `SocketClient` (WebSocket) |
| `client/api.py` | `ClientAPI` (Flask, :4000) — receives incoming peer connection requests |
| `client/av.py` | `AV` — key rotation loop, encryption, H.264 encode/decode via ffmpeg + OpenCV |
| `client/encryption.py` | Encryption scheme implementations |
| `client/endpoint.py` | `Endpoint` URL builder |
| `client/util.py` | `ClientState`, `APIState`, `SocketState` enums |

### Electron Frontend (`frontend/src/`)

| Path | Purpose |
|------|---------|
| `main/main.ts` | Electron main process; hosts Socket.IO IPC server on :5001 |
| `main/preload.ts` | Exposes `electronAPI.setPeerId()` and `electronAPI.ipcListen()` to renderer |
| `renderer/App.tsx` | Router: `/`, `/join`, `/session/:role/:code` |
| `renderer/screens/Start.tsx` | Home — start or join a session |
| `renderer/screens/Join.tsx` | Code entry form |
| `renderer/screens/Session.tsx` | Active session — dual video, chat, QKD metric widgets |
| `renderer/components/` | `VideoPlayer`, `Header`, `StatusPopup`, chat, widgets |

---

## Session Flow

1. **Host** clicks "Start Session" — a random code is generated and displayed.
2. **Client** enters the code on the Join screen.
3. Both sides call `electronAPI.setPeerId(code)` via IPC.
4. Electron main emits `connect_to_peer` to Python middleware over Socket.IO (:5001).
5. Middleware calls `POST /peer_connection` on the backend server.
6. Server starts a shared WebSocket endpoint and contacts the peer's `ClientAPI` (:4000).
7. Both clients connect to the shared WebSocket and begin streaming encrypted AV.

---

## Video Frame Lifecycle

```
OpenCV capture → H.264 encode (ffmpeg) → AES-128 encrypt (key_index prefix)
    → WebSocket /video → peer decrypt → H.264 decode → IPC 'frame' event
    → Canvas drawImage() in React
```

Keys rotate every **1 second**. Each frame is prefixed with a 4-byte key index so the receiver can synchronise decryption.

---

## Encryption

Three schemes are supported, selected at startup:

| Scheme | Description |
|--------|-------------|
| `AESEncryption` | AES-128 CBC (default) |
| `XOREncryption` | XOR cipher |
| `DebugEncryption` | Passthrough — no encryption |

Three key generators are supported:

| Generator | Description |
|-----------|-------------|
| `RandomKeyGenerator` | Cryptographically random keys |
| `FileKeyGenerator` | Reads keys from `key.bin` (for real QKD hardware) |
| `DebugKeyGenerator` | Fixed key for testing |

---

## State Machines

**User (server-side)**
```
IDLE → AWAITING_CONNECTION → CONNECTED → IDLE
```

**Client (middleware)**
```
NEW → INIT → LIVE → CONNECTED
```

---

## Running Locally

Start each process in a separate terminal. The backend server must be running before the middleware, and the renderer must be running before the Electron main process.

### 1. Backend Server

```bash
cd server
python3 api.py
# REST API: http://localhost:5000
# WebSocket: http://localhost:3000
```

### 2. Python Middleware

```bash
cd frontend/src/middleware
python3 video_chat.py
# ClientAPI: http://localhost:4000
```

### 3. Frontend

In a second terminal (after the renderer is running):

```bash
cd frontend
npm run start:main
```

> If a port is already in use, the middleware will automatically try the next available port in increasing order.

---

## Configuration

The middleware reads its server endpoint from:

- `frontend/src/middleware/dev_python_config.json` (when `DEV = True`)
- `frontend/src/middleware/python_config.json` (production)

```json
{
  "SERVER_IP": "127.0.0.1",
  "SERVER_PORT": 5000
}
```

The network interface used for peer discovery is currently hard-coded in `server/api.py` (`en11` on macOS, `WiFi 2` on Windows) and will need to be updated to match your machine.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Desktop shell | Electron 26 |
| UI | React 18, React Router, Material UI, TypeScript |
| Bundler | Webpack 5, webpack-dev-server |
| Backend server | Python, Flask, Flask-SocketIO, gevent |
| Middleware client | Python, python-socketio, Flask |
| Video | OpenCV (cv2), ffmpeg-python |
| Audio | PyAudio |
| Encryption | PyCryptodome (AES-128 CBC) |
| Networking | psutil (interface discovery), bitarray |

---

## Project Structure

```
quantum-video-chat/
├── server/                         # Backend server
│   ├── api.py                      # REST + WebSocket API
│   ├── server.py                   # User & peer management
│   ├── exceptions.py
│   ├── custom_logging.py
│   └── utils/
│       ├── user.py
│       ├── user_manager.py
│       ├── av.py
│       └── encryption.py
├── frontend/
│   ├── src/
│   │   ├── main/                   # Electron main process
│   │   │   ├── main.ts
│   │   │   └── preload.ts
│   │   ├── renderer/               # React UI
│   │   │   ├── App.tsx
│   │   │   ├── screens/
│   │   │   └── components/
│   │   └── middleware/             # Python client
│   │       ├── video_chat.py
│   │       └── client/
│   └── package.json
└── icebox/                         # Experimental / legacy code
```
