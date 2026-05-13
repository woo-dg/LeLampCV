# Perception pipeline

## Question we were actually answering

“Is this person **paying attention to the lamp / camera**, or only oriented toward it?” Those differ when someone reads a laptop, sketches on paper, or watches a second monitor.

## Engineering progression (what broke at each step)

### 1. Face-in-frame gate

First implementations boiled engagement down to **face detected**. That worked as a presence detector but not as engagement: anyone adjacent to the frame counted even when turned sideways.

### 2. Head direction / pose gates

Adding yaw-like thresholds helped reject extreme profiles, but **failed the laptop case**: torso and head still square to the webcam while eyes aim ~30° downward. The lamp looked “seen” when it was not.

### 3. Iris / eye-region ratios

We pushed gaze discrimination into **normalized iris positions relative to eyelid anchors** using MediaPipe Face Landmarker indices.

**Note on MediaPipe Iris:** older tutorials referenced a standalone **Iris Solution**. Current code follows the Tasks API **Face Landmarker**, which still exposes dense landmarks around each eye—functionally the iris proxy we need, just bundled differently.

### 4. Flicker without temporal filtering

Even with better gaze features, USB frames jittered: one dropout frame flipped booleans. The OpenCV HUD looked epileptic; the twin shook between poses.

**Mitigation:** rolling window consensus on the raw “looks at camera” predicate before the FSM reads it.

### 5. Binary overload during debugging

Mid-development there were experiments with richer discrete labels (multi-class engagement). They were impossible to bench consistently without ground-truth hardware.

**Temporary simplification:** treat downstream logic as **ENGAGED vs DISENGAGED** primitives plus higher-level lamp states. That separation made CSV trials meaningful again.

### 6. Debounce / hysteresis on the FSM

Smoothing fixed pixel noise but not **intent noise**—quick glances off-screen still triggered transitions.

**Mitigation:** asymmetric timers (faster engage acknowledgment, slower disengage) so single-frame spikes do not drop the user into attention-seeking choreography.

### 7. Calibration (`c` key)

Fixed absolute iris bands that worked on a laptop webcam failed on an external monitor sitting higher.

**Mitigation:** capture ~30 frames of ratios while the user actually looks at the lamp; classify gaze **relative to learned baseline offsets**.

## Signals in the shipped stack

| Signal | Source | Purpose |
|--------|--------|---------|
| Face detected | Landmarker success | Gate everything else. |
| Head forward | Landmark geometry | Reject obvious profile/no-show poses. |
| Iris ratios | Eye-region landmarks | Primary gaze proxy vs laptop drift. |
| `eye_contact` | Ratio thresholds / calibrated bands | Intermediate boolean for debugging. |
| `looking_at_camera` | Smoothed rolling consensus | Actual FSM input. |
| Debounced binary label | `state_manager` export | Metrics trials (`predicted` column). |

## Operational limits (honest)

- Low light blows up iris ratios; user sees “unknown” gaze modes in debug text.
- Thick glasses add reflections that violate assumptions baked into landmark ratios.
- Calibration drift happens if the user slouches mid-session—expected for a prototype desk setup.

## Evaluation hygiene

When logging trials, prefer **`n`** after the label settles—transition frames mix gaze truth with operator intent and inflate confusion without teaching anything about steady-state accuracy.
