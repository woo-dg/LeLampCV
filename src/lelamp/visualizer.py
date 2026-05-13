from typing import Optional

import cv2
from mediapipe.tasks.python.vision import drawing_utils, face_landmarker

from .object_perception import ObjectPerceptionResult
from .perception import FacePerceptionResult


def _state_bgr(state: str) -> tuple[int, int, int]:
    if state == "ENGAGED":
        return (0, 255, 0)
    if state == "IDLE":
        return (200, 200, 200)
    if state == "DISENGAGED":
        return (0, 165, 255)
    if state == "ANSWERING":
        return (0, 180, 255)
    if state == "ATTENTION_SEEKING":
        return (0, 255, 255)
    if state == "COOLDOWN":
        return (255, 128, 0)
    return (0, 0, 255)


def draw_perception(
    frame,
    perception_result: FacePerceptionResult,
    state: str,
    *,
    fps: Optional[float] = None,
    frame_ms: Optional[float] = None,
    show_debug: bool = False,
    object_result: Optional[ObjectPerceptionResult] = None,
    latest_answer: Optional[str] = None,
    listening: bool = False,
    behavior_variant: str = "",
    engagement_prediction: str = "",
    metrics_expected_label: str = "",
    metrics_expected_age_s: Optional[float] = None,
) -> None:
    _fh, fw = frame.shape[:2]

    if perception_result.face_detected and perception_result.raw_result.face_landmarks:
        drawing_utils.draw_landmarks(
            frame,
            perception_result.raw_result.face_landmarks[0],
            face_landmarker.FaceLandmarksConnections.FACE_LANDMARKS_FACE_OVAL,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_utils.DrawingSpec(
                color=(0, 255, 255), thickness=1
            ),
            is_drawing_landmarks=False,
        )

    color = _state_bgr(state)
    cv2.putText(
        frame,
        f"STATE: {state}",
        (10, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
    )
    eng_pred = engagement_prediction.strip()
    if eng_pred:
        eg_color = (0, 220, 100) if eng_pred == "ENGAGED" else (0, 180, 255)
        cv2.putText(
            frame,
            f"engagement={eng_pred}",
            (10, 54),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            eg_color,
            1,
            lineType=cv2.LINE_AA,
        )
    has_variant = bool(behavior_variant.strip())
    if has_variant:
        cv2.putText(
            frame,
            f"behavior variant: {behavior_variant.strip()}",
            (10, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (180, 200, 220),
            1,
            lineType=cv2.LINE_AA,
        )
    if listening:
        cv2.putText(
            frame,
            "listening...",
            (max(10, fw - 160), 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (120, 220, 255),
            1,
            lineType=cv2.LINE_AA,
        )
    exp = metrics_expected_label.strip()
    if exp:
        if metrics_expected_age_s is not None:
            exp_cap = f"expected: {exp} settled={metrics_expected_age_s:.1f}s"
        else:
            exp_cap = f"expected: {exp}"
        cv2.putText(
            frame,
            exp_cap,
            (max(10, fw - 380), 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (140, 220, 180),
            1,
            lineType=cv2.LINE_AA,
        )
    reply_color = (60, 200, 255)
    if latest_answer:
        clip = latest_answer if len(latest_answer) <= 72 else latest_answer[:69] + "..."
        reply_y = 90 if has_variant else 74
        cv2.putText(
            frame,
            f"reply: {clip}",
            (10, reply_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            reply_color,
            1,
            lineType=cv2.LINE_AA,
        )
        y = reply_y + 22
    else:
        y = 88 if has_variant else 70
    detail_color = (220, 220, 220)

    if show_debug and fps is not None and frame_ms is not None:
        cv2.putText(
            frame,
            f"FPS ~ {fps:.1f}  frame_ms ~ {frame_ms:.1f}",
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (180, 255, 180),
            1,
        )
        y += 22

    lines = [
        f"calibration: {perception_result.calibration_text}",
        f"calibrated={perception_result.calibrated}",
        f"gaze_direction={perception_result.gaze_direction}",
        f"face_detected={perception_result.face_detected}",
        f"head_forward={perception_result.head_forward}",
        f"eye_contact={perception_result.eye_contact}",
        f"looking_at_camera={perception_result.looking_at_camera}",
    ]
    for line in lines:
        cv2.putText(
            frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, detail_color, 1
        )
        y += 22

    for segment in perception_result.debug_text.split("|"):
        cv2.putText(
            frame,
            segment.strip(),
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            detail_color,
            1,
        )
        y += 20

    if object_result is not None:
        _draw_object_overlay(
            frame,
            object_result,
            show_debug=show_debug,
            reserve_bottom_extra=26 if latest_answer else 0,
        )


def _horizontal_bucket(location_label: str) -> str:
    parts = location_label.split()
    return parts[0] if parts else "?"


def _draw_object_overlay(
    frame,
    object_result: ObjectPerceptionResult,
    *,
    show_debug: bool,
    reserve_bottom_extra: int = 0,
) -> None:
    fh, fw = frame.shape[0], frame.shape[1]
    box_color = (60, 200, 100)
    label_color = (230, 245, 230)

    for obj in object_result.objects:
        x1, y1, x2, y2 = obj.bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
        cap = f"{obj.label} {obj.confidence:.2f} {obj.location_label}"
        ty = max(16, y1 - 4)
        cv2.putText(
            frame,
            cap,
            (x1, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            label_color,
            1,
            lineType=cv2.LINE_AA,
        )

    if object_result.objects:
        parts = [
            f"{o.label}({_horizontal_bucket(o.location_label)})"
            for o in object_result.objects
        ]
        summary = "objects: " + ", ".join(parts)
        max_chars = max(40, fw // 7)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3] + "..."
    else:
        summary = "objects: —"

    sum_y = fh - 28 - reserve_bottom_extra
    dbg_y = fh - 8 - reserve_bottom_extra

    cv2.putText(
        frame,
        summary,
        (10, sum_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (180, 210, 255),
        1,
        lineType=cv2.LINE_AA,
    )

    if show_debug:
        cv2.putText(
            frame,
            f"obj {object_result.debug_text}",
            (10, dbg_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (140, 160, 200),
            1,
            lineType=cv2.LINE_AA,
        )
