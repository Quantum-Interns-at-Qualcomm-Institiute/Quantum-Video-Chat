"""Tests for middleware/client/api.py — ClientAPI class."""
import pytest
import json
from unittest.mock import MagicMock, patch
from shared.endpoint import Endpoint
from shared.exceptions import ServerError


def _make_api(state='INIT', **overrides):
    """Create a ClientAPI instance without starting it."""
    from client.api import ClientAPI, APIState
    mock_client = overrides.pop('client', MagicMock())
    mock_client.api_endpoint = overrides.pop('endpoint', Endpoint('127.0.0.1', 4000))
    api = ClientAPI(mock_client)
    if state:
        api.state = APIState[state]
    return api


class TestClientAPIState:
    def test_init_sets_state(self):
        api = _make_api()
        from client.api import APIState
        assert api.state == APIState.INIT
        assert api.client is not None

    def test_kill_when_not_live_returns(self):
        api = _make_api(state='INIT')
        # Should not raise, just returns
        api.kill()

    def test_kill_when_live(self):
        from client.api import APIState
        api = _make_api(state='LIVE')
        api.http_server = MagicMock()
        api.kill()
        assert api.state == APIState.INIT
        api.http_server.stop.assert_called_once()


class TestAPIStateOrdering:
    def test_ordering(self):
        from client.api import APIState
        assert APIState.NEW < APIState.INIT
        assert APIState.INIT < APIState.LIVE

    def test_cross_type(self):
        from client.api import APIState
        result = APIState.NEW.__lt__('string')
        assert result is NotImplemented


class TestRemoveLastPeriod:
    def test_with_period(self):
        from client.api import _remove_last_period
        assert _remove_last_period("hello.") == "hello"

    def test_without_period(self):
        from client.api import _remove_last_period
        assert _remove_last_period("hello") == "hello"

    def test_single_period(self):
        from client.api import _remove_last_period
        assert _remove_last_period(".") == ""


class TestClientAPIPeerConnectionEndpoint:
    @pytest.fixture(autouse=True)
    def setup_api(self):
        self.api = _make_api(state='LIVE')
        self.client = self.api.app.test_client()
        yield

    def test_peer_connection_success(self):
        self.api.client.handle_peer_connection.return_value = True

        response = self.client.post('/peer_connection',
            data=json.dumps({
                'peer_id': 'p1',
                'socket_endpoint': ('127.0.0.1', 3000)
            }),
            content_type='application/json')
        assert response.status_code == 200

    def test_peer_connection_refused(self):
        self.api.client.handle_peer_connection.return_value = False

        response = self.client.post('/peer_connection',
            data=json.dumps({
                'peer_id': 'p1',
                'socket_endpoint': ('127.0.0.1', 3000)
            }),
            content_type='application/json')
        assert response.status_code == 418

    def test_peer_connection_exception(self):
        self.api.client.handle_peer_connection.side_effect = Exception("boom")

        response = self.client.post('/peer_connection',
            data=json.dumps({
                'peer_id': 'p1',
                'socket_endpoint': ('127.0.0.1', 3000)
            }),
            content_type='application/json')
        assert response.status_code == 500

    def test_peer_connection_with_session_settings(self):
        """session_settings should be forwarded from the request body."""
        self.api.client.handle_peer_connection.return_value = True

        settings = {'video_width': 320, 'frame_rate': 30}
        response = self.client.post('/peer_connection',
            data=json.dumps({
                'peer_id': 'p1',
                'socket_endpoint': ('127.0.0.1', 3000),
                'session_settings': settings,
            }),
            content_type='application/json')
        assert response.status_code == 200
        call_kwargs = self.api.client.handle_peer_connection.call_args
        assert call_kwargs[1].get('session_settings') == settings


class TestClientAPIPeerDisconnectedEndpoint:
    @pytest.fixture(autouse=True)
    def setup_api(self):
        self.api = _make_api(state='LIVE')
        self.client = self.api.app.test_client()
        yield

    def test_peer_disconnected_success(self):
        response = self.client.post('/peer_disconnected',
            data=json.dumps({'peer_id': 'peer1'}),
            content_type='application/json')
        assert response.status_code == 200
        self.api.client.handle_peer_disconnected.assert_called_once_with('peer1')

    def test_peer_disconnected_missing_param(self):
        response = self.client.post('/peer_disconnected',
            data=json.dumps({}),
            content_type='application/json')
        # Missing peer_id should trigger a parameter error
        assert response.status_code != 200


class TestClientAPIRun:
    def test_run_when_new_raises(self):
        api = _make_api(state='NEW')
        with pytest.raises(ServerError, match="Cannot start API before initialization"):
            api.run()

    def test_run_when_already_live_raises(self):
        api = _make_api(state='LIVE')
        with pytest.raises(ServerError, match="Cannot start API: already running"):
            api.run()

    def test_run_retries_on_os_error(self):
        """When the port is in use, run() increments port and retries."""
        api = _make_api(state='INIT')

        call_count = [0]
        def mock_serve(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("Address already in use")
            # Second call succeeds (exits normally)

        with patch('client.api.WSGIServer') as MockWSGI:
            MockWSGI.return_value.serve_forever = mock_serve
            api.run()

        assert call_count[0] == 2
        # Port should have been incremented
        api.client.set_api_endpoint.assert_called_once()


class TestBackwardCompatInit:
    """ClientAPI.init() still works as a deprecated alias."""
    def test_init_returns_instance(self):
        from client.api import ClientAPI
        mock_client = MagicMock()
        mock_client.api_endpoint = Endpoint('127.0.0.1', 4000)
        instance = ClientAPI.init(mock_client)
        assert isinstance(instance, ClientAPI)
