import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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

_RIGHT_INNER = 133
_LEFT_INNER = 362

_IRIS_RIGHT = (469, 470, 471, 472)
_IRIS_LEFT = (474, 475, 476, 477)

_RIGHT_LID_TOP = 159
_RIGHT_LID_BOT = 145
_LEFT_LID_TOP = 386
_LEFT_LID_BOT = 374

_MIN_LANDMARKS_FOR_IRIS = 478

_YAW_RATIO_MAX = 0.35
_PITCH_N_MIN = 0.12
_PITCH_N_MAX = 0.72

_IRIS_H_BAND_LO = 0.38
_IRIS_H_BAND_HI = 0.62
_IRIS_V_BAND_LO = 0.38
_IRIS_V_BAND_HI = 0.62


@dataclass
class FacePerceptionResult:
    face_detected: bool
    head_forward: bool
    eye_contact: bool
    looking_at_camera: bool
    raw_result: object
    debug_text: str


def _ensure_model(path: Path) -> None:
    if path.is_file():
        return
    print("Downloading face landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, path)


def _safe_landmark(lms: list, idx: int) -> Optional[Any]:
    if idx < 0 or idx >= len(lms):
        return None
    return lms[idx]


def _head_forward(lms: list) -> tuple[bool, float, float]:
    """Rough head pose from nose vs outer-eye midline and chin (not true gaze)."""
    nose = _safe_landmark(lms, _IDX_NOSE_TIP)
    re = _safe_landmark(lms, _IDX_RIGHT_EYE_OUTER)
    le = _safe_landmark(lms, _IDX_LEFT_EYE_OUTER)
    chin = _safe_landmark(lms, _IDX_CHIN)
    if nose is None or re is None or le is None or chin is None:
        return False, 0.0, 0.0

    eye_mid_x = (re.x + le.x) * 0.5
    eye_width = abs(le.x - re.x) + 1e-6
    yaw_ratio = (nose.x - eye_mid_x) / eye_width
    yaw_ok = abs(yaw_ratio) < _YAW_RATIO_MAX

    eye_mid_y = (re.y + le.y) * 0.5
    chin_span = chin.y - eye_mid_y
    if chin_span <= 1e-6:
        return False, yaw_ratio, 0.0

    pitch_n = (nose.y - eye_mid_y) / chin_span
    pitch_ok = _PITCH_N_MIN < pitch_n < _PITCH_N_MAX
    return bool(yaw_ok and pitch_ok), yaw_ratio, pitch_n


def _iris_centroid(lms: list, indices: tuple[int, ...]) -> Optional[tuple[float, float]]:
    xs = []
    ys = []
    for i in indices:
        p = _safe_landmark(lms, i)
        if p is None:
            return None
        xs.append(p.x)
        ys.append(p.y)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _ratio_in_span(value: float, a: float, b: float) -> Optional[float]:
    lo = min(a, b)
    hi = max(a, b)
    span = hi - lo
    if span <= 1e-6:
        return None
    return (value - lo) / span


def _eye_contact_iris(lms: list) -> Optional[tuple[float, float, float, float]]:
    """(h_left, v_left, h_right, v_right) normalized iris position per eye."""
    if len(lms) < _MIN_LANDMARKS_FOR_IRIS:
        return None

    ic_r = _iris_centroid(lms, _IRIS_RIGHT)
    ic_l = _iris_centroid(lms, _IRIS_LEFT)
    if ic_r is None or ic_l is None:
        return None

    ro = _safe_landmark(lms, _IDX_RIGHT_EYE_OUTER)
    ri = _safe_landmark(lms, _RIGHT_INNER)
    lo = _safe_landmark(lms, _IDX_LEFT_EYE_OUTER)
    li = _safe_landmark(lms, _LEFT_INNER)
    rtl = _safe_landmark(lms, _RIGHT_LID_TOP)
    rbl = _safe_landmark(lms, _RIGHT_LID_BOT)
    ltl = _safe_landmark(lms, _LEFT_LID_TOP)
    lbl = _safe_landmark(lms, _LEFT_LID_BOT)
    if None in (ro, ri, lo, li, rtl, rbl, ltl, lbl):
        return None

    hr = _ratio_in_span(ic_r[0], ro.x, ri.x)
    vr = _ratio_in_span(ic_r[1], rtl.y, rbl.y)
    hl = _ratio_in_span(ic_l[0], lo.x, li.x)
    vl = _ratio_in_span(ic_l[1], ltl.y, lbl.y)
    if hr is None or vr is None or hl is None or vl is None:
        return None

    return hl, vl, hr, vr


def _eye_contact(
    lms: list, head_forward: bool
) -> tuple[bool, Optional[tuple[float, float, float, float]], bool]:
    """Prototype iris-in-aperture check; fallback mirrors head_forward only."""
    ratios = _eye_contact_iris(lms)
    if ratios is None:
        return head_forward, None, True

    hl, vl, hr, vr = ratios
    ok_l = (
        _IRIS_H_BAND_LO <= hl <= _IRIS_H_BAND_HI
        and _IRIS_V_BAND_LO <= vl <= _IRIS_V_BAND_HI
    )
    ok_r = (
        _IRIS_H_BAND_LO <= hr <= _IRIS_H_BAND_HI
        and _IRIS_V_BAND_LO <= vr <= _IRIS_V_BAND_HI
    )
    return bool(ok_l and ok_r), ratios, False


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
                head_forward=False,
                eye_contact=False,
                looking_at_camera=False,
                raw_result=raw,
                debug_text="no face",
            )

        lms = raw.face_landmarks[0]
        head_forward, yaw_ratio, pitch_n = _head_forward(lms)
        eye_contact, eye_ratios, _used_fallback = _eye_contact(lms, head_forward)
        looking_at_camera = bool(head_forward and eye_contact)

        parts = [f"yaw_ratio={yaw_ratio:.2f}", f"pitch_n={pitch_n:.2f}"]
        if eye_ratios is not None:
            hl, vl, hr, vr = eye_ratios
            parts += [
                f"eye_x_L={hl:.2f}",
                f"eye_y_L={vl:.2f}",
                f"eye_x_R={hr:.2f}",
                f"eye_y_R={vr:.2f}",
                "iris",
            ]
        else:
            parts.append("eye_contact=fallback/no_iris")

        return FacePerceptionResult(
            face_detected=True,
            head_forward=head_forward,
            eye_contact=eye_contact,
            looking_at_camera=looking_at_camera,
            raw_result=raw,
            debug_text="|".join(parts),
        )

    def close(self) -> None:
        self._landmarker.close()
