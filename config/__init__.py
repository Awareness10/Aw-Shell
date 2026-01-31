"""
Aw-Shell configuration package.
"""
# Import only specific names actually defined in data.py
# This prevents circular imports by not importing everything
from .settings_constants import APP_NAME, APP_NAME_CAP
from .data import CACHE_DIR, CONFIG_FILE
