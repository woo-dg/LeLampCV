# Architecture

LeLampCV is split into modules with narrow imports so you can replace one piece (different LLM, different twin, different logger) without rewiring the whole capture loop. The split is not cosmetic: **`main.py` orchestrates**, but **`perception.py`**, **`state_manager.py`**, **`behavior.py`**, **`memory.py`**, and **`conversation.py`** each own one failure domain.

## High-level pipeline

1. **Capture** — webcam frames every iteration; microphone handled by a background listener that pauses while the lamp speaks (no push-to-talk key).
2. **Face/gaze perception** — MediaPipe Face Landmarker → boolean engagement primitive + debug vectors.
3. **FSM** — debounced gaze → discrete lamp states including attention/cooldown choreography.
4. **Behavior command** — numeric pose + light targets + human-readable reasons.
5. **Outputs in parallel** — OpenCV HUD (operator view), JSON twin feed (viewer), optional Sheets queue (audit), metrics sampling (evaluation), JSONL memory (objects).

## Module responsibilities (low level)

| Module | Responsibility | Must not do |
|--------|----------------|-------------|
| `perception.py` | Landmarks → gaze → smoothing → calibration lifecycle | Choose lamp colors or write disk |
| `state_manager.py` | Timers, debounce, variant pick for attention | Run network I/O |
| `behavior.py` | Map `(state, variant)` → `LampBehaviorCommand` | Read webcam |
| `async_object_perception.py` | Bounded queue, worker thread, latest-result cache | Block the main loop on inference |
| `object_perception.py` | Single-thread YOLO inference entry | Know about FSM |
| `memory.py` | Dedup + append JSONL | Parse natural language |
| `conversation.py` | Classify intent, retrieve evidence, call LLM polish paths | Control servos directly |
| `grok_client.py` | HTTP to xAI API | Decide routing |
| `behavior_exporter.py` / `conversation_exporter.py` | Atomic JSON writes for twin | Business logic |
| `google_sheets_logger.py` | Enqueue rows; worker thread does network | Block capture |
| `metrics.py` | CSV append + Markdown summary on shutdown | Affect lamp pose |
| `visualizer.py` | Draw overlays | Change perception results |

## Data contracts (quick reference)

Between perception and FSM:

- **`FacePerceptionResult`** — `face_detected`, `head_forward`, `eye_contact`, `looking_at_camera`, `gaze_direction`, `calibration_text`, `debug_text` (+ `calibrated`, `raw_result` internally).

Between FSM and behavior:

- **FSM state string** + optional **variant** string.

Between behavior and consumers:

- **`LampBehaviorCommand`** — `state`, `behavior_name`, `variant`, `pan_angle`, `tilt_angle`, `light_color`, `brightness`, motion/light `*_description`, `reason`.

Between YOLO and memory:

- **`DetectedObject`** → serialized as **`ObjectMemoryEntry`** (+ ISO timestamp and FSM state snapshot).

Between conversation and UI/audio:

- **`ConversationResult`** — `answer`, `mode`, `object_query`, `memory_found`, `memory_evidence`.

See **[system_design.md](system_design.md)** for full tables and the control-loop ordering.

## Timing considerations

- **Gaze path** runs synchronously every frame; its median (~13 ms on logged hardware) dominates interactive feel.
- **YOLO path** is amortized: enqueue is cheap; inference median (~212 ms) is tracked separately and **must not** stall gaze.
- **Sheets path** is asynchronous; worst-case Wi-Fi stalls must never delay `cv2.imshow` or state updates.
- **TTS path** uses a worker; `ANSWERING` behavior bridges user expectation while audio catches up.

## Failure containment

| Failure | System response |
|---------|-----------------|
| Google Sheets unreachable / auth bad | Logger disables after startup check or drops rows with warnings; **app continues**. |
| Grok API error or missing key | Memory answers fall back to **deterministic** strings from `conversation.py`; general chat degrades to a clear “can’t reach brain” style message. |
| TTS init/speak failure | Text still prints to terminal; behavior may still show **ANSWERING** for the timeout window. |
| YOLO slow or GPU busy | Main loop **never waits** on inference; memory simply updates later. |
| Empty / missing memory row | Router returns explicit **no memory** copy; LLM is instructed not to invent coordinates. |
| Bad JSONL line | Reader skips line with a warning; recall continues over valid rows. |

This list is what makes the demo survivable under conference Wi-Fi and flaky USB cameras.

## Google Sheets vs simulator (control plane)

Both receive **mirrors** of the behavior command, but only **local JSON** sits on the hot path for the twin. Sheets prove *what was commanded* during testing—useful for supervisors who want spreadsheet truth without scrubbing video frame-by-frame.

**map_behaviour acts like a run log for the command stream.** If this were connected to physical hardware, the same pan/tilt/light values being written to the sheet are the values that would be sent to the actuator/light layer.

## Related docs

- **[system_design.md](system_design.md)** — full diagram + contracts + loop narrative  
- **[tradeoffs.md](tradeoffs.md)** — why the splits above exist  
- **[evaluation.md](evaluation.md)** — what the metrics CSV actually measures  
