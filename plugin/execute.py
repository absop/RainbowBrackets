import re
import os
import time
import sublime

from sublime import Region
from .debug  import Debuger


class Tree:
    __slots__ = ["opening", "closing", "contain"]

    def __init__(self, opening, closing, contain):
        self.opening = opening
        self.closing = closing
        self.contain = contain


class RainbowBracketsExecutor():
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
        self.config = config
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
