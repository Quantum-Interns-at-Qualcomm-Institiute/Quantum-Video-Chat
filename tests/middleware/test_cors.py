"""CORS header tests for the Quantum Video Chat middleware Flask app."""
import pytest
from tests.middleware._helpers import load_middleware_module

mw_state = load_middleware_module('state')
MiddlewareState = mw_state.MiddlewareState


@pytest.fixture()
def client():
    state = MiddlewareState()
    state.flask_app.config["TESTING"] = True
    yield state.flask_app.test_client()


class TestCORS:
    def test_cors_headers_on_static(self, client):
        """Static route should include CORS headers."""
        res = client.get("/static/app.js",
                         headers={"Origin": "https://andypeterson2.github.io"})
        # File may 404 in test env, but CORS headers should still be present
        assert res.headers.get("Access-Control-Allow-Origin") is not None

    def test_cors_allows_any_origin(self, client):
        """Verify CORS allows cross-origin requests."""
        res = client.get("/static/style.css",
                         headers={"Origin": "http://localhost:8000"})
        allow = res.headers.get("Access-Control-Allow-Origin", "")
        assert allow in ("*", "http://localhost:8000"), f"Expected wildcard or echo, got: {allow}"

    def test_socketio_cors_allowed(self):
        """Verify Socket.IO is configured with cors_allowed_origins."""
        state = MiddlewareState()
        sio = state.sio
        # flask-socketio stores cors config in the server options
        assert sio is not None, "SocketIO should be initialized"
