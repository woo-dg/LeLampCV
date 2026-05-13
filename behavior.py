from dataclasses import dataclass


@dataclass
class LampBehaviorCommand:
    state: str
    behavior_name: str
    pan_angle: float
    tilt_angle: float
    light_color: str
    brightness: float
    motion_description: str
    light_description: str
    reason: str


def behavior_for_state(state: str) -> LampBehaviorCommand:
    if state == "ENGAGED":
        return LampBehaviorCommand(
            state=state,
            behavior_name="attentive",
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
            pan_angle=90.0,
            tilt_angle=115.0,
            light_color="blue",
            brightness=0.25,
            motion_description="head lowers slightly",
            light_description="dim blue light",
            reason="user is not actively looking toward the camera",
        )
    return LampBehaviorCommand(
        state=state,
        behavior_name="unknown",
        pan_angle=90.0,
        tilt_angle=90.0,
        light_color="white",
        brightness=0.1,
        motion_description="neutral",
        light_description="dim white light",
        reason="unrecognized state",
    )
