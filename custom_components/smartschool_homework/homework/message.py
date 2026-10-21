"""Build the Homework report and the Results report messages (no AI: teachers' text is shown as-is)."""

from __future__ import annotations

from datetime import date
from itertools import groupby

from .fetch import next_school_day
from .results import FACES

NOTHING_AT_ALL = "Nothing due for the next school day, and nothing on the planner for the coming week."

MARKERS = {"test": "⚠️ TEST", "homework": "📝 Homework", "bring": "🎒 Bring", "other": "•"}
DONE, OPEN = "✅", "⬜"


def _day(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B}"


def _item_lines(item, show_day: bool = False) -> list[str]:
    details = [item.type_label]
    if show_day:
        details.append(f"{item.due:%A}")
    if item.due_time:
        details.append(item.due_time)
    box = DONE if item.done else OPEN
    lines = [f"{box} {MARKERS.get(item.type, '•')} · {item.subject} ({', '.join(details)})", f"   {item.title or '(no title)'}"]
    if item.description:
        lines.append(f"   {item.description}")
    return lines


def build_message(items, today: date) -> str:
    """Items due up to the next school day first (Sat/Sun/Fri evening -> Monday), then the rest of the week."""
    if not items:
        return NOTHING_AT_ALL

    target = next_school_day(today)
    due_next = [i for i in items if i.due <= target]
    later = [i for i in items if i.due > target]

    if due_next:
        lines = [f"📚 Due {_day(target)}", ""]
        for item in due_next:
            lines += _item_lines(item, show_day=item.due != target)  # e.g. something due on a Sunday
    else:
        lines = [f"📚 Nothing due {_day(target)}."]

    if later:
        lines += ["", "Coming up this week"]
        for day, day_items in groupby(later, key=lambda i: i.due):
            lines += ["", _day(day)]
            for item in day_items:
                lines += _item_lines(item)

    return "\n".join(lines)


def _score_line(result) -> str:
    face = FACES.get(result.colour or "", "•")
    score = f"{result.score} ({result.percentage}%)" if result.percentage is not None else result.score
    note = " (doesn't count)" if not result.counts else ""
    return f"{face} {result.subject} · {score}{note}"


def build_results_message(results) -> str:
    """The Results report: one block per new Result, oldest test first."""
    lines = ["🎓 New results"]
    for result in results:
        lines += ["", _score_line(result), f"   {result.name or '(no name)'}", f"   Taken {_day(result.taken)}"]
        lines += [f"   💬 {text}" for text in result.feedback]
    return "\n".join(lines)
