"""One-off: print paths of JSON files that look like Google service accounts."""
from __future__ import annotations

import os
import re
from pathlib import Path

SERVICE_ACCOUNT = re.compile(r'"type"\s*:\s*"service_account"')
HOME = Path.home()
ROOTS = [
    HOME / "Downloads" / "leLampCV",
    HOME / "Documents",
    HOME / "Desktop",
]
MAX_DEPTH = 8


def main() -> None:
    for root in ROOTS:
        root = root.resolve()
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel_depth = len(Path(dirpath).relative_to(root).parts)
            if rel_depth > MAX_DEPTH:
                dirnames.clear()
                continue
            for name in filenames:
                if not name.endswith(".json"):
                    continue
                path = Path(dirpath) / name
                try:
                    if path.stat().st_size > 400_000:
                        continue
                    head = path.read_text(encoding="utf-8", errors="ignore")[:12_000]
                    if SERVICE_ACCOUNT.search(head):
                        print(path)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
