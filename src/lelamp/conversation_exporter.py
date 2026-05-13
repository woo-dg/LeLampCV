"""Export latest Q&A metadata for the Three.js simulator."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .conversation import ConversationResult


def export_latest_conversation(
    *,
    question: str,
    result: ConversationResult,
    listening: bool = False,
    path: str = "simulator/latest_conversation.json",
) -> None:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "question": question.strip(),
            "answer": result.answer.strip(),
            "mode": result.mode,
            "object_query": result.object_query if result.object_query else "",
            "memory_found": bool(result.memory_found),
            "listening": bool(listening),
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except Exception as exc:
        print(f"Warning: conversation export failed ({type(exc).__name__})")
