import json
from datetime import date

from explain import NOTHING_AT_ALL, build_user_message, explain
from fetch import Item

TODAY = date(2026, 9, 29)


def _item(due, title, type_="homework"):
    return Item(subject="Wiskunde", title=title, description=None, due=due, due_time="08:15", type=type_, type_label="Taak")


def test_prompt_splits_tomorrow_from_later():
    items = [_item(date(2026, 9, 30), "A"), _item(date(2026, 10, 2), "B", "test")]
    payload = json.loads(build_user_message(items, TODAY).split("\n", 1)[1])
    assert payload["tomorrow"] == "Wednesday 2026-09-30"
    assert [i["title"] for i in payload["due_tomorrow"]] == ["A"]
    assert [i["title"] for i in payload["later_this_week"]] == ["B"]
    assert payload["later_this_week"][0]["type"] == "test"
    assert payload["due_tomorrow"][0]["description"] is None


def test_no_items_needs_no_api_call():
    assert explain([], TODAY, settings={}) == NOTHING_AT_ALL
