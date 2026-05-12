import cv2
from mediapipe.tasks.python.vision import drawing_utils, face_landmarker

from perception import FacePerceptionResult


def _state_bgr(state: str) -> tuple[int, int, int]:
    if state == "ENGAGED":
        return (0, 255, 0)
    if state == "IDLE":
        return (200, 200, 200)
    if state == "DISENGAGED":
        return (0, 165, 255)
    if state == "ATTENTION_SEEKING":
        return (0, 255, 255)
    if state == "COOLDOWN":
        return (255, 128, 0)
    return (0, 0, 255)


def draw_perception(frame, perception_result: FacePerceptionResult, state: str) -> None:
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
        f"STATE (debounced): {state}",
        (10, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        color,
        2,
    )
    y = 65
    detail_color = (220, 220, 220)
    cv2.putText(
        frame,
        f"GAZE: {perception_result.gaze_direction}",
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (180, 220, 255),
        2,
    )
    y += 28
    raw_engaged = perception_result.face_detected and perception_result.looking_at_camera
    lines = [
        f"raw_engaged={raw_engaged}",
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
