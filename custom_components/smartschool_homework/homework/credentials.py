"""The Smartschool login, from the flat settings dict (UPPER_CASE keys).

The app reads those settings from .env (config.py's load_settings); the integration builds them
from its config entry (reporter.to_settings).
"""

from __future__ import annotations

SMARTSCHOOL_FIELDS = ("username", "password", "main_url", "mfa")


def smartschool_credentials(settings: dict[str, str]):
    from smartschool import AppCredentials

    missing = [f for f in SMARTSCHOOL_FIELDS if not settings.get(f"SMARTSCHOOL_{f.upper()}")]
    if missing:
        raise RuntimeError(f"Missing Smartschool settings: {', '.join('SMARTSCHOOL_' + m.upper() for m in missing)}")

    main_url = settings["SMARTSCHOOL_MAIN_URL"].removeprefix("https://").removeprefix("http://").strip("/")
    return AppCredentials(
        username=settings["SMARTSCHOOL_USERNAME"],
        password=settings["SMARTSCHOOL_PASSWORD"],
        main_url=main_url,
        mfa=settings["SMARTSCHOOL_MFA"],
    )
