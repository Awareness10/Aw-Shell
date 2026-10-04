class GlobalKeybindHandler:
    """Handler for global keybinds that act on every monitor (see the
    "Toggle Bar" bind in config/settings_utils.py)."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._monitor_manager = None
    
    def set_monitor_manager(self, monitor_manager):
        """Set the monitor manager reference."""
        self._monitor_manager = monitor_manager
    
    def toggle_bar(self) -> bool:
        """
        Toggle bar visibility and force notch/dock to occlusion mode.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._monitor_manager:
            return False

        monitors = self._monitor_manager.get_monitors()

        for monitor in monitors:
            bar = self._monitor_manager.get_instance(monitor['id'], 'bar')
            notch = self._monitor_manager.get_instance(monitor['id'], 'notch')
        
            if bar and notch:
                try:
                    current_visibility = bar.get_visible()
                    bar.set_visible(not current_visibility)
                    
                    if not current_visibility:
                        # Bar is being shown - restore from occlusion
                        notch.restore_from_occlusion()
                        # Also restore docks on all monitors
                        try:
                            from modules.dock import Dock
                            for dock_instance in Dock._instances:
                                if hasattr(dock_instance, 'restore_from_occlusion'):
                                    dock_instance.restore_from_occlusion()
                        except ImportError:
                            pass
                    else:
                        # Bar is being hidden - force occlusion
                        notch.force_occlusion()
                        # Also force occlusion on docks on all monitors
                        try:
                            from modules.dock import Dock
                            for dock_instance in Dock._instances:
                                if hasattr(dock_instance, 'force_occlusion'):
                                    dock_instance.force_occlusion()
                        except ImportError:
                            pass
                    
                except Exception as e:
                    print(f"GlobalKeybindHandler: Error toggling bar: {e}")
                    return False
        
        return True


# Singleton accessor
_global_keybind_handler_instance = None

def get_global_keybind_handler() -> GlobalKeybindHandler:
    """Get the global GlobalKeybindHandler instance."""
    global _global_keybind_handler_instance
    if _global_keybind_handler_instance is None:
        _global_keybind_handler_instance = GlobalKeybindHandler()
    return _global_keybind_handler_instance

def init_global_keybind_objects():
    """Initialize global keybind handler with monitor manager."""
    try:
        from utils.monitor_manager import get_monitor_manager
        
        handler = get_global_keybind_handler()
        manager = get_monitor_manager()
        handler.set_monitor_manager(manager)
        
        return handler
    except ImportError as e:
        print(f"Error initializing global keybind objects: {e}")
        return None