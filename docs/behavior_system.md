# Behavior system

`behavior.py` is intentionally boring: **no perception imports**, no networking—only `behavior_for_state(state, variant?) → LampBehaviorCommand`. That constraint matters because anything consuming `LampBehaviorCommand` (twin, CSV logger, Sheets row formatter, future MCU firmware bridge) must agree on one schema.

## Command schema recap

`LampBehaviorCommand` carries:

- **Pose**: `pan_angle`, `tilt_angle` (degrees as commanded—not servo microseconds).
- **Light**: `light_color` (named token), `brightness` (0–1 scalar).
- **Identity**: `state`, `behavior_name`, `variant`.
- **Audit**: `motion_description`, `light_description`, `reason`.

Google Sheets copies those fields into columns alongside perception booleans, so **the sheet shows exactly what hardware would have been asked to do** on each logged tick (subject to logging interval).

## State → behavior mapping (summary table)

Angles below are the **defaults shipped in code**; they encode “dim withdrawn lamp” vs “upright attentive lamp,” etc.

| FSM state | `behavior_name` | Pan° | Tilt° | Light | Brightness | Purpose |
|-----------|-----------------|------|-------|-------|------------|---------|
| **ENGAGED** | `attentive` | 90 | 80 | green | 1.0 | User appears to attend—open, bright posture. |
| **DISENGAGED** | `withdrawn` | 90 | 115 | blue | 0.25 | User not attending—lower head, dim idle light. |
| **ATTENTION_SEEKING** | `attention_seek` | 90 | varies by variant | yellow / amber / pale tones | 0.75–0.95 | Prompt disengaged user with motion/light variety. |
| **COOLDOWN** | `cooldown` | 90 | 110 | purple | 0.18 | Cool down after seek—anti-nag. |
| **ANSWERING** | `answering` | 90 | 85 | amber | 0.9 | Visual tie-in while speaking / answering. |

Unknown states fall back to a neutral “unknown” command with dim white light—should never trigger during normal runs.

## Attention-seeking variants (exact defaults)

When FSM == `ATTENTION_SEEKING`, `variant` selects one row below (`behavior.py`):

| Variant | Pan° | Tilt° | Light token | Brightness | Motion/light idea |
|---------|------|-------|-------------|------------|-------------------|
| `curious_wiggle` | 90 | 90 | yellow | 0.95 | Side-to-side wiggle + bright pulse |
| `soft_pulse` | 90 | 105 | warm_yellow | 0.75 | Minimal pose shift; soft pulse |
| `peek_up` | 90 | 75 | amber | 0.85 | Tilts upward “checking in” |
| `side_glance` | 90 | 95 | pale_yellow | 0.80 | Side glance motion |
| `tiny_nod` | 90 | 90 | amber | 0.80 | Small nod pattern |

**Why variants exist:** if every disengagement produced identical motion, testers tuned it out. Pseudo-random selection (`state_manager`) trades mechanical realism for **noticeability without increasing CV complexity**.

## Cooldown as anti-annoyance

After attention-seeking fires, the lamp enters **COOLDOWN**: motion trims to near-zero, brightness drops to a calm purple band. Without this, a marginal gaze flutter would spam prompts—bad UX and bad science (behavior would dominate perception faults).

## Mapping to potential hardware

Interpretation for a physical build:

- `pan_angle` / `tilt_angle` → two PWM servos or stepper segments with calibrated zero references.
- `brightness` → PWM duty on warm-white + amber LED channels (color mixing depends on driver).
- `light_color` token → lookup table for RGB ratios until a calibrated spectral model exists.

The Three.js twin reads the **same numeric fields** from JSON—so discrepancies between “what sheet says” and “what viewer shows” narrow down to renderer bugs, not perception bugs.

## Logging angle

Because Sheets rows embed **behavior commands plus gaze booleans**, reviewers can correlate “what the lamp tried to do” with “what perception claimed about the face.” That is the **map_behaviour / proof-of-command-stream** story—parallel to the simulator JSON, not replacing it.
