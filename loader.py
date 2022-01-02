import sublime

from .plugin.manage   import RainbowBracketsViewManager
from .plugin.commands import (
    RainbowBracketsToggleDebugCommand,
    RainbowBracketsClearColorSchemesCommand,
    RainbowBracketsColorCommand,
    RainbowBracketsSweepCommand,
    RainbowBracketsSetupCommand,
    RainbowBracketsCloseCommand,
    RainbowBracketsEditBracketsCommand
)

def plugin_loaded():
    sublime.set_timeout_async(RainbowBracketsViewManager.init)


def plugin_unloaded():
    RainbowBracketsViewManager.exit()
