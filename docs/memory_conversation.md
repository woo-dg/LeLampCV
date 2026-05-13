# Memory and conversation

## Object memory

1. Async YOLO pulls probable desk objects from each sampled frame.
2. `memory.py` appends sightings as JSON lines under `runtime/memory/object_memory.jsonl`.
3. Dedup (`MEMORY_DEDUP_SECONDS`) avoids spamming identical `(label, coarse region)` pairs.

Location here means a **grid bucket** (`left middle`, etc.), not metric depth—good enough to answer “where did you last see it?” in human terms.

## Conversation routing

`conversation.py` normalizes questions and routes **object-location phrasing** through memory **before** general LLM chat. If nothing matches, the reply states honestly that nothing was remembered yet.

## Grok / xAI

- **Memory answers**: Grok only paraphrases text grounded in stored evidence; deterministic strings carry the factual location/time.
- **General chat**: separate prompt path without memory claims.

If `XAI_API_KEY` is unset, memory answers fall back to deterministic strings and general chat short-circuits with a clear message.
