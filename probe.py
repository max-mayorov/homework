"""Step 1 probe: log in with the parent credentials and dump raw Smartschool data for the next 7 days.

Usage:
    python probe.py                   # next 7 days from today
    python probe.py --date 2026-10-05 # pretend today is that date

The output contains your child's data. It goes to stdout only; nothing is logged or saved
(apart from the smartschool library's own session cookie cache in ~/.cache/smartschool/).
Check it yourself before sharing, and never share your .env or credentials.yml.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import traceback
from datetime import date, datetime, timedelta
from enum import Enum

from config import load_settings, smartschool_credentials

DAYS = 7


def to_plain(obj):
    """Turn the library's (pydantic) dataclasses into JSON-friendly data, skipping the session."""
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


def dump(obj) -> None:
    print(json.dumps(to_plain(obj), indent=2, ensure_ascii=False))


def header(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def section(title: str, fn) -> bool:
    header(title)
    try:
        fn()
        return True
    except Exception as exc:  # noqa: BLE001 - the whole point is to show the exact error
        print(f"ERROR: {type(exc).__name__}: {exc}")
        traceback.print_exc(file=sys.stdout)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="pretend today is YYYY-MM-DD")
    args = parser.parse_args()

    start: date = args.date
    end: date = start + timedelta(days=DAYS)
    print(f"Window: {start} .. {end} (inclusive)")

    from smartschool import FutureTasks, PlannedElements, Smartschool, SmartschoolLessons, SmartschoolMomentInfos

    session = Smartschool(smartschool_credentials(load_settings()))
    results: dict[str, bool] = {}

    # --- 1. Login + who are we? ---------------------------------------------------------
    def login():
        user = session.authenticated_user
        print("Login OK. authenticated_user as returned by Smartschool:")
        dump(user)
        print(f"\nplatform_id: {session.platform_id}")

    results["login"] = section("1. Login / authenticated user", login)
    if not results["login"]:
        print("\nLogin failed; not trying the data endpoints.")
        return 1

    # --- 2. FutureTasks -----------------------------------------------------------------
    def future_tasks():
        days = list(FutureTasks(session))
        in_window = [d for d in days if as_date(d.date) and start <= as_date(d.date) <= end]
        print(f"FutureTasks returned {len(days)} day(s); {len(in_window)} in the window.")
        if days and not in_window:
            print("Dates returned (all outside the window):", [str(d.date) for d in days])
        for day in in_window:
            dump(day)

    results["FutureTasks"] = section("2. FutureTasks (next 7 days)", future_tasks)

    # --- 3. PlannedElements -------------------------------------------------------------
    def planned_elements():
        from_dt = datetime.combine(start, datetime.min.time())
        till_dt = datetime.combine(end, datetime.max.time()).replace(microsecond=0)
        elements = list(PlannedElements(session, from_date=from_dt, till_date=till_dt))
        print(f"PlannedElements returned {len(elements)} element(s).")
        for element in elements:
            dump(element)

    results["PlannedElements"] = section("3. PlannedElements (next 7 days)", planned_elements)

    # --- 4. Agenda lessons (the library calls these SmartschoolLessons) -----------------
    lessons_in_window = []

    def lessons():
        all_lessons = list(SmartschoolLessons(session, timestamp_to_use=start))
        lessons_in_window.extend(l for l in all_lessons if as_date(l.date) and start <= as_date(l.date) <= end)
        print(f"SmartschoolLessons returned {len(all_lessons)} lesson(s); {len(lessons_in_window)} in the window.")
        for lesson in lessons_in_window:
            dump(lesson)

    results["SmartschoolLessons"] = section("4. Agenda lessons / SmartschoolLessons (next 7 days)", lessons)

    # --- 5. Moment info for lessons that have something attached -------------------------
    def moment_infos():
        flagged = [
            l
            for l in lessons_in_window
            if any(str(getattr(l, a, "") or "0") not in ("0", "") for a in ("assignment_end_status", "test_deadline_status", "both_start_status"))
            or l.subject
        ]
        print(f"{len(flagged)} lesson(s) in the window have a subject or an assignment/test flag. Showing up to 10.")
        for lesson in flagged[:10]:
            print(f"\n-- momentID {lesson.moment_id} ({lesson.date}, hour {lesson.hour})")
            for info in SmartschoolMomentInfos(session, moment_id=lesson.moment_id):
                dump(info)

    results["SmartschoolMomentInfos"] = section("5. Agenda moment info / SmartschoolMomentInfos", moment_infos)

    header("Summary")
    for name, ok in results.items():
        print(f"  {name:24s} {'OK' if ok else 'FAILED'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
