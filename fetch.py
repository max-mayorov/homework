"""Fetch upcoming homework/tests from Smartschool and normalize them into simple dataclasses.

Only the planner (PlannedElements) is used: the probe showed that, for a parent login,
FutureTasks and the agenda lessons come back empty while the planner has everything.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Brussels")
LOOKAHEAD_DAYS = 7

# Smartschool assignment types (school-configurable, usually Dutch) -> our coarse type.
TEST_TYPES = {"toets", "grote toets", "kleine toets", "test", "examen", "overhoring", "herhalingstoets", "proefwerk", "evaluatie"}
HOMEWORK_TYPES = {"taak", "opdracht", "les leren", "leren", "huiswerk", "oefeningen", "werk"}
BRING_TYPES = {"meebrengen"}


@dataclass(frozen=True)
class Item:
    subject: str
    title: str
    description: str | None
    due: date
    due_time: str | None  # "HH:MM" (Brussels time), None for whole-day items
    type: str  # "test" | "homework" | "bring" | "other"
    type_label: str  # the school's own name for the type, e.g. "Toets"


def classify(type_label: str) -> str:
    label = type_label.strip().lower()
    if label in TEST_TYPES:
        return "test"
    if label in HOMEWORK_TYPES:
        return "homework"
    if label in BRING_TYPES:
        return "bring"
    return "other"


def normalize_planned_element(raw: dict) -> Item:
    """Turn one planned element (as a plain dict, see `to_plain`) into an Item."""
    period = raw["period"]
    start = datetime.fromisoformat(str(period["date_time_from"]))
    if start.tzinfo is not None:
        start = start.astimezone(TZ)

    courses = [c["name"] for c in raw.get("courses") or [] if c.get("name")]
    type_label = ((raw.get("assignment_type") or {}).get("name") or "").strip()
    description = (raw.get("description") or "").strip() or None  # the planner list API has no description today

    return Item(
        subject=", ".join(courses) or "(no subject)",
        title=(raw.get("name") or "").strip(),
        description=description,
        due=start.date(),
        due_time=None if period.get("whole_day") else start.strftime("%H:%M"),
        type=classify(type_label),
        type_label=type_label or "(none)",
    )


def normalize_all(raws: list[dict], today: date) -> list[Item]:
    """Normalize and keep items due from tomorrow up to and including today + LOOKAHEAD_DAYS."""
    last = today + timedelta(days=LOOKAHEAD_DAYS)
    items = [normalize_planned_element(r) for r in raws]
    items = [i for i in items if today < i.due <= last]
    return sorted(items, key=lambda i: (i.due, i.due_time or "", i.subject, i.title))


def to_plain(obj):
    """Turn the library's (pydantic) dataclasses into plain dicts/lists, skipping the session."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj) if f.name != "session"}
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def fetch(settings: dict[str, str], today: date) -> list[Item]:
    from smartschool import PlannedElements, Smartschool

    from config import smartschool_credentials

    session = Smartschool(smartschool_credentials(settings))
    start = datetime.combine(today + timedelta(days=1), time.min, TZ)
    end = datetime.combine(today + timedelta(days=LOOKAHEAD_DAYS), time(23, 59, 59), TZ)

    raws = [to_plain(e) for e in PlannedElements(session, from_date=start, till_date=end)]
    items = normalize_all(raws, today)
    tomorrow = today + timedelta(days=1)
    log.info("Fetched %d planner element(s); %d in window, %d due tomorrow", len(raws), len(items), sum(i.due == tomorrow for i in items))
    return items
