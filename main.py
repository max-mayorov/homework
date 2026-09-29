"""Evening homework check: fetch from Smartschool, summarize with Claude, send via Telegram.

    python main.py                      # normal run (sends to Telegram)
    python main.py --dry-run            # print the summary instead of sending
    python main.py --date 2026-10-05    # pretend today is that date
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from config import load_settings
from fetch import TZ

log = logging.getLogger("homework")

SECRET_KEYS = ("SMARTSCHOOL_PASSWORD", "SMARTSCHOOL_MFA", "SMARTSCHOOL_USERNAME", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN")


OWN_MODULES = {"__main__", "main", "config", "fetch", "explain", "notify"}


def _log_filter(record) -> bool:
    # Our modules log non-sensitive progress at INFO; libraries (smartschool logs the username
    # at INFO) only get through at WARNING and above.
    return record["name"] in OWN_MODULES or record["level"].no >= logging.WARNING


def setup_logging() -> None:
    """Route everything through one quiet loguru sink.

    The smartschool library pulls in logprise, which redirects *all* stdlib logging into
    loguru and adds its own loguru handlers/excepthook, so we configure loguru, not logging.
    """
    import smartschool  # noqa: F401 - importing it installs logprise's hooks, which we then adjust
    from loguru import logger as loguru_logger

    loguru_logger.remove()
    # diagnose=False: never print variable values (credentials!) in tracebacks
    loguru_logger.add(sys.stderr, level="INFO", filter=_log_filter, diagnose=False, backtrace=False, format="{time:YYYY-MM-DD HH:mm:ss} {level} {name}: {message}")
    sys.excepthook = sys.__excepthook__
    logging.getLogger().setLevel(logging.INFO)


def redact(text: str, settings: dict[str, str]) -> str:
    for key in SECRET_KEYS:
        value = settings.get(key)
        if value and len(value) >= 3:
            text = text.replace(value, "***")
    return text


def error_message(step: str, exc: BaseException, settings: dict[str, str]) -> str:
    detail = redact(f"{type(exc).__name__}: {exc}", settings)
    if len(detail) > 300:
        detail = detail[:300] + "…"
    return f"⚠️ Homework check failed while {step}.\n{detail}"


def run(args, settings: dict[str, str]) -> int:
    from explain import explain
    from fetch import fetch
    from notify import send

    today: date = args.date or datetime.now(TZ).date()
    step = "fetching from Smartschool"
    try:
        items = fetch(settings, today)
        step = "writing the summary"
        summary = explain(items, today, settings)
        step = "sending to Telegram"
        if args.dry_run:
            print(summary)
        else:
            send(settings, summary)
        return 0
    except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
        message = error_message(step, exc, settings)
        log.error("Failed while %s (%s)", step, type(exc).__name__)
        if args.dry_run:
            print(message)
            return 1
        try:
            send(settings, message)
        except Exception as send_exc:  # noqa: BLE001
            log.error("Could not send the error to Telegram either: %s", redact(str(send_exc), settings))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the summary instead of sending it")
    parser.add_argument("--date", type=date.fromisoformat, help="pretend today is YYYY-MM-DD")
    args = parser.parse_args()

    setup_logging()
    return run(args, load_settings())


if __name__ == "__main__":
    sys.exit(main())
