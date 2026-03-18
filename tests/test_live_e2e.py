"""
Live end-to-end integration test.

Spawns three real OS processes — a server, a passive client (B), and an
initiating client (A) — on localhost using non-conflicting ports.  Both
clients use DEBUG_VIDEO (random B&W frames, no camera) and DebugEncryption
(pass-through, no key-file needed).  The test asserts that at least one
video frame is received by *each* client within TIMEOUT seconds.

Run:
    cd <worktree>
    python -m pytest tests/test_live_e2e.py -v -s
"""

import os
import sys
import multiprocessing as mp
import threading
import time

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_S_REST   = 15050   # server REST port
_S_WS     = 13000   # server WebSocket port
_CA_API   = 14000   # client-A REST port
_CB_API   = 14001   # client-B REST port

_TIMEOUT    = 30    # seconds to wait for frames / messages
_MIN_FRAMES = 1     # frames required per client

# Separate ports for the message test to avoid TIME_WAIT collisions
# when both tests run in the same pytest session.
_S_REST_MSG  = 15051
_S_WS_MSG    = 13001
_CA_API_MSG  = 14002
_CB_API_MSG  = 14003


# ---------------------------------------------------------------------------
# Helpers shared between the main process and subprocesses
# (defined at module level so spawn can pickle them)
# ---------------------------------------------------------------------------

def _setup_path():
    """Replicate conftest.py path setup inside a spawned subprocess."""
    root = _WORKTREE
    for p in [root,
              os.path.join(root, 'server'),
              os.path.join(root, 'middleware')]:
        if p not in sys.path:
            sys.path.insert(0, p)


class _ReportingAdapter:
    """
    Minimal FrontendAdapter (duck-typed) that puts the client_id into
    *frames_q* each time a peer video frame arrives.
    """

    def __init__(self, client_id: str, frames_q):
        self._id = client_id
        self._q  = frames_q

    def send_frame(self, data: bytes) -> None:
        """Peer video frame received — report to the test process."""
        self._q.put(self._id)

    def send_self_frame(self, data, width, height) -> None:
        pass  # local preview; ignored

    def on_peer_id(self, callback) -> None:
        pass  # no GUI to trigger connect_to_peer

    def send_status(self, event: str, data=None) -> None:
        pass  # connection-status events; ignored in test


# ---------------------------------------------------------------------------
# Subprocess target functions
# ---------------------------------------------------------------------------

def _server_main(rest_port, ws_port, ready, error_q):
    """
    Subprocess: run a real ServerAPI (REST) + SocketAPI (WebSocket).
    Signals *ready* once the REST server is bound, then blocks until killed.
    """
    try:
        os.environ['QVC_SERVER_REST_PORT'] = str(rest_port)
        os.environ['QVC_SERVER_WS_PORT']   = str(ws_port)
        _setup_path()

        from threading import Thread as _Thread
        from rest_api import ServerAPI       # server/rest_api.py
        from server import Server            # server/server.py
        from shared.endpoint import Endpoint

        server = Server(Endpoint('127.0.0.1', rest_port))
        ServerAPI.init(server)

        t = _Thread(target=ServerAPI.start, daemon=True)
        t.start()
        time.sleep(0.5)   # give the gevent WSGI server time to bind
        ready.set()

        threading.Event().wait()   # block forever until SIGTERM

    except Exception:
        import traceback
        error_q.put(('server', traceback.format_exc()))


