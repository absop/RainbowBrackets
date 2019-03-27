import os
import json

import sublime
import sublime_plugin

from . import profile


class Debuger:
    debug = False

    def print(*args):
        if Debuger.debug:
            print(*args)

# Provide a additional color_scheme.
# Simply provide the BGcolor dynamically, so that the BGcolor of
# the brackets matches the BGcolor of the color scheme being used.
class ColorSchemeWriter(object):
    minlayer = 0
    maxlayer = 0
    unmatched = {
        "name": profile.unmatched_key,
        "scope": profile.unmatched_scope,
        "foreground": profile.brackets_colors["unmatched"]
    }
    matched = []
    scheme_data = profile.scheme_data
    fgcolors = profile.brackets_colors["matched"]
    numcolor = len(fgcolors)

    def __init__(self, filename):
        self.update_abspath_and_bgcolor(filename)
        self.update_layer(0, 15)

    def update_abspath_and_bgcolor(self, filename):
        self.filename = filename
        self.bgcolor = self.nearest_background(filename)
        self.abspath = profile._cache_color_scheme_path(filename)
        for rule in self.matched:
            rule["background"] = self.bgcolor

    def update_scheme(self, filename):
        def flush_views():
            Debuger.print("flush_views with color_scheme: ", filename)
            for window in sublime.windows():
                for view in window.views():
                    if view.settings().has("rainbow"):
                        view.settings().set("color_scheme", filename)
                        Debuger.print("\tfile: ", view.file_name())

        self.update_abspath_and_bgcolor(filename)
        self.write_color_scheme("update_scheme")
        sublime.set_timeout(flush_views, 250)

    def background(self, filename):
        view = sublime.active_window().active_view()
        view.settings().set("color_scheme", filename)
        bgcolor = view.style()["background"]
        return bgcolor

    def nearest_background(self, filename):
        bgcolor = self.background(filename)
        b = int(bgcolor[5:7], 16)
        b += 1 - 2 * (b == 255)
        return bgcolor[:-2] + "%02x" % b

    def update_brackets_colors(self, brackets_colors):
        self.fgcolors = brackets_colors["matched"]
        self.numcolor = len(self.fgcolors)
        self.unmatched["foreground"] = brackets_colors["unmatched"]
        for i in range(self.minlayer, self.maxlayer):
            self.matched[i]["foreground"] = self.fgcolors[i % self.numcolor]

        self.write_color_scheme("update_brackets_colors")

    def rule_dict(self, i):
        return {
            "name": profile._matched_key(i),
            "scope": profile._matched_scope(i),
            "foreground": self.fgcolors[i % self.numcolor],
            "background": self.bgcolor
        }

    def update_layer(self, minlayer, maxlayer):
        # for n less than 2^16
        def clp2(number):
            for i in (1, 2, 4, 8):
                number |= number >> i
            return number + 1

        if maxlayer > self.maxlayer or minlayer < self.minlayer:
            if maxlayer > self.maxlayer:
                self.up_layer_to(clp2(maxlayer))
            if minlayer < self.minlayer:
                self.down_layer_to(-clp2(abs(minlayer)))
            self.write_color_scheme("update_layer")

    def up_layer_to(self, maxlayer):
        Debuger.print("up layer from:", self.maxlayer, "to:", maxlayer)
        higher = [self.rule_dict(i) for i in range(self.maxlayer, maxlayer)]
        self.matched = self.matched + higher
        self.maxlayer = maxlayer

    def down_layer_to(self, minlayer):
        Debuger.print("down layer from:", self.minlayer, "to:", minlayer)
        lower = [self.rule_dict(i) for i in range(minlayer, self.minlayer)]
        self.matched = lower + self.matched
        self.minlayer = minlayer

    def write_color_scheme(self, caller):
        self.scheme_data["rules"] = self.matched + [self.unmatched]
        with open(self.abspath, "w") as file:
            file.write(json.dumps(self.scheme_data))
        Debuger.print("{}: write file: {}, bg: {}".format(
            caller, self.abspath, self.bgcolor))


