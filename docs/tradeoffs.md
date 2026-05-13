# Tradeoffs

Each row is a decision we had to make after something broke in practice—not a hypothetical preference.

---

### Digital twin vs physical hardware

**Problem**  
A 6-DOF lamp introduces backlash, power limits, wiring noise, and long iteration cycles. Debugging gaze thresholds while motors hunt would have blurred whether perception or mechanics was wrong.

**Decision**  
Implement behaviors against a Three.js twin fed by the same JSON command struct intended for hardware.

**Why**  
Keeps the challenge focused on **perception-to-command correctness**, which is the actual CV/control contribution before mechanics.

**Cost**  
No measured servo settling time, no mechanical vibration coupling, no real-world illumination bounce off the lamp body.

**Result**  
`LampBehaviorCommand` is stable enough that swapping the renderer for GPIO/PWM later does not require rewriting perception.

---

### Head pose alone vs gaze-aware perception

**Problem**  
Users routinely face the webcam while reading a laptop slightly below the optical axis—head says “present,” eyes say “not with you.” Engagement looked high when attention was gone.

**Decision**  
Add iris / eye-region ratios from MediaPipe Face Landmarker on top of coarse head gates.

**Why**  
Eye direction is a stronger cue for **joint attention** than nose yaw alone.

**Cost**  
More fragile under dark rooms, heavy glasses, or extreme head tilt; requires calibration (`c`).

**Result**  
False ENGAGED rates dropped enough that attention-seeking behaviors triggered when they should—after actual disengagement, not just bad pose estimation noise.

---

### Fixed thresholds vs calibration

**Problem**  
Fixed iris ratio bands worked on one desk setup and failed on another camera height.

**Decision**  
Capture a short baseline (`c`) while the user looks at the lamp; classify gaze relative to that baseline.

**Why**  
Hardware variation becomes a **session parameter**, not a constant buried in code.

**Cost**  
Demos need a deliberate calibration step; forgetting it looks like “broken gaze.”

**Result**  
Judges could rerun the same binary on different laptops without retuning Python constants.

---

### Frame-by-frame decisions vs temporal smoothing / debounce

**Problem**  
Raw `looking_at_camera` flickered frame-to-frame; the FSM and twin swapped states faster than humans perceive intent.

**Decision**  
Rolling window consensus on the gaze boolean + asymmetric engage/disengage debounce timers in the FSM.

**Why**  
Physical motion (real or simulated) should ignore single-frame dropout typical of USB webcams.

**Cost**  
Hundreds of milliseconds of intentional lag before state flips—noticeable if you expect twitch gaming responsiveness.

**Result**  
Stable behaviors and cleaner evaluation trials (less accidental logging on transitions).

---

### YOLOv8n vs YOLOv8s

**Problem**  
Nano missed objects often enough that memory recall demos returned empty when the desk clearly had a bottle/cup/phone.

**Decision**  
Standardize on **YOLOv8s** weights.

**Why**  
Recall quality matters more than shaving milliseconds once async inference exists.

**Cost**  
Heavier model: more VRAM/CPU time per inference.

**Result**  
Higher fraction of successful `memory saved:` events; fewer “I never saw it” false negatives caused by detector dropout.

---

### Synchronous YOLO vs async YOLO

**Problem**  
Blocking YOLO inside the main loop pushed **total_loop_ms** into the hundreds of milliseconds—unacceptable next to a ~13 ms perception slice.

**Decision**  
Dedicated worker thread + latest-result mailbox; main loop only enqueues frames on a timer.

**Why**  
Engagement is safety-critical for UX; object memory can tolerate **eventual consistency** within ~1 second.

**Cost**  
Memory timestamps lag reality slightly; objects that appear for less than one sampling interval may never register.

**Result**  
Latency CSV medians stayed low while object inference still ran continuously.

---

### LLM-first recall vs memory-first routing

**Problem**  
Voice question “where is my bottle?” sometimes produced plausible chatbot nonsense instead of JSONL-backed coordinates—the classic hallucination failure.

**Decision**  
`conversation.py` classifies location-style questions **before** general chat, retrieves evidence from `memory.py`, and only then optionally calls Grok to **word** the answer.

**Why**  
Locations must be **grounded** in stored sightings or explicitly absent—not invented.

**Cost**  
Brittle phrasing: unusual utterances need better normalization rules; no free-form RAG.

**Result**  
Demonstrators could trust spoken answers matched terminal `Conversation mode:` lines and JSONL rows.

---

### Google Sheets vs direct simulator control

**Problem**  
Pulling commands from Sheets would couple frame rate to Google API latency and retries—a reliability nightmare.

**Decision**  
Twin reads **local** `latest_behavior.json`; Sheets receives duplicate rows via async logger.

**Why**  
Real-time preview cannot depend on cloud round-trips.

**Cost**  
Two sinks must agree by construction (same source struct); reviewers need to know JSON is authoritative for motion.

**Result**  
Sheets became audit trail / teaching artifact (“map_behaviour” proof), not a control plane.

---

### Playful personality vs factual grounding

**Problem**  
Casual tone reads friendly but masks wrong facts—especially dangerous for spatial claims.

**Decision**  
Allow playful paraphrase **only** when `memory_evidence` contains a concrete match; otherwise deterministic honesty + strict LLM system prompts on memory paths.

**Why**  
Personality is worthwhile only if it cannot contradict telemetry.

**Cost**  
More prompt engineering and routing branches; general chat still needs guardrails against pretending to see objects.

**Result**  
Users stopped getting confident wrong directions—a regression we actually saw before memory-first routing.

---

### Metrics scope: binary engagement vs rich FSM

**Problem**  
Logging ATTENTION_SEEKING as “wrong ENGAGED” would punish intentional choreography.

**Decision**  
Trials compare keyboard ground truth vs **debounced binary gaze**, while storing FSM state as context columns.

**Why**  
Judges care whether gaze sensing matches human labels—not whether the lamp politely nudges a disengaged user.

**Cost**  
Metrics under-report “full interaction quality”; they only score perception alignment.

**Result**  
Interpretable accuracy numbers (85.32% overall in frozen submission) without conflating behavior design with classifier error.
