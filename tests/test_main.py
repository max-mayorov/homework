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
