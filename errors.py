"""Turn a failure into a short message for the parent, with every configured secret masked."""

from __future__ import annotations

SECRET_KEYS = ("SMARTSCHOOL_PASSWORD", "SMARTSCHOOL_MFA", "SMARTSCHOOL_USERNAME", "TELEGRAM_BOT_TOKEN")


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
