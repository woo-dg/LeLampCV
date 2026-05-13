# Architecture

LeLampCV splits the problem into small modules so you can swap pieces (different LLM, different lamp hardware) without rewriting perception.

## High level

1. **Capture** — webcam frames + optional microphone.
2. **Perception** — face mesh + iris proxies → head pose + gaze → smoothed “looking at camera”.
3. **State machine** — debounces gaze, adds attention-seeking / cooldown behaviors when the user stays disengaged.
4. **Behavior commands** — each FSM state maps to pan, tilt, light color/brightness, and a human-readable reason string.
5. **Outputs** — OpenCV overlay, TTS, optional Google Sheets queue, JSON files for the Three.js twin, append-only object memory.

## Low-level module flow

```
Frame (BGR)
  → lelamp.perception.FacePerception.detect  → FacePerceptionResult
  → lelamp.state_manager.EngagementStateManager.update → state + variant + debounced binary label

state (+ variant)
  → lelamp.behavior.behavior_for_state → LampBehaviorCommand
  → lelamp.behavior_exporter.export_behavior_command → simulator/latest_behavior.json

parallel:
Frame → AsyncObjectPerception worker → YOLO boxes → lelamp.memory.ObjectMemory (JSONL)

typed/voice question
  → lelamp.conversation.ConversationManager (memory-first)
  → lelamp.grok_client (optional polish / general chat)
  → lelamp.voice_output + conversation_exporter → simulator/latest_conversation.json
```

## Why separate behavior mapping?

`behavior.py` is the single source of truth for **what the lamp should do** numerically and descriptively. The simulator consumes the same JSON a physical rig could consume later (servo targets + lighting). Perception should not know about HTML or TTS; it only emits geometric and boolean signals.

## Google Sheets

Logging runs on a background thread so network stalls never block the camera loop. Sheets are an audit trail, not a control plane.
