# LeLampCV

A software-first digital twin for an expressive lamp agent that detects attention, reacts through a 3D lamp simulation, remembers objects it sees, and answers questions from memory through voice.

## What it does

- Detects **ENGAGED** vs **DISENGAGED** using face, head, and iris-derived gaze cues (MediaPipe Face Landmarker).
- Calibrates gaze for the current camera and seating position.
- Applies temporal smoothing and FSM debouncing so states do not flicker.
- Maps states to lamp behaviors (pose + light) with several attention-seeking variants.
- Runs **YOLOv8** object detection on a background thread and logs sightings to JSONL memory.
- Routes **memory-first** for location-style questions; optional **Grok/xAI** paraphrases grounded answers and handles general chat.
- Speaks replies with **pyttsx3** (platform TTS).
- Exports JSON for a **Three.js** viewer at `simulator/`.
- Optionally logs behavior rows to **Google Sheets** via a service account (local credentials file, never committed).

## Demo flow (happy path)

1. Calibrate gaze (`c`).
2. Look at the lamp feed → **ENGAGED**.
3. Look away → **DISENGAGED**.
4. Stay disengaged → attention-seeking motion/light.
5. Show an object → `memory saved:` line in the console.
6. Ask “where is my bottle?” (voice or typed) → spoken answer from memory + twin shows **ANSWERING**.

## Architecture (text diagram)

```
camera + microphone
    → perception.py / object_perception.py
    → state_manager.py
    → behavior.py
    → simulator + voice + logs
                ↘ memory.py
                     → conversation.py + grok_client.py
                     → voice_output.py
```

`behavior.py` defines **`LampBehaviorCommand`** (angles, light, reason). The simulator polls `latest_behavior.json`; physical hardware could reuse the same payload. Google Sheets receives mirrored rows for auditing only—it does not drive the lamp. Object recall reads **`runtime/memory/object_memory.jsonl`**; Grok may rephrase but should not invent locations when memory routing applies.

## Repository layout

| Path | Purpose |
|------|---------|
| `src/lelamp/main.py` | Webcam loop, FSM integration, exports |
| `src/lelamp/perception.py` | Face / gaze perception |
| `src/lelamp/object_perception.py` | YOLO desk-object detection |
| `src/lelamp/async_object_perception.py` | Non-blocking YOLO worker |
| `src/lelamp/state_manager.py` | Engagement FSM + debounce |
| `src/lelamp/behavior.py` | State → lamp command |
| `src/lelamp/behavior_exporter.py` | `simulator/latest_behavior.json` |
| `src/lelamp/conversation.py` | Memory-first Q&A routing |
| `src/lelamp/conversation_exporter.py` | `simulator/latest_conversation.json` |
| `src/lelamp/memory.py` | JSONL object memory |
| `src/lelamp/grok_client.py` | xAI Grok client (OpenAI-compatible API) |
| `src/lelamp/voice_input.py` | Push-to-talk speech recognition |
| `src/lelamp/voice_output.py` | Non-blocking TTS worker |
| `src/lelamp/google_sheets_logger.py` | Optional Sheets sink |
| `src/lelamp/metrics.py` | Latency + engagement CSV logging |
| `src/lelamp/visualizer.py` | OpenCV HUD |
| `src/lelamp/paths.py` | Repo-root-relative paths |
| `simulator/` | Three.js twin + example JSON schemas |
| `docs/` | Architecture / perception / behavior / memory notes |
| `evaluation/` | Frozen CSV + written summary for judges |
| `scripts/` | `run_app.py`, `test_tts.py` |
| `models/` | MediaPipe task file + YOLO weights (see `models/README.md`) |
| `runtime/` | Gitignored memory + metrics outputs during runs |

## Setup

- **Python 3.10+** recommended.
- Install deps:

```bash
pip install -r requirements.txt
```

- **Grok** (optional): set `XAI_API_KEY`.

PowerShell:

```powershell
$env:XAI_API_KEY="your_key_here"
```

- **Google Sheets** (optional): download a service account JSON locally, point `LELAMP_GOOGLE_CREDENTIALS` at that file, and set `LELAMP_SPREADSHEET_ID`. Both must be valid or logging stays off. The JSON is ignored by `.gitignore`.

- **Voice input**: requires `SpeechRecognition` plus working microphone access; **PyAudio** can be finicky on Windows—install wheels separately if pip fails.

## Running

Terminal 1 (repo root):

```bash
python scripts/run_app.py
```

Terminal 2:

```bash
cd simulator
python -m http.server 8000
```

Browser: `http://localhost:8000`

The entry script `chdir`s to the repo root so JSON exports land in `simulator/`.

## Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `c` | Calibrate gaze |
| `r` | Reset calibration |
| `v` | Push-to-talk voice input |
| `1` | Expected **ENGAGED** (metrics) |
| `2` | Expected **DISENGAGED** |
| `0` | Clear expected label |
| `n` | Log settled engagement trial |
| `m` | Force log trial |

## Evaluation snapshot

From `evaluation/submission_summary.md` (binary gaze reliability):

- Total trials: **109**, correct **93**, accuracy **85.32%**
- **ENGAGED**: **100.00%** (19 trials)
- **DISENGAGED**: **82.22%** (90 trials)

Latency medians (main loop excludes blocking YOLO):

- Perception **13.28 ms**
- Total loop **23.74 ms**
- Async object inference **212.35 ms**

Details: `evaluation/README.md`, raw CSVs in `evaluation/`.

## Design decisions

Short version—see `docs/tradeoffs.md` for narrative:

- Iris-aware gaze beats head pose alone for “actually looking”.
- Smoothing + debounce beats naive frame-wise thresholds.
- **YOLOv8s** + async inference trades heavier models for smoother UX.
- Memory-first routing beats LLM-first recall for object locations.
- Digital twin decouples behavior logic from hardware bring-up.

## Limitations

- YOLO only knows COCO-like everyday classes; weird props may never register.
- Gaze quality depends on lighting, glasses, and calibration discipline.
- Speech recognition mis-hears short fragments; typing still works.
- The twin is behavioral stand-in for real servos / LEDs.
- Memory is a simple JSONL scan—no embeddings or long-horizon reasoning.

## Future work

- Physically actuated lamp (PWM servos + warm-white LED strips).
- Better spatial grounding (depth or plane estimation).
- Multi-user profiles.
- Interruption detection while speaking.
- Prosody / frustration cues beyond gaze alone.

## Demo video

Demo video: **TODO add link**

## Screenshots / GIFs

Screenshots/GIFs: **TODO** add simulator captures, memory recall, evaluation summary (`assets/screenshots/`, `assets/demo/`).

Also drop an architecture diagram PNG/SVG under `assets/diagrams/` when ready.
