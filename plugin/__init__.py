from __future__ import annotations

import sublime

from .manager  import RainbowBracketsViewManager
from .commands import RbToggleDebugCommand
from .commands import RbClearColorSchemesCommand
from .commands import RbColorCommand
from .commands import RbSweepCommand
from .commands import RbSetupCommand
from .commands import RbCloseCommand
from .commands import RbEditBracketsCommand


__all__ = (
    # ST: core
    'plugin_loaded',
    'plugin_unloaded',
    # ST: listeners
    'RainbowBracketsViewManager',
    # ST: commands
    'RbToggleDebugCommand',
    'RbClearColorSchemesCommand',
    'RbEditBracketsCommand',
    'RbColorCommand',
    'RbSweepCommand',
    'RbSetupCommand',
    'RbCloseCommand',
)


def plugin_loaded():
    sublime.set_timeout_async(RainbowBracketsViewManager.init)


def plugin_unloaded():
    RainbowBracketsViewManager.exit()
