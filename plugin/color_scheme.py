import json
import weakref

from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from pathlib import PurePath, Path

import sublime

from .debug  import Debuger
from .consts import DEFAULT_CS
from .consts import PACKAGE_NAME
from .consts import PACKAGE_URL


builtin_color_names = [
    'redish',
    'orangish',
    'yellowish',
    'greenish',
    'cyanish',
    'bluish',
    'purplish',
    'pinkish'
]


def _nearest_color(color : str):
    """
    Assume the input color is well-formed
    """
    c = int(color[1:], 16)
    r, g, b = (c >> 16) & 0xff, (c >> 8) & 0xff, c & 0xff
    r = r + (1 if r < 255 else -1)
    return f'#{r:02x}{g:02x}{b:02x}'


# scope color pairs
PlainRules = List[Tuple[str, str]]


class ColorSchemeManager:
    plain_rules : Dict[str, PlainRules] = {}

    view_current_cs : Dict[sublime.View, Optional[str]] = {}

    def __new__(cls, *args, **kwargs):
        if hasattr(cls, 'objref'):
            if obj := cls.objref():
                return obj
        self = object.__new__(cls)
        cls.objref = weakref.ref(self)
        return self

    def set_colors(self, scope_color_pairs : PlainRules):
        index = str(scope_color_pairs)
        self.last_written_cs = None
        self.plain_rules[index] = scope_color_pairs
        self.current_rules_index = index

        for view in self.view_current_cs:
            self.rewrite_view_cs(view)

    def attach_view(self, view : sublime.View):
        self.view_current_cs[view] = None
        def on_change():
            view_new_cs = settings.get('color_scheme', DEFAULT_CS)
            if view_new_cs != self.view_current_cs[view]:
                self.view_current_cs[view] = view_new_cs
                if view_new_cs != self.last_written_cs:
                    self.rewrite_view_cs(view)
        settings = view.settings()
        settings.add_on_change('rb.color_scheme_mgr', on_change)

    def detach_view(self, view : sublime.View):
        view.settings().clear_on_change('rb.color_scheme_mgr')
        self.view_current_cs.pop(view, None)

    def rewrite_view_cs(self, view : sublime.View):
        cs = self.view_current_cs[view]
        if cs is None:
            return

        def update_cs():
            # The color scheme to preview has been updated since
            # the timeout was created
            if cs != self.view_current_cs[view]:
                return
            if cs == self.last_written_cs:
                return
            self.write_view_cs(view, cs)
            self.last_written_cs = cs

        sublime.set_timeout(update_cs, 250)

    def write_view_cs(self, view : sublime.View, color_scheme : str) -> None:
        """
        We assume that there are no two CS with the same name
        and different extensions. Even if they do, they are not
        used at the same time.
        """
        style = view.style()
        cs_text = self.generate_cs_text(
            tuple(style[k] for k in builtin_color_names),
            style['background'],
            self.current_rules_index
        )
        cs_path = PurePath(color_scheme)
        cache_path = self.cache_path()
        cache_path.mkdir(parents=True, exist_ok=True)
        cache_path.joinpath(
            cs_path.with_suffix('.sublime-color-scheme').name
            ).write_text(cs_text)
        Debuger.print(f'Write color scheme {cs_path.stem}')

    def cache_path(self):
        try:
            return self._cache_path
        except:
            self._cache_path = Path(
                sublime.packages_path(), 'User', 'Color Schemes', PACKAGE_NAME)
            return self._cache_path

    @lru_cache
    def generate_cs_text(self,
        colors : Tuple[str], bg : str, rules_index : str) -> str:
        """
        Generate the color scheme text from the given colors,
        background color and rules index, use lru_cache to
        cache the results.
        """
        rules = []
        variables = {}
        nearest_bg = _nearest_color(bg)
        color_map = dict(zip(builtin_color_names, colors))
        for scope, color in self.plain_rules[rules_index]:
            if scope.endswith('error._rb'):
                background = bg
            else:
                background = nearest_bg
            if color in color_map:
                variables[f'region-{color}'] = color_map[color]
                foreground = f'var(region-{color})'
            else:
                foreground = color
            rules.append({
                "scope": scope,
                "foreground": foreground,
                "background": background
            })

        return json.dumps(
            {
                "author": PACKAGE_URL,
                "variables": variables,
                "rules": rules
            }
        )

    def get_all_inuse_color_schemes(self):
        color_scheme_set = set()
        for window in sublime.windows():
            for view in window.views(include_transient=True):
                color_scheme = view.settings().get('color_scheme')
                color_scheme_set.add(PurePath(color_scheme).stem)
        return color_scheme_set

    def clear_color_schemes(self):
        cache_path = self.cache_path()
        inuse_color_schemes = self.get_all_inuse_color_schemes()
        for file in cache_path.iterdir():
            if file.stem not in inuse_color_schemes:
                try:
                    file.unlink()
                    Debuger.print('Removed', file.name)
                except:
                    pass


cs_mgr = ColorSchemeManager()
