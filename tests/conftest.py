"""
Root conftest.py -- sets up sys.path so imports mirror the project's runtime layout.

The project uses sys.path.insert at runtime (in main.py, video_chat.py, etc.) to make
`shared`, `server`, and `middleware` importable. We replicate that here for tests.
"""
import os
import sys
from pathlib import Path

# Enable dev-only encryption modes (XOR, DEBUG) for testing
os.environ.setdefault("QVC_DEVELOPMENT", "true")

_ROOT = str(Path(__file__).resolve().parent.parent)

# Add root first so `shared.xyz` imports work
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Add server and middleware BEFORE shared on sys.path so that bare imports
# like `from state import APIState` (in server/) resolve to server/state.py
# rather than shared/state.py.  At runtime the CWD handles this; in tests
# we must replicate it via sys.path ordering.
for subdir in ("server", "middleware"):
    path = str(Path(_ROOT) / subdir)
    if path not in sys.path:
        sys.path.insert(0, path)

import pytest

from shared.endpoint import Endpoint


@pytest.fixture
def mock_endpoint():
    """Reusable Endpoint fixture."""
    return Endpoint("127.0.0.1", 5000)
