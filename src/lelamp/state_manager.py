from __future__ import annotations

import random
from dataclasses import dataclass

ENGAGE_DEBOUNCE_SECONDS = 0.20
DISENGAGE_DEBOUNCE_SECONDS = 0.50

DISENGAGED_TO_ATTENTION_SECONDS = 3.0
ATTENTION_SEEKING_DURATION_SECONDS = 2.0
COOLDOWN_SECONDS = 8.0

_ATTENTION_VARIANTS: tuple[str, ...] = (
    "curious_wiggle",
    "soft_pulse",
    "peek_up",
    "side_glance",
    "tiny_nod",
)


@dataclass(frozen=True)
class EngagementUpdateResult:
    state: str
    attention_variant: str
    debounced_engagement: str


class EngagementStateManager:
    """ENGAGED / DISENGAGED / ATTENTION_SEEKING / COOLDOWN with debounced gaze."""

    def __init__(self) -> None:
        self._debounced_engagement: str = "DISENGAGED"
        self._candidate: str | None = None
        self._candidate_since: float | None = None

        self._had_engagement: bool = False
        self._phase: str = "DISENGAGED"
        self._disengaged_since: float | None = None
        self._attention_since: float | None = None
        self._cooldown_since: float | None = None
        self._attention_variant: str = ""
        self._last_picked_variant: str = ""

    @property
    def current_attention_variant(self) -> str:
        return self._attention_variant if self._phase == "ATTENTION_SEEKING" else ""

    def _pick_attention_variant(self) -> str:
        choices = [v for v in _ATTENTION_VARIANTS if v != self._last_picked_variant]
        if not choices:
            choices = list(_ATTENTION_VARIANTS)
        pick = random.choice(choices)
        self._last_picked_variant = pick
        return pick

    def _update_debounced_engagement(
        self,
        *,
        face_detected: bool,
        looking_at_camera: bool,
        current_time: float,
    ) -> str:
        raw_engaged = bool(face_detected and looking_at_camera)
        desired = "ENGAGED" if raw_engaged else "DISENGAGED"

        if desired == self._debounced_engagement:
            self._candidate = None
            self._candidate_since = None
            return self._debounced_engagement

        if self._candidate != desired:
            self._candidate = desired
            self._candidate_since = current_time
            return self._debounced_engagement

        assert self._candidate_since is not None
        elapsed = current_time - self._candidate_since
        if desired == "ENGAGED" and elapsed >= ENGAGE_DEBOUNCE_SECONDS:
            self._debounced_engagement = "ENGAGED"
            self._candidate = None
            self._candidate_since = None
        elif desired == "DISENGAGED" and elapsed >= DISENGAGE_DEBOUNCE_SECONDS:
            self._debounced_engagement = "DISENGAGED"
            self._candidate = None
            self._candidate_since = None

        return self._debounced_engagement

    def _clear_phase_timers(self) -> None:
        self._phase = "DISENGAGED"
        self._disengaged_since = None
        self._attention_since = None
        self._cooldown_since = None
        self._attention_variant = ""

    def update(
        self,
        *,
        face_detected: bool,
        looking_at_camera: bool,
        current_time: float,
    ) -> EngagementUpdateResult:
        engagement = self._update_debounced_engagement(
            face_detected=face_detected,
            looking_at_camera=looking_at_camera,
            current_time=current_time,
        )

        if engagement == "ENGAGED":
            self._had_engagement = True
            self._clear_phase_timers()
            return EngagementUpdateResult("ENGAGED", "", engagement)

        assert engagement == "DISENGAGED"

        if self._phase == "DISENGAGED":
            if self._disengaged_since is None:
                self._disengaged_since = current_time
            if not self._had_engagement:
                return EngagementUpdateResult("DISENGAGED", "", engagement)
            if (
                current_time - self._disengaged_since
                >= DISENGAGED_TO_ATTENTION_SECONDS
            ):
                self._phase = "ATTENTION_SEEKING"
                self._attention_since = current_time
                self._attention_variant = self._pick_attention_variant()
                return EngagementUpdateResult(
                    "ATTENTION_SEEKING",
                    self._attention_variant,
                    engagement,
                )
            return EngagementUpdateResult("DISENGAGED", "", engagement)

        if self._phase == "ATTENTION_SEEKING":
            assert self._attention_since is not None
            if (
                current_time - self._attention_since
                >= ATTENTION_SEEKING_DURATION_SECONDS
            ):
                self._phase = "COOLDOWN"
                self._cooldown_since = current_time
                self._attention_variant = ""
                return EngagementUpdateResult("COOLDOWN", "", engagement)
            return EngagementUpdateResult(
                "ATTENTION_SEEKING",
                self._attention_variant,
                engagement,
            )

        if self._phase == "COOLDOWN":
            assert self._cooldown_since is not None
            if current_time - self._cooldown_since >= COOLDOWN_SECONDS:
                self._phase = "DISENGAGED"
                self._disengaged_since = current_time
                self._attention_since = None
                self._cooldown_since = None
                return EngagementUpdateResult("DISENGAGED", "", engagement)
            return EngagementUpdateResult("COOLDOWN", "", engagement)

        return EngagementUpdateResult("DISENGAGED", "", self._debounced_engagement)
