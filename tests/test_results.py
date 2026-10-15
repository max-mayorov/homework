import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fetch import TZ
from results import Result, load_last_run, new_results, normalize_result, save_last_run, window_start

RAWS = json.loads((Path(__file__).parent / "fixtures" / "results.json").read_text(encoding="utf8"))
NOW = datetime(2026, 10, 15, 16, 5, tzinfo=TZ)


def test_normalize_percentage_result():
    assert normalize_result(RAWS[1]) == Result(
        subject="Frans",
        name="Test Verbes colonne 2",
        score="4/10",
        percentage=40,
        colour="red",
        taken=date(2026, 10, 2),
        published=datetime(2026, 10, 12, 9, 47, 2, tzinfo=TZ),
        feedback=("Au travail! Herhaal de werkwoorden.",),
        counts=True,
    )


def test_normalize_text_result_and_not_counting():
    text = normalize_result(RAWS[5])
    assert (text.score, text.percentage, text.colour) == ("Goed", None, "steel")
    assert normalize_result(RAWS[2]).counts is False


def test_deleted_and_unpublished_results_are_skipped():
    assert normalize_result(RAWS[4]) is None
    assert normalize_result(dict(RAWS[0], is_published=False)) is None


def test_window_starts_at_last_run_but_at_most_14_days_back():
    assert window_start(None, NOW) == NOW - timedelta(days=14)
    yesterday = NOW - timedelta(days=1)
    assert window_start(yesterday, NOW) == yesterday
    assert window_start(NOW - timedelta(days=30), NOW) == NOW - timedelta(days=14)


def test_new_results_are_in_the_window_and_sorted_by_date_taken():
    since = datetime(2026, 10, 8, 7, 51, 20, tzinfo=TZ)  # exactly the Nederlands publication: not new
    names = [r.name for r in new_results(RAWS, since, NOW)]
    assert names == ["Test Verbes colonne 2", "Test hoofdstuk 1", "Presentatie"]


def test_results_published_after_now_wait_for_the_next_run():
    at_publication = datetime(2026, 10, 13, 16, 0, tzinfo=TZ)
    names = [r.name for r in new_results(RAWS, at_publication - timedelta(hours=1), at_publication)]
    assert names == ["Test hoofdstuk 1"]  # published exactly at `now` counts
    assert new_results(RAWS, at_publication, at_publication + timedelta(minutes=5)) == []


def test_last_run_round_trip(tmp_path):
    path = tmp_path / "last_results_run.txt"
    assert load_last_run(path) is None
    save_last_run(NOW, path)
    assert load_last_run(path) == NOW
    path.write_text("garbage", encoding="utf8")
    assert load_last_run(path) is None
