import re
import os
import json
import time

import sublime
import sublime_plugin


SETTINGS_FILE = "RainbowBrackets.sublime-settings"


class Debuger():
    debug = False

    @classmethod
    def print(cls, *args):
        if cls.debug:
            print("RainbowBrackets:", *args, sep="\n\t")


class RainbowBracketsCommand(sublime_plugin.WindowCommand):
    def run(self, action):
        view = self.window.active_view()

        if action == "force add view":
            view.settings().set("rb_enable", True)
            RainbowBracketsViewListener.check_add_view(view, force=True)
            sublime_plugin.check_view_event_listeners(view)

        elif action == "clear view":
            if (view.settings().has("rb_syntax") and
                view.settings().get("rb_enable", True)):
                view.settings().set("rb_enable", False)
                sublime_plugin.check_view_event_listeners(view)

        elif action == "toggle debug":
            Debuger.debug = not Debuger.debug
            sublime.load_settings(SETTINGS_FILE).set("debug", Debuger.debug)
            sublime.save_settings(SETTINGS_FILE)

        elif action == "clear color schemes":
            ColorSchemeManager.clear_color_schemes()


class OperateBracketsCommand(sublime_plugin.TextCommand):
    def run(self, edit, action="", to="", select_content=True):
        if action == "select":
            for p in self.find_cursor_brackets():
                cover = self.cover(p[0], p[1])
                self.view.sel().add(cover)

        elif action == "transform":
            self.transform(edit, to)

        elif action == "remove":
            self.remove(edit, select_content)

    def transform(self, edit, to):
        replace_list = []
        for p in self.find_cursor_brackets():
            if self.view.substr(p[0]) == to:
                continue
            replace_list.append((p[0], to))
            replace_list.append((p[1], self.bracket_pairs[to]))

        replace_list.sort(key=lambda i:i[0], reverse=True)
        for region, content in replace_list:
            self.view.replace(edit, region, content)

    def remove(self, edit, select_content=True):
        brackets = [p for p in self.find_cursor_brackets()]
        regions = [r for p in brackets for r in p]

        regions.sort()
        for r in reversed(regions):
            self.view.erase(edit, r)

        if select_content:
            selections = []
            for p in brackets:
                begin = p[0].a - regions.index(p[0])
                end = p[1].a - regions.index(p[1])
                selection = sublime.Region(begin, end)
                selections.append(selection)
            self.view.sel().add_all(selections)

    def cover(self, left, right):
        return sublime.Region(left.a, right.b)

    def find_cursor_brackets(self):
        pairs = []
        for region in self.view.sel():
            brackets = self.search_nearest_brackets(region)
            if brackets:
                if pairs and brackets == pairs[-1]:
                    continue
                else:
                    pairs.append(brackets)
        return pairs

    def search_nearest_brackets(self, region):
        def search(region, opening, closing, next):
            stack = []
            while full_text_region.contains(region):
                tokens = view.extract_tokens_with_scopes(region)
                if tokens:
                    region, scope = tokens[0]
                    if not match_selector(region.a, selector):
                        token = substr(region)
                        if token in opening:
                            if stack:
                                if p[stack[-1]] == token:
                                    stack.pop()
                                else:
                                    return False
                            else:
                                if pair[0] is None:
                                    pair[0] = (region, token)
                                    return True
                                elif pair[0][1] == p[token]:
                                    pair[1] = (region, token)
                                    return True
                        elif token in closing:
                            stack.append(token)
                    next(region)
                else:
                    return False
            return False

        def last(region):
            region.a = region.b = region.begin() - 1

        def next(region):
            region.a = region.end()
            region.b = region.a + 1

        view, pair = self.view, [None, None]
        full_text_region = sublime.Region(0, view.size())
        p, o, c, selector = RainbowBracketsViewListener.get_brackets(view)
        self.bracket_pairs = p

        match_selector, substr = view.match_selector, view.substr
        begin, end = region.begin(), region.end()
        l = sublime.Region(begin - 1, begin)
        r = sublime.Region(end, end + 1)
        search(l, o, c, last) and search(r, c, o, next)

        return pair[0] and pair[1] and (pair[0][0], pair[1][0])


