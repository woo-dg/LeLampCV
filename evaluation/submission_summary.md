# Evaluation Summary

## Binary Engagement Reliability

- Predicted column uses debounced binary gaze: ENGAGED vs DISENGAGED.
- ATTENTION_SEEKING, COOLDOWN, and ANSWERING are behavior states, not failures of binary engagement.

- total trials: 109
- correct trials: 93
- overall accuracy: 85.32%

- accuracy by expected class:
  - ENGAGED: 100.00% (19 trials)
  - DISENGAGED: 82.22% (90 trials)

- trials logged under FSM behavior state:
  - ATTENTION_SEEKING: 16
  - COOLDOWN: 33
  - DISENGAGED: 25
  - ENGAGED: 35

## Latency

Main-loop samples exclude blocking YOLO time. object_inference_ms is measured on the background worker.

- perception median: 13.28 ms
- total loop median: 23.74 ms
- object inference median: 212.35 ms
- state and behavior mapping were both under 1 ms median

## Notes

Trials were manually labeled using keyboard controls during live webcam testing.
YOLO runs asynchronously, so total_loop_ms reflects the camera/perception path without blocking on object inference.
