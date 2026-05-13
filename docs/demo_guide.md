# Demo guide

Checklist for recording or live judging:

1. Terminal A: `python scripts/run_app.py`
2. Terminal B: `cd simulator` then `python -m http.server 8000`
3. Browser: open `http://localhost:8000`
4. In the OpenCV window, press `c` and hold a neutral “looking at the lamp” pose until calibration finishes.
5. Look toward the camera → confirm **ENGAGED** state / green-ish cue in overlay + twin.
6. Look away → **DISENGAGED** / dimmer twin.
7. Stay disengaged several seconds → attention-seeking variant triggers (motion/light pulse).
8. Present an object clearly (e.g., bottle) until the console prints `memory saved: …`.
9. Remove or obscure the object.
10. Press `v`, ask aloud “where is my bottle?” (or type the question in the terminal feeding stdin).
11. Listen for TTS; watch twin switch to **ANSWERING** while JSON cards update.
12. Optionally show `evaluation/submission_summary.md` or CSV previews for judges.

**Tip:** mute competing audio, face a diffuse light source, and frame head + shoulders so iris landmarks stay visible.
