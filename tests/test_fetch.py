import json
from datetime import date
from pathlib import Path

from homework.fetch import Item, classify, normalize_all, normalize_planned_element

RAWS = json.loads((Path(__file__).parent / "fixtures" / "planned_elements.json").read_text(encoding="utf8"))
TODAY = date(2026, 9, 29)


def test_normalize_single_element():
    item = normalize_planned_element(RAWS[1])
    assert item == Item(
        subject="Wiskunde",
        title="Toets H 1.3",
        description=None,
        due=date(2026, 10, 2),
        due_time="09:05",
        type="test",
        type_label="Toets",
        done=False,
    )


def test_types_are_classified():
    by_title = {i.title: i.type for i in normalize_all(RAWS, TODAY)}
    assert by_title["Toets H 1.3"] == "test"
    assert by_title["Toets: hoofdstuk 2 t.e.m. p. 40"] == "test"  # "Grote toets"
    assert by_title["H3: vergelijkingen oefenen"] == "bring"  # "Meebrengen"
    assert by_title["à étudier: les verbes p20-22"] == "homework"  # "Les leren"
    assert by_title["Kaartoefening p 24, meebrengen: passer"] == "homework"  # "Opdracht"
    assert by_title["Sportdag"] == "other"


def test_classify_is_case_insensitive_and_defaults_to_other():
    assert classify(" TOETS ") == "test"
    assert classify("Something new") == "other"
    assert classify("") == "other"


def test_element_without_course_or_type():
    item = normalize_planned_element(RAWS[6])
    assert item.subject == "(no subject)"
    assert item.type_label == "(none)"
    assert item.due_time is None  # whole day


def test_window_is_tomorrow_to_seven_days_and_sorted():
    items = normalize_all(RAWS, TODAY)
    assert [i.due for i in items] == sorted(i.due for i in items)
    assert all(date(2026, 9, 30) <= i.due <= date(2026, 10, 6) for i in items)
    assert "Too far away" not in {i.title for i in items}  # 2026-10-09
    # Same day ordered by time
    tomorrow = [i.due_time for i in items if i.due == date(2026, 9, 30)]
    assert tomorrow == ["08:15", "11:05"]


def test_items_due_today_are_excluded():
    items = normalize_all(RAWS, date(2026, 9, 30))
    assert date(2026, 9, 30) not in {i.due for i in items}


def test_due_date_uses_brussels_time():
    raw = dict(RAWS[1], period={"date_time_from": "2026-10-01T23:30:00+00:00", "whole_day": False})
    item = normalize_planned_element(raw)
    assert item.due == date(2026, 10, 2)
    assert item.due_time == "01:30"


def test_description_is_kept_when_present():
    item = normalize_planned_element(dict(RAWS[0], description="  Bring a calculator  "))
    assert item.description == "Bring a calculator"


def test_done_flag_from_resolved_status():
    by_title = {i.title: i.done for i in normalize_all(RAWS, TODAY)}
    assert by_title["H3: vergelijkingen oefenen"] is True  # "resolved"
    assert by_title["Toets H 1.3"] is False  # "unresolved"
    assert by_title["Sportdag"] is False  # ""
