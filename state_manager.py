from __future__ import annotations

DISENGAGED_TO_ATTENTION_SECONDS = 3.0
ATTENTION_SEEKING_DURATION_SECONDS = 1.0
COOLDOWN_TO_IDLE_SECONDS = 15.0


class EngagementStateManager:
    """Tracks lamp engagement: IDLE → ENGAGED → DISENGAGED → ATTENTION_SEEKING → COOLDOWN → (optional) IDLE."""

    def __init__(self) -> None:
        self._state = "IDLE"
        self._disengaged_since: float | None = None
        self._attention_since: float | None = None
        self._cooldown_no_face_since: float | None = None

    def _clear_timers(self) -> None:
        self._disengaged_since = None
        self._attention_since = None
        self._cooldown_no_face_since = None

    def update(
        self,
        *,
        face_detected: bool,
        looking_at_camera: bool,
        current_time: float,
    ) -> str:
        engaged = bool(face_detected and looking_at_camera)

        if self._state == "IDLE":
            if engaged:
                self._state = "ENGAGED"
                self._clear_timers()
            return self._state

        if self._state == "ENGAGED":
            if engaged:
                return self._state
            self._state = "DISENGAGED"
            self._disengaged_since = current_time
            self._attention_since = None
            self._cooldown_no_face_since = None
            return self._state

        if self._state == "DISENGAGED":
            if engaged:
                self._state = "ENGAGED"
                self._clear_timers()
                return self._state
            if (
                self._disengaged_since is not None
                and (current_time - self._disengaged_since)
                >= DISENGAGED_TO_ATTENTION_SECONDS
            ):
                self._state = "ATTENTION_SEEKING"
                self._attention_since = current_time
                self._disengaged_since = None
            return self._state

        if self._state == "ATTENTION_SEEKING":
            if engaged:
                self._state = "ENGAGED"
                self._clear_timers()
                return self._state
            if (
                self._attention_since is not None
                and (current_time - self._attention_since)
                >= ATTENTION_SEEKING_DURATION_SECONDS
            ):
                self._state = "COOLDOWN"
                self._attention_since = None
                self._cooldown_no_face_since = (
                    current_time if not face_detected else None
                )
            return self._state

        if self._state == "COOLDOWN":
            if engaged:
                self._state = "ENGAGED"
                self._clear_timers()
                return self._state
            if not face_detected:
                if self._cooldown_no_face_since is None:
                    self._cooldown_no_face_since = current_time
                elif (
                    current_time - self._cooldown_no_face_since
                ) >= COOLDOWN_TO_IDLE_SECONDS:
                    self._state = "IDLE"
                    self._clear_timers()
            else:
                self._cooldown_no_face_since = None
            return self._state

        return self._state
