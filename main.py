import os
import json

import sublime
import sublime_plugin

from . import profile


CS_DEFAULT = "Monokai.sublime-color-scheme"


class Loger:
    debug = False

    def print(*args):
        if Loger.debug:
            print("[Rainbow Brackets:]", *args)


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


class RainbowViewListener(object):
    def __init__(self, view, brackets, mode=0):
        self.view = view
        self.mode = mode
        self.brackets = {}

        self.left_brackets = sorted(brackets)
        self.right_brackets = [brackets[k] for k in self.left_brackets]
        for i in range(len(self.left_brackets)):
            self.brackets[self.left_brackets[i]] = self.right_brackets[i]
            self.brackets[self.right_brackets[i]] = self.left_brackets[i]

    def clear_all(self):
        for no in range(RainbowViewsManager.color_number):
            key = "rainbow_color_matched_no_" + str(no)
            self.view.erase_regions(key)
        self.view.erase_regions("rainbow_color_unmatched")

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

    def serialize_regions(self, matched_regions, no):
        bucket_len = RainbowViewsManager.color_number
        region_buckets = [[] for i in range(bucket_len)]
        for level in matched_regions:
            bucket_no = level % bucket_len
            regions = matched_regions[level]
            region_buckets[bucket_no].extend(regions)

        return region_buckets

    def add_regions_with_level(self, region_buckets):
        for no in range(len(region_buckets)):
            color_no = str(no)
            key = "rainbow_color_matched_no_" + color_no
            scope = color_no + ".matched.color.rainbow"
            regions = region_buckets[no]
            self.view.add_regions(key, regions,
                scope=scope,
                flags=sublime.DRAW_NO_OUTLINE)

    def add_regions(self, matched, unmatched):
        self.clear_all()
        if matched:
            region_buckets = self.serialize_regions(matched, 0)
            self.add_regions_with_level(region_buckets)

        if unmatched:
            key = "rainbow_color_unmatched"
            self.view.add_regions(key, unmatched,
                scope="unmatched.color.rainbow",
                flags=sublime.DRAW_NO_FILL)

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
                    if "comment" in scope or "string" in scope:
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
                    if "comment" in scope or "string" in scope:
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
                    if "comment" in scope or "string" in scope:
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
    ignored_views = []

    @classmethod
    def _tinct_view(cls, view, brackets, mode):
        if not brackets:
            Loger.print("Not work in current file because no brackets was added!")
            return
        view_listener = RainbowViewListener(view, brackets, mode)
        view_listener.on_load()
        cls.tincted_views[view.id()] = view_listener
        mode = "all" if mode == profile.RAINBOW_MODE_ALL else "part"
        Loger.print("_tinct_view:\n\tfile: {}\n\tbrackets: {}\n\tmode: {}".format(
            view.file_name(), brackets, mode))

    @classmethod
    def _load_view(cls, view):
        def get_config_for_view():
            syntax = view.settings().get("syntax", None)
            if syntax is not None:
                syntax = os.path.basename(syntax).lower()
                lang, ext = os.path.splitext(syntax)
                if lang in cls.languages:
                    return cls.languages[lang]
            if view.file_name():
                ext = os.path.splitext(view.file_name())[1].lstrip(".")
                for lang in cls.languages:
                    config = cls.languages[lang]
                    if ext in config.get("extensions", []):
                        return config
            return None

        if view.id() in cls.ignored_views:
            return

        config = get_config_for_view()
        if config is not None:
            non_brackets = config.get("!brackets", [])
            brackets = {b: cls.brackets[b] for b in cls.brackets if b not in non_brackets}
            mode = config.get("mode", profile.DEFAULT_MODE)
            cls._tinct_view(view, brackets, mode)

    @classmethod
    def tinct_view(cls, view):
        if view.id() in cls.ignored_views:
            cls.ignored_views.remove(view.id())

        if view.id() not in cls.tincted_views:
            cls._load_view(view)
        if view.id() not in cls.tincted_views:
            mode = profile.DEFAULT_MODE
            cls._tinct_view(view, cls.brackets, mode)

    @classmethod
    def clear_view(cls, view):
        if view.id() in cls.tincted_views:
            view_listener = cls.tincted_views[view.id()]
            view_listener.clear_all()
            cls.tincted_views.pop(view.id())
            cls.ignored_views.append(view.id())

    @classmethod
    def clear_all(cls):
        for view_listener in cls.tincted_views.values():
            view_listener.clear_all()

    def on_load(self, view):
        RainbowViewsManager._load_view(view)

    def on_modified(self, view):
        if view.id() in self.tincted_views:
            view_listener = self.tincted_views[view.id()]
            view_listener.on_modified()

    def on_activated(self, view):
        if view.id() not in self.tincted_views:
            self.on_load(view)

    def on_selection_modified(self, view):
        if view.id() in self.tincted_views:
            view_listener = self.tincted_views[view.id()]
            view_listener.on_selection_modified()

    def on_close(self, view):
        if view.id() in self.tincted_views:
            self.tincted_views.pop(view.id())


