import os
import sys
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

#from fabric import Application
import glaze
from glaze import generate_theme


def _init_theme_from_wallpaper():
    """Initialize glaze theme from current wallpaper using matugen."""
    wallpaper_path = Path.home() / ".current.wall"

    if wallpaper_path.exists():
        try:
            new_theme, backend = generate_theme(image_path=str(wallpaper_path))
            # Must update both: package namespace AND theme module's global
            # (get_current_theme() reads from theme module's globals)
            glaze.theme = new_theme
            # Access the actual module via sys.modules to set its global
            sys.modules['glaze.theme'].theme = new_theme # type: ignore
            print(f"Loaded theme from wallpaper using {backend}")
        except Exception as e:
            print(f"Warning: Could not generate theme from wallpaper: {e}")
    else:
        print("Warning: No wallpaper found at ~/.current.wall, using default theme")


def _configure_sys_path_for_direct_execution():
    """
    Ajusta sys.path si este script se ejecuta directamente,
    para asegurar que las importaciones relativas dentro del paquete 'config' funcionen.
    Esto permite ejecutar `python config/config.py` desde cualquier directorio.
    """
    if __name__ == "__main__":
        current_file_dir = Path(__file__).resolve().parent
        project_root = current_file_dir.parent

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

_configure_sys_path_for_direct_execution()

if __name__ == "__main__" and not __package__:
    from config.settings_constants import APP_NAME
    from config.settings_gui import AwShellSettings # AwShellSettings
    from config.settings_utils import load_bind_vars
else:
    from .settings_constants import APP_NAME
    from .settings_gui import AwShellSettings
    from .settings_utils import load_bind_vars


def open_config():
    """
    Entry point for opening the configuration GUI using Fabric Application.
    """
    load_bind_vars()
    _init_theme_from_wallpaper()

    #show_lock_checkbox = True
    dest_lock = Path.home() / ".config/hypr/hyprlock.conf"
    src_lock = Path.home() / f".config/{APP_NAME}/config/hypr/hyprlock.conf"
    if not dest_lock.exists() and src_lock.exists():
        try:
            os.makedirs(os.path.dirname(dest_lock), exist_ok=True)
            shutil.copy(src_lock, dest_lock)
            #show_lock_checkbox = False 
            print(f"Copied default hyprlock config to {dest_lock}")
        except Exception as e:
            print(f"Error copying default hyprlock config: {e}")
            #show_lock_checkbox = os.path.exists(src_lock)

    #show_idle_checkbox = True
    dest_idle = Path.home() / ".config/hypr/hypridle.conf"
    src_idle = Path.home() / f".config/{APP_NAME}/config/hypr/hypridle.conf"
    if not os.path.exists(dest_idle) and os.path.exists(src_idle):
        try:
            os.makedirs(os.path.dirname(dest_idle), exist_ok=True)
            shutil.copy(src_idle, dest_idle)
            #show_idle_checkbox = False
            print(f"Copied default hypridle config to {dest_idle}")
        except Exception as e:
            print(f"Error copying default hypridle config: {e}")
            #show_idle_checkbox = os.path.exists(src_idle)

    app = QApplication(sys.argv)
    win = AwShellSettings()
    win.show()
    sys.exit(app.exec())

    
if __name__ == "__main__":
    open_config()
