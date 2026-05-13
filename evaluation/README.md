# Evaluation deliverables

This folder is the **frozen submission packet** for reliability + latency claims. It exists separately from `runtime/metrics/` so judges are not asked to diff gitignored scratch logs against whatever happened last night.

## Contents

| File | Role |
|------|------|
| `submission_summary.md` | Numbers + definitions copied for reviewers (does not auto-update). |
| `latency_log.csv` | Raw main-loop + worker inference timings captured during the logged session. |
| `engagement_trials.csv` | Keyboard-ground-truth trials vs debounced gaze predictions. |
| `notes.md` | Exact keys pressed, settle-time guidance, interpretation caveats. |

## Binary engagement reliability (frozen headline)

- **109** trials, **93** correct → **85.32%** overall  
- **ENGAGED:** **100.00%** (19 trials)  
- **DISENGAGED:** **82.22%** (90 trials)  

`predicted` encodes **debounced gaze binary engagement**, not “whatever lamp animation is playing.” ATTENTION_SEEKING / COOLDOWN / ANSWERING are lamp behaviors captured as extra columns for context—they are **not** treated as classifier failures when ground truth stays DISENGAGED.

## Latency (frozen headline)

| Metric | Median |
|--------|--------|
| Perception (`perception_ms`) | **13.28 ms** |
| Total loop (`total_loop_ms`) | **23.74 ms** |
| Async object inference (`object_inference_ms`) | **212.35 ms** |

`total_loop_ms` excludes blocking on YOLO; inference runs on a worker thread and lands later in memory.

## Relationship to `runtime/metrics/`

Active development continuously appends CSV rows under `runtime/metrics/` and overwrites `summary.md` when the app exits cleanly. That directory is **gitignored** because it is machine-local noise.

**Policy:** when you finish an evaluation session worth submitting, copy the CSV snippets (or entire files) here and refresh `submission_summary.md` if numbers shift materially.

## Methodology pointers

- Definitions + limitations: `docs/evaluation.md`
- Labeling protocol: `notes.md`
- Full system context (why async inference exists): `docs/system_design.md`
