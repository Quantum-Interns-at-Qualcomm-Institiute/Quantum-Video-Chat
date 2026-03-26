"""
Central configuration for Quantum Video Chat.

All hardcoded constants live here.  Values are resolved in order:
  1. Environment variable (QVC_* prefix)
  2. settings.ini at the project root
  3. frontend/settings.ini (fallback location)
  4. Hardcoded default below

The DEFAULTS dict mirrors every tunable constant so the front-end
can populate the "Reset to Defaults" action.

For testability, the Config dataclass bundles all settings into an
injectable object.  Module-level globals are backward-compatible
aliases to the default Config instance.
"""
import configparser
import logging
import os
import socket as _socket
from dataclasses import dataclass

import psutil as _psutil

from shared.encryption import EncryptSchemes, KeyGenerators

# ---------------------------------------------------------------------------
# INI loader
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Fall back to frontend/settings.ini when no settings.ini exists at the
# project root so that both processes always read the same file.
_SETTINGS_FILE: str = next(
    (p for p in (
        os.path.join(_PROJECT_ROOT, 'settings.ini'),
        os.path.join(_PROJECT_ROOT, 'frontend', 'settings.ini'),
    ) if os.path.exists(p)),
    os.path.join(_PROJECT_ROOT, 'frontend', 'settings.ini'),
)

def _load_ini() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if os.path.exists(_SETTINGS_FILE):
        cp.read(_SETTINGS_FILE)
    return cp

_ini = _load_ini()


def _get(section: str, key: str, default, env_key: str | None = None, cast=str):
    """Return env-var override > INI value > hardcoded default."""
    if env_key:
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return cast(env_val)
    try:
        return cast(_ini.get(section, key))
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default


