# Tradeoffs

1. **Digital twin vs hardware** — Building the expressive layer against Three.js + JSON avoided burning hardware time while gaze thresholds were still moving. The tradeoff is no real servo latency or mechanical noise yet.

2. **Head pose vs gaze** — Head pose is stable but ambiguous when eyes wander. Iris ratios cost CPU but cut false “engaged” positives.

3. **Fixed thresholds vs calibration** — Global constants are easier to document; calibration adds a setup step but survives different cameras.

4. **Per-frame vs smoothed decisions** — Smoothing delays truth by a few frames yet removes flicker that made both metrics and the twin unusable.

5. **YOLOv8n vs YOLOv8s** — Nano is lighter; small improves recall on cluttered desks at the price of VRAM/time. This repo defaults to **s** while isolating inference asynchronously.

6. **Sync vs async YOLO** — Blocking inference dominated loop time (~200 ms). Moving detection to a worker keeps interaction responsive; tradeoff is memory updates lag up to one interval.

7. **LLM-first vs memory-first Q&A** — Letting the LLM invent locations failed demos. Routing locations through JSONL first trades flexibility for truthfulness.

8. **Sheets vs simulator** — Sheets add latency variance and credentials overhead but give judges a raw event log without screen recording.

9. **Playful tone vs grounded facts** — Memory answers allow playful wording only after evidence exists; otherwise we risk confident hallucinations.

10. **Metrics scope** — Binary engagement accuracy ignores attention/cooldown artistry on purpose; those states are behaviors layered on top of gaze, not classification mistakes by default.
