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

## Architecture

Full system design (diagrams, data contracts, control loop, Sheets rationale): **[docs/system_design.md](docs/system_design.md)**.

Source Mermaid (export to PNG/SVG before submission if you want a rendered figure): **[assets/diagrams/system_architecture.mmd](assets/diagrams/system_architecture.mmd)**.

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
| Google Sheets **map_behaviour** / behavior log | Timestamped rows: gaze flags, FSM state, pan/tilt/light, debug text—readable proof of the command stream. |
| `runtime/memory/object_memory.jsonl` | Append-only object sightings (gitignored; copy a snippet if a rubric asks for raw memory). |
| `simulator/latest_behavior.json` | Same `LampBehaviorCommand` fields the twin animates (gitignored at runtime). |
| `simulator/latest_conversation.json` | Question, answer, routing mode, memory hit flag (gitignored at runtime). |
| Terminal | `memory saved: …`, `Conversation mode: …`, TTS status lines. |

**map_behaviour acts like a run log for the command stream.** If this were connected to physical hardware, the same pan/tilt/light values being written to the sheet are the values that would be sent to the actuator/light layer. The simulator stays on local JSON for latency; the sheet is there so reviewers can scroll through decisions without replaying video.

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

## Screenshots / GIFs / diagram export

- Add simulator captures under `assets/screenshots/` or `assets/demo/`.
- Render **[assets/diagrams/system_architecture.mmd](assets/diagrams/system_architecture.mmd)** to PNG or SVG (Mermaid CLI, VS Code plugin, or mermaid.live) and reference it here once exported.
