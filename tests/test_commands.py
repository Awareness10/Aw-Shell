"""Tests for utils/commands.py - the command facade `fabric-cli exec` calls.

fabric's `exec` runs the code with exec() in main.py's module namespace
(FileHook.from_here takes the outermost stack frame), so these tests run the
same strings with exec() against a namespace shaped like main.py's.
"""

import ast
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import utils.commands as commands
from config.settings_constants import DEFAULTS
from config.settings_utils import bind_vars, generate_hyprlua
from utils.commands import NOTCH_VIEWS, ShellCommands, install_legacy_aliases

MAIN_PY = Path(__file__).resolve().parent.parent / "main.py"

# Verbatim from the aw-shell.lua generate_hyprlua() wrote up to v1.3.0 and the
# matugen post_hooks of that time; users still have these files
LEGACY_NOTCH_VIEWS = (
    "dashboard", "bluetooth", "pins", "kanban", "launcher", "tmux", "cliphist",
    "tools", "overview", "wallpapers", "mixer", "emoji", "power",
)
LEGACY_RANDOM_WALLPAPER = "notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)"
LEGACY_CAFFEINE = "notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)"
LEGACY_TOGGLE_BAR = ("from utils.global_keybinds import get_global_keybind_handler; "
                     "get_global_keybind_handler().toggle_bar()")
LEGACY_CSS = "app.set_css()"
LEGACY_GTK_THEME = "app.apply_gtk_theme()"


@pytest.fixture
def graph():
    """Fake object graph: the app and a notch with the paths binds reach into."""
    return MagicMock(name="app"), MagicMock(name="notch")


@pytest.fixture
def namespace(graph):
    """main.py's module namespace as fabric's exec sees it."""
    app, notch = graph
    shell = ShellCommands(app, notch)
    install_legacy_aliases(app, shell)
    return {"app": app, "notch": notch, "shell": shell}


@pytest.fixture
def handler():
    with patch.object(commands, "get_global_keybind_handler") as get:
        yield get.return_value


def run(namespace, source):
    """What `fabric-cli exec aw-shell '<source>'` does in the shell."""
    exec(source, namespace, namespace)


# ── Facade methods ────────────────────────────────────────────────────


@pytest.mark.parametrize("view", NOTCH_VIEWS)
def test_open_opens_notch_view(graph, view):
    app, notch = graph
    ShellCommands(app, notch).open(view)
    notch.open_notch.assert_called_once_with(view)


def test_random_wallpaper(graph):
    app, notch = graph
    ShellCommands(app, notch).random_wallpaper()
    notch.dashboard.wallpapers.set_random_wallpaper.assert_called_once_with(None, external=True)


def test_toggle_caffeine(graph):
    app, notch = graph
    ShellCommands(app, notch).toggle_caffeine()
    button = notch.dashboard.widgets.buttons.caffeine_button
    button.toggle_inhibit.assert_called_once_with(external=True)


def test_toggle_bar_toggles_every_monitor(graph, handler):
    handler.toggle_bar.return_value = True
    assert ShellCommands(*graph).toggle_bar() is True
    handler.toggle_bar.assert_called_once_with()


def test_reload_css_sets_built_stylesheet(graph):
    from config.paths import APP_DIR
    app, notch = graph
    with patch("utils.stylesheet.build_stylesheet", return_value="css") as build:
        ShellCommands(app, notch).reload_css()
    build.assert_called_once_with()
    app.set_stylesheet_from_string.assert_called_once_with("css", base_path=str(APP_DIR))


@pytest.mark.parametrize("enabled", [True, False])
def test_apply_gtk_theme_follows_setting(graph, enabled):
    with patch("config.data.GTK_THEMING", enabled), \
            patch("config.gtk_theme.apply_gtk_theme") as apply:
        ShellCommands(*graph).apply_gtk_theme()
    apply.assert_called_once_with(enabled)


# ── New expressions (generated lua, matugen post_hooks) ──────────────