class BracketsViewListener(object):
    MODE_ALL = 0    # Highlight all brackets.
    MODE_PART = 1   # Only highlight brackets near to the cursor.

    def __init__(self, view, language, brackets, threshold, mode=0):
        self.view = view
        self.mode = mode
        self.minlayer = 0
        self.maxlayer = 0
        self.brackets = {}
        self.language = language
        self.threshold = threshold
        self.configure_brackets(brackets)

    def configure_brackets(self, brackets):
        self.left_brackets = sorted(brackets)
        self.right_brackets = [brackets[k] for k in self.left_brackets]
        for i in range(len(self.left_brackets)):
            self.brackets[self.left_brackets[i]] = self.right_brackets[i]
            self.brackets[self.right_brackets[i]] = self.left_brackets[i]

    def on_load(self):
        region = sublime.Region(0, self.view.size())
        self.add_all_brackets(region)

    def on_modified(self):
        if self.mode == self.MODE_ALL:
            self.on_load()
        else:
            self.rainbow_with_point(self.view.sel()[0].a)

    def on_selection_modified(self):
        if self.mode == self.MODE_PART:
            self.rainbow_with_point(self.view.sel()[0].a)

    def add_all_brackets(self, region):
        matched, unmatched =  self.get_all_brackets(region)
        if matched:
            for layer in sorted(matched):
                key = profile._matched_key(layer)
                self.view.add_regions(key, matched[layer],
                    scope=profile._matched_scope(layer),
                    flags=sublime.DRAW_NO_OUTLINE)
            self.minlayer = minlayer = min(matched)
            self.maxlayer = maxlayer = max(matched)
            RainbowBracketsListener.color_scheme_writer.update_layer(minlayer, maxlayer)
        if unmatched:
            self.view.add_regions(profile.unmatched_key, unmatched,
                scope=profile.unmatched_scope,
                flags=sublime.DRAW_NO_FILL)

    def rainbow_with_point(self, point):
        matched, unmatched = self.get_nearest_brackets(point)
        self.update_regions(matched, unmatched)
        RainbowBracketsListener.color_scheme_writer.update_layer(self.minlayer, self.minlayer)

    def update_regions(self, matched, unmatched):
        if matched:
            for layer in range(self.minlayer, self.maxlayer + 1):
                key = profile._matched_key(layer)
                self.view.erase_regions(key)
            self.minlayer = min(matched)
            self.maxlayer = max(matched)

            for layer in sorted(matched):
                key = profile._matched_key(layer)
                self.view.add_regions(key, matched[layer],
                    scope=profile._matched_scope(layer),
                    flags=sublime.DRAW_NO_OUTLINE)

        self.view.erase_regions(profile.unmatched_key)
        self.view.add_regions(profile.unmatched_key, unmatched,
            scope=profile.unmatched_scope,
            flags=sublime.DRAW_NO_FILL)

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
                        layer = len(left_brackets)
                        matched_brackets.setdefault(layer, []).append(left_regions.pop())
                        matched_brackets[layer].append(region)
                    else:
                        unmatched_brackets.append(region)
        return match_result

    def get_nearest_brackets(self, point):
        begin = max(point - self.threshold//2, 0)
        end = min(begin + self.threshold, self.view.size())
        ltokens = self.view.extract_tokens_with_scopes(sublime.Region(begin, point))
        rtokens = self.view.extract_tokens_with_scopes(sublime.Region(point, end))
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
                            layer = len(lineal_stack) - len(branch_stack)
                            right = branch_stack.pop()[0]
                            matched_brackets.setdefault(layer, []).append(region)
                            matched_brackets[layer].append(right)
                        else:
                            unmatched_brackets.append(region)
                    else:
                        lineal_stack.append((region, token))

            branch_stack, lineal_layer = [], -1
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
                            layer =  lineal_layer - len(branch_stack)
                            matched_brackets.setdefault(layer, []).append(left)
                            matched_brackets[layer].append(region)
                        else:
                            unmatched_brackets.append(region)
                    elif lineal_stack and self.brackets[token] == lineal_stack[0][1]:
                        rt = lineal_stack.pop(0)[0]
                        lineal_layer += 1
                        matched_brackets.setdefault(lineal_layer, []).append(rt)
                        matched_brackets[lineal_layer].append(region)
                    else:
                        unmatched_brackets.append(region)
        return match_result


class RainbowBracketsListener(sublime_plugin.EventListener):
    view_listeners = {}

    def configure_for_view(self, view):
        # return: (language name, language config)
        language = extensions = None
        syntax = view.settings().get("syntax", None)
        if view.file_name() and os.path.splitext(view.file_name())[1]:
            extensions = os.path.splitext(view.file_name())[1].lstrip(".")
        if syntax is not None:
            syntax = os.path.basename(syntax).lower()
            language, _ = os.path.splitext(syntax)
        if language not in self.languages:
            for lang, config in self.languages.items():
                if extensions in config["extensions"]:
                    return (lang, self.languages.get(lang, {}))
        return (language, self.languages.get(language, {}))

    def on_load(self, view):
        language, config = self.configure_for_view(view)
        if config and config["brackets"]:
            mode = config["mode"]
            brackets = config["brackets"]
            threshold = config.get("threshold", 20000)
            Debuger.print("on_load: file: {}, brackets: {}".format(
                view.file_name(), brackets))

            listener = BracketsViewListener(view, language, brackets, threshold, mode)
            listener.on_load()
            view.settings().set("color_scheme", self.filename)
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
    def load_language_config():
        cls.languages = settings.get("languages", {})
        for lang, config in cls.languages.items():
            extensions = config.get("extensions", [])
            config["mode"] = int(config["mode"] == "part")
            config["extensions"] = [e.lstrip(".") for e in extensions]
            cls.languages[lang.lower()] = cls.languages.pop(lang)

    def update_brackets_colors():
        brackets_colors = settings.get("brackets_colors", profile.brackets_colors)
        if brackets_colors != cls.brackets_colors:
            cls.color_scheme_writer.update_brackets_colors(brackets_colors)
            cls.brackets_colors = brackets_colors

    def update_scheme():
        filename = preferences.get("color_scheme")
        if filename != cls.filename:
            cls.color_scheme_writer.update_scheme(filename)
            cls.filename = filename

    settings = profile._load_settings(pref=False)
    preferences = profile._load_settings(pref=True)
    cls.filename = preferences.get("color_scheme")
    cls.brackets_colors = profile.brackets_colors
    cls.color_scheme_writer = ColorSchemeWriter(cls.filename)

    load_language_config()
    update_brackets_colors()

    settings.add_on_change("brackets_colors", update_brackets_colors)
    settings.add_on_change("languages", load_language_config)
    preferences.add_on_change("color_scheme", update_scheme)


def plugin_loaded():
    os.makedirs(profile._cache_color_scheme_dir(relative=False), exist_ok=True)
    load_settings(RainbowBracketsListener)
