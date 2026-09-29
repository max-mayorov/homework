"""Build the evening message from the normalized items (no AI: teacher's text is shown as-is)."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import groupby

NOTHING_AT_ALL = "Nothing due tomorrow, and nothing on the planner for the coming week."

MARKERS = {"test": "⚠️ TEST", "homework": "📝 Homework", "bring": "🎒 Bring", "other": "•"}


def _day(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B}"


def _item_lines(item) -> list[str]:
    when = f", {item.due_time}" if item.due_time else ""
    lines = [f"{MARKERS.get(item.type, '•')} · {item.subject} ({item.type_label}{when})", f"   {item.title or '(no title)'}"]
    if item.description:
        lines.append(f"   {item.description}")
    return lines


def build_message(items, today: date) -> str:
    if not items:
        return NOTHING_AT_ALL

    tomorrow = today + timedelta(days=1)
    due_tomorrow = [i for i in items if i.due == tomorrow]
    later = [i for i in items if i.due > tomorrow]

    if due_tomorrow:
        lines = [f"📚 Due tomorrow, {_day(tomorrow)}", ""]
        for item in due_tomorrow:
            lines += _item_lines(item)
    else:
        lines = [f"📚 Nothing due tomorrow, {_day(tomorrow)}."]

    if later:
        lines += ["", "Coming up this week"]
        for day, day_items in groupby(later, key=lambda i: i.due):
            lines += ["", _day(day)]
            for item in day_items:
                lines += _item_lines(item)

    return "\n".join(lines)
