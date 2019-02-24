import os
import json

import sublime
import sublime_plugin

from . import profile


class Debuger:
    debug = True

    def print(*args):
        if Debuger.debug:
            print(*args)


class ColorScheme(object):
    fgcolors = profile.brackets_colors["matched"]
    matched = []
    minlayer = maxlayer = 0
    numcolor = len(fgcolors)
    unmatched = {
        "name": profile.unmatched_key,
        "scope": profile.unmatched_scope,
        "foreground": profile.brackets_colors["unmatched"]
        # "background": self.bgcolor
    }

    def __init__(self, filename):
        self.abspath = profile._cache_color_scheme_path(filename, relative=False)
        self.bgcolor = self.nearest_background(filename)
        self.update_layer(0, 15)

    def rules(self):
        return self.matched + [self.unmatched]

    # for n less than 2^16
    def clp2(self, n):
        for i in (1, 2, 4, 8):
            n |= n >> i
        return n + 1

    def rule_dict(self, i):
        return {
            "name": profile._matched_key(i),
            "scope": profile._matched_scopes(i),
            "foreground": self.fgcolors[i % self.numcolor],
            "background": self.bgcolor
        }

    def update_layer(self, minlayer, maxlayer):
        if minlayer < self.minlayer:
            self.down_layer_to(-self.clp2(abs(minlayer)))
        if maxlayer > self.maxlayer:
            self.up_layer_to(self.clp2(maxlayer))

    def up_layer_to(self, maxlayer):
        if maxlayer >= self.maxlayer:
            Debuger.print("up layer from:", self.maxlayer, "to:", maxlayer)
            matched = [self.rule_dict(i) for i in range(self.maxlayer, maxlayer)]
            self.matched = self.matched + matched
            self.maxlayer = maxlayer

    def down_layer_to(self, minlayer):
        if minlayer <= self.minlayer:
            Debuger.print("down layer from:", self.minlayer, "to:", minlayer)
            matched = [self.rule_dict(i) for i in range(minlayer, self.minlayer)]
            self.matched = matched + self.matched
            self.minlayer = minlayer

    def update_colors(self, brcolors):
        self.fgcolors = brcolors["matched"]
        self.numcolor = len(self.fgcolors)

        self.unmatched["foreground"] = brcolors["unmatched"]
        for i in range(self.minlayer, self.maxlayer):
            self.matched[i]["foreground"] = self.fgcolors[i % self.numcolor]

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


# 额外提供的 color_scheme, 只需动态提供背景色
# 以便使括号的背景颜色与颜色方案的背景色一致即可
class ColorSchemeWriter(object):
    cached_color_schemes = {}
    scheme_data = profile.scheme_data

    def __init__(self, filename):
        if filename in self.cached_color_schemes:
            color_scheme = self.cached_color_schemes[filename]
        else:
            color_scheme = ColorScheme(filename)
        if not (self.cached_color_schemes and
                color_scheme.maxlayer >= self.color_scheme.maxlayer and
                color_scheme.minlayer <= self.color_scheme.minlayer and
                os.path.exists(color_scheme.abspath)):
            if self.cached_color_schemes:
                minlayer = self.color_scheme.minlayer
                maxlayer = self.color_scheme.maxlayer
                color_scheme.update_layer(minlayer, maxlayer)
            self.write_color_scheme("ColorSchemeWriter", color_scheme)
        self.filename = filename
        self.color_scheme = color_scheme
        self.cached_color_schemes[filename] = color_scheme

    def update_scheme(self, filename):
        def flush_views():
            Debuger.print("flush_views with color_scheme: ", filename)
            for window in sublime.windows():
                for view in window.views():
                    if view.settings().has("rainbow"):
                        view.settings().set("color_scheme", filename)
                        Debuger.print("\tfile: ", view.file_name())

        self.__init__(filename)
        timeout = 500 * filename not in self.cached_color_schemes
        sublime.set_timeout(flush_views, timeout)

    def update_colors(self, brackets_colors):
        # current color_scheme first.
        self.color_scheme.update_colors(brackets_colors)
        self.cached_color_schemes.pop(self.filename)
        self.write_color_scheme("update_colors", self.color_scheme)
        for color_scheme in self.cached_color_schemes.values():
            color_scheme.update_colors(brackets_colors)
            self.write_color_scheme("update_colors", color_scheme)

        self.cached_color_schemes[self.filename] = self.color_scheme

    def update_layer(self, minlayer, maxlayer):
        if not (self.color_scheme.maxlayer >= maxlayer and
                self.color_scheme.minlayer <= minlayer):
            self.color_scheme.update_layer(minlayer, maxlayer)
            self.write_color_scheme("update_layer", self.color_scheme)

    def write_color_scheme(self, caller, color_scheme):
        self.scheme_data["rules"] = color_scheme.rules()
        with open(color_scheme.abspath, "w") as file:
            file.write(json.dumps(self.scheme_data))
        Debuger.print("{}: write file: {}, bg: {}".format(
            caller, color_scheme.abspath, color_scheme.bgcolor))


