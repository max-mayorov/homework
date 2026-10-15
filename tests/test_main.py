import pytest

from main import error_message, redact

SETTINGS = {"SMARTSCHOOL_PASSWORD": "hunter22", "TELEGRAM_BOT_TOKEN": "123:ABCsecret", "SMARTSCHOOL_MFA": "2012-01-31"}


def test_redact_hides_secret_values():
    text = "failed https://api.telegram.org/bot123:ABCsecret/sendMessage with hunter22 and 2012-01-31"
    out = redact(text, SETTINGS)
    assert "hunter22" not in out and "ABCsecret" not in out and "2012-01-31" not in out


def test_error_message_is_short_and_redacted():
    msg = error_message("fetching from Smartschool", RuntimeError("bad password hunter22 " + "z" * 1000), SETTINGS)
    assert msg.startswith("⚠️ Homework check failed while fetching from Smartschool.")
    assert "hunter22" not in msg
    assert len(msg) < 400


def test_printer_failure_does_not_stop_telegram(monkeypatch):
    from argparse import Namespace
    from datetime import date

    import fetch
    import main
    import notify
    import printer

    sent = []
    monkeypatch.setattr(fetch, "fetch", lambda settings, today: [])
    monkeypatch.setattr(notify, "send", lambda settings, text: sent.append(text))

    def broken_printer(address, img):
        raise printer.PrinterError("Could not print to 10.0.0.9:9100 (TimeoutError: timed out)")

    monkeypatch.setattr(printer, "print_image", broken_printer)
    settings = dict(SETTINGS, PRINTER_ADDRESS="10.0.0.9")
    code = main.run(Namespace(dry_run=False, date=date(2026, 9, 29)), settings)

    assert code == 1
    assert len(sent) == 2
    assert sent[0].startswith("Nothing due")  # the report itself
    assert sent[1].startswith("⚠️ Homework check failed while printing.")


def test_no_printer_address_means_no_printing(monkeypatch):
    from argparse import Namespace
    from datetime import date

    import fetch
    import main
    import notify
    import printer

    monkeypatch.setattr(fetch, "fetch", lambda settings, today: [])
    monkeypatch.setattr(notify, "send", lambda settings, text: None)
    monkeypatch.setattr(printer, "print_image", lambda *a: pytest.fail("should not print"))
    assert main.run(Namespace(dry_run=False, date=date(2026, 9, 29)), SETTINGS) == 0


def test_env_file_values_are_taken_literally(tmp_path, monkeypatch):
    import config

    (tmp_path / ".env").write_text(
        "SMARTSCHOOL_PASSWORD='ab#c${HOME}d'\nTELEGRAM_CHAT_ID=12#34\nTELEGRAM_BOT_TOKEN=\"x#y z\"\n", encoding="utf8"
    )
    monkeypatch.setattr(config, "HERE", tmp_path)
    for key in ("SMARTSCHOOL_PASSWORD", "TELEGRAM_CHAT_ID", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.setenv(key, "x")  # records the original state, so pytest restores it afterwards
        monkeypatch.delenv(key)
    settings = config.load_settings()
    assert settings["SMARTSCHOOL_PASSWORD"] == "ab#c${HOME}d"
    assert settings["TELEGRAM_CHAT_ID"] == "12#34"
    assert settings["TELEGRAM_BOT_TOKEN"] == "x#y z"


def _results_args(dry_run=False, since=None):
    from argparse import Namespace

    return Namespace(dry_run=dry_run, date=None, results=True, since=since)


def _fake_results(monkeypatch, tmp_path, results):
    import results as results_module

    calls = []

    def fake_fetch(settings, since, now):
        calls.append(since)
        return results

    monkeypatch.setattr(results_module, "fetch_results", fake_fetch)
    monkeypatch.setattr(results_module, "LAST_RUN_FILE", tmp_path / "last_results_run.txt")
    return calls


def _one_result():
    from datetime import date, datetime

    from results import Result

    return Result(subject="Frans", name="Test", score="4/10", percentage=40, colour="red", taken=date(2026, 10, 2), published=datetime(2026, 10, 13, 16, 0))


def test_results_report_is_sent_and_remembered(monkeypatch, tmp_path):
    import main
    import notify
    from results import load_last_run

    sent = []
    calls = _fake_results(monkeypatch, tmp_path, [_one_result()])
    monkeypatch.setattr(notify, "send", lambda settings, text: sent.append(text))

    assert main.run_results(_results_args(), SETTINGS) == 0
    assert sent and sent[0].startswith("🎓 New results")
    last = load_last_run()
    assert last is not None

    # the next run starts where this one ended
    assert main.run_results(_results_args(), SETTINGS) == 0
    assert calls[1] == last


def test_no_new_results_sends_nothing_but_is_remembered(monkeypatch, tmp_path):
    import main
    import notify
    import printer
    from results import load_last_run

    _fake_results(monkeypatch, tmp_path, [])
    monkeypatch.setattr(notify, "send", lambda *a: pytest.fail("should not send"))
    monkeypatch.setattr(printer, "print_image", lambda *a: pytest.fail("should not print"))
    assert main.run_results(_results_args(), dict(SETTINGS, PRINTER_ADDRESS="10.0.0.9")) == 0
    assert load_last_run() is not None


def test_results_dry_run_is_not_remembered(monkeypatch, tmp_path, capsys):
    import main
    from results import load_last_run

    _fake_results(monkeypatch, tmp_path, [_one_result()])
    assert main.run_results(_results_args(dry_run=True), SETTINGS) == 0
    assert "🎓 New results" in capsys.readouterr().out
    assert load_last_run() is None


def test_since_overrides_the_remembered_time(monkeypatch, tmp_path):
    from datetime import date, datetime

    import main
    from fetch import TZ

    calls = _fake_results(monkeypatch, tmp_path, [])
    main.run_results(_results_args(dry_run=True, since=date(2026, 10, 1)), SETTINGS)
    assert calls == [datetime(2026, 10, 1, tzinfo=TZ)]


def test_failed_telegram_is_not_remembered_but_failed_printing_is(monkeypatch, tmp_path):
    import main
    import notify
    import printer
    from results import load_last_run

    _fake_results(monkeypatch, tmp_path, [_one_result()])

    def broken_telegram(settings, text):
        raise notify.TelegramError("Could not reach Telegram (ConnectionError)")

    monkeypatch.setattr(notify, "send", broken_telegram)
    assert main.run_results(_results_args(), SETTINGS) == 1
    assert load_last_run() is None

    sent = []
    monkeypatch.setattr(notify, "send", lambda settings, text: sent.append(text))

    def broken_printer(address, img):
        raise printer.PrinterError("Could not print to 10.0.0.9:9100 (TimeoutError: timed out)")

    monkeypatch.setattr(printer, "print_image", broken_printer)
    assert main.run_results(_results_args(), dict(SETTINGS, PRINTER_ADDRESS="10.0.0.9")) == 1
    assert sent[1].startswith("⚠️ Results check failed while printing.")
    assert load_last_run() is not None
