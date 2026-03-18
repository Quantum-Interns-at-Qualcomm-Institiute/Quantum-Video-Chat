"""
server_comms — QKD server communication (REST + health checks).

Single responsibility: HTTP interactions with the QKD server.
"""
import os
import sys
import gevent
import requests
import socket as _socket

from state import MiddlewareState, WIDTH, HEIGHT
from video import VideoThread


def _get_local_ip() -> str:
    """Auto-detect local IP address."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        addr = s.getsockname()[0]
        s.close()
        return addr
    except Exception:
        return '127.0.0.1'


LOCAL_IP = _get_local_ip()

# Maximum number of times to retry a WebSocket session connection
_WS_CONNECT_MAX_ATTEMPTS = 5
_WS_CONNECT_RETRY_DELAY  = 0.5  # seconds (doubles each attempt)


def connect_to_session_ws(state: MiddlewareState, ws_endpoint, peer_id):
    """Connect this middleware's server_client to the session WebSocket.

    Retries with exponential back-off because the SocketAPI server-thread
    may not be listening yet when the callback arrives (race condition between
    ``start_websocket()`` spawning the thread and this greenlet running).
    """
    ws_host, ws_port = ws_endpoint
    print(f'(middleware): Connecting to session WebSocket at {ws_host}:{ws_port}')
    if state.server_client.connected:
        try:
            state.server_client.disconnect()
        except Exception:
            pass

    delay = _WS_CONNECT_RETRY_DELAY
    for attempt in range(1, _WS_CONNECT_MAX_ATTEMPTS + 1):
        try:
            state.server_client.connect(
                f'http://{ws_host}:{ws_port}',
                auth={'user_id': state.user_id},
                wait_timeout=10,
            )
            print(f'(middleware): Session WebSocket connected (attempt {attempt}).')
            return  # success
        except Exception as exc:
            if attempt < _WS_CONNECT_MAX_ATTEMPTS:
                print(f'(middleware): WS connect attempt {attempt} failed ({exc}), '
                      f'retrying in {delay:.1f}s…')
                gevent.sleep(delay)
                delay = min(delay * 2, 4.0)
            else:
                print(f'(middleware): WS connect failed after {attempt} attempts: {exc}')
                state.sio.emit('server-error',
                               f'Could not connect to session — {exc}')


def configure_server(state: MiddlewareState, sid, data):
    """Verify the QKD server via its REST /admin/status endpoint."""
    host = data.get('host', '')
    port = int(data.get('port', 7777))
    print(f'(middleware): configure_server → {host}:{port}')

    if not host:
        state.sio.emit('server-error', 'No host provided.', room=sid)
        return

    url = f'http://{host}:{port}/admin/status'
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        state.server_host = host
        state.server_port = port
        info = resp.json()
        print(f'(middleware): QKD server verified at {host}:{port} — '
              f'state={info.get("api_state")}, users={info.get("user_count")}')
        state.server_alive = True
        state.sio.emit('server-connected', room=sid)
        start_health_checks(state)
    except requests.ConnectionError:
        msg = f'Could not connect to {host}:{port} — Connection refused'
        print(f'(middleware): ERROR — {msg}')
        state.sio.emit('server-error', msg, room=sid)
    except Exception as exc:
        msg = f'Could not connect to {host}:{port} — {exc}'
        print(f'(middleware): ERROR — {msg}')
        state.sio.emit('server-error', msg, room=sid)


def create_user(state: MiddlewareState, sid):
    """Register this middleware with the QKD server, getting back a user_id."""
    if not state.server_host:
        state.sio.emit('server-error', 'Not connected to a server.', room=sid)
        return

    try:
        resp = requests.post(state.server_url('/create_user'), json={
            'api_endpoint': (LOCAL_IP, state.middleware_port),
        }, timeout=5)
        resp.raise_for_status()
        state.user_id = resp.json().get('user_id', '')
        print(f'(middleware): Registered with QKD server as user {state.user_id}')
        state.sio.emit('user-registered', {'user_id': state.user_id}, room=sid)
    except Exception as exc:
        msg = f'Failed to register with server — {exc}'
        print(f'(middleware): ERROR — {msg}')
        state.sio.emit('server-error', msg, room=sid)


def join_room(state: MiddlewareState, sid, peer_id=None):
    """Handle join_room from browser — start session or connect to peer."""
    if not state.server_host:
        state.sio.emit('server-error', 'Not connected to a server.', room=sid)
        return
    if not state.user_id:
        state.sio.emit('server-error', 'Not registered with server yet.', room=sid)
        return

    if not peer_id:
        print(f'(middleware): join_room — start session, waiting for peer. '
              f'Share user_id={state.user_id}')
        state.sio.emit('waiting-for-peer', {'user_id': state.user_id}, room=sid)
        return

    if peer_id == state.user_id:
        msg = (f'Cannot connect to yourself (user_id={state.user_id}). '
               f'For same-device testing, run a second middleware on a '
               f'different port: python3 client.py --port 5002')
        print(f'(middleware): ERROR — {msg}')
        state.sio.emit('server-error', msg, room=sid)
        return

    print(f'(middleware): join_room → requesting peer connection '
          f'user={state.user_id} peer={peer_id}')

    try:
        # Use a generous timeout: the server contacts client 1 before responding,
        # but with our non-blocking REST handler client 1 now replies instantly.
        resp = requests.post(state.server_url('/peer_connection'), json={
            'user_id': state.user_id,
            'peer_id': peer_id,
        }, timeout=30)
        data = resp.json()

        if resp.status_code != 200:
            msg = data.get('details', data.get('error_message', 'Unknown error'))
            print(f'(middleware): peer_connection error: {msg}')
            state.sio.emit('server-error', msg, room=sid)
            return

        ws_endpoint = data.get('socket_endpoint')
        if ws_endpoint:
            connect_to_session_ws(state, ws_endpoint, peer_id)
    except Exception as exc:
        msg = f'Peer connection failed — {exc}'
        print(f'(middleware): ERROR — {msg}')
        state.sio.emit('server-error', msg, room=sid)


def leave_room(state: MiddlewareState, sid):
    """Browser leaves the room — stop media, disconnect from session WS."""
    print('(middleware): leave_room → server')
    if state.video_thread is not None:
        state.video_thread.stop()
        state.video_thread = None
    if state.audio_thread is not None:
        state.audio_thread.stop()
        state.audio_thread = None

    if state.server_client.connected:
        try:
            state.server_client.disconnect()
        except Exception:
            pass

    if state.server_host and state.user_id:
        try:
            requests.post(state.server_url('/disconnect_peer'), json={
                'user_id': state.user_id,
            }, timeout=5)
        except Exception as exc:
            print(f'(middleware): leave_room — disconnect_peer failed: {exc}')


def start_video(state: MiddlewareState, room_id):
    """Start or restart the video thread after a room is assigned."""
    if state.video_thread is not None and state.video_thread.is_alive():
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
    devices = []
    try:
        import cv2
    except ImportError:
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
                devices.append({'index': i, 'label': f'Camera {i}'})
                cap.release()
            else:
                cap.release()
                # Don't break — some indices may be skipped on certain systems
    finally:
        # Always restore stderr
        os.dup2(saved_stderr_fd, 2)
        os.close(saved_stderr_fd)

    # Append mock/test sources so users can select them from the camera picker
    from video import MOCK_DEVICE_A, MOCK_DEVICE_B
    devices.append({'index': MOCK_DEVICE_A, 'label': 'Test Pattern A'})
    devices.append({'index': MOCK_DEVICE_B, 'label': 'Test Pattern B'})

    return devices


def start_audio(state: MiddlewareState, room_id):
    """Start or restart the audio thread after a room is assigned."""
    from audio import AudioThread
    if state.audio_thread is not None and state.audio_thread.is_alive():
        state.audio_thread.stop()
        state.audio_thread.join(timeout=2)
    state.audio_thread = AudioThread(state, device=state.audio_device)
    state.audio_thread.start()


def enumerate_audio_devices():
    """Probe for available audio input devices and return a list of dicts.

    Each dict: ``{'index': int, 'label': str}``
    """
    devices = []
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                name = info.get('name', f'Audio Input {i}')
                devices.append({'index': i, 'label': name})
        pa.terminate()
    except ImportError:
        pass
    except Exception:
        pass

    # Append mock/test sources so users can select them from the audio picker
    from audio import MOCK_AUDIO_DEVICE_A, MOCK_AUDIO_DEVICE_B
    devices.append({'index': MOCK_AUDIO_DEVICE_A, 'label': 'Test Tone A'})
    devices.append({'index': MOCK_AUDIO_DEVICE_B, 'label': 'Test Tone B'})

    return devices


# ─── Health checks ────────────────────────────────────────────────────────────

# Require this many consecutive failures before broadcasting server-error.
# A single blip (e.g. server busy during peer_connection) won't trigger a
# browser re-registration cascade.
_HEALTH_FAILURE_THRESHOLD = 2


def _health_check_loop(state: MiddlewareState):
    """Ping the QKD server every 10s.  Emit status changes to all browsers."""
    consecutive_failures = 0
    while True:
        gevent.sleep(10)
        if not state.server_host:
            if state.server_alive:
                state.server_alive = False
                state.sio.emit('server-error', 'Server connection lost.')
            continue
        try:
            resp = requests.get(state.server_url('/admin/status'), timeout=5)
            resp.raise_for_status()
            consecutive_failures = 0
            if not state.server_alive:
                state.server_alive = True
                state.sio.emit('server-connected')
                print('(middleware): Health check — server back online')
        except Exception:
            consecutive_failures += 1
            print(f'(middleware): Health check — server unreachable '
                  f'(failure {consecutive_failures}/{_HEALTH_FAILURE_THRESHOLD})')
            if consecutive_failures >= _HEALTH_FAILURE_THRESHOLD and state.server_alive:
                state.server_alive = False
                state.sio.emit('server-error', 'Server health check failed.')
                print('(middleware): Health check — declaring server down')


def start_health_checks(state: MiddlewareState):
    """Spawn the health-check greenlet (idempotent)."""
    if state.health_greenlet is None or state.health_greenlet.dead:
        state.health_greenlet = gevent.spawn(_health_check_loop, state)
