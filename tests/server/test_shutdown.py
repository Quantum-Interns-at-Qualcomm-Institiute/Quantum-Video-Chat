"""Tests for server graceful shutdown -- main.py, ServerAPI.graceful_shutdown(),
and the /admin/shutdown endpoint."""
import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from shared.endpoint import Endpoint
from shared.exceptions import ServerError


# ---------------------------------------------------------------------------
# Unit tests: ServerAPI.graceful_shutdown()
# ---------------------------------------------------------------------------

class TestGracefulShutdown:
    """ServerAPI.graceful_shutdown() stops the combined REST+WS server."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        from rest_api import ServerAPI
        from state import APIState
        ServerAPI.state = APIState.INIT
        ServerAPI.server = None
        ServerAPI.socketio = None
        ServerAPI.endpoint = Endpoint('127.0.0.1', 5050)
        yield
        ServerAPI.state = APIState.INIT
        ServerAPI.server = None

    def test_stops_api_when_live(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.LIVE
        ServerAPI.socketio = MagicMock()
        ServerAPI.server = MagicMock(spec=[])

        ServerAPI.graceful_shutdown()

        ServerAPI.socketio.stop.assert_called_once()
        assert ServerAPI.state == APIState.IDLE

    def test_does_not_raise_when_not_live(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.IDLE
        ServerAPI.server = None

        # Should not raise -- kill() failure is caught
        ServerAPI.graceful_shutdown()


# ---------------------------------------------------------------------------
# Unit tests: main._shutdown()
# ---------------------------------------------------------------------------

class TestMainShutdown:
    """The _shutdown() signal handler in main.py calls graceful_shutdown and exits."""

    def test_shutdown_calls_graceful_shutdown_and_exits(self):
        import importlib
        import main as main_mod
        importlib.reload(main_mod)

        with patch('rest_api.ServerAPI.graceful_shutdown') as mock_gs, \
             pytest.raises(SystemExit) as exc_info:
            main_mod._shutdown(sig=signal.SIGINT, frame=None)

        mock_gs.assert_called_once()
        assert exc_info.value.code == 0

    def test_shutdown_with_sigterm(self):
        import importlib
        import main as main_mod
        importlib.reload(main_mod)

        with patch('rest_api.ServerAPI.graceful_shutdown') as mock_gs, \
             pytest.raises(SystemExit) as exc_info:
            main_mod._shutdown(sig=signal.SIGTERM, frame=None)

        mock_gs.assert_called_once()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Unit tests: /admin/shutdown endpoint
# ---------------------------------------------------------------------------

class TestAdminShutdownEndpoint:
    """The /admin/shutdown endpoint triggers graceful shutdown."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        from rest_api import ServerAPI
        from state import APIState
        from admin_routes import init_admin

        ServerAPI.state = APIState.INIT
        ServerAPI.server = MagicMock()
        ServerAPI.server.start_time = time.time()
        ServerAPI.server.user_manager.get_all_users.return_value = {}
        ServerAPI.server.event_log = deque(maxlen=500)
        ServerAPI.endpoint = Endpoint('127.0.0.1', 5050)
        ServerAPI.socketio = MagicMock()
        ServerAPI.state = APIState.IDLE

        self._shutdown_called = False

        def fake_shutdown():
            self._shutdown_called = True

        init_admin(ServerAPI.server, lambda: ServerAPI.state, shutdown_fn=fake_shutdown)

        self.api = ServerAPI
        self.client = ServerAPI.app.test_client()
        yield
        ServerAPI.state = APIState.INIT

    def test_shutdown_returns_200(self):
        response = self.client.post('/admin/shutdown')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'shutting_down'

    def test_shutdown_triggers_callback(self):
        """The shutdown function is scheduled (via Timer) after response."""
        with patch('admin_routes.threading.Timer') as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            response = self.client.post('/admin/shutdown')
            assert response.status_code == 200

            MockTimer.assert_called_once()
            # First arg is delay, second is the function
            args = MockTimer.call_args[0]
            assert args[0] == 0.5  # delay
            mock_timer_instance.start.assert_called_once()

    def test_shutdown_unavailable_without_fn(self):
        """Returns 503 when no shutdown function was registered."""
        from admin_routes import init_admin
        init_admin(self.api.server, lambda: self.api.state, shutdown_fn=None)

        response = self.client.post('/admin/shutdown')
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Integration test: start server process, SIGINT it, verify clean exit
# ---------------------------------------------------------------------------

class TestServerProcessShutdown:
    """Integration test: start the real server process and verify Ctrl+C works."""

    @pytest.fixture
    def server_dir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'server',
        )

    def _start_server(self, server_dir, rest_port):
        """Start server/main.py and wait for it to begin listening."""
        logs_dir = os.path.join(server_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        env = os.environ.copy()
        env['QVC_LOCAL_IP'] = '127.0.0.1'
        env['QVC_SERVER_REST_PORT'] = str(rest_port)

        proc = subprocess.Popen(
            [sys.executable, 'main.py'],
            cwd=server_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for the server to start listening
        import socket
        for _ in range(40):  # up to 4 seconds
            time.sleep(0.1)
            if proc.poll() is not None:
                _, stderr = proc.communicate(timeout=1)
                return None, f"Server exited early: {stderr.decode()[:500]}"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)
                s.connect(('127.0.0.1', rest_port))
                s.close()
                return proc, None
            except (ConnectionRefusedError, OSError):
                pass

        proc.kill()
        proc.wait(timeout=2)
        return None, "Server did not start in time"

    def test_sigint_exits_cleanly(self, server_dir):
        """Start server/main.py, send SIGINT, assert process exits within 5s."""
        proc, err = self._start_server(server_dir, 15050)
        if proc is None:
            pytest.skip(err)

        try:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
                pytest.fail("Server did not exit within 5s after SIGINT")

            assert proc.returncode is not None, "Server process did not terminate"
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)

    def test_sigterm_exits_cleanly(self, server_dir):
        """Start server/main.py, send SIGTERM, assert process exits within 5s."""
        proc, err = self._start_server(server_dir, 15052)
        if proc is None:
            pytest.skip(err)

        try:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
                pytest.fail("Server did not exit within 5s after SIGTERM")

            assert proc.returncode is not None, "Server process did not terminate"
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
