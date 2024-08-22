import re
import os
import time
import sublime

from sublime import Region
from .debug  import Debuger


class BracketTree:
    __slots__ = ["opening", "closing", "contain"]

    def __init__(self, opening, closing, contain):
        self.opening = opening
        self.closing = closing
        self.contain = contain


class RainbowBracketsExecutor():
    def __init__(self, view, syntax, config):
        self.err_key   = config["err_key"]
        self.err_scope = config["err_scope"]
        self.coloring  = config["coloring"]
        self.keys      = config["keys"]
        self.brackets  = config["bracket_pairs"]
        self.pattern   = config["pattern"]
        self.scopes    = config["scopes"]
        self.selector  = config["selector"]
        self.color_number = len(self.keys)
        self.err_bracket_regions   = []
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
            if self.err_bracket_regions:
                self.view.add_regions(
                    self.err_key,
                    self.err_bracket_regions,
                    scope=self.err_scope,
                    flags=sublime.DRAW_EMPTY|sublime.PERSISTENT)
        else:
            self.construct_bracket_trees()

    def clear_bracket_regions(self):
        self.view.erase_regions(self.err_key)
        for key in self.keys:
            self.view.erase_regions(key)

    def construct_bracket_trees(self):
        self.bracket_regions_trees = []

        opening_stack   = []
        tree_node_stack = [BracketTree(None, None, self.bracket_regions_trees)]

        def handle_bracket_region(bracket, region,
            Node=BracketTree,
            brackets=self.brackets,
            opening_stack=opening_stack,
            opening_stack_append=opening_stack.append,
            opening_stack_pop=opening_stack.pop,
            tree_node_stack=tree_node_stack,
            tree_node_stack_append=tree_node_stack.append,
            tree_node_stack_pop=tree_node_stack.pop
            ):
            if bracket in brackets:
                tree_node_stack_append(Node(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)

        view_full_text = self.view.substr(Region(0, self.view.size()))
        self.iterate_matches(
            self.regexp.finditer(view_full_text),
            self.view.match_selector,
            self.selector,
            handle_bracket_region
        )

    def construct_bracket_trees_and_lists(self):
        self.err_bracket_regions   = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []

        opening_stack    = []
        tree_node_stack  = [BracketTree(None, None, self.bracket_regions_trees)]
        regions_by_layer = [list() for _ in range(self.color_number)]

        def handle_bracket_region(bracket, region,
            Node=BracketTree,
            brackets=self.brackets,
            num_layers=self.color_number,
            opening_stack=opening_stack,
            opening_stack_append=opening_stack.append,
            opening_stack_pop=opening_stack.pop,
            tree_node_stack=tree_node_stack,
            tree_node_stack_append=tree_node_stack.append,
            tree_node_stack_pop=tree_node_stack.pop,
            appends=[rs.append for rs in regions_by_layer]
            ):
            if bracket in brackets:
                tree_node_stack_append(Node(region, None, []))
                opening_stack_append(bracket)

            elif opening_stack and bracket == brackets[opening_stack[-1]]:
                opening_stack_pop()
                node = tree_node_stack_pop()
                node.closing = region
                tree_node_stack[-1].contain.append(node)
                layer = len(opening_stack) % num_layers
                appends[layer](node.opening)
                appends[layer](node.closing)
            else:
                self.err_bracket_regions.append(region)

        view_full_text = self.view.substr(Region(0, self.view.size()))
        self.iterate_matches(
            self.regexp.finditer(view_full_text),
            self.view.match_selector,
            self.selector,
            handle_bracket_region
        )

        self.bracket_regions_lists = [ls for ls in regions_by_layer if ls]

    def iterate_matches(self, matches, ignore, ignored_scope_selector, handle):
        if ignored_scope_selector:
            for m in matches:
                if ignore(m.span()[0], ignored_scope_selector):
                    continue
                handle(m.group(), Region(*m.span()))
        else:
            for m in matches:
                handle(m.group(), Region(*m.span()))
