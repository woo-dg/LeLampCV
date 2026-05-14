# Demo guide

Nothing in this repo hardcodes a canned demo sequence—the behaviors emerge from live gaze, timers, YOLO detections, and microphone input. This checklist exists so **recorded video can prove each challenge requirement** without improvising explanations mid-take.

## Preconditions

- Two terminals + browser twin (`README.md` Running section).
- Quiet-enough room for always-on ASR; typing still works if audio fails.
- Prefer **common YOLO COCO objects** (bottle, cup, chair, phone, laptop). Exotic props may never receive a class label.
- Run `python scripts/test_tts.py` once before recording so edge-tts/pygame (or pyttsx3 fallback) works on your machine.

## Reproducible checklist (challenge coverage)

1. **Simulator running** — `python -m http.server` inside `simulator/`; verify JSON polls succeed (`Pipeline` card updates).
2. **Calibrate gaze (`c`)** — hold a neutral “looking at lamp/camera” pose until status reads calibrated.
3. **Show ENGAGED** — intentional eye contact; confirm overlay + twin green-attentive posture.
4. **Show DISENGAGED** — deliberate gaze away; confirm dim withdrawn pole + twin state text.
5. **Attention-seeking** — remain disengaged ~few seconds until motion/light variant triggers; note variant label on HUD/twin.
6. **Memory formation** — place object in frame until terminal prints `memory saved: <label> at <bucket>`.
7. **Move object off-camera** — proves recall is not “currently visible cheating.”
8. **Voice recall** — ask your recall question aloud (mic listens continuously; no key); listen for TTS grounded answer.
9. **Twin correlation** — observe **ANSWERING** behavior while lamp speaks; conversation card flips to memory mode / badge.
10. **Evidence trail** — optionally screen-record Sheets rows (`map_behaviour`) scrolling with timestamps + pan/tilt/light columns, or show CSV snippets under `evaluation/`.

## What reviewers learn from each step

| Step | Proves |
|------|--------|
| 3–4 | Gaze pipeline + smoothing behave |
| 5 | Higher-level behavior choreography fires off gaze timers |
| 6–9 | Async vision → JSONL → memory-first conversation → audio works |
| 10 | External audit matches simulator JSON (same command stream) |

## Tips that save retakes

- The OpenCV window is **mirrored** like a selfie preview; your left/right matches what the model sees.
- Avoid backlighting—iris ratios saturate fast.
- After calibration, **do not** change seated height dramatically mid-demo.
- If ASR mis-hears, repeat slowly or fall back to typed stdin questions—the routing logic is identical.

This guide does not script wording; it only guarantees you captured **engagement, attention behavior, memory write, memory recall, and correlated twin motion** in one continuous take.
