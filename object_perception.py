"""YOLO scene objects for future memory layer; structured output only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

YOLO_MODEL_NAME = "yolov8s.pt"
OBJECT_CONFIDENCE_THRESHOLD = 0.30
MAX_OBJECTS = 12


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    location_label: str


@dataclass
class ObjectPerceptionResult:
    objects: list[DetectedObject]
    debug_text: str


def _normalize_label(label: str) -> str:
    raw = label.strip()
    key = raw.lower()
    aliases = {
        "cell phone": "phone",
        "tv": "screen",
        "dining table": "table",
    }
    return aliases.get(key, raw)


def _debug_ok(num_kept: int) -> str:
    return (
        f"{YOLO_MODEL_NAME} ok n={num_kept} "
        f"conf>={OBJECT_CONFIDENCE_THRESHOLD:.2f}"
    )


def _horizontal_band(cx: float, w: int) -> str:
    t = w / 3.0
    if cx < t:
        return "left"
    if cx < 2.0 * t:
        return "center"
    return "right"


def _vertical_band(cy: float, h: int) -> str:
    t = h / 3.0
    if cy < t:
        return "upper"
    if cy < 2.0 * t:
        return "middle"
    return "lower"


def _location_label(cx: float, cy: float, w: int, h: int) -> str:
    return f"{_horizontal_band(cx, w)} {_vertical_band(cy, h)}"


class ObjectPerception:
    """Loads YOLO once (`YOLO_MODEL_NAME`); detect() runs on BGR frames."""

    def __init__(self) -> None:
        self._model: Optional[Any] = None
        try:
            from ultralytics import YOLO

            self._model = YOLO(YOLO_MODEL_NAME)
        except Exception as exc:
            print(f"Warning: object detection unavailable ({type(exc).__name__}: {exc})")

    def detect(self, frame_bgr) -> ObjectPerceptionResult:
        if self._model is None:
            return ObjectPerceptionResult(objects=[], debug_text="no model")

        try:
            h, w = frame_bgr.shape[:2]
            results = self._model.predict(
                source=frame_bgr,
                verbose=False,
                conf=OBJECT_CONFIDENCE_THRESHOLD,
                imgsz=640,
            )
            if not results:
                return ObjectPerceptionResult(objects=[], debug_text=_debug_ok(0))

            r0 = results[0]
            boxes = r0.boxes
            if boxes is None or len(boxes) == 0:
                return ObjectPerceptionResult(objects=[], debug_text=_debug_ok(0))

            names = r0.names or {}
            scored: list[tuple[float, int]] = []
            for i in range(len(boxes)):
                conf = float(boxes.conf[i].item())
                if conf < OBJECT_CONFIDENCE_THRESHOLD:
                    continue
                scored.append((conf, i))

            scored.sort(key=lambda x: x[0], reverse=True)
            scored = scored[:MAX_OBJECTS]

            objects: list[DetectedObject] = []
            for conf, i in scored:
                xyxy = boxes.xyxy[i].cpu().numpy().tolist()
                x1, y1, x2, y2 = [int(round(v)) for v in xyxy]
                x1 = max(0, min(x1, w - 1))
                x2 = max(0, min(x2, w - 1))
                y1 = max(0, min(y1, h - 1))
                y2 = max(0, min(y2, h - 1))
                if x2 <= x1 or y2 <= y1:
                    continue

                cx = (x1 + x2) * 0.5
                cy = (y1 + y2) * 0.5
                cls_id = int(boxes.cls[i].item())
                raw_label = str(names.get(cls_id, str(cls_id)))
                label = _normalize_label(raw_label)

                objects.append(
                    DetectedObject(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        center=(int(round(cx)), int(round(cy))),
                        location_label=_location_label(cx, cy, w, h),
                    )
                )

            return ObjectPerceptionResult(objects=objects, debug_text=_debug_ok(len(objects)))
        except Exception as exc:
            print(f"Warning: object detection failed ({type(exc).__name__}: {exc})")
            return ObjectPerceptionResult(
                objects=[],
                debug_text=(
                    f"{YOLO_MODEL_NAME} error {type(exc).__name__} "
                    f"conf>={OBJECT_CONFIDENCE_THRESHOLD:.2f}"
                ),
            )

    def close(self) -> None:
        self._model = None
