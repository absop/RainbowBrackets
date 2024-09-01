import re
import os
import time
import sublime

from typing import Callable, Dict, List, Optional, TypedDict
from typing_extensions import Self

from .logger import Logger


class BracketTree:
    __slots__ = ['opening', 'closing', 'contain']

    def __init__(
        self,
        opening: sublime.Region,
        closing: sublime.Region,
        contain: List[Self]
    ):
        self.opening = opening
        self.closing = closing
        self.contain = contain


class RainbowBracketsExecutor():
    def __init__(self, view: sublime.View, syntax: Optional[str], config):
        self.err_key   = config['err_key']        # type: str
        self.err_scope = config['err_scope']      # type: str
        self.coloring  = config['coloring']       # type: bool
        self.keys      = config['keys']           # type: List[str]
        self.scopes    = config['scopes']         # type: List[str]
        self.selector  = config['selector']       # type: str
        self.brackets  = config['bracket_pairs']  # type: Dict[str, str]
        self.pattern   = config['pattern']        # type: str
        self.color_number = len(self.keys)
        self.err_bracket_regions: List[sublime.Region] = []
        self.bracket_regions_lists: List[List[sublime.Region]] = []
        self.bracket_regions_trees: List[BracketTree] = []
        self.regexp = re.compile(self.pattern)
        self.syntax = syntax
        self.config = config
        self.view = view

    def __del__(self):
        self.clear_bracket_regions()
        Logger.print(f'Exited from {self.view_file_name()}')

    def view_file_name(self):
        return os.path.basename(self.view.file_name() or 'untitled')

    def load(self):
        start = time.time()
        self.check_bracket_regions()
        end = time.time()
        if Logger.debug:
            Logger.print(
                '\n\t'.join([
                    f'Loaded on {self.view_file_name()}',
                    f'pattern: {self.pattern}',
                    f'selector: {self.selector}',
                    f'syntax: {self.syntax}',
                    f'coloring: {self.coloring}',
                    f'cost time: {end - start:>.2f}'
                ])
            )

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
                        flags=sublime.DRAW_NO_OUTLINE|sublime.PERSISTENT
                    )
            if self.err_bracket_regions:
                self.view.add_regions(
                    self.err_key,
                    self.err_bracket_regions,
                    scope=self.err_scope,
                    flags=sublime.DRAW_EMPTY|sublime.PERSISTENT
                )
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

        def handle_bracket_region(
            bracket, region,
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

        self._iterate_brackets(handle_bracket_region)

    def construct_bracket_trees_and_lists(self):
        self.err_bracket_regions   = []
        self.bracket_regions_lists = []
        self.bracket_regions_trees = []

        opening_stack    = []
        tree_node_stack  = [BracketTree(None, None, self.bracket_regions_trees)]
        regions_by_layer = [list() for _ in range(self.color_number)]

        def handle_bracket_region(
            bracket, region,
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

        self._iterate_brackets(handle_bracket_region)
        self.bracket_regions_lists = [ls for ls in regions_by_layer if ls]

    def _iterate_brackets(
        self,
        handle: Callable[[str, sublime.Region], None],
        Region=sublime.Region
    ):
        full_text = self.view.substr(Region(0, self.view.size()))
        matches = self.regexp.finditer(full_text)
        ignore = self.view.match_selector
        ignored_scope_selector = self.selector
        if ignored_scope_selector:
            for m in matches:
                if ignore(m.span()[0], ignored_scope_selector):
                    continue
                handle(m.group(), Region(*m.span()))
        else:
            for m in matches:
                handle(m.group(), Region(*m.span()))
