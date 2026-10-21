"""Copy the shared modules into the Home Assistant integration, so it can be installed on its own (e.g. by HACS).

    python scripts/sync_ha_core.py           # write custom_components/smartschool_homework/core/*.py
    python scripts/sync_ha_core.py --check   # exit 1 if the copies are out of date

The modules at the top of the repo are the originals: edit those, then run this. Imports
between them become relative imports (`from fetch import TZ` -> `from .fetch import TZ`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "custom_components" / "smartschool_homework" / "core"
MODULES = ("config", "errors", "fetch", "message", "notify", "printer", "results")

_IMPORT = re.compile(rf"^(\s*)from ({'|'.join(MODULES)}) import ", re.MULTILINE)


def generated(name: str) -> str:
    source = (ROOT / f"{name}.py").read_text(encoding="utf8")
    header = f"# Copied from {name}.py at the top of the repo by scripts/sync_ha_core.py. Edit that file, not this one.\n"
    return header + _IMPORT.sub(r"\1from .\2 import ", source)


def out_of_date() -> list[str]:
    return [name for name in MODULES if not (CORE / f"{name}.py").exists() or (CORE / f"{name}.py").read_text(encoding="utf8") != generated(name)]


def main() -> int:
    if "--check" in sys.argv[1:]:
        stale = out_of_date()
        if stale:
            print(f"Out of date in {CORE.relative_to(ROOT)}: {', '.join(stale)}. Run: python scripts/sync_ha_core.py", file=sys.stderr)
        return 1 if stale else 0
    for name in MODULES:
        (CORE / f"{name}.py").write_text(generated(name), encoding="utf8")
    print(f"Wrote {len(MODULES)} module(s) to {CORE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
