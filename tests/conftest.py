import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# The reports' logic: the Home Assistant integration's `homework` package (main.py does the same)
sys.path.insert(0, str(ROOT / "custom_components" / "smartschool_homework"))
