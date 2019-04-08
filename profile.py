import os
import sublime


plain_text_syntax = "plain text"
scheme_data = {
    "name": "Rainbow Brackets",
    "author": "https://github.com/absop",
    "variables": {},
    "globals": {},
    "rules": []
}


RAINBOW_MODE_ALL = 0
RAINBOW_MODE_PART = 1
DEFAULT_MODE = RAINBOW_MODE_ALL


def _cache_color_scheme_dir(relative=True):
    leaf = "User/Color Schemes/{}".format(__package__)
    branch = "Packages" if relative else sublime.packages_path()
    return os.path.join(branch, leaf).replace("\\", "/")


def _cache_color_scheme_path(color_scheme):
    extname = "sublime-color-scheme"
    dirname = _cache_color_scheme_dir(relative=False)
    filename = os.path.basename(color_scheme).replace("tmTheme", extname)
    return dirname + "/" + filename


def _load_settings(pref=True):
    file = "{}.sublime-settings".format("Preferences" if pref else __package__)
    return sublime.load_settings(file)
