import re
import os
import sublime
import sublime_plugin

from collections import ChainMap
from typing import Any, Dict, Optional

from .color_scheme  import cs_mgr
from .consts        import PACKAGE_NAME
from .consts        import SETTINGS_FILE
from .logger        import Logger
from .executor      import RainbowBracketsExecutor


def show_error_message(msg: str):
    sublime.error_message(f'{PACKAGE_NAME}: {msg}')


def compile_config(
    config: Dict[str, Any],
    syntax: Optional[str],
    is_default: bool,
    scope_color_map: Dict[str, str]
):
    color_cycle = config.get('color.cycle', [])
    color_error = config.get('color.error')
    if color_cycle:
        scopes = config['scopes'] = []
        keys = config['keys'] = []
        for i, color in enumerate(color_cycle):
            if is_default:
                key   = f'_rb_l{i}'
                scope = f'l{i}._rb'
            else:
                key   = f'_rb_l{i}_{syntax}'
                scope = f'{syntax}.l{i}._rb'
            keys.append(key)
            scopes.append(scope)
            scope_color_map[scope] = color
        config['keys']   = keys
        config['scopes'] = scopes
    if color_error is not None:
        if is_default:
            key   = f'_rb_error'
            scope = f'error._rb'
        else:
            key   = f'_rb_error_{syntax}'
            scope = f'{syntax}.error._rb'
        config['err_key']   = key
        config['err_scope'] = scope
        scope_color_map[scope] = color_error
    if 'bracket_pairs' in config:
        pairs = config['bracket_pairs']
        brackets = sorted(list(pairs.keys()) + list(pairs.values()))
        config['pattern']  = '|'.join(re.escape(b) for b in brackets)
    if 'ignored_scopes' in config:
        config['selector'] = '|'.join(config['ignored_scopes'])


class RainbowBracketsViewManager(sublime_plugin.EventListener):
    default_config = {}
    configs_by_stx = {}
    syntaxes_by_ext = {}
    view_executors: Dict[int, RainbowBracketsExecutor] = {}
    is_ready = False

    @classmethod
    def init(cls):
        cls.settings = sublime.load_settings(SETTINGS_FILE)
        cls.settings.add_on_change(PACKAGE_NAME, cls.reload)
        cls.load_config()
        cls.check_load_active_view()

    @classmethod
    def exit(cls):
        cls.settings.clear_on_change(PACKAGE_NAME)

    @classmethod
    def reload(cls):
        cls.load_config()
        cls.check_load_active_view()
        cls.reload_view_executors()

    @classmethod
    def load_config(cls):
        cls.is_ready = False

        default_config  = cls.settings.get('default_config', {})
        configs_by_stx  = cls.settings.get('syntax_specific', {})
        syntaxes_by_ext = {}
        scope_color_map = {}

        default_config.setdefault('coloring', False)
        default_config.setdefault('enabled', True)

        compile_config(default_config, None, True, scope_color_map)
        for syntax, config in configs_by_stx.items():
            compile_config(config, syntax, False, scope_color_map)

        for syntax, config in configs_by_stx.items():
            for ext in config.get('extensions', []):
                syntaxes_by_ext[ext] = syntax

        Logger.debug = cls.settings.get('debug', False)
        Logger.pprint(configs_by_stx)

        cs_mgr.set_colors(list(scope_color_map.items()))

        cls.syntaxes_by_ext = syntaxes_by_ext
        cls.configs_by_stx = configs_by_stx
        cls.default_config = default_config
        cls.is_ready = True

    @classmethod
    def reload_view_executors(cls):
        disabled_views = []
        for view_id in cls.view_executors:
            executor = cls.view_executors[view_id]
            view = executor.view
            syntax, config = cls.get_syntax_config(view)
            if not config['enabled']:
                disabled_views.append(view)
                continue
            if (syntax == executor.syntax and
                config == executor.config):
                continue
            Logger.print(f'Reloading {executor.view_file_name()}')
            executor.clear_bracket_regions()
            executor.__init__(view, syntax, config)
            executor.load()
        for view in disabled_views:
            cls.close_view_executor(view)

    @classmethod
    def check_view_add_executor(cls, view, force=False):
        if not cls.is_ready:
            if force:
                show_error_message('error in loading settings')
            return

        if view.view_id in cls.view_executors:
            return cls.view_executors[view.view_id]

        if view.settings().get('rb_enable', True):
            syntax, config = cls.get_syntax_config(view)
            if config['enabled'] or force:
                if config['bracket_pairs']:
                    executor = RainbowBracketsExecutor(view, syntax, config)
                    cs_mgr.attach_view(view)
                    cls.view_executors[view.view_id] = executor
                    return executor
                elif force:
                    show_error_message('empty brackets list')
        return None

    @classmethod
    def get_syntax_config(cls, view):
        syntax = cls.get_view_syntax(view)
        if syntax is not None:
            config = ChainMap(cls.configs_by_stx[syntax], cls.default_config)
        else:
            config = cls.default_config
        return syntax, config

    @classmethod
    def get_view_syntax(cls, view):
        syntax = view.syntax()
        if syntax and syntax.name in cls.configs_by_stx:
            return syntax.name
        filename = view.file_name()
        if filename:
            ext = os.path.splitext(filename)[1]
            return cls.syntaxes_by_ext.get(ext, None)
        return None

    @classmethod
    def force_add_executor(cls, view):
        view.settings().set('rb_enable', True)
        return cls.check_view_add_executor(view, force=True)

    @classmethod
    def get_view_executor(cls, view):
        return cls.view_executors.get(view.view_id, None)

    @classmethod
    def check_load_active_view(cls):
        active_view = sublime.active_window().active_view()
        cls.check_view_load_executor(active_view)

    @classmethod
    def check_view_load_executor(cls, view):
        executor = view.size() and cls.check_view_add_executor(view)
        if executor and not executor.bracket_regions_trees:
            executor.load()

    @classmethod
    def setup_view_executor(cls, view):
        executor = cls.force_add_executor(view)
        executor and executor.load()  # type: ignore

    @classmethod
    def close_view_executor(cls, view):
        executor = cls.view_executors.pop(view.view_id, None)
        if executor and executor.coloring:
            executor.clear_bracket_regions()

    @classmethod
    def color_view(cls, view):
        executor = cls.get_view_executor(view)
        if executor and not executor.coloring:
            executor.coloring = True
            executor.check_bracket_regions()
        elif not executor:
           executor = cls.force_add_executor(view)
           if executor:
                executor.coloring = True
                executor.load()

    @classmethod
    def sweep_view(cls, view):
        executor = cls.get_view_executor(view)
        if executor and executor.coloring:
            executor.coloring = False
            executor.clear_bracket_regions()

    @classmethod
    def get_view_bracket_pairs(cls, view):
        executor = cls.get_view_executor(view)
        return executor and executor.brackets

    @classmethod
    def get_view_bracket_trees(cls, view):
        executor = cls.get_view_executor(view)
        if not executor:
            cls.setup_view_executor(view)
            executor = cls.get_view_executor(view)
        return executor and executor.bracket_regions_trees

    def on_load(self, view):
        self.check_view_load_executor(view)

    def on_post_save(self, view):
        self.check_view_load_executor(view)

    def on_activated(self, view):
        self.check_view_load_executor(view)

    def on_modified(self, view):
        executor = self.view_executors.get(view.view_id, None)
        executor and executor.check_bracket_regions()  # type: ignore

    def on_close(self, view):
        self.view_executors.pop(view.view_id, None)
        cs_mgr.detach_view(view)
