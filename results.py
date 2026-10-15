"""Fetch Results (Smartschool "Resultaten") and pick the new ones for the Results report.

A Result is new when its publication time is after the previous Results report was delivered,
and no more than NEW_RESULTS_MAX_DAYS ago. The time of the last delivered report is kept in
LAST_RUN_FILE next to the code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from fetch import TZ, to_plain

log = logging.getLogger(__name__)

NEW_RESULTS_MAX_DAYS = 14
LAST_RUN_FILE = Path(__file__).resolve().parent / "last_results_run.txt"

# Smartschool's score colour, worst to best, as a smiley. Colours Smartschool has but we haven't
# seen used ("steel", "grass") get no face rather than a guessed one.
FACES = {"red": "😞", "yellow": "😐", "green": "🙂", "olive": "😄"}


@dataclass(frozen=True)
class Result:
    subject: str
    name: str
    score: str  # "14,5/20", or the school's text/symbol for non-numeric results
    percentage: int | None  # as Smartschool computes it; None for non-numeric results
    colour: str | None  # Smartschool's score colour: "red" | "yellow" | "green" | "olive" | ...
    taken: date  # the day of the test or assignment
    published: datetime  # when it became visible (Brussels time)
    feedback: tuple[str, ...] = ()
    counts: bool = True  # False when it doesn't count towards the grade


def _brussels(value) -> datetime:
    dt = datetime.fromisoformat(str(value))
    return dt.astimezone(TZ) if dt.tzinfo else dt.replace(tzinfo=TZ)


def normalize_result(raw: dict) -> Result | None:
    """Turn one evaluation (as a plain dict, see `fetch.to_plain`) into a Result; None if it isn't visible."""
    if raw.get("deleted") or not raw.get("is_published", True):
        return None
    graphic = raw.get("graphic") or {}
    if graphic.get("type") == "percentage":
        score, percentage = str(graphic.get("description") or "").strip(), graphic.get("value")
    else:
        score, percentage = str(graphic.get("value") or graphic.get("description") or "").strip(), None
    courses = [c["name"] for c in raw.get("courses") or [] if c.get("name")]
    feedback = tuple(t for f in raw.get("feedback") or [] if (t := (f.get("text") or "").strip()))
    return Result(
        subject=", ".join(courses) or "(no subject)",
        name=(raw.get("name") or "").strip(),
        score=score or "(no score)",
        percentage=percentage,
        colour=graphic.get("color"),
        taken=_brussels(raw["date"]).date(),
        published=_brussels(raw["availability_date"]),
        feedback=feedback,
        counts=bool(raw.get("does_count", True)),
    )


def window_start(last_run: datetime | None, now: datetime) -> datetime:
    """Start of the Results report window: the last delivered report, but never more than NEW_RESULTS_MAX_DAYS ago."""
    oldest = now - timedelta(days=NEW_RESULTS_MAX_DAYS)
    return oldest if last_run is None else max(last_run, oldest)


def new_results(raws: list[dict], since: datetime, now: datetime) -> list[Result]:
    """Results published after `since` and up to `now`, oldest test first."""
    results = [r for r in map(normalize_result, raws) if r and since < r.published <= now]
    return sorted(results, key=lambda r: (r.taken, r.subject, r.name))


def load_last_run(path: Path | None = None) -> datetime | None:
    try:
        return _brussels((path or LAST_RUN_FILE).read_text(encoding="utf8").strip())
    except (FileNotFoundError, ValueError):
        return None


def save_last_run(when: datetime, path: Path | None = None) -> None:
    (path or LAST_RUN_FILE).write_text(when.isoformat() + "\n", encoding="utf8")


def fetch_results(settings: dict[str, str], since: datetime, now: datetime) -> list[Result]:
    from smartschool import Results, Smartschool

    from config import smartschool_credentials

    session = Smartschool(smartschool_credentials(settings))
    # "details" would make the library fetch each Result again (class averages), which also
    # fails to parse for some schools; we don't use it.
    raws = [to_plain(r, skip=("session", "details")) for r in Results(session)]
    results = new_results(raws, since, now)
    log.info("Fetched %d result(s); %d new since %s", len(raws), len(results), f"{since:%Y-%m-%d %H:%M}")
    return results
