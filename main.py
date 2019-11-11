import os

import sublime
import sublime_plugin

from .lib import Loger
from .lib import Color


class RainbowBracketsCommand(sublime_plugin.TextCommand):
    def run(self, edit, action):
        Loger.print("RainbowBrackets: " + action)

        if action == "make rainbow":
            RainbowBracketsViewsManager.force_tinct_view(self.view)
        elif action == "clear rainbow":
            RainbowBracketsViewsManager.clear_view(self.view)
        elif action == "toggle log":
            Loger.debug = not Loger.debug
        elif action == "rebuild color scheme":
            Color.clear_color_scheme()


parens_missed = """
    There are no brackets will be matched,
    please check your settings or restart.
"""

syntax_missed = """
    No settings for this kind of file are found,
    it will be treat as a plain text.
"""

color_missed = """
    There are no colors are added, please check
    your settings file or restart Sublime Text.
"""

warn_plain_text = """
    Plain text syntax maybe cause mistaken tokens.
"""


class RainbowBracketsViewListener(object):
    def __init__(self, view, syntax):
        self.view = view
        self.syntax = syntax
        self.keys = set()
        specific = Color.syntax_specific[self.syntax]
        self.opening = specific["opening"]
        self.closing = specific["closing"]

        if not self.opening:
            Loger.warn(parens_missed)

    def erase_regions(self):
        for key in self.keys:
            self.view.erase_regions(key)
        self.keys.clear()

    def add_regions(self):
        self.erase_regions()

        if self.matched:
            rbuckets = [[] for i in range(Color.color_number)]
            for level in range(len(self.matched)):
                regions = self.matched[level]
                rbuckets[level % Color.color_number].extend(regions)

            for l in range(Color.color_number):
                key, scope, color = Color.key_scope_colors[l]
                self.view.add_regions(key, rbuckets[l],
                    scope=scope,
                    flags=sublime.DRAW_NO_OUTLINE)
                self.keys.add(key)

        if self.mismatched:
            self.view.add_regions(Color.mismatched_key, self.mismatched,
                scope=Color.mismatched_scope,
                flags=sublime.DRAW_EMPTY)
            self.keys.add(Color.mismatched_key)

    def on_load(self):
        if not (self.opening and self.closing):
            return
        region = sublime.Region(0, self.view.size())
        tokens = self.view.extract_tokens_with_scopes(region)
        if len(tokens) < 1:
            return
        self.get_all_brackets(tokens, self.opening, self.closing)
        self.add_regions()

    def on_modified(self):
        self.on_load()

    def get_all_brackets(self, tokens, opening, closing):
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
                if stack and token == Color.parents[stack[-1]]:
                    stack.pop()
                    self.matched[len(stack)].append(regions.pop())
                    self.matched[len(stack)].append(region)
                else:
                    self.mismatched.append(region)
            else:
                continue


class RainbowBracketsViewsManager(sublime_plugin.EventListener):
    tincted_views = {}
    ignored_views = {}

    @classmethod
    def do_tinct_view(cls, view, syntax):
        view_listener = RainbowBracketsViewListener(view, syntax)
        view_listener.on_load()
        cls.tincted_views[view.view_id] = view_listener

        file = view.file_name() or "untitled"
        entry = ["do_tinct_view:", "file: {}", "syntax: {}"]
        Loger.print("\n\t".join(entry).format(file, syntax))

    @classmethod
    def syntax_for_view(cls, view):
        syntax = view.settings().get("syntax")
        syntax, ext = os.path.splitext(os.path.basename(syntax))
        return syntax.lower()

    # if view is ignored, recover it
    @classmethod
    def try_load_view(cls, view):
        syntax = cls.syntax_for_view(view)
        if view.view_id in cls.ignored_views:
            view_listener = cls.ignored_views.pop(view.view_id)
            if view_listener.syntax == syntax:
                view_listener.on_load()
                cls.tincted_views[view.view_id] = view_listener
                return

        if (syntax in Color.syntax_specific and
            syntax != Color.plain_text_syntax):
            cls.do_tinct_view(view, syntax)
        elif view.file_name():
            ext = os.path.splitext(view.file_name())[1].lstrip(".")
            for syntax, specific in Color.syntax_specific.items():
                if ext in specific["extensions"]:
                    cls.do_tinct_view(view, syntax)
                    return

    @classmethod
    def force_tinct_view(cls, view):
        if view.view_id not in cls.tincted_views:
            cls.try_load_view(view)
        if view.view_id not in cls.tincted_views:
            syntax = cls.syntax_for_view(view)
            if syntax not in Color.syntax_specific:
                syntax = Color.plain_text_syntax
                Loger.warn(syntax_missed)
            if syntax == Color.plain_text_syntax:
                Loger.warn(warn_plain_text)
            cls.do_tinct_view(view, syntax)

    @classmethod
    def load_view(cls, view):
        # ignore views such as console, commands panel...
        views = sublime.active_window().views()
        if view.size() < 2 or view not in views:
            return
        if view.view_id not in cls.ignored_views:
            cls.try_load_view(view)

    @classmethod
    def clear_view(cls, view):
        if view.view_id in cls.tincted_views:
            view_listener = cls.tincted_views.pop(view.view_id)
            view_listener.erase_regions()
            cls.ignored_views[view.view_id] = view_listener

    @classmethod
    def flush_view(cls, view):
        if view.view_id in cls.tincted_views:
            cls.tincted_views[view.view_id].add_regions()

    @classmethod
    def clear_all(cls):
        for view_listener in cls.tincted_views.values():
            view_listener.erase_regions()

    def on_load(self, view):
        RainbowBracketsViewsManager.load_view(view)

    def on_modified(self, view):
        if view.view_id in self.tincted_views:
            self.tincted_views[view.view_id].on_modified()

    def on_activated(self, view):
        if view.view_id not in self.tincted_views:
            self.on_load(view)

    def on_post_save(self, view):
        self.on_activated(view)

    def on_close(self, view):
        if view.view_id in self.tincted_views:
            self.tincted_views.pop(view.view_id)
        elif view.view_id in self.ignored_views:
            self.ignored_views.pop(view.view_id)


def plugin_loaded():
    def flush_active_view():
        view = sublime.active_window().active_view()
        RainbowBracketsViewsManager.flush_view(view)

    Color.load_settings(flush_active_view)
    if Color.color_number == 0:
        Loger.error(color_missed)
        raise ValueError("No colors are added")

    view = sublime.active_window().active_view()
    sublime.set_timeout(lambda: RainbowBracketsViewsManager.load_view(view), 500)


def plugin_unloaded():
    Color.unload_settings()
    RainbowBracketsViewsManager.clear_all()
