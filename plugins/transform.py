from collections import OrderedDict

import sublime
import sublime_plugin


BRACKETS = {'(': ')', '[': ']', '{': '}'}


def is_matched_brackets(l, r):
    if l in BRACKETS:
        return BRACKETS[l] == r
    return False


class BracketRegion:
    def __init__(self, shape, left, right):
        self.shape = shape
        self.left = left
        self.right = right

    def region_all(self):
        return sublime.Region(self.left.a, self.right.b)

    def left_move(self, cur):
        for r in (self.left, self.right):
            r.a -= cur
            r.b -= cur


def select_bracket(v):
    def selector():
        v.run_command('expand_selection', {'to': "brackets"})
        return v.sel()[0]

    def matched(region):
        a = region.begin()
        b = region.end()
        lb = v.substr(a)
        rb = v.substr(b - 1)
        if is_matched_brackets(lb, rb):
            return BracketRegion(
                lb, sublime.Region(a, a + 1),
                sublime.Region(b - 1, b))
        else:
            return False

    cursor_0 = v.sel()[0].a
    region = selector()
    if (region.empty() and region.a == cursor_0):
        return False
    else:
        first_match = matched(region)
        if (first_match):
            return first_match
        else:
            return matched(selector())


class BracketsSelectCommand(sublime_plugin.TextCommand):
    def run(self, edit):

        v = self.view
        selections = [s for s in v.sel()]
        v.sel().clear()
        should_selected = []

        for s in selections:
            v.sel().add(s)
            br = select_bracket(v)
            if br:
                should_selected.append(br.region_all())
            else:
                should_selected.append(s)
            v.sel().clear()

        v.sel().add_all(should_selected)
        v.show_at_center(should_selected[0])


class BracketsTransformCommand(sublime_plugin.TextCommand):

    def run(self, edit, to):
        def replace_bracket(br):
            if br.shape != to:
                v.replace(edit, br.left, to)
                v.replace(edit, br.right, BRACKETS[to])

        v = self.view
        cursors_to = []
        cursors = [s.a for s in v.sel()]
        v.sel().clear()

        for cursor in cursors:
            v.sel().add(cursor)
            br = select_bracket(v)
            if br:
                replace_bracket(br)
                cursors_to.append(br.left.a)
            else:
                cursors_to.append(cursor)
            v.sel().clear()

        v.sel().add_all(cursors_to)
        v.show_at_center(cursors_to[0])


class BracketsTakeOffCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        def take_off(br):
            region = br.region_all()
            contain = self.view.substr(sublime.Region(br.left.b, br.right.a))
            self.view.replace(edit, region, contain)
            region.b -= 2
            return region

        v = self.view
        selections = [s.a for s in v.sel()]
        v.sel().clear()

        bregions = OrderedDict()
        for s in selections:
            v.sel().add(s)
            br = select_bracket(v)
            if br:
                bregions[br.left.a] = br
            v.sel().clear()

        bregions = [bregions[key] for key in bregions]

        should_selected = []
        left_move = 0
        for br in bregions:
            br.left_move(left_move)
            should_selected.append((take_off(br)))
            left_move += 2

        if not should_selected:
            should_selected = selections

        v.sel().add_all(should_selected)
        v.show_at_center(should_selected[0])