class RainbowBracketsViewListener(sublime_plugin.ViewEventListener):
    is_ready = False
    color_number = 7
    bracket_pairs = {}
    filetypes = {}

    @classmethod
    def read_settings(cls, settings):
        Debuger.debug = settings.get("debug", False)
        brackets = settings.get("brackets", {})
        rainbow_colors = settings.get("rainbow_colors", {})

        cls.is_ready = True
        cls.color_number = len(rainbow_colors.get("matched", []))
        cls.bracket_pairs = pairs = {}
        cls.filetypes = filetypes = brackets.get("filetypes", {})

        for o, c in brackets.get("pairs", {}).items():
            cls.bracket_pairs[o] = c
            cls.bracket_pairs[c] = o

        default = filetypes.get("default", {})
        for ftype, value in filetypes.items():
            for key in ("ignored_scopes", "opening"):
                if key not in value:
                    value[key] = default.get(key, [])

            value["opening"] = set(value["opening"])
            value["closing"] = set(pairs[o] for o in value["opening"])
            value["selector"] = "|".join(value["ignored_scopes"])

        if cls.color_number == 0 or len(cls.bracket_pairs) == 0:
            msg = "RainbowBrackets: settings are loading..."
            sublime.status_message(msg)
            cls.is_ready = False

    @classmethod
    def get_brackets(cls, view):
        syntax = view.settings().get("rb_syntax", "default")
        values = cls.filetypes.get(syntax)
        return (cls.bracket_pairs,
            values["opening"],
            values["closing"],
            values["selector"])

    @classmethod
    def check_add_view(cls, view, force=False):
        if not cls.is_ready:
            if force:
                msg = "RainbowBrackets: settings loading error."
                sublime.error_message(msg)
            return

        def check_view_syntax(view, settings):
            syntax = os.path.splitext(
                os.path.basename(settings.get("syntax")))[0].lower()

            if (syntax in cls.filetypes):
                return syntax

            elif view.file_name():
                extension = os.path.splitext(view.file_name())[1].lstrip(".")
                for syntax, values in cls.filetypes.items():
                    if syntax == "default":
                        continue
                    if extension in values["extensions"]:
                        return syntax
            return None

        settings = view.settings()
        if settings.get("rb_enable", True) and not settings.has("rb_syntax"):
            syntax = check_view_syntax(view, settings)

            if syntax is None and force is True:
                syntax = "default"

            if syntax:
                brackets = cls.filetypes.get(syntax)
                if brackets["opening"] and brackets["closing"]:
                    settings.set("rb_syntax", syntax)

    @classmethod
    def is_applicable(cls, settings):
        return settings.get("rb_enable", True) and settings.has("rb_syntax")

    def __init__(self, view):
        syntax = view.settings().get("rb_syntax")
        values = self.filetypes.get(syntax)
        self.opening = values["opening"]
        self.closing = values["closing"]
        self.selector = values["selector"]
        self.matched_regions = []
        self.mismatched_regions = []
        self.need_clean = True
        self.view = view
        self.bracket_pattern = "|".join([
            re.escape(b) for b in self.bracket_pairs
        ])

        start = time.time()

        self.add_bracket_regions()

        end = time.time()

        Debuger.print(
            "loaded file: %s" % self.view.file_name(),
            "selector: %s" % self.selector,
            "cost time: %.5f" % (end - start))

    def __del__(self):
        Debuger.print("exiting from file: %s" % self.view.file_name())
        if self.need_clean:
            self.clear_bracket_regions()
            self.view.settings().erase("rb_syntax")

    def on_pre_close(self):
        self.need_clean = False

    # TODO: A better method to update dynamically.
    def on_modified(self):
        self.clear_bracket_regions()
        self.add_bracket_regions()

    def add_bracket_regions(self):
        self.find_all_bracket_regions()

        if self.matched_regions:
            for level, regions in enumerate(self.matched_regions):
                key = "rb_level%d" % level
                self.view.add_regions(key, regions,
                    scope="level%d.rb" % level,
                    flags=sublime.DRAW_NO_OUTLINE|sublime.PERSISTENT)

        if self.mismatched_regions:
            self.view.add_regions("rb_mismatched", self.mismatched_regions,
                scope="mismatched.rb",
                flags=sublime.DRAW_EMPTY|sublime.PERSISTENT)

    def clear_bracket_regions(self):
        for level in range(len(self.matched_regions)):
            self.view.erase_regions("rb_level%d" % level)
        if self.mismatched_regions:
            self.view.erase_regions("rb_mismatched")
        self.mismatched_regions = []
        self.matched_regions = []

    def find_all_bracket_regions(self):
        view, selector = self.view, self.selector
        opening, pairs = self.opening, self.bracket_pairs
        full_text = view.substr(sublime.Region(0, self.view.size()))

        number_levels = self.color_number
        matched_regions = [list() for i in range(number_levels)]
        bracket_stack, region_stack = [], []

        if selector:
            for region in view.find_all(self.bracket_pattern):
                if view.match_selector(region.a, selector):
                    continue

                bracket = full_text[region.a:region.b]

                if bracket in opening:
                    region_stack.append(region)
                    bracket_stack.append(bracket)

                elif bracket_stack and bracket == pairs[bracket_stack[-1]]:
                    bracket_stack.pop()
                    level = len(bracket_stack) % number_levels
                    matched_regions[level].append(region_stack.pop())
                    matched_regions[level].append(region)

                else:
                    self.mismatched_regions.append(region)
        else:
            for region in view.find_all(self.bracket_pattern):
                bracket = full_text[region.a:region.b]

                if bracket in opening:
                    region_stack.append(region)
                    bracket_stack.append(bracket)

                elif bracket_stack and bracket == pairs[bracket_stack[-1]]:
                    bracket_stack.pop()
                    level = len(bracket_stack) % number_levels
                    matched_regions[level].append(region_stack.pop())
                    matched_regions[level].append(region)

                else:
                    self.mismatched_regions.append(region)

        self.matched_regions = [ls for ls in matched_regions if ls]


