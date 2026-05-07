def engagement_state(has_detections: bool) -> str:
    return "ENGAGED" if has_detections else "DISENGAGED"
