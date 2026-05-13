# Evaluation deliverables

Formal artifacts for the SW/CV challenge: engagement reliability and latency.

## What is here

- `submission_summary.md` — headline numbers and definitions.
- `latency_log.csv` / `engagement_trials.csv` — raw logs from a live session when present.
- `notes.md` — how trials were labeled and how to reproduce.

## Engagement metric

**Binary engagement** is **ENGAGED** vs **DISENGAGED**, derived from debounced gaze (`predicted` in the CSV). That is separate from **ATTENTION_SEEKING**, **COOLDOWN**, or **ANSWERING**, which are lamp behavior states driven by the same perception signal plus timers.

## Latency

Main-loop latency samples (`total_loop_ms`, etc.) do **not** block on YOLO. Object inference runs in a background worker; see `object_inference_ms` in the latency CSV.

## Regenerating CSVs

Run `python scripts/run_app.py`, use keyboard metrics controls (`1`, `2`, `n`, …), then quit with `q`. New CSVs and `runtime/metrics/summary.md` are written automatically. Copy or archive those files here if you want a frozen submission snapshot.
