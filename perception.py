import urllib.request
from dataclasses import dataclass
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_FILENAME = "face_landmarker.task"

_IDX_NOSE_TIP = 1
_IDX_RIGHT_EYE_OUTER = 33
_IDX_LEFT_EYE_OUTER = 263
_IDX_CHIN = 152

_YAW_RATIO_MAX = 0.35
_PITCH_N_MIN = 0.12
_PITCH_N_MAX = 0.72


@dataclass
class FacePerceptionResult:
    face_detected: bool
    looking_at_camera: bool
    raw_result: object
    debug_text: str


def _ensure_model(path: Path) -> None:
    if path.is_file():
        return
    print("Downloading face landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, path)


def _forward_facing(lms: list) -> tuple[bool, str]:
    """Rough yaw/pitch from 2D normalized landmarks (nose vs eyes/chin)."""
    nose = lms[_IDX_NOSE_TIP]
    re = lms[_IDX_RIGHT_EYE_OUTER]
    le = lms[_IDX_LEFT_EYE_OUTER]
    chin = lms[_IDX_CHIN]

    eye_mid_x = (re.x + le.x) * 0.5
    eye_width = abs(le.x - re.x) + 1e-6
    yaw_ratio = (nose.x - eye_mid_x) / eye_width
    yaw_ok = abs(yaw_ratio) < _YAW_RATIO_MAX

    eye_mid_y = (re.y + le.y) * 0.5
    chin_span = chin.y - eye_mid_y
    if chin_span <= 1e-6:
        return False, f"yaw_ratio={yaw_ratio:.2f} pitch_bad=chin_span"

    pitch_n = (nose.y - eye_mid_y) / chin_span
    pitch_ok = _PITCH_N_MIN < pitch_n < _PITCH_N_MAX
    looking = yaw_ok and pitch_ok
    return looking, f"yaw_ratio={yaw_ratio:.2f} pitch_n={pitch_n:.2f}"


class FacePerception:
    def __init__(self) -> None:
        model_path = Path(__file__).resolve().parent / "models" / MODEL_FILENAME
        _ensure_model(model_path)
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def detect(self, frame_rgb, timestamp_ms: int) -> FacePerceptionResult:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        raw = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        if not raw.face_landmarks:
            return FacePerceptionResult(
                face_detected=False,
                looking_at_camera=False,
                raw_result=raw,
                debug_text="no face",
            )
        lms = raw.face_landmarks[0]
        looking, geom = _forward_facing(lms)
        return FacePerceptionResult(
            face_detected=True,
            looking_at_camera=looking,
            raw_result=raw,
            debug_text=geom,
        )

    def close(self) -> None:
        self._landmarker.close()