def _getbool(section: str, key: str, default: bool, env_key: str | None = None) -> bool:
    """Boolean-aware variant of _get — interprets 'true'/'1'/'yes' as True."""
    if env_key:
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val.lower() in ('true', '1', 'yes')
    try:
        return _ini.getboolean(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default


# ---------------------------------------------------------------------------
# Network helper
# ---------------------------------------------------------------------------

def get_local_ip() -> str:
    """Auto-detect local IP by finding the first active non-loopback interface."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        addr = s.getsockname()[0]
        s.close()
        return addr
    except Exception:
        logging.debug("UDP probe for local IP failed", exc_info=True)
    for addrs in _psutil.net_if_addrs().values():
        for prop in addrs:
            if prop.family == 2 and not prop.address.startswith('127.'):
                return prop.address
    return '127.0.0.1'


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Injectable configuration object. All settings in one place."""

    # Network
    local_ip: str = ''
    middleware_port: int = 5001
    server_rest_port: int = 5050
    client_api_port: int = 4000

    # Video
    video_width: int = 640
    video_height: int = 480
    display_width: int = 960
    display_height: int = 720
    frame_rate: int = 15

    # Audio
    sample_rate: int = 8000
    audio_wait: float = 0.125
    mute_audio: bool = False

    # Encryption
    key_length: int = 128
    encrypt_scheme: str = 'AES'
    key_generator: str = 'FILE'

    # BB84
    bb84_num_raw_bits: int = 4096
    bb84_qber_threshold: float = 0.11
    bb84_fiber_length_km: float = 1.0
    bb84_source_intensity: float = 0.1
    bb84_detector_efficiency: float = 0.10
    bb84_eavesdropper_enabled: bool = False

    # Debug
    debug_video: bool = False

    # Derived properties
    @property
    def video_shape(self) -> tuple:
        return (self.video_height, self.video_width, 3)

    @property
    def display_shape(self) -> tuple:
        return (self.display_height, self.display_width, 3)

    @property
    def frames_per_buffer(self) -> int:
        return self.sample_rate // 6

    @classmethod
    def from_ini(cls, ini_path: str | None = None) -> 'Config':
        """Load config from an INI file, with env-var overrides."""
        if ini_path:
            cp = configparser.ConfigParser()
            if os.path.exists(ini_path):
                cp.read(ini_path)
        else:
            cp = _ini

        def get(section, key, default, env_key=None, cast=str):
            if env_key:
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    return cast(env_val)
            try:
                return cast(cp.get(section, key))
            except (configparser.NoSectionError, configparser.NoOptionError):
                return default

        def getbool(section, key, default, env_key=None):
            if env_key:
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    return env_val.lower() in ('true', '1', 'yes')
            try:
                return cp.getboolean(section, key)
            except (configparser.NoSectionError, configparser.NoOptionError):
                return default

        return cls(
            local_ip=os.environ.get('QVC_LOCAL_IP') or get_local_ip(),
            middleware_port=get('network', 'middleware_port', 5001,
                                  env_key='QVC_IPC_PORT', cast=int),
            server_rest_port=get('network', 'server_rest_port', 5050,
                                 env_key='QVC_SERVER_REST_PORT', cast=int),
            client_api_port=get('network', 'client_api_port', 4000,
                                env_key='QVC_CLIENT_API_PORT', cast=int),
            video_width=get('video', 'video_width', 640, cast=int),
            video_height=get('video', 'video_height', 480, cast=int),
            display_width=get('video', 'display_width', 960, cast=int),
            display_height=get('video', 'display_height', 720, cast=int),
            frame_rate=get('video', 'frame_rate', 15, cast=int),
            sample_rate=get('audio', 'sample_rate', 8000, cast=int),
            audio_wait=get('audio', 'audio_wait', 0.125, cast=float),
            mute_audio=getbool('audio', 'mute_by_default', False, env_key='QVC_MUTE_AUDIO'),
            key_length=get('encryption', 'key_length', 128, cast=int),
            encrypt_scheme=get('encryption', 'encrypt_scheme', 'AES'),
            key_generator=get('encryption', 'key_generator', 'FILE'),
            bb84_num_raw_bits=get('bb84', 'num_raw_bits', 4096, cast=int),
            bb84_qber_threshold=get('bb84', 'qber_threshold', 0.11, cast=float),
            bb84_fiber_length_km=get('bb84', 'fiber_length_km', 1.0, cast=float),
            bb84_source_intensity=get('bb84', 'source_intensity', 0.1, cast=float),
            bb84_detector_efficiency=get('bb84', 'detector_efficiency', 0.10, cast=float),
            bb84_eavesdropper_enabled=getbool('bb84', 'eavesdropper_enabled', False,
                                               env_key='QVC_BB84_EAVESDROPPER'),
            debug_video=getbool('debug', 'video_enabled', False, env_key='QVC_DEBUG_VIDEO'),
        )


# ---------------------------------------------------------------------------
# Default instance (created from INI + env vars)
# ---------------------------------------------------------------------------

_default = Config.from_ini()

# ---------------------------------------------------------------------------
# Module-level aliases (backward compatible)
# ---------------------------------------------------------------------------

LOCAL_IP: str = _default.local_ip

MIDDLEWARE_PORT: int = _default.middleware_port
SERVER_REST_PORT: int = _default.server_rest_port
CLIENT_API_PORT: int = _default.client_api_port

_VIDEO_WIDTH: int = _default.video_width
_VIDEO_HEIGHT: int = _default.video_height
_DISPLAY_WIDTH: int = _default.display_width
_DISPLAY_HEIGHT: int = _default.display_height

VIDEO_SHAPE: tuple = _default.video_shape
DISPLAY_SHAPE: tuple = _default.display_shape
FRAME_RATE: int = _default.frame_rate

SAMPLE_RATE: int = _default.sample_rate
FRAMES_PER_BUFFER: int = _default.frames_per_buffer
AUDIO_WAIT: float = _default.audio_wait

KEY_LENGTH: int = _default.key_length

_scheme_name: str = _default.encrypt_scheme
DEFAULT_ENCRYPT_SCHEME = EncryptSchemes[_scheme_name]

_keygen_name: str = _default.key_generator
DEFAULT_KEY_GENERATOR = KeyGenerators[_keygen_name]

DEBUG_VIDEO: bool = _default.debug_video
MUTE_AUDIO: bool = _default.mute_audio

# ---------------------------------------------------------------------------
# Defaults dict (consumed by frontend for "Reset to Defaults")
# ---------------------------------------------------------------------------

DEFAULTS = {
    'network': {
        'middleware_port': 5001,
        'server_rest_port': 5050,
        'client_api_port': 4000,
    },
    'video': {
        'video_width': 640,
        'video_height': 480,
        'display_width': 960,
        'display_height': 720,
        'frame_rate': 15,
    },
    'audio': {
        'sample_rate': 8000,
        'audio_wait': 0.125,
        'mute_by_default': False,
    },
    'encryption': {
        'key_length': 128,
        'encrypt_scheme': 'AES',
        'key_generator': 'FILE',
    },
    'bb84': {
        'num_raw_bits': 4096,
        'qber_threshold': 0.11,
        'fiber_length_km': 1.0,
        'source_intensity': 0.1,
        'detector_efficiency': 0.10,
        'eavesdropper_enabled': False,
    },
    'debug': {
        'video_enabled': False,
    },
}
