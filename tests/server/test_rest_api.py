"""Tests for server/rest_api.py -- ServerAPI Flask routes."""
import json
from unittest.mock import MagicMock

import pytest

from shared.endpoint import Endpoint
from shared.exceptions import BadRequest, ServerError


class TestServerAPIRoutes:
    @pytest.fixture(autouse=True)
    def setup_api(self):
        """Reset ServerAPI state and set up a test client."""
        from rest_api import ServerAPI
        from state import APIState

        # Reset class state
        ServerAPI.state = APIState.INIT
        ServerAPI.server = MagicMock()
        ServerAPI.endpoint = Endpoint("127.0.0.1", 5050)
        ServerAPI.socketio = MagicMock()
        ServerAPI.state = APIState.IDLE

        self.api = ServerAPI
        self.client = ServerAPI.app.test_client()
        yield
        # Reset after test
        ServerAPI.state = APIState.INIT

    def test_create_user_success(self):
        self.api.server.add_user.return_value = "abc12"
        self.api.state = MagicMock()  # bypass state checks in HandleExceptions

        response = self.client.post("/create_user",
            data=json.dumps({"api_endpoint": ["127.0.0.1", 4000]}),
            content_type="application/json")
        data = json.loads(response.data)
        assert response.status_code == 200
        assert data["user_id"] == "abc12"

    def test_create_user_server_error(self):
        self.api.server.add_user.side_effect = ServerError("boom")

        response = self.client.post("/create_user",
            data=json.dumps({"api_endpoint": ["127.0.0.1", 4000]}),
            content_type="application/json")
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["error_code"] == "500"

    def test_peer_connection_success(self):
        mock_endpoint = MagicMock()
        mock_endpoint.__iter__ = MagicMock(return_value=iter(("127.0.0.1", 5050)))
        self.api.server.handle_peer_connection.return_value = (mock_endpoint, "test-session-id")

        response = self.client.post("/peer_connection",
            data=json.dumps({"user_id": "u1", "peer_id": "u2"}),
            content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "socket_endpoint" in data
        assert "session_id" in data
        assert data["session_id"] == "test-session-id"

    def test_peer_connection_bad_request(self):
        self.api.server.handle_peer_connection.side_effect = BadRequest("bad")

        response = self.client.post("/peer_connection",
            data=json.dumps({"user_id": "u1", "peer_id": "u2"}),
            content_type="application/json")
        assert response.status_code == 400

    def test_remove_user_success(self):
        self.api.server.remove_user.return_value = None

        response = self.client.delete("/remove_user",
            data=json.dumps({"user_id": "abc12"}),
            content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["user_id"] == "abc12"

    def test_disconnect_peer_success(self):
        self.api.server.disconnect_peer.return_value = None

        response = self.client.post("/disconnect_peer",
            data=json.dumps({"user_id": "abc12"}),
            content_type="application/json")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "disconnected"


class TestServerAPIStateMachine:
    def test_init_when_live_raises(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.LIVE
        mock_server = MagicMock()
        mock_server.api_endpoint = Endpoint("127.0.0.1", 5050)

        with pytest.raises(ServerError, match="Cannot reconfigure"):
            ServerAPI.init(mock_server)

    def test_init_sets_idle(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.INIT
        mock_server = MagicMock()
        mock_server.api_endpoint = Endpoint("127.0.0.1", 5050)

        ServerAPI.init(mock_server)
        assert ServerAPI.state == APIState.IDLE

    def test_start_before_init_raises(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.INIT
        with pytest.raises(ServerError, match="before initialization"):
            ServerAPI.start()

    def test_kill_when_not_live_raises(self):
        from rest_api import ServerAPI
        from state import APIState

        ServerAPI.state = APIState.IDLE
        with pytest.raises(ServerError, match="Cannot kill"):
            ServerAPI.kill()
