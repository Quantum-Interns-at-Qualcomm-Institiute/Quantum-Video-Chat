"""Tests for server/utils/user.py — User class and UserState enum."""
from utils.user import User, UserState

from shared.endpoint import Endpoint


class TestUserState:
    def test_members(self):
        assert UserState.IDLE.value == 'IDLE'
        assert UserState.AWAITING_CONNECTION.value == 'AWAITING CONNECTION'
        assert UserState.CONNECTED.value == 'CONNECTED'

    def test_total_members(self):
        assert len(UserState) == 3


class TestUser:
    def test_default_construction(self):
        ep = Endpoint('192.168.1.1', 5000)
        user = User(ep)
        assert user.state == UserState.IDLE
        assert user.peer is None

    def test_custom_state_and_peer(self):
        ep = Endpoint('192.168.1.1', 5000)
        user = User(ep, state=UserState.CONNECTED, peer='peer123')
        assert user.state == UserState.CONNECTED
        assert user.peer == 'peer123'

    def test_endpoint_is_new_instance(self):
        ep = Endpoint('192.168.1.1', 5000)
        user = User(ep)
        # Should be a different Endpoint object (re-constructed via Endpoint(*ep))
        assert user.api_endpoint is not ep
        assert str(user.api_endpoint) == str(ep)

    def test_iter(self):
        ep = Endpoint('192.168.1.1', 5000)
        user = User(ep, state=UserState.IDLE, peer=None)
        items = list(user)
        assert len(items) == 3
        assert isinstance(items[0], Endpoint)
        assert items[1] == UserState.IDLE
        assert items[2] is None

    def test_str(self):
        ep = Endpoint('192.168.1.1', 5000)
        user = User(ep)
        result = str(user)
        assert isinstance(result, str)
        assert '192.168.1.1' in result
