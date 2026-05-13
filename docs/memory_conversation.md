# Memory and conversation

## What memory stores (and what it does not)

Object memory is **append-only JSONL** (`runtime/memory/object_memory.jsonl`). Each line is one **`ObjectMemoryEntry`**: timestamp, label, coarse **`location_label`** (image thirds: `left middle`, etc.), confidence, bbox/center, and the lamp **FSM state** at observation time.

Location is **bucketed screen space**, not metric depth. That matches what YOLO gives without adding depth cameras—good enough for voice answers like “left side of the frame.”

Dedup (`MEMORY_DEDUP_SECONDS`) prevents logging the same `(label, bucket)` every frame when the webcam barely moves.

## Memory-first routing (diagram)

```text
User text (typed or ASR)
       │
       ▼
conversation.py  ──► normalize / classify intent
       │
       ├─ MEMORY_LOCATION_QUERY ──► memory.py scan JSONL (+ fuzzy label match)
       │         │
       │         ├─ match ──► build memory_evidence string (label, bucket, time)
       │         │                  │
       │         │                  ▼
       │         │             Grok format_memory_answer (optional)
       │         │                  │
       │         └─ no match ──► deterministic “don’t remember yet” string
       │                          │
       │                          ▼
       │                     Grok may still polish wording,
       │                     but evidence explicitly says “no match.”
       │
       └─ GENERAL_QUERY ──► Grok answer_general_question (no JSONL requirement)
```

## Concrete example: bottle recall

1. **User:** “Where is my bottle?”  
2. **`conversation.py`** strips fillers, classifies **`MEMORY_LOCATION_QUERY`**, extracts fragment `bottle`.  
3. **`memory.py`** scans recent JSONL rows; fuzzy alias logic maps user wording ↔ stored labels (`water bottle` ↔ `bottle`).  
4. **Hit:** evidence block lists `label`, `location_label`, timestamp, confidence.  
5. **`grok_client.format_memory_answer`** rewrites text *without changing facts* (temperature capped; system prompt forbids inventing coordinates).  
6. **`voice_output`** speaks final string; **`conversation_exporter`** writes mode + `memory_found=true` for the twin HUD.

If step 3 misses, the deterministic core says the lamp has **not** logged that object—and Grok is constrained to stay honest rather than improvising a desk direction.

## Example modes (what judges should hear / see)

| User utterance (intent) | Mode | Memory | Outcome |
|-------------------------|------|--------|---------|
| “Where’s my bottle?” | `MEMORY_LOCATION_QUERY` | hit | Answer cites bucket + rough time; twin shows memory badge hit. |
| “Where’s my wallet?” | `MEMORY_LOCATION_QUERY` | miss | Explicit “don’t remember seeing wallet”; badge shows miss. |
| “Where’s my” (fragment) | `CLARIFICATION_NEEDED` | n/a | Asks which object—**no JSONL search** on bogus fragments. |
| “What is recursion?” | `GENERAL_QUERY` | ignored | Grok answers CS question; no spatial claims required. |

## Hallucination bug we actually fixed

Early iterations let Grok answer location questions **without** forcing JSONL retrieval first. The model confidently produced plausible directions (“it’s on your desk”) even when memory was empty or pointed elsewhere.

**Fix:** strict routing order—location language triggers **`MEMORY_LOCATION_QUERY`** before **`GENERAL_QUERY`**—and Grok’s memory formatter receives **`memory_evidence`** plus a deterministic fallback sentence. If evidence states **no match**, the model must admit ignorance (prompt-enforced), not invent geometry.

## Why Grok is not the source of truth

`memory.py` remains authoritative for **whether** an object was seen and **where** the detector placed it. Grok only selects pronouns and tone around those facts.

If Grok is disabled or offline, you still get a truthful spoken answer from the deterministic path—the demo degrades to robotic wording, not wrong coordinates.

## Simulator coupling

When memory hits, behavior forcing **`ANSWERING`** pairs spoken output with amber/light motion so observers correlate speech with lamp state. `latest_conversation.json` exposes **`memory_found`** so the twin HUD cannot silently pretend recall succeeded.
