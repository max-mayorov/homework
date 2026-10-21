from datetime import date

from homework.fetch import Item, next_school_day
from homework.message import NOTHING_AT_ALL, build_message

TUESDAY = date(2026, 9, 29)
SATURDAY = date(2026, 10, 3)
SUNDAY = date(2026, 10, 4)
MONDAY = date(2026, 10, 5)


def _item(due, title, type_="homework", label="Taak", time="08:15", description=None, done=False):
    return Item(subject="Wiskunde", title=title, description=description, due=due, due_time=time, type=type_, type_label=label, done=done)


def test_next_school_day():
    assert next_school_day(TUESDAY) == date(2026, 9, 30)
    assert next_school_day(date(2026, 10, 1)) == date(2026, 10, 2)  # Thursday -> Friday
    assert next_school_day(date(2026, 10, 2)) == MONDAY  # Friday
    assert next_school_day(SATURDAY) == MONDAY
    assert next_school_day(SUNDAY) == MONDAY


def test_nothing_at_all():
    assert build_message([], TUESDAY) == NOTHING_AT_ALL


def test_tomorrow_then_week_grouped_by_day():
    items = [
        _item(date(2026, 9, 30), "Oefeningen p 12"),
        _item(date(2026, 10, 2), "Toets H 1.3", "test", "Toets", "09:05"),
        _item(date(2026, 10, 2), "Passer", "bring", "Meebrengen", None),
    ]
    msg = build_message(items, TUESDAY)
    assert msg.startswith("📚 Due Wednesday 30 September")
    assert msg.index("Oefeningen p 12") < msg.index("Coming up this week") < msg.index("Friday 2 October")
    assert "⬜ ⚠️ TEST · Wiskunde (Toets, 09:05)" in msg
    assert "⬜ 🎒 Bring · Wiskunde (Meebrengen)" in msg
    assert msg.count("Friday 2 October") == 1


def test_saturday_and_sunday_report_monday():
    items = [_item(MONDAY, "Maandagtaak"), _item(date(2026, 10, 6), "Dinsdagtaak")]
    for today in (SATURDAY, SUNDAY):
        msg = build_message(items, today)
        assert msg.startswith("📚 Due Monday 5 October")
        assert msg.index("Maandagtaak") < msg.index("Coming up this week") < msg.index("Dinsdagtaak")


def test_weekend_item_before_monday_is_shown_with_its_day():
    msg = build_message([_item(SUNDAY, "Zondag inleveren", time=None), _item(MONDAY, "Maandagtaak")], SATURDAY)
    assert "⬜ 📝 Homework · Wiskunde (Taak, Sunday)" in msg
    assert "Coming up this week" not in msg


def test_nothing_due_next_school_day_is_one_line():
    msg = build_message([_item(date(2026, 10, 1), "Later")], TUESDAY)
    assert msg.splitlines()[0] == "📚 Nothing due Wednesday 30 September."
    assert "Coming up this week" in msg


def test_done_items_are_kept_and_checked():
    msg = build_message([_item(date(2026, 9, 30), "Klaar", done=True), _item(date(2026, 9, 30), "Nog doen")], TUESDAY)
    assert "✅ 📝 Homework · Wiskunde (Taak, 08:15)\n   Klaar" in msg
    assert "⬜ 📝 Homework · Wiskunde (Taak, 08:15)\n   Nog doen" in msg


def test_description_shown_only_when_present():
    msg = build_message([_item(date(2026, 9, 30), "Taak", description="Rekenmachine meebrengen")], TUESDAY)
    assert "Rekenmachine meebrengen" in msg


def test_results_message():
    import json
    from pathlib import Path

    from homework.message import build_results_message
    from homework.results import normalize_result

    raws = json.loads((Path(__file__).parent / "fixtures" / "results.json").read_text(encoding="utf8"))
    results = [normalize_result(raws[i]) for i in (2, 1, 5)]
    assert build_results_message(results) == "\n".join(
        [
            "🎓 New results",
            "",
            "🙂 Nederlands · 14,5/20 (73%) (doesn't count)",
            "   Spelling werkwoorden",
            "   Taken Thursday 1 October",
            "",
            "😞 Frans · 4/10 (40%)",
            "   Test Verbes colonne 2",
            "   Taken Friday 2 October",
            "   💬 Au travail! Herhaal de werkwoorden.",
            "",
            "• Engels · Goed",
            "   Presentatie",
            "   Taken Wednesday 7 October",
        ]
    )
