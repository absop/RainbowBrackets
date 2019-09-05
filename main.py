import os
import json

import sublime
import sublime_plugin

from . import profile


class Loger:
    debug = False

    def print(*args):
        if Loger.debug:
            print("[Rainbow Brackets: log]", *args)

    def warning(*args):
        print("[Rainbow Brackets: warning]", *args)


class RainbowToggleLogCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        Loger.debug = not Loger.debug


class RainbowCommand(sublime_plugin.TextCommand):
    def log_command(self):
        filename = self.view.file_name() or "untitled"
        Loger.print("{}:".format(self.name()), filename)


class RainbowTinctViewCommand(RainbowCommand):
    def run(self, edit):
        self.log_command()
        RainbowViewsManager.tinct_view(self.view)


class RainbowClearViewCommand(RainbowCommand):
    def run(self, edit):
        self.log_command()
        RainbowViewsManager.clear_view(self.view)


class RainbowCleanColorSchemesCommand(RainbowCommand):
    def run(self, edit):
        self.log_command()
        current_color_scheme = RainbowViewsManager.color_scheme
        cache_dir = profile._cache_color_scheme_dir(relative=False)
        for color_scheme in os.listdir(cache_dir):
            if color_scheme != current_color_scheme:
                try:
                    os.remove(os.path.join(cache_dir, color_scheme))
                except:
                    pass


class RainbowRebuildColorSchemeCommand(RainbowCommand):
    def run(self, edit):
        self.log_command()
        current_color_scheme = RainbowViewsManager.color_scheme
        RainbowViewsManager.write_color_scheme(current_color_scheme)


