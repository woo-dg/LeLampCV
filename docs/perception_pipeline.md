# Perception pipeline

## Question

What signals actually indicate someone is engaged with a desk lamp/camera, versus merely facing that direction?

## What we tried

1. **Face present + coarse head pose** — fast, but misleading: you can face the camera while reading a monitor slightly below eye line.
2. **Eye / iris landmarks** — MediaPipe Face Landmarker exposes iris-related indices even though older “Iris Solution” demos are gone. Ratios within each eye give a much stronger “looking here vs elsewhere” cue than nose yaw alone.
3. **Raw frame decisions** — noisy; lamp state flickered and the twin jittered.
4. **Temporal smoothing** — small sliding window over raw gaze booleans before committing.
5. **FSM debounce** — separate engage/disengage timers so brief glances do not flip outputs.
6. **Calibration** — fixed absolute iris bands failed across cameras; capturing a short baseline while the user looks at the lamp fixes most setups.

## Signals used in the final stack

- Face detected (landmarker succeeded).
- Head reasonably forward (yaw/pitch gates).
- Iris-derived horizontal/vertical ratios per eye.
- Optional calibrated baseline for gaze classification.
- Rolling temporal consensus (`looking_at_camera`).
- Debounced binary label fed to metrics (`debounced_engagement`).

## Limits

Lighting, glasses, and extreme head tilt still break iris ratios. That is why calibration is manual (`c` key) and metrics trials should avoid transition frames (`n` preferred over `m`).
