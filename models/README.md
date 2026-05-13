# Model weights

Place YOLO weights here for object detection, for example:

- `yolov8s.pt` (default in code)

Ultralytics will download weights if the file is missing and you pass a hub name instead; this repo expects a local file path when present.

MediaPipe Face Landmarker (`face_landmarker.task`) also lives here; if absent, `perception.py` downloads it on first run.
