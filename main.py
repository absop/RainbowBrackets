import os
import json

import sublime
import sublime_plugin

from .plugins import profile
from .plugins.searcher import BracketsSearcher


def on_save_debug():
    return False


class ColorSchemeWriter(object):
    brackets_colors = profile.BRACKETS_COLORS
    colors_loop = len(brackets_colors)
    cached_color_schemes = []
    scheme_data = {
       "author": "https://github.com/absop",
       "name": profile.COLOR_SCHEME_NAME,
       "variables": {},
       "globals": {},
       "rules": []
    }

    # 额外提供的 color_scheme, 只需动态提供背景色
    # 以便使括号的背景颜色与颜色方案的背景色一致即可
    def __init__(self, color_scheme):
        self.color_scheme = color_scheme
        self.abspath = profile._cache_color_scheme_path(color_scheme, relative=False)
        self.bgcolor = self.nearest_color(self.background(color_scheme))

        if not (self.abspath in self.cached_color_schemes and os.path.exists(self.abspath)):
            self.scheme_data["rules"] = []
            self.brackets_layer_from_to(0, 15)
            self.cached_color_schemes.append(self.abspath)

    def update_scheme(self, color_scheme):
        self.__init__(color_scheme)

        def flush_view():
            for window in sublime.windows():
                for view in window.views():
                    if view.settings().has("rainbow_brackets"):
                        if on_save_debug():
                            print(view.file_name(), self.color_scheme)
                        view.settings().set("color_scheme", self.color_scheme)

        sublime.set_timeout(flush_view, 500)

    def update_colors(self, colors):
        self.brackets_colors = colors
        self.colors_loop = len(colors)
        self.scheme_data["rules"] = []
        self.brackets_layer_from_to(0, self.deepest_layer)

    def background(self, color_scheme):
        view = sublime.active_window().active_view()
        view.settings().set("color_scheme", color_scheme)
        bgcolor = view.style()["background"]
        return bgcolor

    # Applies only to #RRGGBB color
    def nearest_color(self, color):
        b = int(color[5:7], 16)
        b += 1 - 2 * (b == 255)
        return color[:-2] + "%02X" % b

    def brackets_layer_from_to(self, current, deepest):
        for layer in range(current, deepest):
            self.scheme_data["rules"].append({
                "name": "Brackets Layer{}".format(layer),
                "scope": profile.BRACKETS_SCOPES.format(layer),
                "foreground": self.brackets_colors[layer % self.colors_loop],
                "background": self.bgcolor
            })
        self.deepest_layer = deepest

        with open(self.abspath, "w") as file:
            file.write(json.dumps(self.scheme_data))

    def brackets_layer_to(self, to):
        self.brackets_layer_from_to(self.deepest_layer, to)


class BracketsRender(object):
    def __init__(self, view, brackets):
        self.view = view
        self.searcher = BracketsSearcher(view, brackets)
        if on_save_debug():
            print(brackets)

    def render(self, region):
        matched_brackets, unmatched_brackets =  self.searcher.get_brackets_by_layer(region)
        for layer in sorted(matched_brackets):
            regions = [sublime.Region(p, p+1) for p in matched_brackets[layer]]
            key = profile.BRACKETS_SCOPES.format(layer)
            self.view.add_regions(key, regions,
                scope=key,
                flags=sublime.DRAW_NO_OUTLINE)

    def on_modified(self):
        pass

    def on_load(self):
        self.render(sublime.Region(0, self.view.size()))

    def on_hover(self, point, hover_zone):
        pass


class RainbowBracketsListener(sublime_plugin.EventListener):
    view_listeners = {}

    def on_load(self, view):
        lang = extensions = supported_brackets = None

        if view.file_name() and os.path.splitext(view.file_name())[1]:
            extensions = os.path.splitext(view.file_name())[1].lstrip(".")
        if view.settings().get("syntax", None):
            syntax = view.settings().get("syntax", None)
            lang = os.path.basename(syntax[:-15]).lower()
        if lang not in self.supported_languages:
            for l in self.supported_languages:
                if extensions in self.supported_languages[l]["extensions"]:
                    lang = l
                    break
        if (lang in self.supported_languages and
            self.supported_languages[lang].get("brackets", {})):
            supported_brackets = self.supported_languages[lang].get("brackets", {})
            brackets_render = BracketsRender(view, supported_brackets)
            brackets_render.on_load()
            view.settings().set("color_scheme", self.color_scheme)
            view.settings().set("rainbow_brackets", True)
            self.view_listeners[view.id()] = brackets_render

            if on_save_debug():
                print("render running: ", view.file_name())

    def on_new(self, view):
        pass
        self.on_load(view)

    def on_modified(self, view):
        pass

    def on_activated(self, view):
        if view.settings().has("rainbow_brackets") and view.id() in self.view_listeners:
            return
        self.on_load(view)

    def on_selection_modified(self, view):
        pass

    def on_hover(self, view, point, hover_zone):
        pass

    def on_post_save(self, view):
        if on_save_debug():
            self.reload_module(view.file_name())

    def reload_module(self, path):
        dir = os.path.dirname(__file__)
        if path.endswith(".py") and path.startswith(dir) and path != __file__:
            start = len(sublime.packages_path())+1
            modulename = path[start:-3]
            if path.endswith("__init__.py"):
                modulename = modulename[:-9]
            modulename = modulename.replace("/", ".")
            modulename = modulename.replace("\\", ".")
            sublime_plugin.reload_plugin(modulename)
            sublime_plugin.reload_plugin("{}.main".format(__package__))


def load_settings(cls):
    def call_back1():
        if on_save_debug():
            print("call_back1")
        colors = cls.settings.get("brackets_colors", profile.BRACKETS_COLORS)
        cls.color_scheme_writer.update_colors(colors)

    def call_back2():
        if on_save_debug():
            print("call_back2")
        supported_languages = cls.settings.get("supported_languages", {})
        supported_extensions = []
        for lang in supported_languages:
            for ext in supported_languages[lang].get("extensions", []):
                supported_extensions.append(ext if ext[0] == "." else "." + ext)
            supported_languages[lang.lower()] = supported_languages.pop(lang)

        cls.supported_languages = supported_languages
        cls.supported_extensions = supported_extensions

    def call_back3():
        if on_save_debug():
            print("call_back3")
        cls.color_scheme = cls.preferences.get("color_scheme")
        cls.color_scheme_writer.update_scheme(cls.color_scheme)

    cls.settings = profile._load_settings(pref=False)
    cls.preferences = profile._load_settings(pref=True)
    cls.color_scheme = cls.preferences.get("color_scheme")
    cls.color_scheme_writer = ColorSchemeWriter(cls.color_scheme)

    call_back1()
    call_back2()

    cls.settings.add_on_change("brackets_colors", call_back1)
    cls.settings.add_on_change("supported_languages", call_back2)
    cls.preferences.add_on_change("color_scheme", call_back3)


def plugin_loaded():
    os.makedirs(profile._cache_color_scheme_dir(relative=False), exist_ok=True)
    load_settings(RainbowBracketsListener)
