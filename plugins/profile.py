import os
import sublime


BRACKETS_SCOPES = "brackets.layer.{}"
COLOR_SCHEME_NAME = "Rainbow Brackets"
BRACKETS_COLORS = [
    "#FF0000",
    "#FF6A00",
    "#FFD800",
    "#00FF00",
    "#0094FF",
    "#0041FF",
    "#7D00E5"
]


def _package_name():
    return __package__.split(".")[0]


def _cache_color_scheme_dir(relative=True):
    leaf = "User/{}/Color Schemes".format(_package_name())
    branch = "Packages" if relative else sublime.packages_path()
    return os.path.join(branch, leaf).replace("\\", "/")


def _cache_color_scheme_path(color_scheme, relative=True):
    dirname = _cache_color_scheme_dir(relative)
    filename = os.path.basename(color_scheme).replace("tmTheme", "sublime-color-scheme")
    return dirname + "/" + filename


def _load_settings(pref=True):
    file = "{}.sublime-settings".format("Preferences" if pref else _package_name())
    return sublime.load_settings(file)
