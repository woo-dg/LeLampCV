from dataclasses import dataclass
from typing import Optional


@dataclass
class LampBehaviorCommand:
    state: str
    behavior_name: str
    variant: str
    pan_angle: float
    tilt_angle: float
    light_color: str
    brightness: float
    motion_description: str
    light_description: str
    reason: str


def _attention_seek_command(variant: str) -> LampBehaviorCommand:
    v = variant or "curious_wiggle"
    if v == "curious_wiggle":
        return LampBehaviorCommand(
            state="ATTENTION_SEEKING",
            behavior_name="attention_seek",
            variant="curious_wiggle",
            pan_angle=90.0,
            tilt_angle=90.0,
            light_color="yellow",
            brightness=0.95,
            motion_description="small curious side-to-side wiggle",
            light_description="bright yellow attention pulse",
            reason="user stayed disengaged, so lamp tries a subtle wiggle",
        )
    if v == "soft_pulse":
        return LampBehaviorCommand(
            state="ATTENTION_SEEKING",
            behavior_name="attention_seek",
            variant="soft_pulse",
            pan_angle=90.0,
            tilt_angle=105.0,
            light_color="warm_yellow",
            brightness=0.75,
            motion_description="minimal movement with soft light pulse",
            light_description="warm pulsing light",
            reason="user stayed disengaged, so lamp tries a gentle light cue",
        )
    if v == "peek_up":
        return LampBehaviorCommand(
            state="ATTENTION_SEEKING",
            behavior_name="attention_seek",
            variant="peek_up",
            pan_angle=90.0,
            tilt_angle=75.0,
            light_color="amber",
            brightness=0.85,
            motion_description="lamp peeks upward toward the user",
            light_description="warm amber check-in light",
            reason="user stayed disengaged, so lamp looks up to check in",
        )
    if v == "side_glance":
        return LampBehaviorCommand(
            state="ATTENTION_SEEKING",
            behavior_name="attention_seek",
            variant="side_glance",
            pan_angle=90.0,
            tilt_angle=95.0,
            light_color="pale_yellow",
            brightness=0.8,
            motion_description="lamp glances side to side",
            light_description="soft pale yellow light",
            reason="user stayed disengaged, so lamp glances subtly",
        )
    if v == "tiny_nod":
        return LampBehaviorCommand(
            state="ATTENTION_SEEKING",
            behavior_name="attention_seek",
            variant="tiny_nod",
            pan_angle=90.0,
            tilt_angle=90.0,
            light_color="amber",
            brightness=0.8,
            motion_description="small nodding motion",
            light_description="warm nodding response light",
            reason="user stayed disengaged, so lamp gives a tiny nod",
        )
    return _attention_seek_command("curious_wiggle")


def behavior_for_state(
    state: str,
    variant: Optional[str] = None,
) -> LampBehaviorCommand:
    v = (variant or "").strip()
    if state == "ENGAGED":
        return LampBehaviorCommand(
            state=state,
            behavior_name="attentive",
            variant="",
            pan_angle=90.0,
            tilt_angle=80.0,
            light_color="green",
            brightness=1.0,
            motion_description="head faces user",
            light_description="bright green light",
            reason="user is detected and looking toward the camera",
        )
    if state == "DISENGAGED":
        return LampBehaviorCommand(
            state=state,
            behavior_name="withdrawn",
            variant="",
            pan_angle=90.0,
            tilt_angle=115.0,
            light_color="blue",
            brightness=0.25,
            motion_description="head lowers slightly",
            light_description="dim blue light",
            reason="user is not actively looking toward the camera",
        )
    if state == "ANSWERING":
        return LampBehaviorCommand(
            state=state,
            behavior_name="answering",
            variant="",
            pan_angle=90.0,
            tilt_angle=85.0,
            light_color="amber",
            brightness=0.9,
            motion_description="head faces user while answering",
            light_description="warm pulsing answer light",
            reason="lamp is responding to a memory question",
        )
    if state == "COOLDOWN":
        return LampBehaviorCommand(
            state=state,
            behavior_name="cooldown",
            variant="",
            pan_angle=90.0,
            tilt_angle=110.0,
            light_color="purple",
            brightness=0.18,
            motion_description="lamp stays calm after trying to re-engage",
            light_description="dim purple cooldown light",
            reason=(
                "lamp recently attempted attention-seeking and is waiting "
                "before trying again"
            ),
        )
    if state == "ATTENTION_SEEKING":
        return _attention_seek_command(v)
    return LampBehaviorCommand(
        state=state,
        behavior_name="unknown",
        variant="",
        pan_angle=90.0,
        tilt_angle=90.0,
        light_color="white",
        brightness=0.1,
        motion_description="neutral",
        light_description="dim white light",
        reason="unrecognized state",
    )
