from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_PATH = REPO_ROOT / "src"
DESKTOP_SRC_PATH = REPO_ROOT / "desktop" / "src"

for path in (str(SRC_PATH), str(DESKTOP_SRC_PATH)):
    if path not in sys.path:
        sys.path.insert(0, path)
