import re
import os
import json
import time

import sublime
import sublime_plugin

from sublime import Region

SETTINGS_FILE = "RainbowBrackets.sublime-settings"


class Debuger():
    debug = False
    employer = "RainbowBrackets"

    @classmethod
    def print(cls, *args, **kwargs):
        if cls.debug:
            print(f"{cls.employer}:", *args, **kwargs)

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


class Tree:
    __slots__ = ["opening", "closing", "contain"]

    def __init__(self, opening, closing, contain):
        self.opening = opening
        self.closing = closing
        self.contain = contain


class RainbowBracketsControllerCommand(sublime_plugin.WindowCommand):
    def run(self, action):
        view = self.window.active_view()

        if action == "setup plugin":
            RainbowBracketsViewManager.setup_view_listener(view)

        elif action == "close plugin":
            RainbowBracketsViewManager.close_view_listener(view)

        elif action == "make rainbow":
            RainbowBracketsViewManager.color_view(view)

        elif action == "clear rainbow":
            RainbowBracketsViewManager.sweep_view(view)

        elif action == "toggle debug":
            Debuger.debug = not Debuger.debug
            sublime.load_settings(SETTINGS_FILE).set("debug", Debuger.debug)
            sublime.save_settings(SETTINGS_FILE)

        elif action == "clear color schemes":
            ColorSchemeManager.clear_color_schemes()


class RainbowBracketsOperationsCommand(sublime_plugin.TextCommand):
    def run(self, edit, operation="", to="", select_content=True):
        def find_cursor_brackets(regex=None):
            last_bracket = None
            for region in view.sel():
                bracket = self.find_nearest(trees, region, regex)
                if bracket is None or bracket == last_bracket:
                    continue
                else:
                    last_bracket = bracket
                    yield bracket

        view  = self.view
        trees = RainbowBracketsViewManager.get_view_bracket_trees(view)
        if not trees:
            return

        if operation == "select":
            regex = to and re.compile(to + r'\b') or None
            for p in find_cursor_brackets(regex=regex):
                region = self.cover(p)
                view.sel().add(region)

        elif operation == "remove":
            pairs = [p for p in find_cursor_brackets()]
            regions = [r for p in pairs for r in p]
            regions.sort()
            for r in reversed(regions):
                view.erase(edit, r)
            if select_content:
                selections = []
                for p in pairs:
                    begin = p[0].a - regions.index(p[0])
                    end = p[1].a - regions.index(p[1])
                    selections.append(Region(begin, end))
                view.sel().add_all(selections)

        elif operation == "transform":
            mapping = RainbowBracketsViewManager.get_view_bracket_pairs(view)
            replace_list = []
            for p in find_cursor_brackets():
                if view.substr(p[0]) == to:
                    continue
                replace_list.append((p[0], to))
                replace_list.append((p[1], mapping[to]))
            replace_list.sort(key=lambda i:i[0], reverse=True)
            for region, content in replace_list:
                view.replace(edit, region, content)

    def cover(self, bracket_pair):
        return Region(bracket_pair[0].a, bracket_pair[1].b)

    def find_nearest(self, trees, r, regex):
        pairs = self.binary_path_search(trees, r.begin(), r.end())
        bracket = None
        if pairs and regex is not None:
            for p in reversed(pairs):
                point = p[0].end()
                text = self.view.substr(Region(point, point + 31))
                if regex.match(text) is not None:
                    bracket = p
                    break
            else:
                bracket = pairs[0]
        elif pairs:
            bracket = pairs[-1]

        if bracket is None and r.empty():
            for tree in trees:
                if (tree.opening.a == r.a or
                    tree.closing.b == r.a):
                    bracket = (tree.opening, tree.closing)
                    break
        return bracket

    def binary_path_search(self, trees, r_begin, r_end):
        bracket_path = []
        while True:
            found_closer = False
            lo, hi = 0, len(trees) - 1
            while lo <= hi:
                mi = (lo + hi) >> 1
                tr = trees[mi]
                oa = tr.opening.a
                cb = tr.closing.b
                if cb < r_begin:
                    lo = mi + 1
                elif oa > r_end:
                    hi = mi - 1
                else:
                    if oa < r_begin and r_end < cb:
                        found_closer = True
                        trees = tr.contain
                        p = (tr.opening, tr.closing)
                        bracket_path.append(p)
                    break
            if not found_closer:
                break
        return bracket_path


