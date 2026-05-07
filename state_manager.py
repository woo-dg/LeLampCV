def engagement_state(face_detected: bool, looking_at_camera: bool) -> str:
    if face_detected and looking_at_camera:
        return "ENGAGED"
    return "DISENGAGED"
