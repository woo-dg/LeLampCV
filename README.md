# LeLampCV

A software-first digital twin for an expressive lamp agent that detects attention, reacts through a 3D lamp simulation, remembers objects it sees, and answers questions from memory through voice.

## What it does

- Detects **ENGAGED** vs **DISENGAGED** using face, head, and iris-derived gaze cues (MediaPipe Face Landmarker).
- Calibrates gaze for the current camera and seating position.
- Applies temporal smoothing and FSM debouncing so states do not flicker.
- Maps states to lamp behaviors (pose + light) with several attention-seeking variants.
- Runs **YOLOv8** object detection on a background thread and logs sightings to JSONL memory.
- Routes **memory-first** for location-style questions; optional **Grok/xAI** paraphrases grounded answers and handles general chat.
- Speaks answers via **edge-tts** (neural voice) with **pygame** playback when available; **pyttsx3** remains the offline fallback.
- Exports JSON for a **Three.js** viewer at `simulator/`.
- Optionally logs behavior rows to **Google Sheets** via a service account (local credentials file, never committed).

## Demo flow (happy path)

1. Calibrate gaze (`c`).
2. Look at the lamp feed → **ENGAGED**.
3. Look away → **DISENGAGED**.
4. Stay disengaged → attention-seeking motion/light.
5. Show an object → `memory saved:` line in the console.
6. Ask “where is my bottle?” (voice or typed) → spoken answer from memory + twin shows **ANSWERING**.

## Architecture

Full system design (diagrams, data contracts, control loop, Sheets rationale): **[docs/system_design.md](docs/system_design.md)**.

### Three concurrent paths

**Real-time control path** — closes the loop from pixels to something the lamp “does”:

```
camera → FacePerception → EngagementStateManager → behavior.py
       → behavior_exporter → simulator/latest_behavior.json → Three.js twin
```

**Memory / conversation path** — object recall and Q&A sit beside gaze; they do not replace it:

```
camera (sampled) → async YOLO worker → memory.py (JSONL)
stdin / voice → conversation.py → [memory evidence] → Grok (optional wording)
               → voice_output + conversation_exporter → simulator/latest_conversation.json
```

**Logging / evaluation path** — proves what happened without affecting frame deadlines:

```
perception + FSM + behavior command → metrics.py (CSV under runtime/metrics/)
                                   → Google Sheets row queue (optional audit log)
frozen summaries + CSV copies → evaluation/
```

The Sheets logger and metrics logger see the **same** behavior commands the simulator consumes; they are not upstream controllers.

## Evidence and logs

These artifacts together show perception → command → memory → speech:

