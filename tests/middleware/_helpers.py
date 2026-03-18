"""Helper to import middleware modules without sys.path conflicts."""
import importlib.util
import os
import sys

_MW_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'middleware',
)


def load_middleware_module(name: str, fresh: bool = False):
    """Import a module from middleware/ by file path, avoiding sys.path conflicts.

    Both server/ and middleware/ have identically named modules (e.g. state.py).
    The root conftest puts server/ first on sys.path, so bare imports resolve to
    server/. This function loads by absolute path to avoid the collision.

    Pass fresh=True to force a re-execution (e.g. to pick up changed env vars).
    """
    path = os.path.join(_MW_DIR, f'{name}.py')
    mod_name = f'mw_{name}'
    if not fresh and mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
