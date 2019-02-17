

class BracketsTree(object):
    def __init__(self, lshape, lpoint):
        self.lshape = lshape
        self.rshape = BracketsSearcher.brackets[lshape]
        self.lpoint = lpoint
        self.rpoint = None
        self.children = []


class BracketsSearcher(object):
    def __init__(self, view, brackets):
        self.view = view
        self.brackets = brackets
        self.matched_brackets = []

    def jump2end_of_string_or_comment(self, point):
        match = self.view.match_selector
        if match(point, "string") or match(point, "comment"):
            return self.view.extract_scope(point).end()
        return point

    def get_brackets(self, region):
        content = self.view.substr(region)
        b_stk, p_stk = [], []
        matched_brackets = {}
        unmatched_brackets = []
        i, length = 0, region.size()

        while i < length:
            # skip string scope and comment scope
            point = self.jump2end_of_string_or_comment(region.a + i)
            if point > i + region.a:
                i = point - region.a
                continue
            char = content[i]
            if char in set(self.brackets.keys()):
                b_stk.append(char)
                p_stk.append(point)

            elif b_stk and char == self.brackets[b_stk[-1]]:
                matched_brackets.setdefault(b_stk.pop(), []).append(
                    (p_stk.pop(), point, len(b_stk)))

            elif char in set(self.brackets.values()):
                unmatched_brackets.append((point, char))

            i += 1

        while b_stk:
            unmatched_brackets.append((p_stk.pop(), b_stk.pop()))

        return (matched_brackets, unmatched_brackets)

    def get_brackets_by_layer(self, region):
        content = self.view.substr(region)
        b_stk, p_stk = [], []
        matched_brackets = {}
        unmatched_brackets = []
        i, length = 0, region.size()

        while i < length:
            # skip string scope and comment scope
            point = self.jump2end_of_string_or_comment(region.a + i)
            if point > i + region.a:
                i = point - region.a
                continue
            char = content[i]
            if char in set(self.brackets.keys()):
                b_stk.append(char)
                p_stk.append(point)

            elif b_stk and char == self.brackets[b_stk[-1]]:
                b_stk.pop()
                matched_brackets.setdefault(len(b_stk), []).extend((p_stk.pop(), point))

            elif char in set(self.brackets.values()):
                unmatched_brackets.append(point)
            i += 1

        while p_stk:
            unmatched_brackets.append(p_stk.pop())

        return (matched_brackets, unmatched_brackets)

    def get_brackets_tree(self, region):
        content = self.view.substr(region)
        brackets_node_stk = []
        matched_brackets = []
        unmatched_brackets = []
        i, length = 0, region.size()

        while i < length:
           # skip string scope and comment scope
            point = self.jump2end_of_string_or_comment(region.a + i)
            if point > i + region.a:
                i = point - region.a
                continue
            char = content[i]
            if char in set(self.brackets.keys()):
                brackets_node_stk.append(BracketsTree(char, point))

            elif brackets_node_stk and char == brackets_node_stk[-1].rshape:
                brackets_node = brackets_node_stk.pop()
                brackets_node.rpoint = point
                if brackets_node_stk:
                    brackets_node_stk[-1].children.append(brackets_node)
                else:
                    matched_brackets.append(brackets_node)

            elif char in set(self.brackets.values()):
                unmatched_brackets.append((point, char))

            i += 1

        while brackets_node_stk:
            brackets_node = brackets_node_stk.pop()
            unmatched_brackets.append(brackets_node.lpoint, brackets_node.lshape)

        return (matched_brackets, unmatched_brackets)

    def get_nearest_brackets(self, point, threshold=10000):
        begin = max(point - threshold//2, 0)
        end = min(begin + threshold, self.view.size())
        if end > begin:
            content = self.view.substr(sublime.Region(begin, end))
            i = point - begin


