"""Append-only JSONL object memory for future recall (no UI yet)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from object_perception import DetectedObject

MEMORY_CONFIDENCE_THRESHOLD = 0.50
MEMORY_DEDUP_SECONDS = 5.0


@dataclass
class ObjectMemoryEntry:
    timestamp: str
    label: str
    location_label: str
    confidence: float
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    state: str


def _entry_to_line(entry: ObjectMemoryEntry) -> str:
    d = {
        "timestamp": entry.timestamp,
        "label": entry.label,
        "location_label": entry.location_label,
        "confidence": entry.confidence,
        "bbox": list(entry.bbox),
        "center": list(entry.center),
        "state": entry.state,
    }
    return json.dumps(d, ensure_ascii=False)


def _line_to_entry(line: str) -> Optional[ObjectMemoryEntry]:
    line = line.strip()
    if not line:
        return None
    try:
        d = json.loads(line)
        bbox = d["bbox"]
        center = d["center"]
        return ObjectMemoryEntry(
            timestamp=str(d["timestamp"]),
            label=str(d["label"]),
            location_label=str(d["location_label"]),
            confidence=float(d["confidence"]),
            bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
            center=(int(center[0]), int(center[1])),
            state=str(d["state"]),
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        print(f"Warning: skipped bad memory line ({type(exc).__name__})")
        return None


class ObjectMemory:
    def __init__(self, path: str = "memory/object_memory.jsonl") -> None:
        self._path = Path(path)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"Warning: memory folder unavailable ({type(exc).__name__}: {exc})")
        self._last_saved: dict[tuple[str, str], float] = {}

    def add_sightings(self, objects: list[DetectedObject], state: str) -> None:
        now = time.time()
        iso = datetime.now(timezone.utc).isoformat()
        for obj in objects:
            if obj.confidence < MEMORY_CONFIDENCE_THRESHOLD:
                continue
            key = (obj.label, obj.location_label)
            last = self._last_saved.get(key)
            if last is not None and (now - last) < MEMORY_DEDUP_SECONDS:
                continue
            entry = ObjectMemoryEntry(
                timestamp=iso,
                label=obj.label,
                location_label=obj.location_label,
                confidence=obj.confidence,
                bbox=obj.bbox,
                center=obj.center,
                state=state,
            )
            try:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(_entry_to_line(entry) + "\n")
                self._last_saved[key] = now
                print(f"memory saved: {obj.label} at {obj.location_label}")
            except OSError as exc:
                print(f"Warning: memory write failed ({type(exc).__name__}: {exc})")

    def _read_all(self) -> list[ObjectMemoryEntry]:
        if not self._path.is_file():
            return []
        out: list[ObjectMemoryEntry] = []
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Warning: memory read failed ({type(exc).__name__}: {exc})")
            return []
        for line in text.splitlines():
            e = _line_to_entry(line)
            if e is not None:
                out.append(e)
        return out

    def find_latest(self, label: str) -> Optional[ObjectMemoryEntry]:
        latest: Optional[ObjectMemoryEntry] = None
        for entry in self._read_all():
            if entry.label == label:
                latest = entry
        return latest

    def recent_entries(self, limit: int = 20) -> list[ObjectMemoryEntry]:
        all_e = self._read_all()
        if limit <= 0:
            return []
        return all_e[-limit:]