class RainbowBracketsViewListener():
    def __init__(self, view, syntax, config):
        self.bad_key   = config["bad_key"]
        self.bad_scope = config["bad_scope"]
        self.coloring  = config["coloring"]
        self.keys      = config["keys"]
        self.brackets  = config["bracket_pairs"]
        self.pattern   = config["pattern"]
        self.scopes    = config["scopes"]
        self.selector  = config["selector"]
        self.color_number = len(self.keys)
        self.bad_bracket_regions   = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []
        self.regexp = re.compile(self.pattern)
        self.syntax = syntax
        self.view = view

    def __del__(self):
        Debuger.print(f"exiting from file {self.view_file_name()}")
        self.clear_bracket_regions()

    def view_file_name(self):
        return os.path.basename(self.view.file_name() or 'untitled')

    def load(self):
        start = time.time()
        self.check_bracket_regions()
        end = time.time()
        Debuger.print(
            f"loaded file: {self.view_file_name()}",
            f"pattern: {self.pattern}",
            f"selector: {self.selector}",
            f"syntax: {self.syntax}",
            f"coloring: {self.coloring}",
            f"cost time: {end - start:>.2f}",
            sep="\n\t")

    # TODO: Update the bracket trees dynamically rather
    # than reconstruct them from beginning every time.
    def check_bracket_regions(self):
        if self.coloring:
            self.construct_bracket_trees_and_lists()
            self.clear_bracket_regions()
            if self.bracket_regions_lists:
                for level, regions in enumerate(self.bracket_regions_lists):
                    self.view.add_regions(
                        self.keys[level],
                        regions,
                        scope=self.scopes[level],
                        flags=sublime.DRAW_NO_OUTLINE|sublime.PERSISTENT)
            if self.bad_bracket_regions:
                self.view.add_regions(
                    self.bad_key,
                    self.bad_bracket_regions,
                    scope=self.bad_scope,
                    flags=sublime.DRAW_EMPTY|sublime.PERSISTENT)
        else:
            self.construct_bracket_trees()

    def clear_bracket_regions(self):
        self.view.erase_regions(self.bad_key)
        for key in self.keys:
            self.view.erase_regions(key)

    def construct_bracket_trees(self):
        self.bracket_regions_trees = []

        brackets       = self.brackets
        selector       = self.selector
        number_levels  = self.color_number
        match_selector = self.view.match_selector
        view_full_text = self.view.substr(Region(0, self.view.size()))
        match_iterator = self.regexp.finditer(view_full_text)

        opening_stack          = []
        tree_node_stack        = [Tree(None, None, self.bracket_regions_trees)]
        tree_node_stack_append = tree_node_stack.append
        opening_stack_append = opening_stack.append
        tree_node_stack_pop = tree_node_stack.pop
        opening_stack_pop = opening_stack.pop

        def handle(bracket, region):
            if bracket in brackets:
                tree_node_stack_append(Tree(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)

        self.handle_matches(selector, match_selector, match_iterator, handle)

    def construct_bracket_trees_and_lists(self):
        self.bad_bracket_regions   = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []

        brackets       = self.brackets
        selector       = self.selector
        number_levels  = self.color_number
        match_selector = self.view.match_selector
        view_full_text = self.view.substr(Region(0, self.view.size()))
        match_iterator = self.regexp.finditer(view_full_text)

        opening_stack          = []
        tree_node_stack        = [Tree(None, None, self.bracket_regions_trees)]
        tree_node_stack_append = tree_node_stack.append
        opening_stack_append = opening_stack.append
        tree_node_stack_pop = tree_node_stack.pop
        opening_stack_pop = opening_stack.pop

        regions_by_level = [list() for i in range(number_levels)]
        appends_by_level = [rs.append for rs in regions_by_level]

        def handle(bracket, region):
            if bracket in brackets:
                tree_node_stack_append(Tree(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)
                level = len(opening_stack) % number_levels
                appends_by_level[level](node.opening)
                appends_by_level[level](node.closing)
            else:
                self.bad_bracket_regions.append(region)

        self.handle_matches(selector, match_selector, match_iterator, handle)
        self.bracket_regions_lists = [ls for ls in regions_by_level if ls]

    def handle_matches(self, selector, match_selector, match_iterator, handle):
        if selector:
            for m in match_iterator:
                if match_selector(m.span()[0], selector):
                    continue
                handle(m.group(), Region(*m.span()))
        else:
            for m in match_iterator:
                handle(m.group(), Region(*m.span()))


class RainbowBracketsViewManager(sublime_plugin.EventListener):
    configs_by_stx = {}
    syntaxes_by_ext = {}
    view_listeners = {}
    is_ready = False

    @classmethod
    def load_config(cls, settings):
        cls.is_ready = False

        Debuger.debug = settings.get("debug", False)

        default_config = settings.get("default_config", {})
        configs_by_stx = settings.get("syntax_specific", {})
        syntaxes_by_ext = {}

        for syntax, config in configs_by_stx.items():
            for key in ("enabled", "coloring"):
                if key not in config:
                    config[key] = True
            for key in default_config.keys():
                if key not in config:
                    config[key] = default_config[key]
            for ext in config.get("extensions", []):
                syntaxes_by_ext[ext] = syntax

        if "coloring" not in default_config:
            default_config["coloring"] = False
        if "enabled" not in default_config:
            default_config["enabled"] = True

        configs_by_stx["<default>"] = default_config

        for syntax, config in configs_by_stx.items():
            levels = range(len(config["rainbow_colors"]))
            config["keys"]   = ["rb_l%d_%s" % (i, syntax) for i in levels]
            config["scopes"] = ["%s.l%d.rb" % (syntax, i) for i in levels]
            config["bad_key"]   = "rb_mismatch_%s" % syntax
            config["bad_scope"] = "%s.mismatch.rb" % syntax

            pairs = config["bracket_pairs"]
            brackets = sorted(list(pairs.keys()) + list(pairs.values()))

            config["pattern"]  = "|".join(re.escape(b) for b in brackets)
            config["selector"] = "|".join(config.pop("ignored_scopes"))

        Debuger.pprint(configs_by_stx)

        cls.syntaxes_by_ext = syntaxes_by_ext
        cls.configs_by_stx = configs_by_stx
        cls.is_ready = True

    @classmethod
    def check_view_add_listener(cls, view, force=False):
        if not cls.is_ready:
            if force:
                msg = "RainbowBrackets: error in loading settings."
                sublime.error_message(msg)
            return

        if view.view_id in cls.view_listeners:
            return cls.view_listeners[view.view_id]

        if view.settings().get("rb_enable", True):
            syntax = cls.get_view_syntax(view) or "<default>"
            config = cls.configs_by_stx[syntax]
            if config["enabled"] or force:
                if config["bracket_pairs"]:
                    listener = RainbowBracketsViewListener(view, syntax, config)
                    cls.view_listeners[view.view_id] = listener
                    return listener
                elif force:
                    sublime.error_message("empty brackets list")
        return None

    @classmethod
    def get_view_syntax(cls, view):
        syntax = view.syntax().name
        if syntax in cls.configs_by_stx:
            return syntax
        filename = view.file_name()
        if filename:
            ext = os.path.splitext(filename)[1]
            return cls.syntaxes_by_ext.get(ext, None)
        return None

    @classmethod
    def force_add_listener(cls, view):
        view.settings().set("rb_enable", True)
        return cls.check_view_add_listener(view, force=True)

    @classmethod
    def get_view_listener(cls, view):
        return cls.view_listeners.get(view.view_id, None)

    @classmethod
    def check_view_load_listener(cls, view):
        listener = view.size() and cls.check_view_add_listener(view)
        if listener and not listener.bracket_regions_trees:
            listener.load()

    @classmethod
    def setup_view_listener(cls, view):
        listener = cls.force_add_listener(view)
        listener and listener.load()

    @classmethod
    def close_view_listener(cls, view):
        view.settings().set("rb_enable", False)
        listener = cls.view_listeners.pop(view.view_id, None)
        if listener and listener.coloring:
            listener.clear_bracket_regions()

    @classmethod
    def color_view(cls, view):
        listener = cls.get_view_listener(view)
        if listener and not listener.coloring:
            listener.coloring = True
            listener.check_bracket_regions()
        elif not listener:
           listener = cls.force_add_listener(view)
           if listener:
                listener.coloring = True
                listener.load()

    @classmethod
    def sweep_view(cls, view):
        listener = cls.get_view_listener(view)
        if listener and listener.coloring:
            listener.coloring = False
            listener.clear_bracket_regions()

    @classmethod
    def get_view_bracket_pairs(cls, view):
        listener = cls.get_view_listener(view)
        return listener and listener.brackets

    @classmethod
    def get_view_bracket_trees(cls, view):
        listener = cls.get_view_listener(view)
        if not listener:
            cls.setup_view_listener(view)
            listener = cls.get_view_listener(view)
        return listener and listener.bracket_regions_trees

    def on_load(self, view):
        self.check_view_load_listener(view)

    def on_post_save(self, view):
        self.check_view_load_listener(view)

    def on_activated(self, view):
        self.check_view_load_listener(view)

    def on_modified(self, view):
        listener = self.view_listeners.get(view.view_id, None)
        listener and listener.check_bracket_regions()

    def on_close(self, view):
        self.view_listeners.pop(view.view_id, None)


class ColorSchemeManager(sublime_plugin.EventListener):
    DEFAULT_CS = "Packages/Color Scheme - Default/Monokai.sublime-color-scheme"

    @classmethod
    def init(cls):
        def load_settings_build_cs():
            RainbowBracketsViewManager.load_config(cls.settings)
            cls.build_color_scheme()

        cls.prefs = sublime.load_settings("Preferences.sublime-settings")
        cls.settings = sublime.load_settings(SETTINGS_FILE)
        cls.prefs.add_on_change("color_scheme", cls.rebuild_color_scheme)
        cls.settings.add_on_change("default_config", load_settings_build_cs)
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

        rules = []
        for value in RainbowBracketsViewManager.configs_by_stx.values():
            rules.append({
                "scope": value["bad_scope"],
                "foreground": value["mismatch_color"],
                "background": background
            })
            for scope, color in zip(value["scopes"], value["rainbow_colors"]):
                rules.append({
                    "scope": scope,
                    "foreground": color,
                    "background": nearest_background
                })
        color_scheme_data = {
            "name": os.path.splitext(os.path.basename(cls.color_scheme))[0],
            "author": "https://github.com/absop/RainbowBrackets",
            "variables": {},
            "globals": {},
            "rules": rules
        }

        color_scheme_path = cls.color_scheme_cache_path()
        color_scheme_name = cls.color_scheme_name()
        color_scheme_file = os.path.join(color_scheme_path, color_scheme_name)
        # We only need to write a same named color_scheme,
        # then sublime will load and apply it automatically.
        os.makedirs(color_scheme_path, exist_ok=True)
        with open(color_scheme_file, "w+") as file:
            file.write(json.dumps(color_scheme_data))
            Debuger.print(f"write color scheme {color_scheme_file}")


def plugin_loaded():
    def load_plugin():
        ColorSchemeManager.init()
        active_view = sublime.active_window().active_view()
        RainbowBracketsViewManager.check_view_load_listener(active_view)

    sublime.set_timeout_async(load_plugin)


def plugin_unloaded():
    ColorSchemeManager.prefs.clear_on_change("color_scheme")
    ColorSchemeManager.settings.clear_on_change("default_config")
