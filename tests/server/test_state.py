"""Tests for server/state.py — APIState and SocketState enums."""
import pytest
import os
import importlib.util

# Import server/state.py specifically, not shared/state.py
_server_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'server')
_spec = importlib.util.spec_from_file_location("server_state", os.path.join(_server_dir, "state.py"))
server_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server_state)
APIState = server_state.APIState
SocketState = server_state.SocketState


class TestAPIState:
    def test_members(self):
        assert APIState.INIT.value == 'INIT'
        assert APIState.IDLE.value == 'IDLE'
        assert APIState.LIVE.value == 'LIVE'

    def test_total_members(self):
        assert len(APIState) == 3


class TestSocketState:
    def test_members(self):
        assert SocketState.NEW.value == 'NEW'
        assert SocketState.INIT.value == 'INIT'
        assert SocketState.LIVE.value == 'LIVE'
        assert SocketState.OPEN.value == 'OPEN'

    def test_ordering(self):
        assert SocketState.NEW < SocketState.INIT
        assert SocketState.INIT < SocketState.LIVE
        assert SocketState.LIVE < SocketState.OPEN

    def test_ordering_gt(self):
        assert SocketState.OPEN > SocketState.NEW

    def test_ordering_ge(self):
        assert SocketState.LIVE >= SocketState.LIVE
        assert SocketState.OPEN >= SocketState.NEW

    def test_equality(self):
        assert SocketState.NEW == SocketState.NEW
        assert not (SocketState.NEW == SocketState.INIT)

    def test_cross_type_returns_not_implemented(self):
        result = SocketState.NEW.__lt__('string')
        assert result is NotImplemented

    def test_total_members(self):
        assert len(SocketState) == 4
