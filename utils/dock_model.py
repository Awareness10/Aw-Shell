"""Which buttons the dock shows, without widgets: running windows grouped by
app, matched to the pinned apps, and the unpinned apps that are open.

Toolkit-free, so it can be tested without GTK (tests/test_dock_model.py).
"""

from utils.apps import normalize_window_class


def app_entry(app) -> dict:
    """A desktop app as the dock stores it (dock.json "pinned_apps")."""
    return {
        "name": app.name,
        "display_name": app.display_name,
        "window_class": app.window_class,
        "executable": app.executable,
        "command_line": app.command_line,
    }


def window_id(client: dict) -> str:
    """A window's app key: its initial class, its class, or the part of its
    title before " - "."""
    if class_name := client.get("initialClass", "").lower():
        return class_name
    if class_name := client.get("class", "").lower():
        return class_name
    if title := client.get("title", "").lower():
        possible_name = title.split(" - ")[0].strip()
        return possible_name if possible_name and len(possible_name) > 1 else title
    return "unknown-app"


def group_windows(clients) -> dict[str, list]:
    """Windows per app key; a key with a packaging suffix (.bin, -gtk...)
    also files its windows under the normalized key."""
    running: dict[str, list] = {}
    for client in clients:
        key = window_id(client)
        running.setdefault(key, []).append(client)
        normalized = normalize_window_class(key)
        if normalized != key:
            running.setdefault(normalized, []).extend(running[key])
    return running


def pinned_identifiers(item, app) -> list[str]:
    """Names a pinned app's windows may go by: its stored fields, then its
    desktop entry's (each once, first occurrence first)."""
    names = []
    if isinstance(item, dict):
        for key in ("window_class", "executable", "command_line", "name", "display_name"):
            if item.get(key):
                names.append(item[key].lower())
    elif isinstance(item, str):
        names.append(item.lower())
    if app:
        if app.window_class:
            names.append(app.window_class.lower())
        if app.executable:
            names.append(app.executable.split("/")[-1].lower())
        if app.command_line:
            parts = app.command_line.split()
            if parts:
                names.append(parts[0].split("/")[-1].lower())
        if app.name:
            names.append(app.name.lower())
        if app.display_name:
            names.append(app.display_name.lower())
    return list(dict.fromkeys(names))


def match_running(identifiers, running: dict) -> str | None:
    """The running app key for the first identifier that matches exactly,
    normalized, or (3+ characters) as part of a key."""
    for identifier in identifiers:
        if identifier in running:
            return identifier
        normalized = normalize_window_class(identifier)
        if normalized in running:
            return normalized
        for key in running:
            if len(identifier) >= 3 and identifier in key:
                return key
    return None


def plan_dock(pinned, clients, find_app, find_app_by_key, identifier_map):
    """(pinned, open): pinned is [(pinned item, its windows)] in pinned order;
    open is [(app entry or key, windows)] for running apps not pinned."""
    running = group_windows(clients)
    used = set()
    pinned_plan = []
    for item in pinned:
        matched = match_running(pinned_identifiers(item, find_app(item)), running)
        if matched:
            used.add(matched)
            used.add(normalize_window_class(matched))
        pinned_plan.append((item, running[matched] if matched else []))

    open_plan = []
    for key, windows in running.items():
        if key in used:
            continue
        app = identifier_map.get(key) or identifier_map.get(normalize_window_class(key))
        if not app:
            app = find_app_by_key(key)
        if not app and windows and windows[0].get("title"):
            name = windows[0].get("title", "").split(" - ")[0].strip()
            if len(name) > 2:
                app = find_app_by_key(name)
        open_plan.append((app_entry(app) if app else key, windows))
    return pinned_plan, open_plan
