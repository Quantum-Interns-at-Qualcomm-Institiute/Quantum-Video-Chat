# Quantum Video Chat

Browser-native, peer-to-peer video chat with **BB84 quantum key distribution**. Video and audio flow directly between browsers via WebRTC — encrypted frame-by-frame with AES-128-GCM keys derived from a simulated quantum optical channel.

The system models real quantum hardware: Poissonian photon statistics, fiber attenuation, single-photon APD detectors, and intercept-resend eavesdropping. When the quantum bit error rate (QBER) exceeds the 11% security threshold, keys are rejected and re-exchanged automatically.

## Architecture

```
Browser A ◄══ WebRTC (P2P encrypted media) ══► Browser B
    │                                              │
    └──── Socket.IO signaling ────► Server ◄───────┘
                                  (SDP + ICE relay only)
```

- **Signaling server** (Python/Flask): room management, SDP/ICE relay. No media touches the server.
- **WebRTC**: peer-to-peer video/audio via `RTCPeerConnection`
- **Insertable Streams**: AES-128-GCM frame encryption in a Web Worker (`RTCRtpScriptTransform`)
- **DataChannel**: BB84 key exchange messages flow peer-to-peer
- **BB84 Protocol** (JavaScript): sifting, QBER estimation, Cascade error correction, Toeplitz privacy amplification

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 20+ (for JS tests only; not needed at runtime)
- pip packages: `flask flask-cors python-socketio eventlet`

### Run the signaling server

```bash
cd packages/qvc
pip install flask flask-cors python-socketio eventlet
python signaling/main.py
```

The server starts on a dynamically assigned port (or set `QVC_SERVER_REST_PORT=5050`).

### Run with Docker

```bash
# From the website root
docker compose up -d
```

Port assignments are in `.env`. Set `DEV=1` in `.env` to also serve the Astro frontend.

### Open the client

Navigate to the page that serves `website/client/index.html`. In Docker, this is served by the Astro dev server at `localhost:4322/projects/quantum-video-chat/client/`.

1. Two browser tabs → both connect to the signaling server
2. Tab A clicks **Start Session** → gets a room code
3. Tab B enters the room code → clicks **Join**
4. WebRTC peer connection establishes → video flows P2P
5. BB84 key exchange runs over DataChannel → frames encrypted

## Tests

### Python (signaling server)

```bash
cd packages/qvc
pip install pytest
python -m pytest tests/signaling/ -v
```

31 tests: room management unit tests + signaling flow integration tests.

### JavaScript (crypto, BB84, metrics)

```bash
cd packages/qvc
npm install
NODE_OPTIONS="--experimental-vm-modules" npx jest tests/js/ --verbose
```

23 tests: AES-GCM frame crypto, BB84 protocol over ideal/simulated channels, metrics collector.

## Project Structure

```
signaling/
  server.py          # Flask + Socket.IO signaling server
  rooms.py           # Room management (create, join, leave)
  main.py            # Entry point

website/client/
  index.html         # Frontend entry point
  static/
    app.js           # Main application (state, render, actions)
    style.css        # Styles
    js/
      webrtc.js      # RTCPeerConnection lifecycle + DataChannel
      crypto.js      # AES-128-GCM frame encrypt/decrypt
      crypto-worker.js  # Insertable Streams Web Worker
      metrics.js     # MetricsCollector (rolling windows, thresholds)
      bb84/
        protocol.js  # BB84: sifting, QBER, error correction, privacy amp
        channel.js   # QuantumChannel + ClassicalChannel interfaces
        simulated.js # SimulatedQuantumChannel (photon source, fiber, APD)
        metrics.js   # BB84Metrics data class

shared/              # Legacy shared code (BB84 reference, encryption)
tests/
  signaling/         # Python signaling tests
  js/                # JavaScript tests (jest)
    bb84/            # BB84 protocol + simulation tests
```
