"""Helper to import middleware modules without sys.path conflicts."""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MW_DIR = os.path.join(_ROOT, 'middleware')
_SERVER_DIR = os.path.join(_ROOT, 'server')

# Bare module names that exist in both server/ and middleware/
_CONFLICTING_NAMES = {'state', 'video', 'audio', 'server_comms', 'events', 'custom_logging'}


def load_middleware_module(name: str, fresh: bool = False):
    """Import a module from middleware/ by file path, avoiding sys.path conflicts.

    Both server/ and middleware/ have identically named modules (e.g. state.py).
    The root conftest puts server/ first on sys.path, so bare imports resolve to
    server/. This function temporarily moves middleware/ to the front of sys.path
    during module execution so that internal bare imports (e.g. `from state import
    MiddlewareState` inside server_comms.py) resolve correctly.

    After loading, any conflicting bare module names cached in sys.modules by the
    loading process are cleaned up so subsequent imports by server tests resolve
    to the correct (server/) modules.

    Pass fresh=True to force a re-execution (e.g. to pick up changed env vars).
    """
    path = os.path.join(_MW_DIR, f'{name}.py')
    mod_name = f'mw_{name}'
    if not fresh and mod_name in sys.modules:
        return sys.modules[mod_name]

    # Snapshot conflicting bare module refs so we can restore them after
    saved_modules = {}
    for cname in _CONFLICTING_NAMES:
        if cname in sys.modules:
            saved_modules[cname] = sys.modules[cname]

    # Temporarily prioritize middleware/ on sys.path
    orig_path = sys.path[:]
    if _MW_DIR in sys.path:
        sys.path.remove(_MW_DIR)
    sys.path.insert(0, _MW_DIR)

    try:
        # Remove cached bare modules so they re-resolve to middleware/
        for cname in _CONFLICTING_NAMES:
            sys.modules.pop(cname, None)

        spec = importlib.util.spec_from_file_location(mod_name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        # Restore sys.path
        sys.path[:] = orig_path

        # Restore or remove conflicting bare module names
        for cname in _CONFLICTING_NAMES:
            if cname in saved_modules:
                sys.modules[cname] = saved_modules[cname]
            else:
                sys.modules.pop(cname, None)
