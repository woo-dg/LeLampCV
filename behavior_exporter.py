from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from behavior import LampBehaviorCommand


def export_behavior_command(
    command: LampBehaviorCommand,
    path: str = "simulator/latest_behavior.json",
) -> None:
    """Write latest lamp behavior as JSON for the Three.js simulator (never raises)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": command.state,
            "behavior_name": command.behavior_name,
            "pan_angle": command.pan_angle,
            "tilt_angle": command.tilt_angle,
            "light_color": command.light_color,
            "brightness": command.brightness,
            "motion_description": command.motion_description,
            "light_description": command.light_description,
            "reason": command.reason,
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except Exception as exc:
        print(f"Warning: behavior export failed ({type(exc).__name__})")