def _generated_expressions():
    """The Python each `fabricSend .. "<lua string>"` bind sends."""
    bind_vars.clear()
    bind_vars.update(DEFAULTS.copy())
    lua_strings = re.findall(r'fabricSend \.\. ("(?:[^"\\]|\\.)*")', generate_hyprlua())
    # These Lua strings only use JSON-compatible escapes (\")
    return [json.loads(s).strip().strip("'") for s in lua_strings]


def test_notch_views_match_generated_binds():
    """Every view a keybind opens is a known view, and vice versa."""
    opened = {view for expr in _generated_expressions()
              for view in re.findall(r'shell\.open\("(\w+)"\)', expr)}
    assert opened == set(NOTCH_VIEWS)


def test_generated_binds_only_use_facade():
    exprs = _generated_expressions()
    assert len(exprs) == len(NOTCH_VIEWS) + 4  # + wallpaper, caffeine, bar, css
    assert all(e.startswith("shell.") for e in exprs), exprs


def test_generated_binds_run_against_facade(graph, handler):
    """With only `shell` in the namespace: binds don't reach into the tree."""
    app, notch = graph
    ns = {"shell": ShellCommands(app, notch)}
    with patch("utils.stylesheet.build_stylesheet", return_value=""):
        for expr in _generated_expressions():
            run(ns, expr)
    assert [c.args[0] for c in notch.open_notch.call_args_list] == list(NOTCH_VIEWS)
    notch.dashboard.wallpapers.set_random_wallpaper.assert_called_once()
    notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit.assert_called_once()
    handler.toggle_bar.assert_called_once()
    app.set_stylesheet_from_string.assert_called_once()


# ── Backward compatibility: old expressions keep working ─────────────


@pytest.mark.parametrize("view", LEGACY_NOTCH_VIEWS)
def test_legacy_open_notch(namespace, view):
    run(namespace, f'notch.open_notch("{view}")')
    namespace["notch"].open_notch.assert_called_once_with(view)


def test_legacy_random_wallpaper(namespace):
    run(namespace, LEGACY_RANDOM_WALLPAPER)
    wallpapers = namespace["notch"].dashboard.wallpapers
    wallpapers.set_random_wallpaper.assert_called_once_with(None, external=True)


def test_legacy_caffeine(namespace):
    run(namespace, LEGACY_CAFFEINE)
    button = namespace["notch"].dashboard.widgets.buttons.caffeine_button
    button.toggle_inhibit.assert_called_once_with(external=True)


def test_legacy_toggle_bar(namespace):
    with patch("utils.global_keybinds.get_global_keybind_handler") as get:
        run(namespace, LEGACY_TOGGLE_BAR)
    get.return_value.toggle_bar.assert_called_once_with()


def test_legacy_set_css_reloads_css(namespace):
    with patch("utils.stylesheet.build_stylesheet", return_value="css"):
        run(namespace, LEGACY_CSS)
    namespace["app"].set_stylesheet_from_string.assert_called_once()


def test_legacy_apply_gtk_theme(namespace):
    with patch("config.gtk_theme.apply_gtk_theme") as apply:
        run(namespace, LEGACY_GTK_THEME)
    apply.assert_called_once()


def test_main_keeps_exec_names_at_module_level():
    """The exec namespace is main.py's globals: `shell`, and the `app` and
    `notch` old configs use, must be assigned at module level (not only
    inside a function) and install_legacy_aliases must run."""
    tree = ast.parse(MAIN_PY.read_text())
    main_block = next(node for node in tree.body
                      if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
                      and "--migrate" not in ast.unparse(node.test))
    assigned = set()
    pending = list(main_block.body)
    while pending:  # module-level statements, nested blocks but not functions
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.Assign, ast.For)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assigned |= {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
        pending.extend(ast.iter_child_nodes(node))
    assert {"app", "notch", "shell"} <= assigned
    assert "install_legacy_aliases(app, shell)" in ast.unparse(main_block)
