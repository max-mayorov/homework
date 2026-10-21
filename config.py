"""Load secrets from .env (preferred) or credentials.yml. Never log the values."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

SMARTSCHOOL_FIELDS = ("username", "password", "main_url", "mfa")


def load_settings() -> dict[str, str]:
    """Return settings as a flat dict of UPPER_CASE keys.

    Values from .env / the environment win; credentials.yml fills in anything missing.
    credentials.yml uses the smartschool library's lower-case keys (username, password, ...)
    for the Smartschool fields, and upper-case env-style keys for anything else.
    """
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

