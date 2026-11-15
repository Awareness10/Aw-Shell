"""The notification history's data, without widgets: the history file, date
headers and which cached images are orphans. modules/notifications.py draws it.

The file is a JSON list of notes, newest first:
{"id", "app_icon", "summary", "body", "app_name", "timestamp" (ISO), "cached_image_path"}
"""

import json
import locale
import os
from datetime import datetime, timedelta

from loguru import logger

HISTORY_LIMIT = 50
IMAGE_PREFIX, IMAGE_SUFFIX = "notification_", ".png"


def ordinal(n: int) -> str:
    """The English ordinal suffix: 1st, 2nd, 3rd, 4th, 11th, 21st..."""
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def date_header(dt: datetime, now: datetime | None = None) -> str:
    """"Today", "Yesterday", "October 3rd", or "October 3rd, 2025" in an
    earlier year. Month names are English whatever the system locale."""
    now = now or datetime.now()
    today = now.date()
    if dt.date() == today:
        return "Today"
    if dt.date() == today - timedelta(days=1):
        return "Yesterday"
    original = locale.getlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, ("en_US", "UTF-8"))
    except locale.Error:
        locale.setlocale(locale.LC_TIME, "C")
    try:
        text = f"{dt.strftime('%B')} {dt.day}{ordinal(dt.day)}"
    finally:
        locale.setlocale(locale.LC_TIME, original)
    return text if dt.year == now.year else f"{text}, {dt.year}"


def image_file_name(note_id: str) -> str:
    return f"{IMAGE_PREFIX}{note_id}{IMAGE_SUFFIX}"


def orphan_images(file_names, note_ids) -> list[str]:
    """Cached image files (notification_<id>.png) whose note isn't in the
    history any more; other files are left alone."""
    keep = {str(i) for i in note_ids if i}
    return [
        name for name in file_names
        if name.startswith(IMAGE_PREFIX) and name.endswith(IMAGE_SUFFIX)
        and name[len(IMAGE_PREFIX):-len(IMAGE_SUFFIX)] not in keep
    ]


def parse_timestamp(text) -> datetime:
    """A note's arrival time; now when it's missing or unreadable."""
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return datetime.now()


class HistoryStore:
    """The history file's notes, newest first, at most HISTORY_LIMIT."""

    def __init__(self, path: str):
        self.path = path
        self.notes: list[dict] = []

    def load(self) -> list[dict]:
        """Read the file; a missing or broken file is an empty history."""
        self.notes = []
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    notes = json.load(f)
                if isinstance(notes, list):
                    self.notes = notes
            except (OSError, ValueError) as e:
                logger.error(f"Error loading persistent history: {e}")
        return self.notes

    def save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self.notes, f)
        except OSError as e:
            logger.error(f"Error saving persistent history: {e}")

    def add(self, note: dict) -> None:
        self.notes = [note, *self.notes][:HISTORY_LIMIT]
        self.save()

    def remove(self, note_ids) -> bool:
        """Drop the notes with these ids (compared as text); True if any went."""
        ids = {str(i) for i in note_ids}
        kept = [n for n in self.notes if str(n.get("id")) not in ids]
        removed = len(kept) != len(self.notes)
        self.notes = kept
        self.save()
        return removed

    def clear(self) -> None:
        self.notes = []
        if os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError as e:
                logger.error(f"Error deleting persistent history file: {e}")
