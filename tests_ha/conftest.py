"""Tests for the Home Assistant integration. They need Home Assistant's test harness:

    pip install -r requirements_ha_test.txt
    python -m pytest tests_ha     # picks up tests_ha/pytest.ini

Without it (e.g. on the Raspberry Pi), the tests in this folder aren't collected.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

if importlib.util.find_spec("pytest_homeassistant_custom_component") is None:
    collect_ignore_glob = ["test_*.py"]
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        yield
