"""Match windows to desktop applications (shared by the dock and the notch).

Apps are fabric DesktopApp objects; only their name, display_name,
window_class, executable and command_line attributes are used.
"""

_IDENTIFIER_FIELDS = ("name", "display_name", "window_class", "executable", "command_line")
_CLASS_SUFFIXES = (".bin", ".exe", ".so", "-bin", "-gtk")


def _basename(path: str) -> str:
    return path.split("/")[-1]


def build_identifier_map(apps) -> dict:
    """Lowercased name, display name, window class, executable basename and
    command basename -> app. Later apps win on collisions."""
    identifiers = {}
    for app in apps:
        if app.name:
            identifiers[app.name.lower()] = app
        if app.display_name:
            identifiers[app.display_name.lower()] = app
        if app.window_class:
            identifiers[app.window_class.lower()] = app
        if app.executable:
            identifiers[_basename(app.executable).lower()] = app
        if app.command_line and app.command_line.split():
            identifiers[_basename(app.command_line.split()[0]).lower()] = app
    return identifiers


def normalize_window_class(class_name: str | None) -> str:
    """Lowercase, without packaging suffixes like `.bin` or `-gtk`."""
    if not class_name:
        return ""
    normalized = class_name.lower()
    for suffix in _CLASS_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized


def find_app_by_key(key, identifiers: dict, apps):
    """Exact identifier match first, then the first app with any field
    containing the key."""
    if not key:
        return None
    needle = str(key).lower()
    if needle in identifiers:
        return identifiers[needle]
    for app in apps:
        for field in _IDENTIFIER_FIELDS:
            value = getattr(app, field)
            if value and needle in value.lower():
                return app
    return None


def find_app(identifier, identifiers: dict, apps):
    """Find an app by a string, or by a pinned-app dict tried field by field
    (window class first)."""
    if not identifier:
        return None
    if isinstance(identifier, dict):
        for field in ("window_class", "executable", "command_line", "name", "display_name"):
            if identifier.get(field):
                app = find_app_by_key(identifier[field], identifiers, apps)
                if app:
                    return app
        return None
    return find_app_by_key(identifier, identifiers, apps)
