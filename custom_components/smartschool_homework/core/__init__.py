"""The app's own modules, copied here by scripts/sync_ha_core.py (all but this file).

The smartschool library logs through logprise, which on import takes over *all* of Python's
logging (logging.basicConfig(force=True), patching every logger, sys.excepthook). Inside Home
Assistant that would break HA's own logging, so before anything imports smartschool we register
a stand-in `logprise` module that sends the library's messages to a normal `smartschool` logger.
"""

from __future__ import annotations

import logging
import sys
import types


class _Logger:
    """The part of loguru's logger that smartschool uses: `logger.info("Logging in with {}", name)`."""

    def __init__(self) -> None:
        self._log = logging.getLogger("smartschool")

    def _emit(self, level: int, message, *args, **kwargs) -> None:
        if self._log.isEnabledFor(level):
            text = str(message).format(*args, **kwargs) if args or kwargs else str(message)
            self._log.log(level, "%s", text)

    def trace(self, message, *args, **kwargs) -> None:
        self._emit(logging.DEBUG, message, *args, **kwargs)

    def debug(self, message, *args, **kwargs) -> None:
        self._emit(logging.DEBUG, message, *args, **kwargs)

    def info(self, message, *args, **kwargs) -> None:
        self._emit(logging.INFO, message, *args, **kwargs)

    def success(self, message, *args, **kwargs) -> None:
        self._emit(logging.INFO, message, *args, **kwargs)

    def warning(self, message, *args, **kwargs) -> None:
        self._emit(logging.WARNING, message, *args, **kwargs)

    def error(self, message, *args, **kwargs) -> None:
        self._emit(logging.ERROR, message, *args, **kwargs)

    def exception(self, message, *args, **kwargs) -> None:
        self._emit(logging.ERROR, message, *args, **kwargs)

    def critical(self, message, *args, **kwargs) -> None:
        self._emit(logging.CRITICAL, message, *args, **kwargs)


if "logprise" not in sys.modules:
    _stub = types.ModuleType("logprise")
    _stub.logger = _Logger()
    sys.modules["logprise"] = _stub
