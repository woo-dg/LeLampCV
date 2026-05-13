# Evaluation methodology

This document ties numbers to definitions so reviewers do not have to reverse-engineer the CSV schema.

## Binary engagement reliability

**Question measured:** Does debounced gaze-derived binary engagement match a human operator’s judgment?

| Quantity | Value |
|----------|-------|
| Total trials | **109** |
| Correct trials | **93** |
| Overall accuracy | **85.32%** |
| ENGAGED accuracy | **100.00%** over **19** trials |
| DISENGAGED accuracy | **82.22%** over **90** trials |

**Ground truth (`expected`):** keyboard keys `1` / `2` when the operator believes they are engaged vs disengaged with the lamp/camera.

**Prediction (`predicted`):** debounced binary label exported from `state_manager`—the same primitive that feeds metrics trials before attention choreography reinterpretation.

### Why ATTENTION_SEEKING / COOLDOWN / ANSWERING are not “wrong ENGAGED”

Those strings describe **lamp choreography** layered on top of gaze after timers fire. They appear in contextual CSV columns (`fsm_state`, `lamp_behavior`) so you can sanity-check *why* a pose looked weird, but they **do not** redefine the binary classifier outcome unless your protocol explicitly asks for multi-task scoring.

Misunderstanding this conflates **interaction design** with **perception accuracy** and makes headline percentages meaningless.

## Latency

All numbers below are **medians** from logged interactive sessions (see frozen summary):

| Metric | Median | Notes |
|--------|--------|-------|
| `perception_ms` | **13.28 ms** | Face Landmarker + smoothing inside main loop |
| `total_loop_ms` | **23.74 ms** | Whole iteration excluding blocking YOLO wait |
| `object_inference_ms` | **212.35 ms** | Recorded on async worker when completion observed |

**Critical definition:** `total_loop_ms` **does not** wait for YOLO to finish. Object inference runs concurrently; memory ingestion catches up shortly after detections land.

Supporting columns (`state_ms`, `behavior_ms`) stayed **sub-millisecond median** on logged hardware—mapping math is cheap compared to vision.

## Frozen vs generated summaries

During normal runs, `metrics.py` writes CSV fragments plus **`runtime/metrics/summary.md`** when you exit (`q`). That file is convenient for iteration but **mutates** every session.

**Submission-facing headline:** `evaluation/submission_summary.md` plus CSV copies under `evaluation/` remain the frozen snapshot for judges unless you deliberately refresh them after a new study.

## Reproducing logs

1. Run `python scripts/run_app.py`.
2. Use `1`/`2` to stamp expected labels; prefer `n` once gaze settles (~0.75 s guardrail).
3. Quit with `q` to flush Markdown summary.
4. Compare fresh CSV rows against keyboard intent; copy into `evaluation/` when locking a submission package.

## Honest limitations

- Single-operator labels—no inter-rater reliability study.
- Accuracy measures gaze alignment, not memory correctness or speech transcription fidelity.
- Latency excludes USB scheduler jitter and OS load spikes beyond what the CSV captured.

For procedural detail on labeling keys, see `evaluation/notes.md`.
