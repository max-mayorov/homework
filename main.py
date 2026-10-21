"""Homework and results checks: fetch from Smartschool, build a report, send via Telegram (and print it if PRINTER_ADDRESS is set).

The stand-alone way to run the Home Assistant integration's reports, without Home Assistant: the
reports' logic is the integration's `homework` package (custom_components/smartschool_homework/
homework); this file adds what HA would otherwise do (settings, logging, schedule via cron.sh,
error messages to Telegram).

    python main.py                      # Homework report (sends to Telegram)
    python main.py --dry-run            # print the report instead of sending (and save
                                        # print_preview.png instead of printing)
    python main.py --date 2026-10-05    # pretend today is that date
    python main.py --results            # Results report: Results published since the last one
                                        # (at most 14 days back); nothing is sent if there are none
    python main.py --results --since 2026-10-01   # report Results published since that day instead
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The reports' logic lives in the Home Assistant integration's folder, as the `homework` package
sys.path.insert(0, str(HERE / "custom_components" / "smartschool_homework"))

from config import load_settings  # noqa: E402
from homework.fetch import TZ  # noqa: E402

log = logging.getLogger("homework")

# When the last Results report was delivered
LAST_RUN_FILE = HERE / "last_results_run.txt"

SECRET_KEYS = ("SMARTSCHOOL_PASSWORD", "SMARTSCHOOL_MFA", "SMARTSCHOOL_USERNAME", "TELEGRAM_BOT_TOKEN")


OWN_MODULES = {"__main__", "main", "config"}


def _log_filter(record) -> bool:
    # Our modules (and the homework package) log non-sensitive progress at INFO; libraries
    # (smartschool logs the username at INFO) only get through at WARNING and above.
    name = record["name"] or ""
    return name in OWN_MODULES or name.startswith("homework.") or record["level"].no >= logging.WARNING


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


def error_message(step: str, exc: BaseException, settings: dict[str, str], check: str = "Homework") -> str:
    detail = redact(f"{type(exc).__name__}: {exc}", settings)
    if len(detail) > 300:
        detail = detail[:300] + "…"
    return f"⚠️ {check} check failed while {step}.\n{detail}"


PREVIEW_FILE = "print_preview.png"


def report_failure(step: str, exc: BaseException, args, settings: dict[str, str], check: str = "Homework") -> None:
    from homework.notify import send

    message = error_message(step, exc, settings, check)
    log.error("Failed while %s (%s)", step, type(exc).__name__)
    if args.dry_run:
        print(message)
        return
    try:
        send(settings, message)
    except Exception as send_exc:  # noqa: BLE001
        log.error("Could not send the error to Telegram either: %s", redact(str(send_exc), settings))


def run(args, settings: dict[str, str]) -> int:
    from homework.fetch import fetch
    from homework.message import build_message
    from homework.printer import render_report

    today: date = args.date or datetime.now(TZ).date()
    step = "fetching from Smartschool"
    try:
        items = fetch(settings, today)
        step = "building the message"
        summary = build_message(items, today)
    except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
        report_failure(step, exc, args, settings)
        return 1

    failed = deliver(summary, lambda: render_report(items, today, settings), args, settings, "Homework")
    return 1 if failed else 0


def deliver(text: str, render, args, settings: dict[str, str], check: str) -> list[str]:
    """Send `text` to Telegram and, with PRINTER_ADDRESS set, print `render()`. Returns the steps that failed.

    Telegram and the printer are independent: one failing doesn't stop the other.
    """
    from homework.notify import send

    deliveries = [("sending to Telegram", lambda: print(text) if args.dry_run else send(settings, text))]
    printer_address = settings.get("PRINTER_ADDRESS", "").strip()
    if printer_address:
        deliveries.append(("printing", lambda: print_report(render(), printer_address, args)))

    failed = []
    for step, deliver_one in deliveries:
        try:
            deliver_one()
        except Exception as exc:  # noqa: BLE001
            report_failure(step, exc, args, settings, check)
            failed.append(step)
    return failed


def run_results(args, settings: dict[str, str]) -> int:
    from homework.message import build_results_message
    from homework.printer import render_results
    from homework.results import fetch_results, window_start

    now = datetime.now(TZ)
    since = datetime.combine(args.since, time.min, TZ) if args.since else window_start(load_last_run(), now)
    step = "fetching results from Smartschool"
    try:
        results = fetch_results(settings, since, now)
        step = "building the message"
        text = build_results_message(results)
    except Exception as exc:  # noqa: BLE001 - every failure must reach the parent
        report_failure(step, exc, args, settings, "Results")
        return 1

    if results:
        failed = deliver(text, lambda: render_results(results, settings, now), args, settings, "Results")
    else:
        failed = []
        log.info("No new results; nothing sent")
        if args.dry_run:
            print(f"(no new results since {since:%Y-%m-%d %H:%M})")
    # Once Telegram has the report, it counts as delivered, even if printing failed.
    if not args.dry_run and "sending to Telegram" not in failed:
        save_last_run(now)
    return 1 if failed else 0


def load_last_run(path: Path | None = None) -> datetime | None:
    try:
        value = datetime.fromisoformat((path or LAST_RUN_FILE).read_text(encoding="utf8").strip())
    except (FileNotFoundError, ValueError):
        return None
    return value.astimezone(TZ) if value.tzinfo else value.replace(tzinfo=TZ)


def save_last_run(when: datetime, path: Path | None = None) -> None:
    (path or LAST_RUN_FILE).write_text(when.isoformat() + "\n", encoding="utf8")


def print_report(img, address: str, args) -> None:
    from homework.printer import print_image

    if args.dry_run:
        img.save(PREVIEW_FILE)
        print(f"(dry run: receipt image saved to {PREVIEW_FILE} instead of printing)")
    else:
        print_image(address, img)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the summary instead of sending it; save the receipt image instead of printing")
    parser.add_argument("--date", type=date.fromisoformat, help="homework: pretend today is YYYY-MM-DD")
    parser.add_argument("--results", action="store_true", help="send the Results report instead of the Homework report")
    parser.add_argument("--since", type=date.fromisoformat, help="results: report Results published since YYYY-MM-DD, instead of since the last report")
    args = parser.parse_args()
    if args.results and args.date:
        parser.error("--date is for the homework check; use --since with --results")
    if args.since and not args.results:
        parser.error("--since only works with --results")

    setup_logging()
    return (run_results if args.results else run)(args, load_settings())


if __name__ == "__main__":
    sys.exit(main())