class BracketsViewListener(object):
    MODE_ALL = 0    # Highlight all brackets.
    MODE_PART = 1   # Only highlight brackets near the cursor.

    def __init__(self, view, language, brackets, mode=0):
        self.view = view
        self.mode = mode
        self.minlayer = 0
        self.maxlayer = 0
        self.language = language
        self.brackets = brackets

    def on_load(self):
        region = sublime.Region(0, self.view.size())
        self.add_all_brackets(region, 0)

    def on_modified(self):
        if self.mode == self.MODE_ALL:
            self.on_load()
        else:
            self.rainbow_with_point(self.view.sel()[0].a)

    def on_selection_modified(self):
        if self.mode == self.MODE_PART:
            self.rainbow_with_point(self.view.sel()[0].a)

    def add_all_brackets(self, region, layer):
        matched, unmatched =  self.get_all_brackets(region, layer)
        if matched:
            for layer in sorted(matched):
                key = profile._matched_key(layer)
                self.view.add_regions(key, matched[layer],
                    scope=profile._matched_scopes(layer),
                    flags=sublime.DRAW_NO_OUTLINE)
            self.minlayer = minlayer = min(matched)
            self.maxlayer = maxlayer = max(matched)
            RainbowBracketsListener.color_scheme_writer.update_layer(minlayer, maxlayer)
        if unmatched:
            self.view.add_regions(profile.unmatched_key, unmatched,
                scope=profile.unmatched_scope,
                flags=sublime.DRAW_NO_FILL)

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
                    scope=profile._matched_scopes(layer),
                    flags=sublime.DRAW_NO_OUTLINE)

        self.view.erase_regions(profile.unmatched_key)
        self.view.add_regions(profile.unmatched_key, unmatched,
            scope=profile.unmatched_scope,
            flags=sublime.DRAW_NO_FILL)

    def rainbow_with_point(self, point, threshod=10000):
        matched, unmatched = self.get_nearest_brackets(point, threshod)
        self.update_regions(matched, unmatched)
        RainbowBracketsListener.color_scheme_writer.update_layer(self.minlayer, self.minlayer)

    def get_all_brackets(self, region, minlayer=0):
        tokens_with_scopes = self.view.extract_tokens_with_scopes(region)
        brackets, regions = [], []
        matched_brackets = {}
        unmatched_brackets = []
        match_result = (matched_brackets, unmatched_brackets)
        if len(tokens_with_scopes) >= 1:
            begin = tokens_with_scopes[0][0].a
            end = tokens_with_scopes[-1][0].b
            contents = self.view.substr(sublime.Region(begin, end))
            for region, scope in tokens_with_scopes:
                # skip ignore
                if "comment" in scope or "string" in scope:
                    continue
                token = contents[region.a - begin:region.b - begin]
                if token in self.brackets:
                    brackets.append(token)
                    regions.append(region)

                elif brackets:
                    if token == self.brackets[brackets[-1]]:
                        brackets.pop()
                        no = minlayer + len(brackets)
                        matched_brackets.setdefault(no, []).append(regions.pop())
                        matched_brackets[no].append(region)

                    elif token in self.brackets.values():
                        unmatched_brackets.append(region)
        return match_result

    def get_nearest_brackets(self, point, threshold):
        begin = max(point - threshold//2, 0)
        end = min(begin + threshold, self.view.size())
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
            rbrackrts = set(self.brackets.values())
            contents = self.view.substr(sublime.Region(begin, end))
            ltokens.reverse()
            for region, scope in ltokens:
                # skip ignore
                if "comment" in scope or "string" in scope:
                    continue
                token = contents[region.a - begin:region.b - begin]
                if token in rbrackrts:
                    # 0: region, 1: 括号
                    branch_stack.append((region, token))
                # 如果是左括号
                elif token in self.brackets:
                    # 如果右括号栈非空
                    if branch_stack:
                        # 如果该左括号和非直系栈顶括号匹配
                        if self.brackets[token] == branch_stack[-1][1]:
                            r = branch_stack.pop()[0]
                            layer = len(lineal_stack) - len(branch_stack)
                            matched_brackets.setdefault(layer, []).append(region)
                            matched_brackets[layer].append(r)
                        # 否则，为不匹配的括号
                        else:
                            unmatched_brackets.append(region)
                    else:
                        lineal_stack.append((region, token))

            branch_stack, lineal_layer = [], 0
            for region, scope in rtokens:
                if "comment" in scope or "string" in scope:
                    continue
                token = contents[region.a - begin:region.b - begin]
                if token in self.brackets:
                    branch_stack.append((region, token))

                elif token in rbrackrts:
                    if branch_stack:
                        if self.brackets[branch_stack[-1][1]] == token:
                            l = branch_stack.pop()[0]
                            layer =  lineal_layer - len(branch_stack)
                            matched_brackets.setdefault(layer, []).append(l)
                            matched_brackets[layer].append(region)
                        else:
                            unmatched_brackets.append(region)
                    elif lineal_stack:
                        if self.brackets[lineal_stack[0][1]] == token:
                            rt = lineal_stack.pop(0)[0]
                            lineal_layer += 1
                            matched_brackets.setdefault(lineal_layer, []).append(rt)
                            matched_brackets[lineal_layer].append(region)
                    else:
                        unmatched_brackets.append(region)
        return match_result


class RainbowBracketsListener(sublime_plugin.EventListener):
    view_listeners = {}

    # return: (language name, language config)
    def configure_for_view(self, view):
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
            Debuger.print("on_load: file: {}, brackets: {}".format(
                view.file_name(), brackets))

            listener = BracketsViewListener(view, language, brackets, mode)
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
    def update_colors():
        brackets_colors = settings.get("brackets_colors", profile.brackets_colors)
        if brackets_colors != cls.brackets_colors:
            cls.color_scheme_writer.update_colors(brackets_colors)
            cls.brackets_colors = brackets_colors

    def load_language_config():
        cls.languages = settings.get("languages", {})
        for lang, config in cls.languages.items():
            extensions = config.get("extensions", [])
            config["mode"] = int(config["mode"] == "part")
            config["extensions"] = [e.lstrip(".") for e in extensions]
            cls.languages[lang.lower()] = cls.languages.pop(lang)

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

    update_colors()
    load_language_config()

    settings.add_on_change("brackets_colors", update_colors)
    settings.add_on_change("languages", load_language_config)
    preferences.add_on_change("color_scheme", update_scheme)


def plugin_loaded():
    os.makedirs(profile._cache_color_scheme_dir(relative=False), exist_ok=True)
    load_settings(RainbowBracketsListener)
