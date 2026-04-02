from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
DESKTOP_SRC_PATH = REPO_ROOT / "desktop" / "src"
for path in (SRC_PATH, DESKTOP_SRC_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
