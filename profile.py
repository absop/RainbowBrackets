import os
import sublime


unmatched_key = "Brackets Unmatched"
unmatched_scope = "brackets.unmatched"
scheme_data = {
       "name": "Rainbow Brackets",
       "author": "https://github.com/absop",
       "variables": {},
       "globals": {},
       "rules": []
    }

brackets_colors = {
    "matched": [
        "#FF0000",
        "#FF6A00",
        "#FFD800",
        "#00FF00",
        "#0094FF",
        "#0041FF",
        "#7D00E5",
    ],
    "unmatched": "#FF0000"
}

def _matched_key(i):
    return "Brackets Matched L{}".format(i)

def _matched_scope(i):
    return "brackets.matched.l{}".format(i)


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
