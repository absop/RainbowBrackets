import sublime

from .plugin.manager  import RainbowBracketsViewManager
from .plugin.commands import (
    RbToggleDebugCommand,
    RbClearColorSchemesCommand,
    RbColorCommand,
    RbSweepCommand,
    RbSetupCommand,
    RbCloseCommand,
    RbEditBracketsCommand
)

def plugin_loaded():
    sublime.set_timeout_async(RainbowBracketsViewManager.init)


def plugin_unloaded():
    RainbowBracketsViewManager.exit()
