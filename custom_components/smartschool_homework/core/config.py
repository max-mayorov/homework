# Copied from config.py at the top of the repo by scripts/sync_ha_core.py. Edit that file, not this one.
"""Load secrets from .env (preferred) or credentials.yml. Never log the values."""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

SMARTSCHOOL_FIELDS = ("username", "password", "main_url", "mfa")


def load_settings() -> dict[str, str]:
    """Return settings as a flat dict of UPPER_CASE keys.

    Values from .env / the environment win; credentials.yml fills in anything missing.
    credentials.yml uses the smartschool library's lower-case keys (username, password, ...)
    for the Smartschool fields, and upper-case env-style keys for anything else.
    """
    # Imported here: the Home Assistant integration only uses smartschool_credentials, and doesn't install python-dotenv
    import yaml
    from dotenv import load_dotenv

    load_dotenv(HERE / ".env", interpolate=False)  # keep "${" in passwords literal
    settings: dict[str, str] = {}

    yml = HERE / "credentials.yml"
    if yml.exists():
        data = yaml.safe_load(yml.read_text(encoding="utf8")) or {}
        for key, value in data.items():
            name = f"SMARTSCHOOL_{key.upper()}" if key in SMARTSCHOOL_FIELDS else key.upper()
            settings[name] = str(value)

    for key, value in os.environ.items():
        if value:
            settings[key] = value

    return settings


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
