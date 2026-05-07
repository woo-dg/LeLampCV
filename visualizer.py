import cv2
from mediapipe.tasks.python.vision import drawing_utils, face_landmarker

from perception import FacePerceptionResult


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

    y = 25
    color = (0, 255, 0) if state == "ENGAGED" else (0, 0, 255)
    lines = [
        state,
        f"face_detected={perception_result.face_detected}",
        f"looking_at_camera={perception_result.looking_at_camera}",
        perception_result.debug_text,
    ]
    for line in lines:
        cv2.putText(
            frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
        )
        y += 24
