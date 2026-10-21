"""Route the smartschool library's logging into Home Assistant's, under this integration's logger.

The library logs through logprise, which on import takes over *all* of Python's logging
(logging.basicConfig(force=True), patching every logger, sys.excepthook). That would break
Home Assistant's log, so before anything imports smartschool, `install()` registers a stand-in
`logprise` module. Its logger writes to `custom_components.smartschool_homework.smartschool`, so
the integration's `logger:` setting (or "Enable debug logging") covers the library too.
"""

from __future__ import annotations

import logging
import sys
import types

_LOGGER = logging.getLogger(f"{__package__}.smartschool")


class _LibraryLogger:
    """The part of loguru's logger that smartschool uses: `logger.info("Logging in with {}", name)`."""

    def _emit(self, level: int, message, *args, **kwargs) -> None:
        if _LOGGER.isEnabledFor(level):
            _LOGGER.log(level, "%s", str(message).format(*args, **kwargs) if args or kwargs else message)

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


def install() -> None:
    if "logprise" not in sys.modules:
        stub = types.ModuleType("logprise")
        stub.logger = _LibraryLogger()
        sys.modules["logprise"] = stub
