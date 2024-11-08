import re
import time
import sublime
import sublime_plugin

from typing import Iterable, List, Optional, Pattern, Tuple

from .consts  import SETTINGS_FILE
from .logger  import Logger
from .manager import RainbowBracketsViewManager as _manager
from .executor import BracketTree
from .color_scheme import cs_mgr


class RbToggleDebugCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        Logger.debug = not Logger.debug
        sublime.load_settings(SETTINGS_FILE).set('debug', Logger.debug)
        sublime.save_settings(SETTINGS_FILE)


class RbClearColorSchemesCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        cs_mgr.clear_color_schemes()


class RbViewCommand(sublime_plugin.TextCommand):
    def get_executor(self):
        return _manager.get_view_executor(self.view)

    def is_coloring(self):
        executor = self.get_executor()
        return bool(executor and executor.coloring)


class RbColorCommand(RbViewCommand):
    def run(self, edit):
        _manager.color_view(self.view)

    def is_enabled(self):
        return not self.is_coloring()


class RbSweepCommand(RbViewCommand):
    def run(self, edit):
        _manager.sweep_view(self.view)

    def is_enabled(self):
        return self.is_coloring()


class RbSetupCommand(RbViewCommand):
    def run(self, edit):
        _manager.setup_view_executor(self.view)

    def is_enabled(self):
        return self.get_executor() is None


class RbCloseCommand(RbViewCommand):
    def run(self, edit):
        _manager.close_view_executor(self.view)
        self.view.settings().set('rb_enable', False)

    def is_enabled(self):
        return self.get_executor() is not None


class RbEditBracketsCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        self.view = view
        self.timestamp = 0
        self.operators = {
            'select': self.select,
            'remove': self.remove,
            'transform': self.transform,
        }

    def run(self, edit, operation='', **args):
        trees = _manager.get_view_bracket_trees(self.view)
        if trees:
            self.operators[operation](edit, trees, **args)

    def remove(self, edit, bracket_trees, select_content):
        pairs = [p for p in self._find_cursor_brackets(bracket_trees)]
        regions = [r for p in pairs for r in p]
        regions.sort()
        for r in reversed(regions):
            self.view.erase(edit, r)
        if select_content:
            selections = []
            _Region = sublime.Region
            for p in pairs:
                begin = p[0].a - regions.index(p[0])
                end = p[1].a - regions.index(p[1])
                selections.append(_Region(begin, end))
            self.view.sel().add_all(selections)

    def select(self, edit, bracket_trees, to=''):
        regex = to and re.compile(to + r'\b') or None
        for p in self._find_cursor_brackets(bracket_trees, regex=regex):
            region = self._cover(p)
            self.view.sel().add(region)

    def transform(self, edit, bracket_trees, to):
        left = to
        brackets = _manager.get_view_bracket_pairs(self.view)
        if not brackets or brackets.get(left) is None:
            return
        timestamp = time.time()
        look_farther = False
        if timestamp - self.timestamp < 1 and left == self.last_tobe:
            # Look further away when the keyboard is repeatedly pressed
            look_farther = True
        self.timestamp = timestamp
        self.last_tobe = left
        right = brackets[left]

        points = self.view.sel()
        while True:
            replacements = []
            outer_points = []
            found = False
            for p in self._find_cursor_brackets(bracket_trees, cursors=points):
                outer_points.append(p[0])
                if self.view.substr(p[0]) == left:
                    continue
                replacements.append((p[0], left))
                replacements.append((p[1], right))
                found = True
            if not look_farther or found:
                break
            if not outer_points or outer_points == points:
                break
            points = outer_points

        replacements.sort(key=lambda i:i[0], reverse=True)
        for region, content in replacements:
            self.view.replace(edit, region, content)

    def _cover(self, bracket_pair, _Region=sublime.Region):
        return _Region(bracket_pair[0].a, bracket_pair[1].b)

    def _find_cursor_brackets(
        self,
        trees: List[BracketTree],
        cursors: Optional[Iterable[sublime.Region]] = None,
        regex: Optional[Pattern[str]] = None
    ):
        last_bracket = None
        if cursors is None:
            cursors = self.view.sel()
        for region in cursors:
            bracket = self._find_nearest(trees, region, regex)
            if bracket is None or bracket == last_bracket:
                continue
            else:
                last_bracket = bracket
                yield bracket

    def _find_nearest(
        self,
        trees: List[BracketTree],
        region: sublime.Region,
        regex: Optional[Pattern[str]],
        _Region=sublime.Region
    ):
        pairs = self._binary_path_search(trees, region.begin(), region.end())
        bracket = None
        if pairs and regex is not None:
            for p in reversed(pairs):
                point = p[0].end()
                text = self.view.substr(_Region(point, point + 31))
                if regex.match(text) is not None:
                    bracket = p
                    break
            else:
                bracket = pairs[0]
        elif pairs:
            bracket = pairs[-1]

        if bracket is None and region.empty():
            for tree in trees:
                if (tree.opening.a == region.a or
                    tree.closing.b == region.a):
                    bracket = (tree.opening, tree.closing)
                    break
        return bracket

    def _binary_path_search(
        self,
        trees: List[BracketTree],
        r_begin: int,
        r_end: int
    ):
        bracket_path: List[Tuple[sublime.Region, sublime.Region]] = []
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
                    if (oa < r_begin and r_end < cb or
                        r_begin == r_end and (r_end == oa or r_begin == cb)):
                        found_closer = True
                        trees = tr.contain
                        p = (tr.opening, tr.closing)
                        bracket_path.append(p)
                    break
            if not found_closer:
                break
        return bracket_path