class ColorSchemeManager(sublime_plugin.EventListener):
    DEFAULT_CS = "Packages/Color Scheme - Default/Monokai.sublime-color-scheme"

    @classmethod
    def init(cls):
        def load_settings_build_cs():
            RainbowBracketsViewListener.read_settings(cls.settings)
            cls.build_color_scheme()

        cls.prefs = sublime.load_settings("Preferences.sublime-settings")
        cls.settings = sublime.load_settings(SETTINGS_FILE)
        cls.prefs.add_on_change("color_scheme", cls.rebuild_color_scheme)
        cls.settings.add_on_change("rainbow_colors", load_settings_build_cs)
        cls.color_scheme = cls.prefs.get("color_scheme", cls.DEFAULT_CS)

        load_settings_build_cs()

    @classmethod
    def color_scheme_cache_path(cls):
        return os.path.join(sublime.packages_path(),
            "User", "Color Schemes", "RainbowBrackets")

    @classmethod
    def color_scheme_name(cls):
        return os.path.basename(
            cls.color_scheme).replace("tmTheme", "sublime-color-scheme")

    @classmethod
    def clear_color_schemes(cls, all=False):
        color_scheme_path = cls.color_scheme_cache_path()
        color_scheme_name = cls.color_scheme_name()
        for file in os.listdir(color_scheme_path):
            if file != color_scheme_name or all:
                try:
                    os.remove(os.path.join(color_scheme_path, file))
                except:
                    pass

    @classmethod
    def rebuild_color_scheme(cls):
        scheme = cls.prefs.get("color_scheme", cls.DEFAULT_CS)
        if scheme != cls.color_scheme:
            cls.color_scheme = scheme
            cls.build_color_scheme()

    @classmethod
    def build_color_scheme(cls):
        def nearest_color(color):
            b = int(color[5:7], 16)
            b += 1 - 2 * (b == 255)
            return color[:-2] + "%02x" % b

        def color_scheme_background(color_scheme):
            view = sublime.active_window().active_view()
            # origin_color_scheme = view.settings().get("color_scheme")
            view.settings().set("color_scheme", color_scheme)
            background = view.style().get("background")
            # view.settings().set("color_scheme", origin_color_scheme)
            return background

        background = color_scheme_background(cls.color_scheme)
        nearest_background = nearest_color(background)

        rainbow_colors = cls.settings.get("rainbow_colors", {})
        matched_colors = rainbow_colors.get("matched", [])
        mismatched_color = rainbow_colors.get("mismatched", "#FF0000")

        color_scheme_path = cls.color_scheme_cache_path()
        color_scheme_name = cls.color_scheme_name()
        color_scheme_file = os.path.join(color_scheme_path, color_scheme_name)
        color_scheme_data = {
            "name": os.path.splitext(os.path.basename(cls.color_scheme))[0],
            "author": "RainbowBrackets",
            "variables": {},
            "globals": {},
            "rules": [
                {
                    "scope": "level%d.rb" % level,
                    "foreground": color,
                    "background": nearest_background
                }
                for level, color in enumerate(matched_colors)
            ] + [
                {
                    "scope": "mismatched.rb",
                    "foreground": mismatched_color,
                    "background": background
                }
            ]
        }
        # We only need to write a same named color_scheme,
        # then sublime will load and apply it automatically.
        os.makedirs(color_scheme_path, exist_ok=True)
        with open(color_scheme_file, "w+") as file:
            file.write(json.dumps(color_scheme_data))

    def on_post_save(self, view):
        RainbowBracketsViewListener.check_add_view(view)

    def on_activated(self, view):
        RainbowBracketsViewListener.check_add_view(view)


def plugin_loaded():
    def load_plugin():
        ColorSchemeManager.init()
        active_view = sublime.active_window().active_view()
        RainbowBracketsViewListener.check_add_view(active_view)

    load_plugin()
    if not RainbowBracketsViewListener.is_ready:
        sublime.set_timeout(load_plugin, 50)


def plugin_unloaded():
    ColorSchemeManager.prefs.clear_on_change("color_scheme")
    ColorSchemeManager.settings.clear_on_change("rainbow_colors")
