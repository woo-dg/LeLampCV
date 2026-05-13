import time

import cv2

from behavior import behavior_for_state
from behavior_exporter import export_behavior_command
from google_sheets_logger import GoogleSheetsBehaviorLogger
from memory import ObjectMemory
from object_perception import ObjectPerception, ObjectPerceptionResult
from perception import FacePerception
from state_manager import EngagementStateManager
from visualizer import draw_perception

ENABLE_GOOGLE_SHEETS_LOGGING = True
ENABLE_BEHAVIOR_EXPORT = True
ENABLE_PERCEPTION_DEBUG = True
ENABLE_OBJECT_DETECTION = True
OBJECT_DETECTION_INTERVAL_SECONDS = 1.0

CREDENTIALS_PATH = "map-behaviour-52671793f4cb.json"
SPREADSHEET_ID = "1bUHcBiV1oSGSghiYDUw43URHy4uTthYtjHOCfnwsJgg"
LOG_INTERVAL_SECONDS = 0.5

_FPS_SMOOTH_ALPHA = 0.15
_PERF_PRINT_INTERVAL_S = 3.0


def main() -> None:
    perception = FacePerception()
    state_manager = EngagementStateManager()
    sheet_logger = (
        GoogleSheetsBehaviorLogger(CREDENTIALS_PATH, SPREADSHEET_ID)
        if ENABLE_GOOGLE_SHEETS_LOGGING
        else None
    )
    object_perception = ObjectPerception() if ENABLE_OBJECT_DETECTION else None
    object_memory = ObjectMemory()
    object_result = ObjectPerceptionResult(
        objects=[],
        debug_text="object detection off"
        if not ENABLE_OBJECT_DETECTION
        else "waiting…",
    )
    last_object_detect_time = 0.0

    webcam = cv2.VideoCapture(0)
    timestamp_ms = 0
    last_log_time = 0.0

    fps_smooth = 0.0
    last_frame_ms = 0.0
    last_perf_print = 0.0

    try:
        while webcam.isOpened():
            t_loop = time.perf_counter()

            success, frame = webcam.read()
            if not success:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp_ms += 33
            perception_result = perception.detect(frame_rgb, timestamp_ms)
            state = state_manager.update(
                face_detected=perception_result.face_detected,
                looking_at_camera=perception_result.looking_at_camera,
                current_time=time.time(),
            )
            behavior_command = behavior_for_state(state)
            if ENABLE_BEHAVIOR_EXPORT:
                export_behavior_command(behavior_command)

            now = time.time()
            if (
                sheet_logger is not None
                and sheet_logger.enabled
                and (now - last_log_time) >= LOG_INTERVAL_SECONDS
            ):
                sheet_logger.append_row(
                    state=state,
                    cmd=behavior_command,
                    perception=perception_result,
                )
                last_log_time = now

            if (
                object_perception is not None
                and (now - last_object_detect_time) >= OBJECT_DETECTION_INTERVAL_SECONDS
            ):
                try:
                    object_result = object_perception.detect(frame)
                except Exception as exc:
                    print(
                        f"Warning: object detection failed ({type(exc).__name__}: {exc})"
                    )
                else:
                    object_memory.add_sightings(object_result.objects, state)
                last_object_detect_time = now

            elapsed = time.perf_counter() - t_loop
            last_frame_ms = elapsed * 1000.0
            inst_fps = 1.0 / elapsed if elapsed > 1e-9 else 0.0
            if fps_smooth <= 0.0:
                fps_smooth = inst_fps
            else:
                fps_smooth = (
                    _FPS_SMOOTH_ALPHA * inst_fps
                    + (1.0 - _FPS_SMOOTH_ALPHA) * fps_smooth
                )

            if ENABLE_PERCEPTION_DEBUG:
                if now - last_perf_print >= _PERF_PRINT_INTERVAL_S:
                    print(
                        f"perf: FPS ~ {fps_smooth:.1f}  frame_ms ~ {last_frame_ms:.1f}"
                    )
                    last_perf_print = now

            draw_perception(
                frame,
                perception_result,
                state,
                fps=fps_smooth if ENABLE_PERCEPTION_DEBUG else None,
                frame_ms=last_frame_ms if ENABLE_PERCEPTION_DEBUG else None,
                show_debug=ENABLE_PERCEPTION_DEBUG,
                object_result=object_result if ENABLE_OBJECT_DETECTION else None,
            )

            cv2.imshow("Webcam", frame)
            key = cv2.waitKey(5) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                perception.start_calibration()
            elif key == ord("r"):
                perception.reset_calibration()
    finally:
        if sheet_logger is not None:
            sheet_logger.close_session()
        webcam.release()
        perception.close()
        if object_perception is not None:
            object_perception.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
