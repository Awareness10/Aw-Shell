import json
import subprocess
from typing import Dict, List, Optional, Tuple

import gi

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk

# The main monitor is the one holding this workspace. Monitor IDs follow
# connection order, which changes with how fast each screen wakes up, while
# workspace 1 is normally pinned to the main screen.
PRIMARY_WORKSPACE = 1


class Signal:
    """Simple signal implementation for monitor manager."""

    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        """Connect a callback to this signal."""
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        """Emit the signal to all connected callbacks."""
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Error in signal callback: {e}")


def _hyprctl_json(command: str):
    result = subprocess.run(
        ["hyprctl", command, "-j"], capture_output=True, text=True, check=True, timeout=2.0
    )
    return json.loads(result.stdout)


def _gdk_ids_by_connector() -> Dict[str, int]:
    """GDK monitor index per connector name; empty if GDK can't tell."""
    ids = {}
    try:
        screen = Gdk.Screen.get_default()
        if screen is None:
            return ids
        for i in range(screen.get_n_monitors()):
            name = screen.get_monitor_plug_name(i)
            if isinstance(name, str) and name:
                ids[name] = i
    except Exception as e:
        print(f"MonitorManager: could not read GDK monitors: {e}")
    return ids


def _match_monitor_rule(selector: str, monitors: List[Dict]) -> Optional[str]:
    """Connector name for a workspace rule's monitor (a name or `desc:...`)."""
    for monitor in monitors:
        if selector.startswith("desc:"):
            if monitor.get("description", "").startswith(selector[len("desc:"):].strip()):
                return monitor.get("name")
        elif monitor.get("name") == selector:
            return monitor.get("name")
    return None


