import os
import json
import sublime
import weakref

from .debug  import Debuger
from .consts import DEFAULT_CS
from .consts import PACKAGE_NAME
from .consts import PACKAGE_URL
from .consts import PREFS_FILE


def _nearest_color(color):
    b = int(color[5:7], 16)
    b += 1 - 2 * (b == 255)
    return color[:-2] + "%02x" % b

def _color_scheme_background(color_scheme):
    view = sublime.active_window().active_view()
    # origin_color_scheme = view.settings().get("color_scheme")
    view.settings().set("color_scheme", color_scheme)
    background = view.style().get("background")
    # view.settings().set("color_scheme", origin_color_scheme)
    return background


class ColorSchemeManager:
    def __new__(cls, *args, **kwargs):
        if hasattr(cls, 'objref') and cls.objref() is not None:
            return cls.objref()
        self = object.__new__(cls)
        self.init()
        cls.objref = weakref.ref(self)
        return self

    def init(self):
        self.prefs = sublime.load_settings(PREFS_FILE)
        self.prefs.add_on_change(PACKAGE_NAME, self.rewrite_color_scheme)
        self.color_scheme = self.prefs.get("color_scheme", DEFAULT_CS)

    def exit(self):
        self.prefs.clear_on_change(PACKAGE_NAME)

    def __init__(self, get_configs):
        self.get_configs = get_configs
        self.write_color_scheme()

    def color_scheme_cache_path(self):
        return os.path.join(sublime.packages_path(),
            "User", "Color Schemes", "RainbowBrackets")

    def color_scheme_name(self):
        return os.path.basename(
            self.color_scheme).replace("tmTheme", "sublime-color-scheme")

    def clear_color_schemes(self, all=False):
        color_scheme_path = self.color_scheme_cache_path()
        color_scheme_name = self.color_scheme_name()
        for file in os.listdir(color_scheme_path):
            if file != color_scheme_name or all:
                try:
                    os.remove(os.path.join(color_scheme_path, file))
                except:
                    pass

    def rewrite_color_scheme(self):
        scheme = self.prefs.get("color_scheme", DEFAULT_CS)
        if scheme != self.color_scheme:
            self.color_scheme = scheme
            self.write_color_scheme()

    def write_color_scheme(self):
        color_scheme_path = self.color_scheme_cache_path()
        color_scheme_name = self.color_scheme_name()
        color_scheme_file = os.path.join(color_scheme_path, color_scheme_name)
        color_scheme_data = {
            "name": os.path.splitext(color_scheme_name)[0],
            "author": PACKAGE_URL,
            "variables": {},
            "globals": {},
            "rules": self.get_rules()
        }

        # We only need to write a same named color_scheme,
        # then sublime will load and apply it automatically.
        os.makedirs(color_scheme_path, exist_ok=True)
        with open(color_scheme_file, "w+") as file:
            file.write(json.dumps(color_scheme_data))
            Debuger.print(f"write color scheme {color_scheme_name}")

    def get_rules(self):
        rules = []
        background = _color_scheme_background(self.color_scheme)
        nearest_background = _nearest_color(background)
        for config in self.get_configs():
            rules.append({
                "scope": config["bad_scope"],
                "foreground": config["mismatch_color"],
                "background": background
            })
            for scope, color in zip(config["scopes"], config["rainbow_colors"]):
                rules.append({
                    "scope": scope,
                    "foreground": color,
                    "background": nearest_background
                })
        return rules
