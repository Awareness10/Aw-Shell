"""Shared test fixtures and mock setup.

Sets up mocks for GTK/Fabric imports before any test module imports them,
and configures headless Qt for PySide6 tests.
"""

import os
import sys
import types
from unittest.mock import MagicMock

# ── Headless Qt for PySide6 tests ──
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ── Mock fabric (used by config.settings_constants, config.settings_utils, utils/functions) ──
if "fabric" not in sys.modules:
    _mock_fabric = types.ModuleType("fabric")
    _mock_fabric_utils = types.ModuleType("fabric.utils")
    _mock_fabric_helpers = types.ModuleType("fabric.utils.helpers")
    _mock_fabric_helpers.get_relative_path = lambda p: f"/mock/path/{p}"
    _mock_fabric_helpers.exec_shell_command = lambda cmd: ""
    _mock_fabric_helpers.exec_shell_command_async = MagicMock()
    _mock_fabric.utils = _mock_fabric_utils
    _mock_fabric_utils.helpers = _mock_fabric_helpers
    # fabric.utils also exports these directly
    _mock_fabric_utils.exec_shell_command = _mock_fabric_helpers.exec_shell_command
    _mock_fabric_utils.exec_shell_command_async = _mock_fabric_helpers.exec_shell_command_async
    _mock_fabric_utils.get_relative_path = _mock_fabric_helpers.get_relative_path
    sys.modules["fabric"] = _mock_fabric
    sys.modules["fabric.utils"] = _mock_fabric_utils
    sys.modules["fabric.utils.helpers"] = _mock_fabric_helpers

# ── Mock gi / GTK / GLib (used by config.data, utils/functions, utils/monitor_manager) ──
if "gi" not in sys.modules:
    _mock_gi = types.ModuleType("gi")
    _mock_gi.require_version = lambda *a: None
    _mock_gdk = MagicMock()
    _mock_gtk = MagicMock()
    _mock_glib = MagicMock()
    _mock_glib.get_user_cache_dir.return_value = "/tmp/test-cache"
    _mock_glib.get_os_info.return_value = "arch"
    _mock_gi_repo = types.ModuleType("gi.repository")
    _mock_vte = MagicMock()
    _mock_gi_repo.Gdk = _mock_gdk
    _mock_gi_repo.Gtk = _mock_gtk
    _mock_gi_repo.GLib = _mock_glib
    _mock_gi_repo.Vte = _mock_vte
    sys.modules["gi"] = _mock_gi
    sys.modules["gi.repository"] = _mock_gi_repo
    sys.modules["gi.repository.Gdk"] = _mock_gdk
    sys.modules["gi.repository.Gtk"] = _mock_gtk
    sys.modules["gi.repository.GLib"] = _mock_glib
    sys.modules["gi.repository.Vte"] = _mock_vte
