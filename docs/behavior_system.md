# Behavior system

`behavior.py` maps each high-level state to a **`LampBehaviorCommand`**: pan angle, tilt angle, light color keyword, brightness, optional attention variant, plus human-readable motion/light descriptions.

## Outputs

The command struct is written to `simulator/latest_behavior.json` every frame (when export is enabled). Anything consuming that file—the Three.js twin today, GPIO tomorrow—gets identical inputs.

## Attention seeking

When gaze stays disengaged long enough, the FSM enters **ATTENTION_SEEKING** with one of:

- `curious_wiggle`
- `soft_pulse`
- `peek_up`
- `side_glance`
- `tiny_nod`

Variants tweak tilt bias and brightness modulation in the simulator so repetitive prompting is less robotic.

## Cooldown

After attention-seeking runs, **COOLDOWN** suppresses another prompt for several seconds so the lamp does not nag continuously.

## Answering

While the lamp speaks or displays an answer timeout, the behavior layer forces **ANSWERING**: warmer amber light and a neutral friendly pose. That ties conversational output to something visible in both OpenCV and the twin.
