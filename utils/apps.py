"""Desktop-app helpers: match windows to apps (dock, notch) and rank launcher
search results.

Apps are fabric DesktopApp objects; only their name, display_name,
generic_name, window_class, executable and command_line attributes are used.
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


def command_name(command_line: str | None) -> str:
    """Base command of a desktop entry's Exec line, without path or arguments;
    empty for `/bin/sh -c` wrappers, whose command says nothing about the app."""
    if not command_line or command_line.startswith("/bin/sh -c"):
        return ""
    parts = command_line.split()
    return _basename(parts[0]) if parts else ""


def fuzzy_match(query: str, text: str) -> bool:
    """All characters of query appear in text, in order."""
    it = iter(text)
    return all(c in it for c in query)


def score_app(app, query: str) -> int:
    """Launcher relevance of app for query; 0 means no match. Shorter names
    rank higher within a tier."""
    q = query.casefold()
    name = (app.display_name or "").casefold()
    app_name = (app.name or "").casefold()
    generic = (app.generic_name or "").casefold()
    exe = (app.executable or "").casefold()
    cmd = command_name(app.command_line).casefold()

    if name == q:
        return 10000
    if q in (app_name, exe, cmd):
        return 9000
    if name.startswith(q):
        return 8000 - len(name)
    if app_name.startswith(q) or exe.startswith(q) or cmd.startswith(q):
        return 7000 - len(name)
    for i, word in enumerate(name.split()):
        if word.startswith(q):
            return 6000 - (i * 100) - len(name)
    for word in app_name.replace("-", " ").replace(".", " ").split():
        if word.startswith(q):
            return 5000 - len(name)
    if q in name:
        return 4000 - name.find(q) - len(name)
    if q in f"{app_name} {generic} {exe} {cmd}":
        return 3000 - len(name)
    if fuzzy_match(q, name):
        return 1000
    return 0


def rank_apps(apps, query: str) -> list:
    """Apps matching query, best first, ties by display name. An empty query
    keeps every app, sorted by display name."""
    scored = [(score_app(app, query) if query else 1, app) for app in apps]
    scored = [(score, app) for score, app in scored if score > 0]
    scored.sort(key=lambda x: (-x[0], (x[1].display_name or "").casefold()))
    return [app for _, app in scored]