class MonitorManager:
    """
    Centralized monitor management for Aw-Shell multi-monitor support.
    
    Manages monitor detection, workspace paging, notch states, and component instances.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._monitors: List[Dict] = []
        self._focused_monitor_id: int = 0
        self._notch_states: Dict[int, bool] = {}
        self._current_notch_module: Dict[int, Optional[str]] = {}
        self._monitor_instances: Dict[int, Dict] = {}
        self._monitor_focus_service = None
        
        # Signals
        self.monitor_changed = Signal()
        self.notch_focus_changed = Signal()
        
        self.refresh_monitors()
    
    def set_monitor_focus_service(self, service):
        """Set the monitor focus service reference."""
        self._monitor_focus_service = service
        if service:
            service.monitor_focused.connect(self._on_monitor_focused)
    
    def _get_gtk_monitor_info(self) -> List[Dict]:
        """Get monitor information using GTK/GDK including scale factors."""
        gtk_monitors = []
        try:
            display = Gdk.Display.get_default()
            if display and hasattr(display, 'get_n_monitors'):
                n_monitors = display.get_n_monitors()
                for i in range(n_monitors):
                    monitor = display.get_monitor(i)
                    if monitor:
                        geometry = monitor.get_geometry()
                        scale_factor = monitor.get_scale_factor()
                        model = monitor.get_model() or f'monitor-{i}'
                        
                        gtk_monitors.append({
                            'id': i,
                            'name': model,
                            'width': geometry.width,
                            'height': geometry.height,
                            'x': geometry.x,
                            'y': geometry.y,
                            'scale': scale_factor
                        })
        except Exception as e:
            print(f"Error getting GTK monitor info: {e}")
        
        return gtk_monitors

    def refresh_monitors(self) -> List[Dict]:
        """
        Detect monitors using Hyprland API for accurate info.

        A monitor's id is its GDK index, which is what layer surfaces are
        placed by (`monitor=` on a window), so an id always names the screen
        its surfaces are on. GDK numbers monitors in connection order, which
        can put the main screen anywhere; see get_primary_monitor_id().

        Returns:
            List of monitor dictionaries with id, name, width, height, x, y, scale
        """
        self._monitors = []

        try:
            hypr_monitors = _hyprctl_json("monitors")
            gdk_ids = _gdk_ids_by_connector()

            for monitor in hypr_monitors:
                monitor_name = monitor.get('name', '')
                hypr_id = monitor.get('id', 0)

                if not gdk_ids:
                    # No connector names from GDK; Hyprland ids follow
                    # connection order too
                    monitor_id = hypr_id
                elif monitor_name in gdk_ids:
                    monitor_id = gdk_ids[monitor_name]
                else:
                    print(f"MonitorManager: skipping {monitor_name}, unknown to GDK")
                    continue

                self._monitors.append({
                    'id': monitor_id,
                    'name': monitor_name,
                    'hypr_id': hypr_id,
                    'width': monitor.get('width', 1920),
                    'height': monitor.get('height', 1080),
                    'x': monitor.get('x', 0),
                    'y': monitor.get('y', 0),
                    'focused': monitor.get('focused', False),
                    # Get scale directly from Hyprland (more reliable)
                    'scale': monitor.get('scale', 1.0)
                })

                # Initialize states for new monitors
                if monitor_id not in self._notch_states:
                    self._notch_states[monitor_id] = False
                    self._current_notch_module[monitor_id] = None

            self._monitors.sort(key=lambda m: m['id'])

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                json.JSONDecodeError, FileNotFoundError):
            # Fallback to GTK only if Hyprland fails
            self._fallback_to_gtk()
        
        # Ensure we have at least one monitor
        if not self._monitors:
            self._monitors = [{
                'id': 0,
                'name': 'default',
                'width': 1920,
                'height': 1080,
                'x': 0,
                'y': 0,
                'focused': True,
                'scale': 1.0
            }]
            self._notch_states[0] = False
            self._current_notch_module[0] = None
        
        # Update focused monitor
        for monitor in self._monitors:
            if monitor.get('focused', False):
                self._focused_monitor_id = monitor['id']
                break
        
        self.monitor_changed.emit(self._monitors)
        return self._monitors
    
    def _fallback_to_gtk(self):
        """Fallback monitor detection using GTK with scale information."""
        try:
            display = Gdk.Display.get_default()
            if display and hasattr(display, 'get_n_monitors'):
                n_monitors = display.get_n_monitors()
                for i in range(n_monitors):
                    monitor = display.get_monitor(i)
                    geometry = monitor.get_geometry()
                    scale_factor = monitor.get_scale_factor()
                    
                    self._monitors.append({
                        'id': i,
                        'name': monitor.get_model() or f'monitor-{i}',
                        'width': geometry.width,
                        'height': geometry.height,
                        'x': geometry.x,
                        'y': geometry.y,
                        'focused': i == 0,  # Assume first monitor is focused
                        'scale': scale_factor
                    })
                    
                    if i not in self._notch_states:
                        self._notch_states[i] = False
                        self._current_notch_module[i] = None
        except Exception:
            pass
    
    def get_monitors(self) -> List[Dict]:
        """Get list of all monitors."""
        return self._monitors.copy()

    def get_primary_monitor_name(self) -> Optional[str]:
        """Connector name of the monitor holding PRIMARY_WORKSPACE, or None.

        Hyprland drops empty workspaces, so when the workspace doesn't exist
        right now its workspace rule decides.
        """
        try:
            for workspace in _hyprctl_json("workspaces"):
                if workspace.get("id") == PRIMARY_WORKSPACE:
                    return workspace.get("monitor")

            for rule in _hyprctl_json("workspacerules"):
                if rule.get("workspaceString") == str(PRIMARY_WORKSPACE) and rule.get("monitor"):
                    return _match_monitor_rule(rule["monitor"], _hyprctl_json("monitors"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                json.JSONDecodeError, FileNotFoundError) as e:
            print(f"MonitorManager: could not resolve primary monitor: {e}")
        return None

    def get_primary_monitor_id(self) -> int:
        """Id of the monitor holding PRIMARY_WORKSPACE, else the first monitor's."""
        monitor_id = self.get_monitor_id_by_name(self.get_primary_monitor_name())
        if monitor_id is not None:
            return monitor_id
        return self._monitors[0]['id'] if self._monitors else 0

    def query_focused_monitor_id(self) -> Optional[int]:
        """Id of the monitor Hyprland has focused right now, or None.

        Asks Hyprland rather than trusting the tracked focus, which only
        updates when a notch opens.
        """
        try:
            for monitor in _hyprctl_json("monitors"):
                if monitor.get("focused"):
                    return self.get_monitor_id_by_name(monitor.get("name"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                json.JSONDecodeError, FileNotFoundError) as e:
            print(f"MonitorManager: could not query focused monitor: {e}")
        return None

    def get_monitor_id_by_name(self, name: Optional[str]) -> Optional[int]:
        """Id of the monitor with this connector name (e.g. "DP-3")."""
        for monitor in self._monitors:
            if monitor['name'] == name:
                return monitor['id']
        return None

    def get_monitor_by_id(self, monitor_id: int) -> Optional[Dict]:
        """Get monitor by ID."""
        for monitor in self._monitors:
            if monitor['id'] == monitor_id:
                return monitor.copy()
        return None
    
    def get_focused_monitor_id(self) -> int:
        """Get currently focused monitor ID."""
        return self._focused_monitor_id
    
    def get_focused_monitor(self) -> Optional[Dict]:
        """Get currently focused monitor."""
        return self.get_monitor_by_id(self._focused_monitor_id)
    
    def get_workspace_range_for_monitor(self, monitor_id: int) -> Tuple[int, int]:
        """
        Get workspace range for a monitor.
        All monitors share workspaces 1-10 (Hyprland handles assignment).

        Args:
            monitor_id: Monitor ID (unused, kept for API compatibility)

        Returns:
            Tuple of (start_workspace, end_workspace) - always (1, 10)
        """
        return (1, 10)

    def get_monitor_for_workspace(self, workspace_id: int) -> Optional[int]:
        """
        Get monitor ID for a workspace by querying Hyprland.

        Args:
            workspace_id: Workspace number

        Returns:
            Monitor ID where the workspace is, or None if not found
        """
        try:
            result = subprocess.run(
                ["hyprctl", "workspaces", "-j"],
                capture_output=True,
                text=True,
                check=True
            )
            workspaces = json.loads(result.stdout)
            for ws in workspaces:
                if ws.get('id') == workspace_id:
                    # Find our monitor by name
                    ws_monitor = ws.get('monitor', '')
                    for m in self._monitors:
                        if m.get('name') == ws_monitor:
                            return m.get('id')
            return None
        except Exception:
            return None
    
    def get_monitor_scale(self, monitor_id: int) -> float:
        """
        Get scale factor for a monitor.
        
        Args:
            monitor_id: Monitor ID
            
        Returns:
            Scale factor (default 1.0 if not found)
        """
        monitor = self.get_monitor_by_id(monitor_id)
        return monitor.get('scale', 1.0) if monitor else 1.0
    
    def is_notch_open(self, monitor_id: int) -> bool:
        """Check if notch is open on a monitor."""
        return self._notch_states.get(monitor_id, False)
    
    def set_notch_state(self, monitor_id: int, is_open: bool, module: Optional[str] = None):
        """Set notch state for a monitor."""
        self._notch_states[monitor_id] = is_open
        self._current_notch_module[monitor_id] = module if is_open else None
    
    def get_current_notch_module(self, monitor_id: int) -> Optional[str]:
        """Get current notch module for a monitor."""
        return self._current_notch_module.get(monitor_id)
    
    def close_all_notches_except(self, except_monitor_id: int):
        """Close all notches except on specified monitor."""
        for monitor_id in self._notch_states:
            if monitor_id != except_monitor_id and self._notch_states[monitor_id]:
                self.set_notch_state(monitor_id, False)
                # Get notch instance and close it
                instances = self._monitor_instances.get(monitor_id, {})
                notch = instances.get('notch')
                if notch and hasattr(notch, 'close_notch'):
                    notch.close_notch()
    
    def register_monitor_instances(self, monitor_id: int, instances: Dict):
        """
        Register component instances for a monitor.
        
        Args:
            monitor_id: Monitor ID
            instances: Dict with 'bar', 'notch', 'dock', 'corners' keys
        """
        self._monitor_instances[monitor_id] = instances
    
    def get_monitor_instances(self, monitor_id: int) -> Dict:
        """Get component instances for a monitor."""
        return self._monitor_instances.get(monitor_id, {})
    
    def get_instance(self, monitor_id: int, component: str):
        """Get specific component instance for a monitor."""
        instances = self._monitor_instances.get(monitor_id, {})
        return instances.get(component)
    
    def get_focused_instance(self, component: str):
        """Get component instance from focused monitor."""
        return self.get_instance(self._focused_monitor_id, component)
    
    def _on_monitor_focused(self, monitor_name: str, monitor_id: int, workspace_id: int):
        """Handle monitor focus change."""
        old_focused = self._focused_monitor_id
        self._focused_monitor_id = monitor_id
        
        # Handle notch focus switching
        if old_focused != monitor_id:
            self._handle_notch_focus_switch(old_focused, monitor_id)
    
    def _handle_notch_focus_switch(self, old_monitor: int, new_monitor: int):
        """Handle notch switching between monitors."""
        # Close notch on old monitor if open
        if self.is_notch_open(old_monitor):
            old_module = self.get_current_notch_module(old_monitor)
            self.close_all_notches_except(-1)  # Close all
            
            # Open notch on new monitor with same module
            if old_module:
                new_instances = self.get_monitor_instances(new_monitor)
                notch = new_instances.get('notch')
                if notch and hasattr(notch, 'open_module'):
                    notch.open_module(old_module)
        
        self.notch_focus_changed.emit(old_monitor, new_monitor)


# Singleton accessor
_monitor_manager_instance = None

def get_monitor_manager() -> MonitorManager:
    """Get the global MonitorManager instance."""
    global _monitor_manager_instance
    if _monitor_manager_instance is None:
        _monitor_manager_instance = MonitorManager()
    return _monitor_manager_instance