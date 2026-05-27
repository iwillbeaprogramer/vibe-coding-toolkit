"""Make repository root importable for tests so ``src`` is reachable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("STOCK_API_FORCE_MOCK", "1")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
