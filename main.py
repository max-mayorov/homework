"""Evening homework check: fetch from Smartschool, build a summary, send via Telegram (and print it if PRINTER_ADDRESS is set).

    python main.py                      # normal run (sends to Telegram)
    python main.py --dry-run            # print the summary instead of sending (and save
                                        # print_preview.png instead of printing)
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

SECRET_KEYS = ("SMARTSCHOOL_PASSWORD", "SMARTSCHOOL_MFA", "SMARTSCHOOL_USERNAME", "TELEGRAM_BOT_TOKEN")


OWN_MODULES = {"__main__", "main", "config", "fetch", "message", "notify", "printer"}


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


PREVIEW_FILE = "print_preview.png"


def report_failure(step: str, exc: BaseException, args, settings: dict[str, str]) -> None:
    from notify import send

    message = error_message(step, exc, settings)
    log.error("Failed while %s (%s)", step, type(exc).__name__)
    if args.dry_run:
        print(message)
        return
    try:
        send(settings, message)
    except Exception as send_exc:  # noqa: BLE001
        log.error("Could not send the error to Telegram either: %s", redact(str(send_exc), settings))


def run(args, settings: dict[str, str]) -> int:
    from fetch import fetch
    from message import build_message
    from notify import send

    today: date = args.date or datetime.now(TZ).date()
    step = "fetching from Smartschool"
    try:
        items = fetch(settings, today)
        step = "building the message"
        summary = build_message(items, today)
    except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
        report_failure(step, exc, args, settings)
        return 1

    # Telegram and the printer are independent: one failing doesn't stop the other.
    deliveries = [("sending to Telegram", lambda: print(summary) if args.dry_run else send(settings, summary))]
    printer_address = settings.get("PRINTER_ADDRESS", "").strip()
    if printer_address:
        deliveries.append(("printing", lambda: print_report(items, today, printer_address, args, settings)))

    ok = True
    for step, deliver in deliveries:
        try:
            deliver()
        except Exception as exc:  # noqa: BLE001
            report_failure(step, exc, args, settings)
            ok = False
    return 0 if ok else 1


def print_report(items, today: date, address: str, args, settings: dict[str, str]) -> None:
    from printer import print_image, render_report

    img = render_report(items, today, settings)
    if args.dry_run:
        img.save(PREVIEW_FILE)
        print(f"(dry run: receipt image saved to {PREVIEW_FILE} instead of printing)")
    else:
        print_image(address, img)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the summary instead of sending it; save the receipt image instead of printing")
    parser.add_argument("--date", type=date.fromisoformat, help="pretend today is YYYY-MM-DD")
    args = parser.parse_args()

    setup_logging()
    return run(args, load_settings())


if __name__ == "__main__":
    sys.exit(main())
