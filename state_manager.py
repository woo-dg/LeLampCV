from __future__ import annotations

ENGAGE_DEBOUNCE_SECONDS = 0.20
DISENGAGE_DEBOUNCE_SECONDS = 0.50


class EngagementStateManager:
    """Two-state ENGAGED/DISENGAGED with time debouncing on transitions."""

    def __init__(self) -> None:
        self._official = "DISENGAGED"
        self._candidate: str | None = None
        self._candidate_since: float | None = None

    def update(
        self,
        *,
        face_detected: bool,
        looking_at_camera: bool,
        current_time: float,
    ) -> str:
        raw_engaged = bool(face_detected and looking_at_camera)
        desired = "ENGAGED" if raw_engaged else "DISENGAGED"

        if desired == self._official:
            self._candidate = None
            self._candidate_since = None
            return self._official

        if self._candidate != desired:
            self._candidate = desired
            self._candidate_since = current_time
            return self._official

        assert self._candidate_since is not None
        elapsed = current_time - self._candidate_since
        if desired == "ENGAGED" and elapsed >= ENGAGE_DEBOUNCE_SECONDS:
            self._official = "ENGAGED"
            self._candidate = None
            self._candidate_since = None
        elif desired == "DISENGAGED" and elapsed >= DISENGAGE_DEBOUNCE_SECONDS:
            self._official = "DISENGAGED"
            self._candidate = None
            self._candidate_since = None

        return self._official
