from __future__ import annotations


def reload_plugin() -> None:
    import sys

    # remove all previously loaded plugin modules
    prefix = f"{__package__}."
    plugin_modules = tuple(
        filter(lambda m: m.startswith(prefix) and m != __name__, sys.modules)
    )
    for module_name in plugin_modules:
        del sys.modules[module_name]


reload_plugin()

from .plugin import *  # noqa: F401, F403
