import os
import json

import sublime
import sublime_plugin


def nearest_color(color):
    b = int(color[5:7], 16)
    b += 1 - 2 * (b == 255)
    return color[:-2] + "%02x" % b


class RainbowBracketsCommand(sublime_plugin.WindowCommand):
    def run(self, action):
        if action == "force_add_view":
            RainbowBracketsManager.force_add_view(
                self.window.active_view())

        elif action == "clear_view":
            RainbowBracketsManager.clear_and_ignore_view(
                self.window.active_view())

        elif action == "clear_color_schemes":
            RainbowBracketsManager.clear_color_schemes()


class RainbowBracketsViewEventListener(sublime_plugin.ViewEventListener):
    color_number = 7
    all_brackets = {}
    languages = {}
    plain_text = {}
    plain_text = {
        "opening": set(),
        "closing": set()
    }

    @classmethod
    def is_applicable(cls, settings):
        return settings.get("rb_enable", True) and settings.has("rb_syntax")

    def __init__(self, view):
        syntax = view.settings().get("rb_syntax")
        values = self.languages.get(syntax, self.plain_text)
        self.opening = values["opening"]
        self.closing = values["closing"]
        self.view = view
        self.keys = set()
        self.on_load()

    def on_activated(self):
        pass

    def on_modified(self):
        self.on_load()

    def on_load(self):
        if not (self.opening and self.closing):
            return
        region = sublime.Region(0, self.view.size())
        tokens = self.view.extract_tokens_with_scopes(region)
        if len(tokens) < 1:
            return
        self.find_all_brackets(tokens, self.opening, self.closing)
        self.clear_brackets()

        if self.matched:
            regions_by_level = [[] for i in range(self.color_number)]
            for level, regions in enumerate(self.matched):
                regions_by_level[level % self.color_number].extend(regions)

            for level, regions in enumerate(regions_by_level):
                if regions:
                    key = "level%d_rainbow" % level
                    self.keys.add(key)
                    self.view.add_regions(key, regions,
                        scope="level%d.rainbow" % level,
                        flags=sublime.DRAW_NO_OUTLINE|sublime.PERSISTENT)
        if self.mismatched:
            self.keys.add("mismatched_rainbow")
            self.view.add_regions("mismatched_rainbow", self.mismatched,
                scope="mismatched.rainbow",
                flags=sublime.DRAW_EMPTY|sublime.PERSISTENT)

    def clear_brackets(self):
        for key in self.keys:
            self.view.erase_regions(key)
        self.keys.clear()

    def find_all_brackets(self, tokens, opening, closing):
        self.matched, self.mismatched = [], []
        begin, end = tokens[0][0].a, tokens[-1][0].b
        contents = self.view.substr(sublime.Region(begin, end))

        stack, regions = [], []
        for region, scope in tokens:
            token = contents[region.a - begin:region.b - begin]
            # skip ignore
            if ("comment" in scope or "string" in scope or
                "char" in scope or "symbol" in scope):
                continue

            if token in opening:
                regions.append(region)
                stack.append(token)
                if len(stack) > len(self.matched):
                    self.matched.append([])
            elif token in closing:
                if stack and token == self.all_brackets[stack[-1]]:
                    stack.pop()
                    self.matched[len(stack)].append(regions.pop())
                    self.matched[len(stack)].append(region)
                else:
                    self.mismatched.append(region)
            else:
                continue


