# Quantum Video Chat — Frontend

React + TypeScript browser UI for the Quantum Video Chat application.

See the [root README](../README.md) for full project documentation.

---

## Quick Start

```bash
npm install
npm start
```

## Testing

```bash
npm test
```

## Structure

```
src/
├── middleware/               # Lightweight Python middleware (browser ↔ QKD server)
│   ├── client.py            # Entry point
│   ├── state.py             # Centralised mutable state
│   ├── video.py             # Camera capture thread
│   ├── server_comms.py      # QKD server REST calls + health checks
│   └── events.py            # Socket.io + REST event registration
└── renderer/                # React renderer
    ├── screens/             # MainScreen, Start, Join, Session, Settings
    ├── hooks/               # useConnection, useSession, useMedia
    ├── utils/               # ClientContext, socket, canvas, theme
    └── components/          # Header, ControlBar, MediaControls, ErrorPanel, StatusBar, ...
```