| Artifact | What it proves |
|----------|----------------|
| [evaluation/submission_summary.md](evaluation/submission_summary.md) | Frozen headline metrics for judges (binary engagement + latency medians). |
| [map_behaviour Google Sheet](https://docs.google.com/spreadsheets/d/e/2PACX-1vShtsMiFy-dDUZ51HagY5_e9-NLyyAsHlfsPSc7sOkUMaLDrS_ck8D2QgWa2VOVpyOLNdU2xE47PjKz/pubhtml) | Public run log from test sessions: timestamped perception signals, FSM states, behavior commands, pan/tilt/light values, and debug text. |
| `runtime/memory/object_memory.jsonl` | Append-only object sightings (gitignored; copy a snippet if a rubric asks for raw memory). |
| `simulator/latest_behavior.json` | Same `LampBehaviorCommand` fields the twin animates (gitignored at runtime). |
| `simulator/latest_conversation.json` | Question, answer, routing mode, memory hit flag (gitignored at runtime). |
| Terminal | `memory saved: …`, `Conversation mode: …`, TTS status lines. |

**map_behaviour** is an external audit trail for the perception-to-behavior command stream—not the live control path. During a run, each logged row captures what the stack believed about engagement (face/gaze flags), which behavior state it entered, and the hardware-facing command fields that came out of `behavior.py`: pan angle, tilt angle, light color, brightness, behavior name, plus perception debug text. The Three.js twin reads **`simulator/latest_behavior.json`** from disk so motion stays responsive; nothing in the hot path waits on Google. The Sheet mirrors that same kind of command data so someone reviewing the project can scroll the timeline without our screen recording. If this codebase were wired to real hardware later, those pan/tilt/light values are the same quantities you’d map to servos, LED drivers, or other electronics—here they’re frozen as evidence from testing instead.

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
| `src/lelamp/voice_input.py` | Always-on speech recognition (mic pauses during TTS) |
| `src/lelamp/voice_output.py` | Non-blocking TTS worker |
| `src/lelamp/google_sheets_logger.py` | Optional Sheets sink |
| `src/lelamp/metrics.py` | Latency + engagement CSV logging |
| `src/lelamp/visualizer.py` | OpenCV HUD |
| `src/lelamp/paths.py` | Repo-root-relative paths |
| `simulator/` | Three.js twin + example JSON schemas |
| `docs/` | System design, architecture, tradeoffs, evaluation notes |
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

- **Voice input**: starts listening automatically when the app runs (`SpeechRecognition` + mic). Recognition **pauses while the lamp is speaking** so the reply is not transcribed as your next question. Type questions in the terminal as before. **PyAudio** can be finicky on Windows—install wheels separately if pip fails.
- **Voice output**: default path uses **edge-tts** (`VOICE_BACKEND="auto"` in `src/lelamp/voice_output.py`) for a more natural voice; **pygame** plays the synthesized audio file on a worker thread. If edge-tts fails (network, playback), the worker prints a short warning and falls back to **pyttsx3** so answers still speak. Set `VOICE_BACKEND = "pyttsx3"` there to force SAPI-only.
- **Camera**: the OpenCV preview is **mirrored horizontally by default** (`MIRROR_CAMERA_VIEW` in `src/lelamp/main.py`) so it behaves like a selfie preview; perception, YOLO, and overlays use that same flipped frame so boxes and left/right memory buckets match what you see.

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

Voice questions are picked up **continuously** from the microphone (no key). Metrics keys:

| Key | Action |
|-----|--------|
| `1` | Expected **ENGAGED** (metrics) |
| `2` | Expected **DISENGAGED** |
| `0` | Clear expected label |
| `n` | Log settled engagement trial |
| `m` | Force log trial |

From [evaluation/submission_summary.md](evaluation/submission_summary.md) (binary gaze reliability):

- Total trials: **109**, correct **93**, accuracy **85.32%**
- **ENGAGED**: **100.00%** (19 trials)
- **DISENGAGED**: **82.22%** (90 trials)

Latency medians (main loop excludes blocking YOLO):

- Perception **13.28 ms**
- Total loop **23.74 ms**
- Async object inference **212.35 ms**

Details: [evaluation/README.md](evaluation/README.md), methodology [docs/evaluation.md](docs/evaluation.md).

## Design decisions

Engineering narrative with problem/decision/cost for each fork: **[docs/tradeoffs.md](docs/tradeoffs.md)**.  
Module-level pipeline and failure containment: **[docs/architecture.md](docs/architecture.md)**.

## Limitations

- YOLO only knows COCO-like everyday classes; weird props may never register.
- Gaze quality depends on lighting, glasses, and calibration discipline.
- Speech recognition mis-hears short fragments; typing still works.
- The twin is a behavioral stand-in for real servos / LEDs.
- Memory is a simple JSONL scan—no embeddings or long-horizon reasoning.

## Future work

- Physically actuated lamp (PWM servos + warm-white LED strips).
- Better spatial grounding (depth or plane estimation).
- Multi-user profiles.
- Interruption detection while speaking.
- Prosody / frustration cues beyond gaze alone.

## Demo video

Demo video: **TODO add link**

## Architecture diagram

Source diagram (Mermaid): [assets/diagrams/system_architecture.mmd](assets/diagrams/system_architecture.mmd)

Optional before submission: export that file to PNG or SVG if you want a static figure in the repo or write-up.