def _client_main(client_id, server_rest, my_api_port, is_initiator,
                 peer_q, frames_q, ready, error_q):
    """
    Subprocess: run a real Client (REST API + optional WebSocket).

    Passive (is_initiator=False):
      1. Connect to server → get user_id
      2. Put user_id in peer_q for the initiator
      3. Set ready; wait for the server to contact us via /peer_connection
         (handled automatically by our ClientAPI daemon thread)

    Initiator (is_initiator=True):
      1. Connect to server → get user_id
      2. Set ready; wait for passive client's user_id from peer_q
      3. Call connect_to_peer(peer_id)

    After the websocket session is established, background threads stream
    video; received frames are reported via frames_q.
    """
    try:
        os.environ['QVC_DEBUG_VIDEO']     = 'true'
        os.environ['QVC_CLIENT_API_PORT'] = str(my_api_port)
        _setup_path()

        # ---------------------------------------------------------------
        # Patch shared.config BEFORE any module that reads it is imported.
        # This avoids FileKeyGenerator trying to open key.bin and keeps
        # encryption deterministic across separate processes.
        # ---------------------------------------------------------------
        import shared.config
        from shared.encryption import EncryptSchemes, KeyGenerators
        shared.config.DEFAULT_ENCRYPT_SCHEME = EncryptSchemes.DEBUG
        shared.config.DEFAULT_KEY_GENERATOR  = KeyGenerators.RANDOM

        # ---------------------------------------------------------------
        # Import client.av NOW (before client.client triggers it) so we
        # can patch out the audio namespace — opening audio devices in a
        # headless test process causes PortAudio errors.
        # ---------------------------------------------------------------
        import client.av as _cav
        from shared.av.namespaces import BroadcastFlaskNamespace as _BNS
        _cav.AV.namespaces = {
            '/video': (_BNS, _cav.ClientVideoClientNamespace),
        }

        from client.client import Client
        from shared.endpoint import Endpoint

        adapter   = _ReportingAdapter(client_id, frames_q)
        server_ep = Endpoint('127.0.0.1', server_rest)
        api_ep    = Endpoint('127.0.0.1', my_api_port)

        # Client.__init__ starts the ClientAPI and calls connect() to register
        # with the server and obtain a user_id.
        client = Client(adapter, server_endpoint=server_ep, api_endpoint=api_ep)

        if not is_initiator:
            # Publish our user_id so the initiator can request a connection.
            peer_q.put(client.user_id)
            ready.set()
            # The server will POST to our ClientAPI when the initiator calls
            # connect_to_peer; that handler runs in our ClientAPI daemon thread.
        else:
            ready.set()
            peer_id = peer_q.get(timeout=20)
            # This call is blocking:
            #   POST /peer_connection → server starts WebSocket + contacts peer
            #   → returns WebSocket endpoint → we connect to WebSocket
            client.connect_to_peer(peer_id)

        # Keep the process alive while background threads stream video.
        while True:
            time.sleep(1)

    except Exception:
        import traceback
        error_q.put((client_id, traceback.format_exc()))


def _client_msg_main(client_id, server_rest, my_api_port, is_initiator,
                     peer_q, msg_q, ready, error_q):
    """
    Subprocess: run a real Client and participate in a bidirectional text-
    message exchange.

    * Client.display_message is monkey-patched on the class before the
      Client instance is created so that the bound method captured by
      SocketClient.init routes received messages into *msg_q*.
    * After the WebSocket is live the client sends one message; the server
      broadcasts it to all connected clients (including the sender's echo).
    * msg_q entries: {'receiver': client_id, 'sender': raw_sid, 'text': str}
    """
    try:
        os.environ['QVC_DEBUG_VIDEO']     = 'true'
        os.environ['QVC_CLIENT_API_PORT'] = str(my_api_port)
        _setup_path()

        import shared.config
        from shared.encryption import EncryptSchemes, KeyGenerators
        shared.config.DEFAULT_ENCRYPT_SCHEME = EncryptSchemes.DEBUG
        shared.config.DEFAULT_KEY_GENERATOR  = KeyGenerators.RANDOM

        import client.av as _cav
        from shared.av.namespaces import BroadcastFlaskNamespace as _BNS
        _cav.AV.namespaces = {
            '/video': (_BNS, _cav.ClientVideoClientNamespace),
        }

        # Patch Client.display_message BEFORE creating the instance.
        # self.display_message is resolved at connect_to_websocket() call time
        # via normal Python descriptor lookup, so the patch applies to every
        # Client instance created in this process.
        import client.client as _cc

        def _capture(self_ref, sender_id, text):
            msg_q.put({'receiver': client_id, 'sender': sender_id, 'text': text})

        _cc.Client.display_message = _capture

        from client.client import Client
        from shared.endpoint import Endpoint

        class _NoOpAdapter:
            """Minimal FrontendAdapter; frames are irrelevant for this test."""
            def send_frame(self, data): pass
            def send_self_frame(self, data, w, h): pass
            def on_peer_id(self, cb): pass
            def send_status(self, ev, data=None): pass

        server_ep = Endpoint('127.0.0.1', server_rest)
        api_ep    = Endpoint('127.0.0.1', my_api_port)
        client    = Client(_NoOpAdapter(), server_endpoint=server_ep,
                           api_endpoint=api_ep)

        if not is_initiator:
            peer_q.put(client.user_id)
            ready.set()

            # The server will POST /peer_connection to our ClientAPI daemon
            # thread.  Poll until the WebSocket is up, then send a reply.
            def _send_when_ready():
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    sc = getattr(client, 'websocket_instance', None)
                    if sc is not None and sc.is_connected():
                        time.sleep(0.3)   # let the channel stabilise
                        sc.send_message(f'hello from {client_id}')
                        return
                    time.sleep(0.1)

            import threading as _t
            _t.Thread(target=_send_when_ready, daemon=True).start()
        else:
            ready.set()
            peer_id = peer_q.get(timeout=20)
            # connect_to_peer is synchronous; WebSocket is live on return.
            client.connect_to_peer(peer_id)
            client.websocket_instance.send_message(f'hello from {client_id}')

        # Keep the process alive while messages flow.
        while True:
            time.sleep(1)

    except Exception:
        import traceback
        error_q.put((client_id, traceback.format_exc()))


