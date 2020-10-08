import re
import os
import json
import time

import sublime
import sublime_plugin


SETTINGS_FILE = "RainbowBrackets.sublime-settings"


class Debuger():
    debug = False
    employer = "RainbowBrackets"

    @classmethod
    def print(cls, *args):
        if cls.debug:
            print("%s:" % cls.employer, *args, sep="\n\t")

    @classmethod
    def pprint(cls, obj):
        class setEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, set):
                    return sorted(obj)
                return json.JSONEncoder.default(self, obj)

        if cls.debug:
            print("%s:" % cls.employer, json.dumps(obj,
                cls=setEncoder, indent=4,
                sort_keys=True, ensure_ascii=False))


class RainbowBracketsCommand(sublime_plugin.WindowCommand):
    def run(self, action):
        view = self.window.active_view()

        if action == "make rainbow":
            view.settings().set("rb_enable", True)
            RainbowBracketsViewListener.check_add_view(view, force=True)
            sublime_plugin.check_view_event_listeners(view)

        elif action == "clear rainbow":
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
    def run(self, edit, operation="", to="", select_content=True):
        if operation == "select":
            self.select_brackets()

        elif operation == "remove":
            self.remove_brackets(edit, select_content)

        elif operation == "transform":
            self.transform(edit, to)

    def select_brackets(self):
        for p in self.find_cursor_brackets():
            cover = self.cover(p[0], p[1])
            self.view.sel().add(cover)

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

    def remove_brackets(self, edit, select_content=True):
        pairs = [p for p in self.find_cursor_brackets()]
        regions = [r for p in pairs for r in p]

        regions.sort()
        for r in reversed(regions):
            self.view.erase(edit, r)

        if select_content:
            selections = []
            for p in pairs:
                begin = p[0].a - regions.index(p[0])
                end = p[1].a - regions.index(p[1])
                selections.append(sublime.Region(begin, end))
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
                                if pairs[stack[-1]] == token:
                                    stack.pop()
                                else:
                                    return False
                            else:
                                if pair[0] is None:
                                    pair[0] = (region, token)
                                    return True
                                elif pair[0][1] == pairs[token]:
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
        values = RainbowBracketsViewListener.get_brackets(view)
        o = values["opening"]
        c = values["closing"]
        pairs = values["pairs"]
        selector = values["selector"]

        self.bracket_pairs = pairs

        substr = view.substr
        match_selector = view.match_selector
        begin, end = region.begin(), region.end()
        left = sublime.Region(begin - 1, begin)
        right = sublime.Region(end, end + 1)
        search(left, o, c, last) and search(right, c, o, next)

        return pair[0] and pair[1] and (pair[0][0], pair[1][0])


class RainbowBracketsViewListener(sublime_plugin.ViewEventListener):
    is_ready = False
    color_number = 7
    filetypes = {}

    @classmethod
    def read_settings(cls, settings):
        cls.is_ready = False

        Debuger.debug = settings.get("debug", False)

        rainbow_colors = settings.get("rainbow_colors", {})
        color_number = len(rainbow_colors.get("matched", []))

        brackets = settings.get("brackets", {})
        brackets_pairs = brackets.get("pairs", {})
        filetypes = brackets.get("filetypes", {})
        default = filetypes.get("default", {})

        if color_number == 0 or len(brackets_pairs) == 0:
            msg = "RainbowBrackets: settings are loading..."
            sublime.status_message(msg)
            return

        default_opening = default.get("opening", [])
        default_ignored_scopes = default.get("ignored_scopes", [])
        for ftype, values in filetypes.items():
            opening = values.get("opening", default_opening)
            closing = []
            pairs = {}
            for o in opening:
                c = brackets_pairs[o]
                pairs[o] = c
                pairs[c] = o
                closing.append(c)

            values["pairs"] = pairs
            values["opening"] = set(opening)
            values["closing"] = set(closing)
            values["pattern"] = "|".join(re.escape(b) for b in sorted(pairs))
            values["selector"] = "|".join(
                ("ignored_scopes" in values and values.pop("ignored_scopes")
                    or default_ignored_scopes)
            )

        Debuger.pprint(filetypes)

        cls.color_number = color_number
        cls.filetypes = filetypes
        cls.is_ready = True

    @classmethod
    def get_brackets(cls, view):
        syntax = view.settings().get("rb_syntax", "default")
        return cls.filetypes.get(syntax)

    @classmethod
    def check_add_view(cls, view, force=False):
        if not cls.is_ready:
            if force:
                msg = "RainbowBrackets: error in loading settings."
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
        self.pairs = values["pairs"]
        self.opening = values["opening"]
        self.closing = values["closing"]
        self.pattern = values["pattern"]
        self.selector = values["selector"]
        self.matched_regions = []
        self.mismatched_regions = []
        self.need_clean = True
        self.view = view

        start = time.time()

        self.add_bracket_regions()

        end = time.time()

        Debuger.print(
            "loaded file: " + (self.view.file_name() or "untitled"),
            "pattern: " + self.pattern,
            "selector: " + self.selector,
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
        sels = [r for r in self.view.sel()]
        if len(sels) == 1 and sels[0].a == self.view.size():
            return
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
        opening, pairs = self.opening, self.pairs
        number_levels = self.color_number
        full_text = view.substr(sublime.Region(0, view.size()))

        matched_regions = []
        matched_appends = []
        for i in range(number_levels):
            regions = list()
            matched_regions.append(regions)
            matched_appends.append(regions.append)

        bracket_stack, region_stack = [], []
        region_stack_append = region_stack.append
        bracket_stack_append = bracket_stack.append
        region_stack_pop = region_stack.pop
        bracket_stack_pop = bracket_stack.pop

        if selector:
            for region in view.find_all(self.pattern):
                if view.match_selector(region.a, selector):
                    continue

                bracket = full_text[region.a:region.b]

                if bracket in opening:
                    region_stack_append(region)
                    bracket_stack_append(bracket)

                elif bracket_stack and bracket == pairs[bracket_stack[-1]]:
                    bracket_stack_pop()
                    level = len(bracket_stack) % number_levels
                    matched_appends[level](region_stack_pop())
                    matched_appends[level](region)

                else:
                    self.mismatched_regions.append(region)
        else:
            for region in view.find_all(self.pattern):
                bracket = full_text[region.a:region.b]

                if bracket in opening:
                    region_stack_append(region)
                    bracket_stack_append(bracket)

                elif bracket_stack and bracket == pairs[bracket_stack[-1]]:
                    bracket_stack_pop()
                    level = len(bracket_stack) % number_levels
                    matched_appends[level](region_stack_pop())
                    matched_appends[level](region)

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
