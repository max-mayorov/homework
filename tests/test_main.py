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