# ---------------------------------------------------------------------------
# Helpers used in the main test process
# ---------------------------------------------------------------------------

def _check_errors(error_q):
    """Drain error_q and fail immediately if any subprocess reported an error."""
    errors = []
    while not error_q.empty():
        try:
            errors.append(error_q.get_nowait())
        except Exception:
            break
    if errors:
        msgs = '\n\n'.join(f"[{who}]\n{tb}" for who, tb in errors)
        pytest.fail(f"Subprocess error(s):\n{msgs}")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_live_video_flow():
    """
    Three-process integration test:
        server + client_a (initiator) + client_b (passive)

    Asserts that at least MIN_FRAMES video frames flow from each client to
    the other within TIMEOUT seconds.
    """
    # Make subprocesses able to re-import this module (needed for spawn pickle).
    _extra = os.pathsep.join([
        os.path.join(_WORKTREE, 'tests'),
        _WORKTREE,
    ])
    _prev_pp = os.environ.get('PYTHONPATH', '')
    os.environ['PYTHONPATH'] = (
        f"{_extra}{os.pathsep}{_prev_pp}" if _prev_pp else _extra
    )

    ctx = mp.get_context('spawn')

    server_ready = ctx.Event()
    ca_ready     = ctx.Event()
    cb_ready     = ctx.Event()
    peer_q       = ctx.Queue()   # passive → initiator: user_id string
    frames_q     = ctx.Queue()   # both → test: client_id strings
    error_q      = ctx.Queue()   # any → test: (who, traceback) tuples

    procs = []

    def _spawn(target, args, name):
        p = ctx.Process(target=target, args=args, daemon=True, name=name)
        p.start()
        procs.append(p)
        return p

    try:
        # -- Server ----------------------------------------------------------
        _spawn(_server_main, (_S_REST, _S_WS, server_ready, error_q),
               'e2e-server')
        assert server_ready.wait(timeout=15), \
            "Server did not start within 15 s"
        _check_errors(error_q)

        # -- Clients ---------------------------------------------------------
        # Start client B (passive) FIRST so its user_id is in peer_q before
        # client A tries to read it.
        _spawn(_client_main,
               ('client_b', _S_REST, _CB_API, False,
                peer_q, frames_q, cb_ready, error_q),
               'e2e-client-b')
        _spawn(_client_main,
               ('client_a', _S_REST, _CA_API, True,
                peer_q, frames_q, ca_ready, error_q),
               'e2e-client-a')

        assert cb_ready.wait(timeout=20), \
            "Client B did not connect to server within 20 s"
        assert ca_ready.wait(timeout=20), \
            "Client A did not connect to server within 20 s"
        _check_errors(error_q)

        # -- Collect frames --------------------------------------------------
        received = {'client_a': 0, 'client_b': 0}
        deadline = time.monotonic() + _TIMEOUT

        while time.monotonic() < deadline:
            _check_errors(error_q)
            try:
                who = frames_q.get(timeout=1.0)
                received[who] = received.get(who, 0) + 1
            except Exception:
                pass  # queue.Empty — keep waiting
            if all(v >= _MIN_FRAMES for v in received.values()):
                break

        _check_errors(error_q)

        assert received['client_a'] >= _MIN_FRAMES, (
            f"client_a received only {received['client_a']} frame(s) "
            f"(expected >= {_MIN_FRAMES}); all received = {received}"
        )
        assert received['client_b'] >= _MIN_FRAMES, (
            f"client_b received only {received['client_b']} frame(s) "
            f"(expected >= {_MIN_FRAMES}); all received = {received}"
        )

    finally:
        for p in reversed(procs):
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
        # Restore PYTHONPATH
        if _prev_pp:
            os.environ['PYTHONPATH'] = _prev_pp
        else:
            os.environ.pop('PYTHONPATH', None)


