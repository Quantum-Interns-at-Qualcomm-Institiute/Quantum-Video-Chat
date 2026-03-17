"""Tests for middleware/client/util.py — re-exports."""
from client.util import ClientState, get_parameters


class TestReExports:
    def test_client_state_accessible(self):
        assert ClientState.NEW.value == 'NEW'

    def test_get_parameters_accessible(self):
        result = get_parameters({'a': 1}, 'a')
        assert result == (1,)
