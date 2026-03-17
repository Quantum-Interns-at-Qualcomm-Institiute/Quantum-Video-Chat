"""Tests for the retry-with-backoff logic in ServerCommsMixin.connect()."""
import pytest
from unittest.mock import MagicMock, patch, call
from shared.endpoint import Endpoint
from shared.state import ClientState
from shared.exceptions import ConnectionRefused, UnexpectedResponse
from client.server_comms import ServerCommsMixin


class ConcreteClient(ServerCommsMixin):
    """Minimal host class for ServerCommsMixin testing."""
    def __init__(self):
        self.server_endpoint = Endpoint('127.0.0.1', 5050)
        self.api_endpoint = Endpoint('127.0.0.1', 4000)
        self.state = ClientState.NEW
        self.user_id = None
        self.adapter = MagicMock()

    def connect_to_websocket(self, endpoint):
        pass


def _make_success_response(user_id='abc12'):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {'user_id': user_id}
    return r


def _make_connection_error():
    import requests
    return requests.exceptions.ConnectionError("refused")


class TestConnectRetry:
    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_succeeds_on_first_attempt(self, mock_post, mock_sleep):
        mock_post.return_value = _make_success_response()
        client = ConcreteClient()
        result = client.connect(max_retries=3, base_delay=1.0)
        assert result is True
        assert client.user_id == 'abc12'
        assert client.state == ClientState.LIVE
        mock_sleep.assert_not_called()

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_succeeds_after_retries(self, mock_post, mock_sleep):
        """Fail 3 times, succeed on 4th attempt."""
        err = _make_connection_error()
        mock_post.side_effect = [err, err, err, _make_success_response()]
        client = ConcreteClient()
        result = client.connect(max_retries=5, base_delay=1.0)
        assert result is True
        assert client.user_id == 'abc12'
        assert mock_post.call_count == 4
        assert mock_sleep.call_count == 3  # slept before attempts 2, 3, 4

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_all_retries_exhausted_returns_false(self, mock_post, mock_sleep):
        mock_post.side_effect = _make_connection_error()
        client = ConcreteClient()
        result = client.connect(max_retries=2, base_delay=1.0)
        assert result is False
        assert mock_post.call_count == 3  # initial + 2 retries
        assert client.state == ClientState.NEW  # not changed

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_exponential_backoff_delays(self, mock_post, mock_sleep):
        """Verify delay sequence: 1, 2, 4, 8."""
        mock_post.side_effect = _make_connection_error()
        client = ConcreteClient()
        client.connect(max_retries=4, base_delay=1.0)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0, 8.0]

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_delay_capped_at_30_seconds(self, mock_post, mock_sleep):
        """With base_delay=2, the 5th retry would be 2*2^4=32, capped at 30."""
        mock_post.side_effect = _make_connection_error()
        client = ConcreteClient()
        client.connect(max_retries=6, base_delay=2.0)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        # base_delay=2: 2, 4, 8, 16, 30, 30
        assert delays == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0]

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_status_events_emitted_on_retry(self, mock_post, mock_sleep):
        """Each attempt should emit server_connecting with attempt info."""
        err = _make_connection_error()
        mock_post.side_effect = [err, err, _make_success_response()]
        client = ConcreteClient()
        client.connect(max_retries=3, base_delay=1.0)

        connecting_calls = [
            c for c in client.adapter.send_status.call_args_list
            if c.args[0] == 'server_connecting'
        ]
        assert len(connecting_calls) == 3  # attempts 1, 2, 3
        # Verify attempt numbers
        assert connecting_calls[0].args[1]['attempt'] == 1
        assert connecting_calls[1].args[1]['attempt'] == 2
        assert connecting_calls[2].args[1]['attempt'] == 3

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_server_error_emitted_on_exhaustion(self, mock_post, mock_sleep):
        mock_post.side_effect = _make_connection_error()
        client = ConcreteClient()
        client.connect(max_retries=1, base_delay=1.0)

        events = [c.args[0] for c in client.adapter.send_status.call_args_list]
        assert 'server_error' in events

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_unexpected_response_not_retried(self, mock_post, mock_sleep):
        """UnexpectedResponse errors should raise immediately, not retry."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'details': 'server broke'}
        mock_response.reason = 'Internal Server Error'
        mock_post.return_value = mock_response

        client = ConcreteClient()
        with pytest.raises(UnexpectedResponse):
            client.connect(max_retries=5, base_delay=1.0)
        assert mock_post.call_count == 1  # no retries
        mock_sleep.assert_not_called()

    @patch('client.server_comms.time.sleep')
    @patch('client.server_comms.requests.post')
    def test_zero_retries_is_single_attempt(self, mock_post, mock_sleep):
        mock_post.side_effect = _make_connection_error()
        client = ConcreteClient()
        result = client.connect(max_retries=0, base_delay=1.0)
        assert result is False
        assert mock_post.call_count == 1
        mock_sleep.assert_not_called()
