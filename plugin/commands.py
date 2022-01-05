import re
import sublime
import sublime_plugin

from sublime  import Region
from .consts  import SETTINGS_FILE
from .debug   import Debuger
from .manager import RainbowBracketsViewManager as _manager


class RainbowBracketsToggleDebugCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        Debuger.debug = not Debuger.debug
        sublime.load_settings(SETTINGS_FILE).set("debug", Debuger.debug)
        sublime.save_settings(SETTINGS_FILE)


class RainbowBracketsClearColorSchemesCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        _manager.color_scheme_manager.clear_color_schemes()


class RainbowBracketsViewCommand(sublime_plugin.TextCommand):
    def get_executor(self):
        return _manager.get_view_executor(self.view)

    def is_coloring(self):
        executor = self.get_executor()
        return bool(executor and executor.coloring)


class RainbowBracketsColorCommand(RainbowBracketsViewCommand):
    def run(self, edit):
        _manager.color_view(self.view)

    def is_enabled(self):
        return not self.is_coloring()


class RainbowBracketsSweepCommand(RainbowBracketsViewCommand):
    def run(self, edit):
        _manager.sweep_view(self.view)

    def is_enabled(self):
        return self.is_coloring()


class RainbowBracketsSetupCommand(RainbowBracketsViewCommand):
    def run(self, edit):
        _manager.setup_view_executor(self.view)

    def is_enabled(self):
        return self.get_executor() is None


class RainbowBracketsCloseCommand(RainbowBracketsViewCommand):
    def run(self, edit):
        _manager.close_view_executor(self.view)

    def is_enabled(self):
        return self.get_executor() is not None


class RainbowBracketsEditBracketsCommand(sublime_plugin.TextCommand):
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
        trees = _manager.get_view_bracket_trees(view)
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
            mapping = _manager.get_view_bracket_pairs(view)
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