def test_live_message_flow():
    """
    Three-process integration test: server + client_a (initiator) + client_b (passive).

    After establishing a WebSocket connection, each client sends a text message.
    The server broadcasts each message to all connected clients.  The test asserts
    that within TIMEOUT seconds:
      - client_b received a message whose text contains "client_a"
        (proving client_a's message traversed the server and arrived at client_b)
      - client_a received a message whose text contains "client_b"
        (proving client_b's reply traversed the server and arrived at client_a)
    """
    _extra = os.pathsep.join([
        os.path.join(_WORKTREE, 'tests'),
        _WORKTREE,
    ])
    _prev_pp = os.environ.get('PYTHONPATH', '')
    os.environ['PYTHONPATH'] = (
        f"{_extra}{os.pathsep}{_prev_pp}" if _prev_pp else _extra
    )

    ctx = mp.get_context('spawn')

    server_ready = ctx.Event()
    ca_ready     = ctx.Event()
    cb_ready     = ctx.Event()
    peer_q       = ctx.Queue()   # passive → initiator: user_id string
    msg_q        = ctx.Queue()   # both → test: {'receiver','sender','text'} dicts
    error_q      = ctx.Queue()

    procs = []

    def _spawn(target, args, name):
        p = ctx.Process(target=target, args=args, daemon=True, name=name)
        p.start()
        procs.append(p)
        return p

    try:
        # -- Server ----------------------------------------------------------
        _spawn(_server_main,
               (_S_REST_MSG, _S_WS_MSG, server_ready, error_q),
               'msg-server')
        assert server_ready.wait(timeout=15), \
            "Server did not start within 15 s"
        _check_errors(error_q)

        # -- Clients ---------------------------------------------------------
        # Start client_b first so its user_id reaches peer_q before client_a needs it.
        _spawn(_client_msg_main,
               ('client_b', _S_REST_MSG, _CB_API_MSG, False,
                peer_q, msg_q, cb_ready, error_q),
               'msg-client-b')
        _spawn(_client_msg_main,
               ('client_a', _S_REST_MSG, _CA_API_MSG, True,
                peer_q, msg_q, ca_ready, error_q),
               'msg-client-a')

        assert cb_ready.wait(timeout=20), \
            "Client B did not connect to server within 20 s"
        assert ca_ready.wait(timeout=20), \
            "Client A did not connect to server within 20 s"
        _check_errors(error_q)

        # -- Collect messages ------------------------------------------------
        # Key: receiver client_id → list of entry dicts
        received = {'client_a': [], 'client_b': []}
        deadline = time.monotonic() + _TIMEOUT

        while time.monotonic() < deadline:
            _check_errors(error_q)
            try:
                entry = msg_q.get(timeout=1.0)
                receiver = entry.get('receiver')
                if receiver in received:
                    received[receiver].append(entry)
            except Exception:
                pass  # queue.Empty — keep waiting

            # Stop as soon as each client has received at least one message
            # whose text mentions the *other* client.
            a_has_b = any('client_b' in m['text'] for m in received['client_a'])
            b_has_a = any('client_a' in m['text'] for m in received['client_b'])
            if a_has_b and b_has_a:
                break

        _check_errors(error_q)

        a_texts = [m['text'] for m in received['client_a']]
        b_texts = [m['text'] for m in received['client_b']]

        assert any('client_b' in t for t in a_texts), (
            f"client_a never received a message from client_b. "
            f"client_a received: {a_texts}"
        )
        assert any('client_a' in t for t in b_texts), (
            f"client_b never received a message from client_a. "
            f"client_b received: {b_texts}"
        )

    finally:
        for p in reversed(procs):
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
        if _prev_pp:
            os.environ['PYTHONPATH'] = _prev_pp
        else:
            os.environ.pop('PYTHONPATH', None)
