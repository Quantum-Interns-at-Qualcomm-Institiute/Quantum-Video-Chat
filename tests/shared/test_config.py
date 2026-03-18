"""Tests for shared/config.py — get_local_ip(), env var overrides, INI loading."""
import os
import tempfile
import importlib
import pytest
from unittest.mock import patch, MagicMock


class TestGetLocalIp:
    def test_socket_success(self):
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ('192.168.1.5', 0)

        with patch('shared.config._socket.socket', return_value=mock_socket):
            from shared.config import get_local_ip
            result = get_local_ip()
            assert result == '192.168.1.5'

    def test_socket_fails_psutil_fallback(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("No route")

        mock_addr = MagicMock()
        mock_addr.family = 2
        mock_addr.address = '10.0.0.5'

        with patch('shared.config._socket.socket', return_value=mock_socket):
            with patch('shared.config._psutil.net_if_addrs',
                       return_value={'eth0': [mock_addr]}):
                from shared.config import get_local_ip
                result = get_local_ip()
                assert result == '10.0.0.5'

    def test_psutil_skips_loopback(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("No route")

        loopback = MagicMock()
        loopback.family = 2
        loopback.address = '127.0.0.1'

        real_addr = MagicMock()
        real_addr.family = 2
        real_addr.address = '10.0.0.5'

        with patch('shared.config._socket.socket', return_value=mock_socket):
            with patch('shared.config._psutil.net_if_addrs',
                       return_value={'lo': [loopback], 'eth0': [real_addr]}):
                from shared.config import get_local_ip
                result = get_local_ip()
                assert result == '10.0.0.5'

    def test_all_fail_returns_localhost(self):
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("No route")

        with patch('shared.config._socket.socket', return_value=mock_socket):
            with patch('shared.config._psutil.net_if_addrs', return_value={}):
                from shared.config import get_local_ip
                result = get_local_ip()
                assert result == '127.0.0.1'


class TestDefaultPorts:
    def test_defaults(self):
        from shared.config import (
            MIDDLEWARE_PORT, SERVER_REST_PORT,
            SERVER_WEBSOCKET_PORT, CLIENT_API_PORT
        )
        # These will use whatever env vars are set or defaults
        assert isinstance(MIDDLEWARE_PORT, int)
        assert isinstance(SERVER_REST_PORT, int)
        assert isinstance(SERVER_WEBSOCKET_PORT, int)
        assert isinstance(CLIENT_API_PORT, int)


class TestConstants:
    def test_video_shape(self):
        from shared.config import VIDEO_SHAPE
        assert VIDEO_SHAPE == (480, 640, 3)

    def test_display_shape(self):
        from shared.config import DISPLAY_SHAPE
        assert DISPLAY_SHAPE == (720, 960, 3)

    def test_frame_rate(self):
        from shared.config import FRAME_RATE
        assert FRAME_RATE == 15

    def test_sample_rate(self):
        from shared.config import SAMPLE_RATE
        assert SAMPLE_RATE == 8196

    def test_key_length(self):
        from shared.config import KEY_LENGTH
        assert KEY_LENGTH == 128


class TestDefaults:
    def test_defaults_dict_exists(self):
        from shared.config import DEFAULTS
        assert isinstance(DEFAULTS, dict)

    def test_defaults_has_all_sections(self):
        from shared.config import DEFAULTS
        assert 'network' in DEFAULTS
        assert 'video' in DEFAULTS
        assert 'audio' in DEFAULTS
        assert 'encryption' in DEFAULTS

    def test_defaults_network_values(self):
        from shared.config import DEFAULTS
        assert DEFAULTS['network']['middleware_port'] == 5001
        assert DEFAULTS['network']['server_rest_port'] == 5050
        assert DEFAULTS['network']['server_websocket_port'] == 3000
        assert DEFAULTS['network']['client_api_port'] == 4000

    def test_defaults_video_values(self):
        from shared.config import DEFAULTS
        assert DEFAULTS['video']['video_width'] == 640
        assert DEFAULTS['video']['video_height'] == 480
        assert DEFAULTS['video']['frame_rate'] == 15

    def test_defaults_encryption_values(self):
        from shared.config import DEFAULTS
        assert DEFAULTS['encryption']['key_length'] == 128
        assert DEFAULTS['encryption']['encrypt_scheme'] == 'AES'
        assert DEFAULTS['encryption']['key_generator'] == 'FILE'


class TestIniLoading:
    def test_get_helper_returns_default_when_no_ini(self):
        """_get returns default when INI has no matching section/key."""
        from shared.config import _get
        result = _get('nonexistent', 'key', 42, cast=int)
        assert result == 42

    def test_get_helper_env_var_takes_precedence(self):
        """_get returns env var value over INI and default."""
        from shared.config import _get
        with patch.dict(os.environ, {'QVC_TEST_VAR': '9999'}):
            result = _get('network', 'middleware_port', 5001,
                         env_key='QVC_TEST_VAR', cast=int)
            assert result == 9999

    def test_load_ini_returns_configparser(self):
        from shared.config import _load_ini
        import configparser
        result = _load_ini()
        assert isinstance(result, configparser.ConfigParser)


class TestConfigDataclass:
    def test_default_values(self):
        from shared.config import Config
        cfg = Config()
        assert cfg.video_width == 640
        assert cfg.video_height == 480
        assert cfg.frame_rate == 15
        assert cfg.sample_rate == 8196
        assert cfg.key_length == 128

    def test_derived_properties(self):
        from shared.config import Config
        cfg = Config(video_width=320, video_height=240, display_width=640, display_height=480)
        assert cfg.video_shape == (240, 320, 3)
        assert cfg.display_shape == (480, 640, 3)
        assert cfg.frames_per_buffer == cfg.sample_rate // 6

    def test_custom_overrides(self):
        from shared.config import Config
        cfg = Config(frame_rate=30, sample_rate=44100, key_length=256)
        assert cfg.frame_rate == 30
        assert cfg.sample_rate == 44100
        assert cfg.key_length == 256

    def test_from_ini_returns_config(self):
        from shared.config import Config
        cfg = Config.from_ini()
        assert isinstance(cfg, Config)
        assert cfg.video_width == 640  # default when no INI override

    def test_from_ini_with_file(self):
        from shared.config import Config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write('[video]\nvideo_width = 320\nframe_rate = 30\n')
            f.flush()
            try:
                cfg = Config.from_ini(f.name)
                assert cfg.video_width == 320
                assert cfg.frame_rate == 30
                # Other values should be defaults
                assert cfg.video_height == 480
            finally:
                os.unlink(f.name)

    def test_default_instance_matches_globals(self):
        from shared.config import Config, _default, VIDEO_SHAPE, FRAME_RATE, KEY_LENGTH
        assert _default.video_shape == VIDEO_SHAPE
        assert _default.frame_rate == FRAME_RATE
        assert _default.key_length == KEY_LENGTH