def nearest_background(color_scheme):
    view = sublime.active_window().active_view()
    view.settings().set("color_scheme", color_scheme)
    bgcolor = view.style()["background"]

    b = int(bgcolor[5:7], 16)
    b += 1 - 2 * (b == 255)
    return bgcolor[:-2] + "%02x" % b


def write_color_scheme(color_scheme, rainbow_colors):
    abspath = profile._cache_color_scheme_path(color_scheme)
    bgcolor = nearest_background(color_scheme)

    matched_color = rainbow_colors["matched"]
    unmatched_color = rainbow_colors["unmatched"]
    scheme_rules = []

    for no in range(RainbowViewsManager.color_number):
        color_no, color = str(no), matched_color[no]
        scheme_rules.append({
            "name": "rainbow_color_matched_no_" + color_no,
            "scope": color_no + ".matched.color.rainbow",
            "foreground": color,
            "background": bgcolor
        })
    scheme_rules.append({
        "name": "rainbow_color_unmatched",
        "scope": "unmatched.color.rainbow",
        "foreground": unmatched_color,
        "background": bgcolor
    })
    profile.scheme_data["rules"] = scheme_rules
    with open(abspath, "w") as file:
        file.write(json.dumps(profile.scheme_data))


def load_settings(cls):
    def _load_settings():
        cls.maxsize = settings.get("maxsize", {})
        cls.brackets = settings.get("brackets", {})
        cls.rainbow_colors = settings.get("rainbow_colors", {})
        cls.color_number = len(cls.rainbow_colors["matched"])

        cls.languages = settings.get("languages", {})
        for lang, config in cls.languages.items():
            extensions = config.get("extensions", [])
            config["mode"] = int(config["mode"] == "part")
            cls.languages[lang.lower()] = cls.languages.pop(lang)

        color_scheme = preferences.get("color_scheme", CS_DEFAULT)
        cls.color_scheme = color_scheme
        write_color_scheme(color_scheme, cls.rainbow_colors)

    def _update_color_scheme():
        color_scheme = preferences.get("color_scheme", CS_DEFAULT)
        if cls.color_scheme != color_scheme:
            write_color_scheme(color_scheme, cls.rainbow_colors)

    settings = profile._load_settings(pref=False)
    preferences = profile._load_settings(pref=True)

    _load_settings()

    settings.add_on_change("rainbow_colors", _load_settings)
    preferences.add_on_change("color_scheme", _update_color_scheme)


def plugin_loaded():
    os.makedirs(profile._cache_color_scheme_dir(relative=False), exist_ok=True)
    load_settings(RainbowViewsManager)
    view = sublime.active_window().active_view()
    sublime.set_timeout(lambda: RainbowViewsManager._load_view(view), 500)

def plugin_unloaded():
    RainbowViewsManager.clear_all()
