# Evaluation methodology

Numbers summarized in `evaluation/submission_summary.md` come from logged CSVs (`evaluation/*.csv` when frozen, or `runtime/metrics/*.csv` during development).

## Engagement reliability

- **Expected**: operator key (`1` / `2`).
- **Predicted**: debounced binary gaze label embedded in `metrics.py` trial rows.
- **Accuracy**: exact match between those two strings.

ATTENTION_SEEKING / COOLDOWN / ANSWERING appear as contextual columns (`fsm_state`, `lamp_behavior`) but are **not** treated as engagement failures unless your experimental protocol says otherwise.

## Latency

| Field | Meaning |
|-------|---------|
| `perception_ms` | Face landmarker pass |
| `state_ms` | FSM update |
| `behavior_ms` | Command construction |
| `object_inference_ms` | Last worker-side YOLO duration (not charged to `total_loop_ms`) |
| `total_loop_ms` | End-to-end iteration excluding blocking on YOLO |

Medians in the summary used ~1000+ samples collected during interactive runs.

## Limits

Manual labels encode one operator’s judgment; inter-rater variance is unknown. Latency excludes USB stack jitter breakdown. Object memory accuracy (did YOLO label the right thing?) is orthogonal to engagement metrics.
