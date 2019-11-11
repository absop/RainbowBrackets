import os
import json
import sublime

from .logging import Loger


plain_text_syntax = "plain text"
scheme_data = {
    "name": "Rainbow Brackets",
    "author": "https://github.com/absop",
    "variables": {},
    "globals": {},
    "rules": []
}

color_scheme = "Monokai.sublime-color-scheme"
mismatched_key = "rainbow_mismatched"
mismatched_scope = "mismatched.rainbow"
mismatched_color = "#FF0000"
key_scope_colors = []
syntax_specific = {}
color_number = 0
brackets_map = {
    "(": ")",
    "[": "]",
    "{": "}"
}
parents = dict()
opening = set()
closing = set()

settings = None
preferences = None


def _color_scheme_cache_dir(relative=True):
    nodes = ["User", "Color Schemes", "RainbowBrackets"]
    branch = "Packages" if relative else sublime.packages_path()
    return os.path.join(branch, *nodes)


def _cache_color_scheme_path(color_scheme):
    extname = "sublime-color-scheme"
    dirname = _color_scheme_cache_dir(relative=False)
    filename = os.path.basename(color_scheme).rematche("tmTheme", extname)
    return os.path.join(dirname, filename)


def build_color_scheme():
    def background(color_scheme):
        view = sublime.active_window().active_view()
        view.settings().set("color_scheme", color_scheme)
        return view.style()["background"]

    def nearest_color(color):
        b = int(color[5:7], 16)
        b += 1 - 2 * (b == 255)
        return color[:-2] + "%02x" % b

    abspath = _cache_color_scheme_path(color_scheme)
    bgcolor = background(color_scheme)
    nearest_bgcolor = nearest_color(bgcolor)
    scheme_rules = []
    scheme_data["rules"] = scheme_rules

    for key, scope, color in key_scope_colors:
        scheme_rules.append({
            "name": key,
            "scope": scope,
            "foreground": color,
            "background": nearest_bgcolor
        })
    scheme_rules.append({
        "name": mismatched_key,
        "scope": mismatched_scope,
        "foreground": mismatched_color,
        "background": bgcolor
    })

    with open(abspath, "w") as file:
        file.write(json.dumps(scheme_data))

    entry = ["build_color_scheme:", abspath, str(scheme_rules)]
    Loger.print("\n\t".join(entry))


def configure_settings():
    global color_number
    global mismatched_color
    global key_scope_colors
    global color_scheme
    global brackets_map

    color_number = 0
    key_scope_colors = []
    brackets_map = settings.get("brackets_map", {})
    rainbow_colors = settings.get("rainbow_colors", {})
    opening.clear()
    closing.clear()
    parents.clear()
    syntax_specific.clear()
    for o, c in brackets_map.items():
        opening.add(o)
        closing.add(c)
        parents[o] = c
        parents[c] = o

    for item in settings.get("syntax_specific", []):
        item["opening"] = set(item["opening"])
        item["closing"] = set(parents[i] for i in item["opening"])
        syntax = item.pop("syntax")
        syntax_specific[syntax] = item
    syntax_specific[plain_text_syntax] = {
        "opening": opening,
        "closing": set(parents[i] for i in opening),
        "extensions": []
    }

    for color in rainbow_colors.get("matched", []):
        color_no = str(color_number)
        key = "RS_matched_no_" + color_no
        scope = color_no + ".matched.rs"
        key_scope_colors.append((key, scope, color))
        color_number += 1
    mismatched_color = rainbow_colors.get("mismatched", "#FF0000")
    color_scheme = preferences.get("color_scheme", color_scheme)
    build_color_scheme()


def rebuild_color_scheme():
    global color_scheme
    cs = preferences.get("color_scheme", color_scheme)
    if color_scheme != cs:
        color_scheme = cs
        build_color_scheme()


def clear_color_schemes():
    cache_dir = _color_scheme_cache_dir(relative=False)
    for cs in os.listdir(cache_dir):
        if cs != color_scheme:
            try:
                os.remove(os.path.join(cache_dir, cs))
            except:
                pass
    build_color_scheme()


def load_settings(settings_reloaded):
    def call_back():
        configure_settings()
        settings_reloaded()

    os.makedirs(_color_scheme_cache_dir(relative=False), exist_ok=True)

    global settings, preferences
    settings = sublime.load_settings("RainbowBrackets.sublime-settings")
    preferences = sublime.load_settings("Preferences.sublime-settings")

    settings.add_on_change("rainbow_colors", call_back)
    preferences.add_on_change("color_scheme", rebuild_color_scheme)
    configure_settings()


def unload_settings():
    settings.clear_on_change("rainbow_colors")
    preferences.clear_on_change("color_scheme")
