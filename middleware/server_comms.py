"""server_comms -- QKD server communication (REST + health checks).

Single responsibility: HTTP interactions with the QKD server.
"""
import json as _json
import os
import socket as _socket
import urllib.request

import gevent
import requests
from state import DEFAULT_SERVER_HOST, HEIGHT, WIDTH, MiddlewareState
from video import VideoThread

from shared.logging import get_logger

logger = get_logger(__name__)

HTTP_OK = 200


def _get_local_ip() -> str:
    """Auto-detect local IP address."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        addr = s.getsockname()[0]
        s.close()
    except OSError:
        logger.debug("UDP probe failed, falling back to 127.0.0.1")
        return "127.0.0.1"
    else:
        logger.debug("Detected local IP: %s", addr)
        return addr


LOCAL_IP = _get_local_ip()

# Maximum number of times to retry a WebSocket session connection
_WS_CONNECT_MAX_ATTEMPTS = 5
_WS_CONNECT_RETRY_DELAY  = 0.5  # seconds (doubles each attempt)


def connect_to_session_ws(state: MiddlewareState, ws_endpoint, _peer_id, session_id=None):
    """Connect this middleware's server_client to the session WebSocket.

    Retries with exponential back-off in case of transient failures.
    """
    ws_host, ws_port = ws_endpoint
    logger.info("Connecting to session WebSocket at %s:%s  peer=%s  session=%s",
                ws_host, ws_port, _peer_id, session_id)
    if state.server_client.connected:
        logger.debug("Disconnecting existing server_client before reconnect")
        try:
            state.server_client.disconnect()
        except (ConnectionError, OSError):
            logger.debug("Ignoring error during server_client disconnect")

    delay = _WS_CONNECT_RETRY_DELAY
    for attempt in range(1, _WS_CONNECT_MAX_ATTEMPTS + 1):
        try:
            from shared.ssl_utils import get_ssl_context
            ws_scheme = "https" if get_ssl_context() else "http"
            auth = {"user_id": state.user_id}
            if session_id:
                auth["session_id"] = session_id
            logger.debug("WS connect attempt %s/%s  url=%s://%s:%s",
                         attempt, _WS_CONNECT_MAX_ATTEMPTS, ws_scheme, ws_host, ws_port)
            state.server_client.connect(
                f"{ws_scheme}://{ws_host}:{ws_port}",
                auth=auth,
                wait_timeout=10,
            )
            logger.info("Session WebSocket connected on attempt %s", attempt)
        except (ConnectionError, OSError) as exc:
            if attempt < _WS_CONNECT_MAX_ATTEMPTS:
                logger.warning("WS connect attempt %s failed (%s), retrying in %.1fs...",
                               attempt, exc, delay)
                gevent.sleep(delay)
                delay = min(delay * 2, 4.0)
            else:
                logger.error("WS connect failed after %s attempts: %s", attempt, exc)
                state.sio.emit("server-error",
                               f"Could not connect to session -- {exc}")
        except Exception as exc:
            if attempt < _WS_CONNECT_MAX_ATTEMPTS:
                logger.warning("WS connect attempt %s failed (%s), retrying in %.1fs...",
                               attempt, exc, delay)
                gevent.sleep(delay)
                delay = min(delay * 2, 4.0)
            else:
                logger.error("WS connect failed after %s attempts: %s", attempt, exc)
                state.sio.emit("server-error",
                               f"Could not connect to session -- {exc}")
        else:
            return  # success


def configure_server(state: MiddlewareState, sid, data):
    """Verify the QKD server via its REST /admin/status endpoint."""
    host = data.get("host", "")
    port = int(data.get("port", 0))

    # When the browser sends "localhost" / "127.0.0.1", resolve to the
    # middleware's configured server host (e.g. Docker hostname "server").
    if host in ("localhost", "127.0.0.1") and DEFAULT_SERVER_HOST not in ("localhost", "127.0.0.1"):
        logger.debug("Rewriting host %s -> %s (Docker name resolution)", host, DEFAULT_SERVER_HOST)
        host = DEFAULT_SERVER_HOST
    logger.info("configure_server -> %s:%s  (sid=%s)", host, port, sid)

    if not host:
        logger.warning("configure_server: no host provided")
        state.sio.emit("server-error", "No host provided.", room=sid)
        return

    if not port:
        logger.warning("configure_server: no port provided")
        state.sio.emit("server-error", "No port provided.", room=sid)
        return

    url = f"http://{host}:{port}/admin/status"
    try:
        logger.debug("configure_server: GET %s ...", url)
        req = urllib.request.Request(url)
        admin_key = os.environ.get("QVC_ADMIN_KEY", "")
        if admin_key:
            req.add_header("Authorization", f"Bearer {admin_key}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            status_code = resp.status
        logger.debug("configure_server: response %s  body_len=%d", status_code, len(body))
        if status_code >= 400:
            raise Exception(f"HTTP {status_code}")
        state.server_host = host
        state.server_port = port
        info = _json.loads(body)
        logger.info("QKD server verified at %s:%s -- state=%s  users=%s",
                     host, port, info.get("api_state"), info.get("user_count"))
        state.server_alive = True
        state.sio.emit("server-connected", room=sid)
        logger.debug("Emitted server-connected to sid=%s", sid)
        start_health_checks(state)
    except (ConnectionError, OSError) as exc:
        msg = f"Could not connect to {host}:{port} -- {exc}"
        logger.error(msg)
        state.sio.emit("server-error", msg, room=sid)
    except Exception as exc:
        msg = f"Could not connect to {host}:{port} -- {exc}"
        logger.error(msg)
        state.sio.emit("server-error", msg, room=sid)


def create_user(state: MiddlewareState, sid):
    """Register this middleware with the QKD server, getting back a user_id."""
    if not state.server_host:
        logger.warning("create_user: no server configured")
        state.sio.emit("server-error", "Not connected to a server.", room=sid)
        return

    url = state.server_url("/create_user")
    payload = {"api_endpoint": (LOCAL_IP, state.middleware_port)}
    logger.debug("POST %s  payload=%s", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        state.user_id = resp.json().get("user_id", "")
        logger.info("Registered with QKD server as user %s", state.user_id)
        state.sio.emit("user-registered", {"user_id": state.user_id}, room=sid)
    except requests.RequestException as exc:
        msg = f"Failed to register with server -- {exc}"
        logger.error(msg)
        state.sio.emit("server-error", msg, room=sid)


def join_room(state: MiddlewareState, sid, peer_id=None):
    """Handle join_room from browser -- start session or connect to peer."""
    if not state.server_host:
        logger.warning("join_room: no server configured")
        state.sio.emit("server-error", "Not connected to a server.", room=sid)
        return
    if not state.user_id:
        logger.warning("join_room: not registered")
        state.sio.emit("server-error", "Not registered with server yet.", room=sid)
        return

    if not peer_id:
        logger.info("join_room -- waiting for peer (user_id=%s)", state.user_id)
        state.sio.emit("waiting-for-peer", {"user_id": state.user_id}, room=sid)
        return

    if peer_id == state.user_id:
        msg = (f"Cannot connect to yourself (user_id={state.user_id}). "
               f"For same-device testing, run a second middleware on a "
               f"different port: python3 client.py --port 5002")
        logger.error(msg)
        state.sio.emit("server-error", msg, room=sid)
        return

    logger.info("join_room -> peer_connection  user=%s  peer=%s", state.user_id, peer_id)

    url = state.server_url("/peer_connection")
    payload = {"user_id": state.user_id, "peer_id": peer_id}
    logger.debug("POST %s  payload=%s", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()

        if resp.status_code != HTTP_OK:
            msg = data.get("details", data.get("error_message", "Unknown error"))
            logger.error("peer_connection error %s: %s", resp.status_code, msg)
            state.sio.emit("server-error", msg, room=sid)
            return

        ws_endpoint = data.get("socket_endpoint")
        session_id = data.get("session_id")
        logger.debug("peer_connection response: ws=%s  session=%s", ws_endpoint, session_id)
        if ws_endpoint:
            connect_to_session_ws(state, ws_endpoint, peer_id, session_id=session_id)
    except requests.RequestException as exc:
        msg = f"Peer connection failed -- {exc}"
        logger.error(msg)
        state.sio.emit("server-error", msg, room=sid)


def leave_room(state: MiddlewareState, _sid):
    """Browser leaves the room -- stop media, disconnect from session WS."""
    logger.info("leave_room -- stopping media and disconnecting session WS")
    if state.video_thread is not None:
        logger.debug("Stopping video thread")
        state.video_thread.stop()
        state.video_thread = None
    if state.audio_thread is not None:
        logger.debug("Stopping audio thread")
        state.audio_thread.stop()
        state.audio_thread = None

    if state.server_client.connected:
        logger.debug("Disconnecting server_client (leave_room)")
        try:
            state.server_client.disconnect()
        except (ConnectionError, OSError):
            logger.debug("Ignoring error during server_client disconnect in leave_room")

    if state.server_host and state.user_id:
        url = state.server_url("/disconnect_peer")
        logger.debug("POST %s  user_id=%s", url, state.user_id)
        try:
            requests.post(url, json={"user_id": state.user_id}, timeout=5)
        except requests.RequestException as exc:
            logger.warning("leave_room -- disconnect_peer failed: %s", exc)


def start_video(state: MiddlewareState, _room_id):
    """Start or restart the video thread after a room is assigned."""
    logger.info("start_video  device=%s  room=%s", state.camera_device, _room_id)
    if state.video_thread is not None and state.video_thread.is_alive():
        logger.debug("Stopping existing video thread before restart")
        state.video_thread.stop()
        state.video_thread.join(timeout=2)
    state.video_thread = VideoThread(state, WIDTH, HEIGHT, device=state.camera_device)
    state.video_thread.start()


def enumerate_cameras(max_devices: int = 8):
    """Probe for available video capture devices and return a list of dicts.

    Each dict: ``{'index': int, 'label': str}``

    OpenCV prints "out device of bound" warnings to stderr for every invalid
    index.  We suppress those by redirecting stderr to /dev/null during the
    probe, then restore it afterwards.
    """
    logger.debug("enumerate_cameras: probing up to %d devices", max_devices)
    devices = []
    try:
        import cv2
    except ImportError:
        logger.debug("cv2 not available -- skipping camera enumeration")
        return devices

    # Silence OpenCV's "out device of bound" stderr spam during probing
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved_stderr_fd = os.dup(2)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)

    try:
        for i in range(max_devices):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                devices.append({"index": i, "label": f"Camera {i}"})
                cap.release()
            else:
                cap.release()
    finally:
        os.dup2(saved_stderr_fd, 2)
        os.close(saved_stderr_fd)

    # Append mock/test sources so users can select them from the camera picker
    from video import MOCK_DEVICE_A, MOCK_DEVICE_B
    devices.append({"index": MOCK_DEVICE_A, "label": "Test Pattern A"})
    devices.append({"index": MOCK_DEVICE_B, "label": "Test Pattern B"})

    logger.debug("enumerate_cameras: found %d device(s)", len(devices))
    return devices


def start_audio(state: MiddlewareState, _room_id):
    """Start or restart the audio thread after a room is assigned."""
    logger.info("start_audio  device=%s  room=%s", state.audio_device, _room_id)
    from audio import AudioThread
    if state.audio_thread is not None and state.audio_thread.is_alive():
        logger.debug("Stopping existing audio thread before restart")
        state.audio_thread.stop()
        state.audio_thread.join(timeout=2)
    state.audio_thread = AudioThread(state, device=state.audio_device)
    state.audio_thread.start()


def enumerate_audio_devices():
    """Probe for available audio input devices and return a list of dicts.

    Each dict: ``{'index': int, 'label': str}``
    """
    logger.debug("enumerate_audio_devices: probing")
    devices = []
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()
        logger.debug("PyAudio found %d device(s)", count)
        for i in range(count):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                name = info.get("name", f"Audio Input {i}")
                devices.append({"index": i, "label": name})
        pa.terminate()
    except ImportError:
        logger.debug("pyaudio not available for audio device enumeration")
    except OSError:
        logger.debug("Error enumerating audio devices", exc_info=True)

    # Append mock/test sources so users can select them from the audio picker
    from audio import MOCK_AUDIO_DEVICE_A, MOCK_AUDIO_DEVICE_B
    devices.append({"index": MOCK_AUDIO_DEVICE_A, "label": "Test Tone A"})
    devices.append({"index": MOCK_AUDIO_DEVICE_B, "label": "Test Tone B"})

    logger.debug("enumerate_audio_devices: returning %d device(s)", len(devices))
    return devices


# --- Health checks ---

# Require this many consecutive failures before broadcasting server-error.
# A single blip (e.g. server busy during peer_connection) won't trigger a
# browser re-registration cascade.
_HEALTH_FAILURE_THRESHOLD = 2


def _health_check_loop(state: MiddlewareState):
    """Ping the QKD server every 10s.  Emit status changes to all browsers."""
    logger.debug("Health check loop started (interval=10s, threshold=%d)",
                 _HEALTH_FAILURE_THRESHOLD)
    consecutive_failures = 0
    while True:
        gevent.sleep(10)
        if not state.server_host:
            if state.server_alive:
                logger.warning("Health check -- server_host cleared, marking server down")
                state.server_alive = False
                state.sio.emit("server-error", "Server connection lost.")
            continue
        try:
            req = urllib.request.Request(state.server_url("/admin/status"))
            admin_key = os.environ.get("QVC_ADMIN_KEY", "")
            if admin_key:
                req.add_header("Authorization", f"Bearer {admin_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status >= 400:
                    raise Exception(f"HTTP {resp.status}")
            consecutive_failures = 0
            if not state.server_alive:
                state.server_alive = True
                state.sio.emit("server-connected")
                logger.info("Health check -- server back online")
            else:
                logger.debug("Health check -- OK")
        except Exception:
            consecutive_failures += 1
            logger.warning("Health check -- server unreachable (failure %s/%s)",
                           consecutive_failures, _HEALTH_FAILURE_THRESHOLD)
            if consecutive_failures >= _HEALTH_FAILURE_THRESHOLD and state.server_alive:
                state.server_alive = False
                state.sio.emit("server-error", "Server health check failed.")
                logger.error("Health check -- declaring server down after %d failures",
                             consecutive_failures)


def start_health_checks(state: MiddlewareState):
    """Spawn the health-check greenlet (idempotent)."""
    if state.health_greenlet is None or state.health_greenlet.dead:
        logger.debug("Spawning health check greenlet")
        state.health_greenlet = gevent.spawn(_health_check_loop, state)
    else:
        logger.debug("Health check greenlet already running")