class RainbowBracketsManager(sublime_plugin.EventListener):
    color_scheme = "Monokai.sublime-color-scheme"

    @classmethod
    def init(cls):
        load_settings = sublime.load_settings
        cls.settings = load_settings("RainbowBrackets.sublime-settings")
        cls.preferences = load_settings("Preferences.sublime-settings")
        cls.settings.add_on_change("rainbow_colors", cls.update_color_scheme)
        cls.preferences.add_on_change("color_scheme", cls.rebuild_color_scheme)
        cls.update_color_scheme()
        cls.languages = RainbowBracketsViewEventListener.languages

    @classmethod
    def check_view_syntax(cls, view):
        syntax = os.path.splitext(
            os.path.basename(view.settings().get("syntax")))[0].lower()

        if (syntax in cls.languages):
            return syntax
        elif view.file_name():
            extension = os.path.splitext(view.file_name())[1].lstrip(".")
            for syntax, values in cls.languages.items():
                if extension in values["extensions"]:
                    return syntax
        return None

    @classmethod
    def check_add_view(cls, view, force=False):
        settings = view.settings()
        if (settings.get("rb_enable", True) and
            not settings.has("rb_syntax")):
            syntax = cls.check_view_syntax(view)
            if syntax is not None:
                settings.set("rb_syntax", syntax)
            elif force is True:
                settings.set("rb_syntax", "plain_text")

    @classmethod
    def force_add_view(cls, view):
        view.settings().set("rb_enable", True)
        cls.check_add_view(view, force=True)
        sublime_plugin.check_view_event_listeners(view)

    @classmethod
    def clear_and_ignore_view(cls, view):
        listener = sublime_plugin.find_view_event_listener(view,
            RainbowBracketsViewEventListener)
        if listener is not None:
            listener.clear_brackets()
            view.settings().set("rb_enable", False)
            sublime_plugin.check_view_event_listeners(view)

    @classmethod
    def cache_path(cls):
        return os.path.join(sublime.packages_path(),
            "User", "Color Schemes", "RainbowBrackets")

    @classmethod
    def color_scheme_name(cls):
        return os.path.basename(
            cls.color_scheme).replace("tmTheme", "sublime-color-scheme")

    @classmethod
    def clear_color_schemes(cls, all=False):
        color_scheme_path = cls.cache_path()
        color_scheme_name = cls.color_scheme_name()
        for file in os.listdir(color_scheme_path):
            if file != color_scheme_name or all:
                try:
                    os.remove(os.path.join(color_scheme_path, file))
                except:
                    pass

    @classmethod
    def rebuild_color_scheme(cls):
        scheme = cls.preferences.get("color_scheme", cls.color_scheme)
        if scheme != cls.color_scheme:
            cls.color_scheme = scheme
            cls.build_color_scheme()

    @classmethod
    def build_color_scheme(cls):
        styles = sublime.active_window().active_view().style()
        background = nearest_color(styles["background"])

        color_scheme_path = cls.cache_path()
        color_scheme_name = cls.color_scheme_name()
        color_scheme_file = os.path.join(color_scheme_path, color_scheme_name)
        color_scheme_data = {
            "name": os.path.splitext(os.path.basename(cls.color_scheme))[0],
            "author": "RainbowBrackets",
            "variables": {},
            "globals": {},
            "rules": [
                {
                    "scope": "level%d.rainbow" % level,
                    "foreground": color,
                    "background": background
                }
                for level, color in enumerate(cls.rainbow_colors["matched"])
            ] + [
                {
                    "scope": "mismatched.rainbow",
                    "foreground": cls.rainbow_colors["mismatched"],
                    "background": styles["background"]
                }
            ]
        }
        # We only need to write a same named color_scheme,
        # sublime will load and apply it automatically.
        os.makedirs(color_scheme_path, exist_ok=True)
        with open(color_scheme_file, "w+") as file:
            file.write(json.dumps(color_scheme_data))

    @classmethod
    def update_color_scheme(cls):
        cls.rainbow_colors = cls.settings.get("rainbow_colors", {})
        velcls = RainbowBracketsViewEventListener
        velcls.color_number = len(cls.rainbow_colors["matched"])
        velcls.plain_text["opening"].clear()
        velcls.plain_text["closing"].clear()
        velcls.all_brackets.clear()
        velcls.languages.clear()
        for o, c in cls.settings.get("all_brackets", {}).items():
            velcls.plain_text["opening"].add(o)
            velcls.plain_text["closing"].add(c)
            velcls.all_brackets[o] = c
            velcls.all_brackets[c] = o

        for lang in cls.settings.get("languages", []):
            lang["opening"] = opening = set(lang["opening"])
            lang["closing"] = set(velcls.all_brackets[b] for b in opening)
            velcls.languages[lang.pop("syntax")] = lang

        cls.build_color_scheme()

    def on_post_save(self, view):
        RainbowBracketsManager.check_add_view(view)

    def on_activated(self, view):
        RainbowBracketsManager.check_add_view(view)


def plugin_loaded():
    RainbowBracketsManager.init()
