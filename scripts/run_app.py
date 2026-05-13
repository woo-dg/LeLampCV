"""Entry point: run from repo root so ``simulator/`` exports resolve."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

from lelamp.main import main

if __name__ == "__main__":
    main()
