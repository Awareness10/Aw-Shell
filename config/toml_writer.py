"""TOML output for the matugen config (Python only ships a TOML reader).

Writes back anything tomllib reads, so a user's own keys survive the merge:
tables, arrays of tables, strings, booleans, numbers, dates and arrays.
"""

import datetime
import math
import re

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n",
            "\f": "\\f", "\r": "\\r"}


def _string(text: str) -> str:
    out = []
    for char in text:
        if char in _ESCAPES:
            out.append(_ESCAPES[char])
        elif char < " " or char == "\x7f":
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else _string(key)


def _value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"Can't write {type(value).__name__} to TOML")


def _is_table_array(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _table(table: dict, path: list[str], lines: list[str], header: str | None) -> None:
    """Append table's keys to lines: its plain values under header, then its
    sub-tables and arrays of tables, each under its own header."""
    plain = {k: v for k, v in table.items()
             if not isinstance(v, dict) and not _is_table_array(v)}
    nested = [k for k in table if k not in plain]
    if header is not None and (plain or not nested):  # an empty table still needs its header
        if lines:
            lines.append("")
        lines.append(header)
    lines.extend(f"{_key(k)} = {_value(v)}" for k, v in plain.items())
    for key in nested:
        sub_path = path + [_key(key)]
        dotted = ".".join(sub_path)
        if isinstance(table[key], dict):
            _table(table[key], sub_path, lines, f"[{dotted}]")
        else:
            for item in table[key]:
                if lines:
                    lines.append("")
                lines.append(f"[[{dotted}]]")
                _table(item, sub_path, lines, None)


def dumps(data: dict) -> str:
    """data as a TOML document."""
    lines: list[str] = []
    _table(data, [], lines, None)
    return "\n".join(lines) + "\n" if lines else ""
