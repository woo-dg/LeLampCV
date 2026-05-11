import time

import cv2

from perception import FacePerception
from state_manager import EngagementStateManager
from visualizer import draw_perception


def main() -> None:
    perception = FacePerception()
    state_manager = EngagementStateManager()
    webcam = cv2.VideoCapture(0)
    timestamp_ms = 0
    try:
        while webcam.isOpened():
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
            draw_perception(frame, perception_result, state)

            cv2.imshow("Webcam", frame)
            if cv2.waitKey(5) & 0xFF == ord("q"):
                break
    finally:
        webcam.release()
        perception.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
