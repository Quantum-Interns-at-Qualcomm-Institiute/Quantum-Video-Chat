"""Tests for shared/state.py — ClientState enum."""
import pytest
from shared.state import ClientState


class TestClientState:
    def test_members_exist(self):
        assert ClientState.NEW.value == 'NEW'
        assert ClientState.INIT.value == 'INIT'
        assert ClientState.LIVE.value == 'LIVE'
        assert ClientState.CONNECTED.value == 'CONNECTED'

    def test_ordering_lt(self):
        assert ClientState.NEW < ClientState.INIT
        assert ClientState.INIT < ClientState.LIVE
        assert ClientState.LIVE < ClientState.CONNECTED

    def test_ordering_gt(self):
        assert ClientState.CONNECTED > ClientState.NEW
        assert ClientState.LIVE > ClientState.INIT

    def test_ordering_eq(self):
        assert ClientState.NEW == ClientState.NEW
        assert not (ClientState.NEW == ClientState.INIT)

    def test_ordering_le(self):
        assert ClientState.NEW <= ClientState.NEW
        assert ClientState.NEW <= ClientState.INIT

    def test_ordering_ge(self):
        assert ClientState.CONNECTED >= ClientState.CONNECTED
        assert ClientState.CONNECTED >= ClientState.NEW

    def test_cross_type_returns_not_implemented(self):
        result = ClientState.NEW.__lt__('string')
        assert result is NotImplemented

    def test_total_members(self):
        assert len(ClientState) == 4
