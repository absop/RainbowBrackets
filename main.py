import os
import json

import sublime
import sublime_plugin

from .plugins import profile
from .plugins.searcher import BracketsSearcher


class Debuger:
    debug = True

    def print(*args):
        if Debuger.debug:
            print(*args)


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

        def flush_views():
            Debuger.print("flush_views, color_scheme: ", self.color_scheme)
            for window in sublime.windows():
                for view in window.views():
                    if view.settings().has("rainbow"):
                        view.settings().set("color_scheme", self.color_scheme)
                        Debuger.print("\tfile: ", view.file_name())

        sublime.set_timeout(flush_views, 500)

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
        Debuger.print("write color_scheme: ", self.abspath)

    def brackets_layer_to(self, to):
        self.brackets_layer_from_to(self.deepest_layer, to)


class BracketsViewListener(object):
    def __init__(self, view, brackets):
        self.view = view
        self.searcher = BracketsSearcher(view, brackets)

    def add_all_brackets(self, region):
        matched_brackets, unmatched_brackets =  self.searcher.get_brackets_by_layer(region)
        for layer in sorted(matched_brackets):
            regions = [sublime.Region(p, p+1) for p in matched_brackets[layer]]
            key = profile.BRACKETS_SCOPES.format(layer)
            self.view.add_regions(key, regions,
                scope=key,
                flags=sublime.DRAW_NO_OUTLINE)

    def on_load(self):
        self.add_all_brackets(sublime.Region(0, self.view.size()))

    def on_modified(self):
        pass

    def on_activated(self):
        self.on_load()

    def on_hover(self, point, hover_zone):
        pass

    def on_selection_modified(self):
        pass


class RainbowBracketsListener(sublime_plugin.EventListener):
    view_listeners = {}

    def supported_brackets_of_view(self, view):
        language = extensions = supported_brackets = None
        if view.file_name() and os.path.splitext(view.file_name())[1]:
            extensions = os.path.splitext(view.file_name())[1].lstrip(".")
        if view.settings().get("syntax", None):
            syntax = view.settings().get("syntax", None)
            language = os.path.basename(syntax[:-15]).lower()
        if language not in self.supported_languages:
            for lang in self.supported_languages:
                if extensions in self.supported_languages[lang]["extensions"]:
                    language = lang
                    break
        if language in self.supported_languages:
            return self.supported_languages[language].get("brackets", {})

    def on_load(self, view):
        supported_brackets = self.supported_brackets_of_view(view)
        if supported_brackets:
            listener = BracketsViewListener(view, supported_brackets)
            listener.on_load()
            view.settings().set("color_scheme", self.color_scheme)
            view.settings().set("rainbow", True)
            self.view_listeners[view.id()] = listener

            Debuger.print("on_load: file: {}, brackets: {}".format(
                view.file_name(), supported_brackets))

    def on_modified(self, view):
        if view.id() in self.view_listeners:
            listener = self.view_listeners[view.id()]
            listener.on_modified()

    def on_activated(self, view):
        # after SublimeText start-up, views' original settings are kept.
        if view.settings().has("rainbow") and view.id() not in self.view_listeners:
            self.on_load(view)

    def on_selection_modified(self, view):
        if view.id() in self.view_listeners:
            listener = self.view_listeners[view.id()]
            listener.on_selection_modified()

    def on_hover(self, view, point, hover_zone):
       if view.id() in self.view_listeners:
           listener = self.view_listeners[view.id()]
           listener.on_hover(point, hover_zone)

    def on_close(self, view):
        if view.id() in self.view_listeners:
            self.view_listeners.pop(view.id())
            Debuger.print("close_view, file_name: ", view.file_name())

    def on_post_save(self, view):
        if not (view.settings().has("rainbow") and view.id() in self.view_listeners):
            self.on_load(view)

        if Debuger.debug:
            self.reload_all_modules(view.file_name())

    # Just for test this package conveniently.
    def reload_all_modules(self, path):
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
        Debuger.print("load_settings: call_back1")
        colors = cls.settings.get("brackets_colors", profile.BRACKETS_COLORS)
        cls.color_scheme_writer.update_colors(colors)

    def call_back2():
        Debuger.print("load_settings: call_back2")
        supported_languages = cls.settings.get("supported_languages", {})
        supported_extensions = []
        for lang in supported_languages:
            for ext in supported_languages[lang].get("extensions", []):
                supported_extensions.append(ext if ext[0] == "." else "." + ext)
            supported_languages[lang.lower()] = supported_languages.pop(lang)

        cls.supported_languages = supported_languages
        cls.supported_extensions = supported_extensions

    def call_back3():
        Debuger.print("load_settings: call_back3")
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
