from datetime import date

from fetch import Item
from message import NOTHING_AT_ALL, build_message

TODAY = date(2026, 9, 29)  # a Tuesday


def _item(due, title, type_="homework", label="Taak", time="08:15", description=None):
    return Item(subject="Wiskunde", title=title, description=description, due=due, due_time=time, type=type_, type_label=label)


def test_nothing_at_all():
    assert build_message([], TODAY) == NOTHING_AT_ALL


def test_tomorrow_then_week_grouped_by_day():
    items = [
        _item(date(2026, 9, 30), "Oefeningen p 12"),
        _item(date(2026, 10, 2), "Toets H 1.3", "test", "Toets", "09:05"),
        _item(date(2026, 10, 2), "Passer", "bring", "Meebrengen", None),
    ]
    msg = build_message(items, TODAY)
    assert msg.startswith("📚 Due tomorrow, Wednesday 30 September")
    assert msg.index("Oefeningen p 12") < msg.index("Coming up this week") < msg.index("Friday 2 October")
    assert "⚠️ TEST · Wiskunde (Toets, 09:05)" in msg
    assert "🎒 Bring · Wiskunde (Meebrengen)" in msg
    assert msg.count("Friday 2 October") == 1


def test_nothing_tomorrow_is_one_line():
    msg = build_message([_item(date(2026, 10, 1), "Later")], TODAY)
    assert msg.splitlines()[0] == "📚 Nothing due tomorrow, Wednesday 30 September."
    assert "Coming up this week" in msg


def test_description_shown_only_when_present():
    msg = build_message([_item(date(2026, 9, 30), "Taak", description="Rekenmachine meebrengen")], TODAY)
    assert "Rekenmachine meebrengen" in msg
