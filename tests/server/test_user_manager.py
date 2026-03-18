"""Tests for server/utils/user_manager.py — DictUserStorage, UserStorageFactory, UserManager."""
import pytest
from unittest.mock import MagicMock, patch
from utils.user_manager import (
    DictUserStorage, UserStorageFactory, UserManager,
    DuplicateUser, UserNotFound, InvalidState,
)
from utils.user import UserState


# ---- DictUserStorage ----

class TestDictUserStorage:
    def test_add_and_get(self, dict_storage):
        dict_storage.add_user('u1', {'data': 1})
        assert dict_storage.get_user('u1') == {'data': 1}

    def test_add_duplicate_raises(self, dict_storage):
        dict_storage.add_user('u1', 'info')
        with pytest.raises(DuplicateUser):
            dict_storage.add_user('u1', 'info2')

    def test_get_missing_raises(self, dict_storage):
        with pytest.raises(UserNotFound):
            dict_storage.get_user('nonexistent')

    def test_update_existing(self, dict_storage):
        dict_storage.add_user('u1', 'old')
        dict_storage.update_user('u1', 'new')
        assert dict_storage.get_user('u1') == 'new'

    def test_update_missing_raises(self, dict_storage):
        with pytest.raises(UserNotFound):
            dict_storage.update_user('nonexistent', 'data')

    def test_remove_existing(self, dict_storage):
        dict_storage.add_user('u1', 'info')
        dict_storage.remove_user('u1')
        assert not dict_storage.has_user('u1')

    def test_remove_missing_raises(self, dict_storage):
        with pytest.raises(UserNotFound):
            dict_storage.remove_user('nonexistent')

    def test_has_user_true(self, dict_storage):
        dict_storage.add_user('u1', 'info')
        assert dict_storage.has_user('u1') is True

    def test_has_user_false(self, dict_storage):
        assert dict_storage.has_user('nobody') is False


# ---- UserStorageFactory ----

class TestUserStorageFactory:
    def test_create_dict(self):
        factory = UserStorageFactory()
        storage = factory.create_storage('DICT')
        assert isinstance(storage, DictUserStorage)

    def test_invalid_type_raises(self):
        factory = UserStorageFactory()
        with pytest.raises(ValueError, match="Invalid storage type"):
            factory.create_storage('REDIS')

    def test_context_manager(self):
        with UserStorageFactory() as factory:
            storage = factory.create_storage('DICT')
            assert isinstance(storage, DictUserStorage)


# ---- UserManager ----

class TestUserManager:
    def test_generate_user_id_format(self, user_manager):
        uid = user_manager.generate_user_id()
        assert len(uid) == 5
        assert uid.isalnum()
        assert uid == uid.lower()

    def test_generate_user_id_uniqueness(self, user_manager):
        ids = {user_manager.generate_user_id() for _ in range(100)}
        # With 36^5 possible IDs, 100 should all be unique
        assert len(ids) == 100

    def test_add_user_returns_id(self, user_manager):
        uid = user_manager.add_user(('127.0.0.1', 4000))
        assert isinstance(uid, str)
        assert len(uid) == 5

    def test_generate_token_deterministic(self, user_manager):
        token1 = user_manager.generate_token('test_user')
        token2 = user_manager.generate_token('test_user')
        assert token1 == token2

    def test_generate_token_is_hex(self, user_manager):
        token = user_manager.generate_token('test_user')
        assert len(token) == 64  # SHA-256 hex
        int(token, 16)  # Should not raise

    def test_set_user_state_idle_with_none_peer(self, user_manager):
        uid = user_manager.add_user(('127.0.0.1', 4000))
        # Store a mock user object with state and peer attributes
        mock_user = MagicMock()
        mock_user.state = UserState.IDLE
        mock_user.peer = None
        user_manager.storage.update_user(uid, mock_user)

        # Should not raise
        user_manager.set_user_state(uid, UserState.IDLE, peer=None)

    def test_set_user_state_idle_with_peer_raises(self, user_manager):
        with pytest.raises(InvalidState):
            user_manager.set_user_state('fake_id', UserState.IDLE, peer='someone')

    def test_set_user_state_connected_without_peer_raises(self, user_manager):
        with pytest.raises(InvalidState):
            user_manager.set_user_state('fake_id', UserState.CONNECTED, peer=None)

    def test_set_user_state_connected_with_peer(self, user_manager):
        uid = user_manager.add_user(('127.0.0.1', 4000))
        mock_user = MagicMock()
        mock_user.state = UserState.IDLE
        mock_user.peer = None
        user_manager.storage.update_user(uid, mock_user)

        user_manager.set_user_state(uid, UserState.CONNECTED, peer='peer123')

    def test_remove_user(self, user_manager):
        uid = user_manager.add_user(('127.0.0.1', 4000))
        user_manager.remove_user(uid)
        assert not user_manager.storage.has_user(uid)

    def test_remove_nonexistent_does_not_raise(self, user_manager):
        # remove_user swallows UserNotFound (no re-raise in the code)
        user_manager.remove_user('nonexistent')
