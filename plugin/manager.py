import re
import os
import sublime
import sublime_plugin

from .color_scheme  import ColorSchemeManager
from .consts        import DEFAULT_SYNTAX
from .consts        import PACKAGE_NAME
from .consts        import SETTINGS_FILE
from .debug         import Debuger
from .executor      import RainbowBracketsExecutor


class RainbowBracketsViewManager(sublime_plugin.EventListener):
    configs_by_stx = {}
    syntaxes_by_ext = {}
    view_executors = {}
    is_ready = False

    @classmethod
    def init(cls):
        cls.settings = sublime.load_settings(SETTINGS_FILE)
        cls.settings.add_on_change(PACKAGE_NAME, cls.reload)
        cls.load_config()
        active_view = sublime.active_window().active_view()
        cls.check_view_load_executor(active_view)

    @classmethod
    def exit(cls):
        cls.settings.clear_on_change(PACKAGE_NAME)
        cls.color_scheme_manager.exit()
        cls.color_scheme_manager = None

    @classmethod
    def reload(cls):
        cls.load_config()
        cls.reload_view_executors()

    @classmethod
    def load_config(cls):
        cls.is_ready = False

        default_config  = cls.settings.get("default_config", {})
        configs_by_stx  = cls.settings.get("syntax_specific", {})
        syntaxes_by_ext = {}

        for syntax, config in configs_by_stx.items():
            for key in ("enabled", "coloring"):
                if key not in config:
                    config[key] = True
            for key in default_config.keys():
                if key not in config:
                    config[key] = default_config[key]
            for ext in config.get("extensions", []):
                syntaxes_by_ext[ext] = syntax

        if "coloring" not in default_config:
            default_config["coloring"] = False
        if "enabled" not in default_config:
            default_config["enabled"] = True

        configs_by_stx[DEFAULT_SYNTAX] = default_config

        for syntax, config in configs_by_stx.items():
            levels = range(len(config["rainbow_colors"]))
            config["keys"]   = [f"rb_l{i}_{syntax}" for i in levels]
            config["scopes"] = [f"{syntax}.l{i}.rb" for i in levels]
            config["bad_key"]   = f"rb_mismatch_{syntax}"
            config["bad_scope"] = f"{syntax}.mismatch.rb"

            pairs = config["bracket_pairs"]
            brackets = sorted(list(pairs.keys()) + list(pairs.values()))

            config["pattern"]  = "|".join(re.escape(b) for b in brackets)
            config["selector"] = "|".join(config.pop("ignored_scopes"))

        Debuger.debug = cls.settings.get("debug", False)
        Debuger.pprint(configs_by_stx)

        cls.color_scheme_manager = ColorSchemeManager(configs_by_stx.values)
        cls.syntaxes_by_ext = syntaxes_by_ext
        cls.configs_by_stx = configs_by_stx
        cls.is_ready = True

    @classmethod
    def reload_view_executors(cls):
        for view_id in cls.view_executors:
            executor = cls.view_executors[view_id]
            view = executor.view
            syntax, config = cls.get_syntax_config(view)
            if (syntax == executor.syntax and
                config == executor.config):
                continue
            else:
                Debuger.print(f"reload file {executor.view_file_name()}")
                executor.clear_bracket_regions()
                executor.__init__(view, syntax, config)
                executor.load()

    @classmethod
    def check_view_add_executor(cls, view, force=False):
        if not cls.is_ready:
            if force:
                msg = "RainbowBrackets: error in loading settings."
                sublime.error_message(msg)
            return

        if view.view_id in cls.view_executors:
            return cls.view_executors[view.view_id]

        if view.settings().get("rb_enable", True):
            syntax, config = cls.get_syntax_config(view)
            if config["enabled"] or force:
                if config["bracket_pairs"]:
                    executor = RainbowBracketsExecutor(view, syntax, config)
                    cls.view_executors[view.view_id] = executor
                    return executor
                elif force:
                    sublime.error_message("empty brackets list")
        return None

    @classmethod
    def get_syntax_config(cls, view):
        syntax = cls.get_view_syntax(view) or DEFAULT_SYNTAX
        config = cls.configs_by_stx[syntax]
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
        view.settings().set("rb_enable", True)
        return cls.check_view_add_executor(view, force=True)

    @classmethod
    def get_view_executor(cls, view):
        return cls.view_executors.get(view.view_id, None)

    @classmethod
    def check_view_load_executor(cls, view):
        executor = view.size() and cls.check_view_add_executor(view)
        if executor and not executor.bracket_regions_trees:
            executor.load()

    @classmethod
    def setup_view_executor(cls, view):
        executor = cls.force_add_executor(view)
        executor and executor.load()

    @classmethod
    def close_view_executor(cls, view):
        view.settings().set("rb_enable", False)
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
        executor and executor.check_bracket_regions()

    def on_close(self, view):
        self.view_executors.pop(view.view_id, None)
