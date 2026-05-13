# Evaluation notes

## Manual labeling

Ground-truth **ENGAGED** / **DISENGAGED** was set with keyboard shortcuts while watching the webcam feed and the on-screen debug overlay. The model’s **predicted** column is the debounced binary gaze label recorded at trial log time.

This is a pragmatic bench test: it measures whether the perception stack agrees with the operator’s judgment under the same lighting and desk layout used during development.

## Controls used

| Key | Action |
|-----|--------|
| `c` | Start gaze calibration (look at the lamp/camera) |
| `r` | Reset calibration |
| `1` | Expected label **ENGAGED** (for metrics) |
| `2` | Expected label **DISENGAGED** |
| `0` | Clear expected label |
| `n` | Log trial only if the expected label has been stable ≥ ~0.75 s |
| `m` | Force log (prints a warning if still settling) |
| `q` | Quit (writes `runtime/metrics/summary.md`) |

## Behavior states vs binary engagement

The finite-state lamp adds **ATTENTION_SEEKING** and **COOLDOWN** on top of raw gaze. For evaluation we compare **expected** vs **predicted** binary engagement only. A trial taken while the FSM shows ATTENTION_SEEKING does **not** mean the gaze model “failed” if the user still labels the moment as DISENGAGED.

## Reproduce

1. `python scripts/run_app.py`
2. Calibrate (`c`), then collect segments where you know you are looking at vs away from the camera.
3. Press `1` or `2`, wait briefly, press `n` to append a row to `runtime/metrics/engagement_trials.csv`.
4. Latency rows append about once per second to `runtime/metrics/latency_log.csv`.
5. Quit with `q` and inspect `runtime/metrics/summary.md` or copy CSVs into `evaluation/` for submission.
