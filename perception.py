import urllib.request
from collections import deque
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

_CALIBRATION_TARGET_FRAMES = 30

_YAW_RATIO_MAX = 0.35
_PITCH_N_MIN = 0.12
_PITCH_N_MAX = 0.72

_IRIS_H_BAND_LO = 0.36
_IRIS_H_BAND_HI = 0.64

_IRIS_V_BAND_LO = 0.43
_IRIS_V_BAND_HI = 0.57

_CALIBRATED_H_TOL = 0.14
_CALIBRATED_V_TOL = 0.10

_GAZE_CAL_DV_UP = 0.07
_GAZE_CAL_DV_DOWN = 0.07
_GAZE_CAL_DH_LR = 0.12

_SMOOTHING_WINDOW = 8
_SMOOTHING_MIN_TRUE = 5


@dataclass
class FacePerceptionResult:
    face_detected: bool
    head_forward: bool
    eye_contact: bool
    looking_at_camera: bool
    gaze_direction: str
    raw_result: object
    debug_text: str
    calibrated: bool
    calibration_text: str


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


def _eye_contact_iris_ratios(
    lms: list,
) -> Optional[tuple[float, float, float, float]]:
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


def _gaze_direction_from_ratios_fixed(
    hl: float, vl: float, hr: float, vr: float
) -> str:
    if vl < _IRIS_V_BAND_LO and vr < _IRIS_V_BAND_LO:
        return "up"
    if vl > _IRIS_V_BAND_HI and vr > _IRIS_V_BAND_HI:
        return "down"
    if not (
        _IRIS_H_BAND_LO <= hl <= _IRIS_H_BAND_HI
        and _IRIS_H_BAND_LO <= hr <= _IRIS_H_BAND_HI
    ):
        return "left_or_right"
    return "center"


def _gaze_direction_from_baseline(
    hl: float,
    vl: float,
    hr: float,
    vr: float,
    bl_hl: float,
    bl_vl: float,
    bl_hr: float,
    bl_vr: float,
) -> str:
    dv = ((vl - bl_vl) + (vr - bl_vr)) * 0.5
    if dv < -_GAZE_CAL_DV_UP:
        return "up"
    if dv > _GAZE_CAL_DV_DOWN:
        return "down"
    dh_max = max(abs(hl - bl_hl), abs(hr - bl_hr))
    if dh_max > _GAZE_CAL_DH_LR:
        return "left_or_right"
    return "center"


def _eye_contact_fixed(
    hl: float, vl: float, hr: float, vr: float, gaze_direction: str
) -> bool:
    h_ok_l = _IRIS_H_BAND_LO <= hl <= _IRIS_H_BAND_HI
    h_ok_r = _IRIS_H_BAND_LO <= hr <= _IRIS_H_BAND_HI
    v_ok_l = _IRIS_V_BAND_LO <= vl <= _IRIS_V_BAND_HI
    v_ok_r = _IRIS_V_BAND_LO <= vr <= _IRIS_V_BAND_HI
    return bool(
        gaze_direction == "center" and h_ok_l and h_ok_r and v_ok_l and v_ok_r
    )