class RainbowViewListener(object):
    def __init__(self, view, syntax, brackets, mode=0):
        self.view = view
        self.mode = mode
        self.syntax = syntax

        self.brackets = {}
        for item in brackets.items():
            self.brackets[item[0]] = item[1]
            self.brackets[item[1]] = item[0]

        self.left_brackets = brackets.keys()
        self.right_brackets = brackets.values()

    def clear_all(self):
        for key, scope, color in RainbowViewsManager.key_scope_colors:
            self.view.erase_regions(key)
        self.view.erase_regions(RainbowViewsManager.unmatched_key)

    def on_load(self):
        region = sublime.Region(0, self.view.size())
        self.tinct_within_region(region)

    def on_modified(self):
        if self.mode == profile.RAINBOW_MODE_ALL:
            self.on_load()
        else:
            self.tinct_near_point(self.view.sel()[0].a)

    def on_selection_modified(self):
        if self.mode == profile.RAINBOW_MODE_PART:
            self.tinct_near_point(self.view.sel()[0].a)

    def add_regions_with_level(self, matched_regions):
        bucket_len = RainbowViewsManager.color_number
        region_buckets = [[] for i in range(bucket_len)]
        for level in matched_regions:
            regions = matched_regions[level]
            region_buckets[level % bucket_len].extend(regions)

        for no in range(bucket_len):
            key, scope, color = RainbowViewsManager.key_scope_colors[no]
            regions = region_buckets[no]
            self.view.add_regions(key, regions,
                scope=scope,
                flags=sublime.DRAW_NO_OUTLINE)

    def add_regions(self, matched, unmatched):
        self.clear_all()
        if matched:
            self.add_regions_with_level(matched)

        if unmatched:
            key = RainbowViewsManager.unmatched_key
            self.view.add_regions(key, unmatched,
                scope=RainbowViewsManager.unmatched_scope,
                flags=sublime.DRAW_EMPTY)

    def tinct_within_region(self, region):
        matched, unmatched =  self.get_all_brackets(region)
        self.add_regions(matched, unmatched)

    def tinct_near_point(self, point):
        matched, unmatched = self.get_nearest_brackets(point)
        self.add_regions(matched, unmatched)

    def get_all_brackets(self, region):
        tokens_with_scopes = self.view.extract_tokens_with_scopes(region)
        left_brackets = []
        left_regions = []
        matched_brackets = {}
        unmatched_brackets = []
        match_result = (matched_brackets, unmatched_brackets)
        if len(tokens_with_scopes) >= 1:
            begin = tokens_with_scopes[0][0].a
            end = tokens_with_scopes[-1][0].b
            contents = self.view.substr(sublime.Region(begin, end))
            for region, scope in tokens_with_scopes:
                token = contents[region.a - begin:region.b - begin]
                if token in self.brackets:
                    # skip ignore
                    if ("comment" in scope or "string" in scope or
                        "char" in scope or "symbol" in scope):
                        continue

                    if token in self.left_brackets:
                        left_brackets.append(token)
                        left_regions.append(region)
                    # token in self.right_brackets
                    elif left_brackets and token == self.brackets[left_brackets[-1]]:
                        left_brackets.pop()
                        level = len(left_brackets)
                        matched_brackets.setdefault(level, []).append(left_regions.pop())
                        matched_brackets[level].append(region)
                    else:
                        unmatched_brackets.append(region)
        return match_result

    def get_nearest_brackets(self, point):
        begin = max(point - RainbowViewsManager.maxsize//2, 0)
        end = min(begin + RainbowViewsManager.maxsize, self.view.size())
        left_region = sublime.Region(begin, point)
        right_region = sublime.Region(point, end)
        ltokens = self.view.extract_tokens_with_scopes(left_region)
        rtokens = self.view.extract_tokens_with_scopes(right_region)
        matched_brackets = {}
        unmatched_brackets = []
        match_result = (matched_brackets, unmatched_brackets)
        if ltokens and rtokens:
            if ltokens[-1] == rtokens[0]:
                ltokens.pop()
            begin = (ltokens if ltokens else rtokens)[0][0].a
            end = rtokens[-1][0].b
            lineal_stack, branch_stack = [], []
            contents = self.view.substr(sublime.Region(begin, end))
            ltokens.reverse()
            for region, scope in ltokens:
                token = contents[region.a - begin:region.b - begin]
                if token in self.brackets:
                    # skip ignore
                    if ("comment" in scope or "string" in scope or
                        "char" in scope or "symbol" in scope):
                        continue

                    if token in self.right_brackets:
                        branch_stack.append((region, token))
                    elif branch_stack:
                        if self.brackets[token] == branch_stack[-1][1]:
                            level = len(lineal_stack) - len(branch_stack)
                            right = branch_stack.pop()[0]
                            matched_brackets.setdefault(level, []).append(region)
                            matched_brackets[level].append(right)
                        else:
                            unmatched_brackets.append(region)
                    else:
                        lineal_stack.append((region, token))

            branch_stack, lineal_level = [], -1
            for region, scope in rtokens:
                token = contents[region.a - begin:region.b - begin]
                if token in self.brackets:
                    if ("comment" in scope or "string" in scope or
                        "char" in scope):
                        continue

                    if token in self.left_brackets:
                        branch_stack.append((region, token))
                    elif branch_stack:
                        if self.brackets[token] == branch_stack[-1][1]:
                            left = branch_stack.pop()[0]
                            level =  lineal_level - len(branch_stack)
                            matched_brackets.setdefault(level, []).append(left)
                            matched_brackets[level].append(region)
                        else:
                            unmatched_brackets.append(region)
                    elif lineal_stack and self.brackets[token] == lineal_stack[0][1]:
                        rt = lineal_stack.pop(0)[0]
                        lineal_level += 1
                        matched_brackets.setdefault(lineal_level, []).append(rt)
                        matched_brackets[lineal_level].append(region)
                    else:
                        unmatched_brackets.append(region)
        return match_result


class RainbowViewsManager(sublime_plugin.EventListener):
    tincted_views = {}
    ignored_views = {}

    maxsize = 20000
    color_number = 7
    key_scope_colors = []
    brackets = {}
    languages = {}
    color_scheme = "Monokai.sublime-color-scheme"
    unmatched_key = "rainbow_color_unmatched"
    unmatched_scope = "unmatched.color.rainbow"
    unmatched_color = ""

    @classmethod
    def write_color_scheme(cls, color_scheme):
        def background(color_scheme):
            view = sublime.active_window().active_view()
            view.settings().set("color_scheme", color_scheme)
            return view.style()["background"]

        def nearest_color(color):
            b = int(color[5:7], 16)
            b += 1 - 2 * (b == 255)
            return color[:-2] + "%02x" % b

        abspath = profile._cache_color_scheme_path(color_scheme)
        bgcolor = background(color_scheme)
        nearest_bgcolor = nearest_color(bgcolor)
        scheme_rules = []
        profile.scheme_data["rules"] = scheme_rules

        for key, scope, color in cls.key_scope_colors:
            scheme_rules.append({
                "name": key,
                "scope": scope,
                "foreground": color,
                "background": nearest_bgcolor
            })
        scheme_rules.append({
            "name": cls.unmatched_key,
            "scope": cls.unmatched_scope,
            "foreground": cls.unmatched_color,
            "background": bgcolor
        })

        with open(abspath, "w") as file:
            file.write(json.dumps(profile.scheme_data))

        entry = ["write_color_scheme:", abspath, str(scheme_rules)]
        Loger.print("\n\t".join(entry))

    @classmethod
    def _tinct_view(cls, view, syntax, brackets, mode):
        if not brackets:
            log = "Not work in current file because no brackets was added!"
            Loger.warning(log)
            return
        if syntax == profile.plain_text_syntax:
            Loger.warning("Plain text syntax maybe cause a mistaken token!")

        view_listener = RainbowViewListener(view, syntax, brackets, mode)
        view_listener.on_load()
        cls.tincted_views[view.view_id] = view_listener

        file = view.file_name() or "untitled"
        mode = "all" if mode == profile.RAINBOW_MODE_ALL else "part"
        entry = ["_tinct_view:", "file: {}", "syntax: {}"]
        entry.extend(["brackets: {}", "mode: {}"])
        Loger.print("\n\t".join(entry).format(file, syntax, brackets, mode))

    @classmethod
    def syntax_for_view(cls, view):
        syntax = view.settings().get("syntax")
        syntax, ext = os.path.splitext(os.path.basename(syntax))
        return syntax.lower()

    # if view is ignored, do not ignore it
    @classmethod
    def _load_view(cls, view):
        syntax = cls.syntax_for_view(view)
        if view.view_id in cls.ignored_views:
            view_listener = cls.ignored_views.pop(view.view_id)
            if view_listener.syntax == syntax:
                view_listener.on_load()
                cls.tincted_views[view.view_id] = view_listener
                return

        config = None
        if syntax in cls.languages:
            config = cls.languages[syntax]
        elif view.file_name():
            ext = os.path.splitext(view.file_name())[1].lstrip(".")
            for lang in cls.languages:
                values = cls.languages[lang]
                if ext in values.get("extensions", []):
                    config = values
                    break

        if config is not None:
            non_brackets = config.get("!brackets", [])
            brackets = {b: cls.brackets[b] for b in cls.brackets if b not in non_brackets}
            mode = config.get("mode", profile.DEFAULT_MODE)
            cls._tinct_view(view, syntax, brackets, mode)

    # whatever, tinct view.
    @classmethod
    def tinct_view(cls, view):
        if view.view_id not in cls.tincted_views:
            cls._load_view(view)
        if view.view_id not in cls.tincted_views:
            mode = profile.DEFAULT_MODE
            syntax = cls.syntax_for_view(view)
            cls._tinct_view(view, syntax, cls.brackets, mode)

    @classmethod
    def load_view(cls, view):
        # ignore views such as console, commands panel...
        views = sublime.active_window().views()
        if view.size() < 2 or view not in views:
            return
        if view.view_id not in cls.ignored_views:
            cls._load_view(view)

    @classmethod
    def clear_view(cls, view):
        if view.view_id in cls.tincted_views:
            view_listener = cls.tincted_views.pop(view.view_id)
            view_listener.clear_all()
            cls.ignored_views[view.view_id] = view_listener

    @classmethod
    def clear_all(cls):
        for view_listener in cls.tincted_views.values():
            view_listener.clear_all()

    def on_load(self, view):
        RainbowViewsManager.load_view(view)

    def on_modified(self, view):
        if view.view_id in self.tincted_views:
            view_listener = self.tincted_views[view.view_id]
            view_listener.on_modified()

    def on_selection_modified(self, view):
        if view.view_id in self.tincted_views:
            view_listener = self.tincted_views[view.view_id]
            view_listener.on_selection_modified()

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


def load_settings(cls):
    def _load_settings():
        key_scope_colors = []
        rainbow_colors = settings.get("rainbow_colors", {})
        for color in rainbow_colors.get("matched", []):
            color_no = str(len(key_scope_colors))
            key = "rainbow_color_matched_no_" + color_no
            scope = color_no + ".matched.color.rainbow"
            key_scope_colors.append((key, scope, color))

        cls.color_number = len(key_scope_colors)
        cls.key_scope_colors = key_scope_colors
        cls.unmatched_color = rainbow_colors.get("unmatched", "")

        cls.maxsize = settings.get("maxsize", 0)
        cls.brackets = settings.get("brackets", {})
        cls.languages = settings.get("languages", {})
        for lang, config in cls.languages.items():
            extensions = config.get("extensions", [])
            config["mode"] = int(config["mode"] == "part")
            cls.languages[lang.lower()] = cls.languages.pop(lang)

        color_scheme = preferences.get("color_scheme", cls.color_scheme)
        cls.color_scheme = color_scheme
        cls.write_color_scheme(color_scheme)

    def _update_color_scheme():
        color_scheme = preferences.get("color_scheme", cls.color_scheme)
        if cls.color_scheme != color_scheme:
            cls.write_color_scheme(color_scheme)

    settings = profile._load_settings(pref=False)
    preferences = profile._load_settings(pref=True)

    _load_settings()

    settings.clear_on_change("rainbow_colors")
    preferences.clear_on_change("color_scheme")
    settings.add_on_change("rainbow_colors", _load_settings)
    preferences.add_on_change("color_scheme", _update_color_scheme)


def plugin_loaded():
    os.makedirs(profile._cache_color_scheme_dir(relative=False), exist_ok=True)
    load_settings(RainbowViewsManager)
    view = sublime.active_window().active_view()
    sublime.set_timeout(lambda: RainbowViewsManager.load_view(view), 500)


def plugin_unloaded():
    settings = profile._load_settings(pref=False)
    preferences = profile._load_settings(pref=True)
    settings.clear_on_change("rainbow_colors")
    preferences.clear_on_change("color_scheme")
    RainbowViewsManager.clear_all()
