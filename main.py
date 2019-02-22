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


class ColorScheme(object):
    fgcolors = profile.BRACKETS_COLORS
    numcolor = len(fgcolors)

    def __init__(self, csname):
        self.abspath = profile._cache_color_scheme_path(csname, relative=False)
        self.bgcolor = self.nearest_background(csname)
        self.rules = []
        self.nlayer = 0
        self.add_rules_to(15)

    def add_rules_to(self, nlayer):
        for i in range(self.nlayer, nlayer):
            self.rules.append({
                "name": "Brackets Layer{}".format(i),
                "scope": profile.BRACKETS_SCOPES.format(i),
                "foreground": self.fgcolors[i % self.numcolor],
                "background": self.bgcolor
            })
        self.nlayer = nlayer

    def update_colors(self, colors):
        self.fgcolors = colors
        self.numcolor = len(colors)

        for i in range(self.nlayer):
            self.rules[i]["foreground"] = colors[i % self.numcolor]

    def background(self, csname):
        view = sublime.active_window().active_view()
        view.settings().set("color_scheme", csname)
        bgcolor = view.style()["background"]
        return bgcolor

    def nearest_background(self, csname):
        bgcolor = self.background(csname)
        b = int(bgcolor[5:7], 16)
        b += 1 - 2 * (b == 255)
        return bgcolor[:-2] + "%02x" % b


# 额外提供的 color_scheme, 只需动态提供背景色
# 以便使括号的背景颜色与颜色方案的背景色一致即可
class ColorSchemeWriter(object):
    cached_color_schemes = {}
    scheme_data = {
       "author": "https://github.com/absop",
       "name": profile.COLOR_SCHEME_NAME,
       "variables": {},
       "globals": {},
       "rules": []
    }

    def __init__(self, csname):
        color_scheme = self.cached_color_schemes.get(csname, ColorScheme(csname))
        if not (self.cached_color_schemes and
                color_scheme.nlayer >= self.color_scheme.nlayer and
                os.path.exists(color_scheme.abspath)):
            if self.cached_color_schemes:
                color_scheme.add_rules_to(self.color_scheme.nlayer)
            self.write_color_scheme(color_scheme)
        self.csname = csname
        self.color_scheme = color_scheme
        self.cached_color_schemes[csname] = color_scheme

    def update_scheme(self, csname):
        def flush_views():
            Debuger.print("flush_views with color_scheme: ", csname)
            for window in sublime.windows():
                for view in window.views():
                    if view.settings().has("rainbow"):
                        view.settings().set("color_scheme", csname)
                        Debuger.print("\tfile: ", view.file_name())

        if csname != self.csname:
            self.__init__(csname)
            sublime.set_timeout(flush_views, 500)

    def update_colors(self, colors):
        self.color_scheme.update_colors(colors)
        self.cached_color_schemes.pop(self.csname)
        self.write_color_scheme(self.color_scheme)

        for color_scheme in self.cached_color_schemes.values():
            color_scheme.update_colors(colors)
            self.write_color_scheme(color_scheme)

        self.cached_color_schemes[self.csname] = self.color_scheme

    def add_layer_to(self, nlayer):
        if nlayer > self.color_scheme.nlayer:
            Debuger.print("add_rules_from: {} to: {}".format(self.color_scheme.nlayer, nlayer))
            self.color_scheme.add_rules_to(nlayer)
            self.write_color_scheme(self.color_scheme)

    def write_color_scheme(self, color_scheme):
        self.scheme_data["rules"] = color_scheme.rules
        with open(color_scheme.abspath, "w") as file:
            file.write(json.dumps(self.scheme_data))
        Debuger.print("write file: {}, bg: {}".format(color_scheme.abspath, color_scheme.bgcolor))


class BracketsViewListener(object):
    def __init__(self, view, brackets):
        self.view = view
        self.searcher = BracketsSearcher(view, brackets)

    def add_all_brackets(self, region):
        matched_brackets, unmatched_brackets =  self.searcher.get_brackets_by_layer(region)
        RainbowBracketsListener.color_scheme_writer.add_layer_to(len(matched_brackets))
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

    def brackets_of_view(self, view):
        language = extensions = None
        if view.file_name() and os.path.splitext(view.file_name())[1]:
            extensions = os.path.splitext(view.file_name())[1].lstrip(".")
        if view.settings().get("syntax", None):
            syntax = view.settings().get("syntax", None)
            language = os.path.basename(syntax[:-15]).lower()
        if language not in self.languages:
            for k, v in self.languages.items():
                if extensions in v["extensions"]:
                    language = k
                    break
        if language in self.languages:
            return self.languages[language].get("brackets", {})

    def on_load(self, view):
        brackets = self.brackets_of_view(view)
        if brackets:
            Debuger.print("on_load: file: {}, brackets: {}".format(
                view.file_name(), brackets))

            listener = BracketsViewListener(view, brackets)
            listener.on_load()
            view.settings().set("color_scheme", self.color_scheme)
            view.settings().set("rainbow", True)
            self.view_listeners[view.id()] = listener

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
            Debuger.print("close view: ", view.file_name())

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
        colors = cls.settings.get("brackets_colors", profile.BRACKETS_COLORS)
        cls.color_scheme_writer.update_colors(colors)

    def call_back2():
        languages = cls.settings.get("languages", {})
        extensions = []
        for lang in languages:
            for ext in languages[lang].get("extensions", []):
                extensions.append(ext if ext[0] == "." else "." + ext)
            languages[lang.lower()] = languages.pop(lang)

        cls.languages = languages
        cls.extensions = extensions

    def call_back3():
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