def _eye_contact_calibrated(
    hl: float,
    vl: float,
    hr: float,
    vr: float,
    bl_hl: float,
    bl_vl: float,
    bl_hr: float,
    bl_vr: float,
    gaze_direction: str,
) -> bool:
    if gaze_direction != "center":
        return False
    return (
        abs(hl - bl_hl) <= _CALIBRATED_H_TOL
        and abs(vl - bl_vl) <= _CALIBRATED_V_TOL
        and abs(hr - bl_hr) <= _CALIBRATED_H_TOL
        and abs(vr - bl_vr) <= _CALIBRATED_V_TOL
    )


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
        self._looking_smooth: deque[bool] = deque(maxlen=_SMOOTHING_WINDOW)

        self._calibrating = False
        self._calibrated = False
        self._calibration_samples: list[tuple[float, float, float, float]] = []
        self._baseline: Optional[tuple[float, float, float, float]] = None

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    @property
    def calibration_status_text(self) -> str:
        if self._calibrated:
            return "calibrated"
        if self._calibrating:
            return f"calibrating {len(self._calibration_samples)}/{_CALIBRATION_TARGET_FRAMES}"
        return "not calibrated"

    def start_calibration(self) -> None:
        self._calibrating = True
        self._calibrated = False
        self._baseline = None
        self._calibration_samples = []

    def reset_calibration(self) -> None:
        self._calibrating = False
        self._calibrated = False
        self._baseline = None
        self._calibration_samples = []

    def _finalize_calibration_if_ready(self) -> None:
        if len(self._calibration_samples) < _CALIBRATION_TARGET_FRAMES:
            return
        xs = list(zip(*self._calibration_samples))
        self._baseline = tuple(sum(col) / len(col) for col in xs)
        self._calibrated = True
        self._calibrating = False
        self._calibration_samples = []

    def detect(self, frame_rgb, timestamp_ms: int) -> FacePerceptionResult:
        cal_text = self.calibration_status_text
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        raw = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        if not raw.face_landmarks:
            self._looking_smooth.clear()
            return FacePerceptionResult(
                face_detected=False,
                head_forward=False,
                eye_contact=False,
                looking_at_camera=False,
                gaze_direction="none",
                raw_result=raw,
                debug_text="no face",
                calibrated=self._calibrated,
                calibration_text=cal_text,
            )

        lms = raw.face_landmarks[0]
        head_forward, yaw_ratio, pitch_n = _head_forward(lms)
        eye_ratios = _eye_contact_iris_ratios(lms)

        if (
            self._calibrating
            and head_forward
            and eye_ratios is not None
        ):
            self._calibration_samples.append(eye_ratios)
            self._finalize_calibration_if_ready()

        if eye_ratios is None:
            eye_contact = head_forward
            gaze_direction = "unknown"
            mode_tag = "mode=fallback/no_iris"
        elif self._calibrated and self._baseline is not None:
            bl_hl, bl_vl, bl_hr, bl_vr = self._baseline
            hl, vl, hr, vr = eye_ratios
            gaze_direction = _gaze_direction_from_baseline(
                hl, vl, hr, vr, bl_hl, bl_vl, bl_hr, bl_vr
            )
            eye_contact = _eye_contact_calibrated(
                hl, vl, hr, vr, bl_hl, bl_vl, bl_hr, bl_vr, gaze_direction
            )
            mode_tag = "mode=iris_calibrated"
        else:
            hl, vl, hr, vr = eye_ratios
            gaze_direction = _gaze_direction_from_ratios_fixed(hl, vl, hr, vr)
            eye_contact = _eye_contact_fixed(hl, vl, hr, vr, gaze_direction)
            mode_tag = "mode=iris_fixed"

        raw_looking = bool(head_forward and eye_contact)
        self._looking_smooth.append(raw_looking)
        n_true = sum(1 for x in self._looking_smooth if x)
        looking_at_camera = n_true >= _SMOOTHING_MIN_TRUE

        parts = [
            f"yaw_ratio={yaw_ratio:.2f}",
            f"pitch_n={pitch_n:.2f}",
            f"gaze_direction={gaze_direction}",
        ]
        if eye_ratios is not None:
            hl, vl, hr, vr = eye_ratios
            parts += [
                f"eye_x_L={hl:.2f}",
                f"eye_y_L={vl:.2f}",
                f"eye_x_R={hr:.2f}",
                f"eye_y_R={vr:.2f}",
            ]
            if self._baseline is not None:
                bh = self._baseline
                parts.append(
                    f"baseline_L=({bh[0]:.2f},{bh[1]:.2f}) R=({bh[2]:.2f},{bh[3]:.2f})"
                )
        parts.append(mode_tag)
        parts.append(f"raw_looking={raw_looking}")

        cal_text = self.calibration_status_text
        return FacePerceptionResult(
            face_detected=True,
            head_forward=head_forward,
            eye_contact=eye_contact,
            looking_at_camera=looking_at_camera,
            gaze_direction=gaze_direction,
            raw_result=raw,
            debug_text="|".join(parts),
            calibrated=self._calibrated,
            calibration_text=cal_text,
        )

    def close(self) -> None:
        self._landmarker.close()
