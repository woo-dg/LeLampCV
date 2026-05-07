import cv2


def draw_face_detections(frame, result) -> None:
    for detection in result.detections:
        bbox = detection.bounding_box
        x = bbox.origin_x
        y = bbox.origin_y
        w = bbox.width
        h = bbox.height
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)


def draw_engagement_state(frame, state: str) -> None:
    cv2.putText(
        frame,
        state,
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
    )
