import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_ha_core.py"


def test_home_assistant_copies_match_the_originals():
    spec = importlib.util.spec_from_file_location("sync_ha_core", SCRIPT)
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    assert sync.out_of_date() == [], "run: python scripts/sync_ha_core.py"
