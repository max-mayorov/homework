"""The integration's own counterpart of the app's config.py (not a copy).

fetch() and fetch_results() import `smartschool_credentials` from here. In the app it reads the
settings loaded from .env; here the settings come from the config entry (see reporter.to_settings),
already checked by the config flow.
"""

from __future__ import annotations


def smartschool_credentials(settings: dict[str, str]):
    from smartschool import AppCredentials

    return AppCredentials(
        username=settings["SMARTSCHOOL_USERNAME"],
        password=settings["SMARTSCHOOL_PASSWORD"],
        main_url=settings["SMARTSCHOOL_MAIN_URL"],
        mfa=settings["SMARTSCHOOL_MFA"],
    )
