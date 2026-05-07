from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class FacePerception:
    def __init__(self) -> None:
        model_path = Path(__file__).resolve().parent / "models" / "blaze_face_short_range.tflite"
        if not model_path.is_file():
            raise FileNotFoundError(f"Missing model: {model_path}")
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_detection_confidence=0.5,
        )
        self._detector = vision.FaceDetector.create_from_options(options)

    def detect(self, frame_rgb, timestamp_ms: int):
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        return self._detector.detect_for_video(mp_image, timestamp_ms)

    def close(self) -> None:
        self._detector.close()
