"""xAI Grok via OpenAI-compatible API — memory-grounded answers + optional general chat."""

from __future__ import annotations

import os
from typing import Optional

_GENERAL_SYSTEM_PROMPT = """You are the voice of an expressive memory-enabled lamp prototype.
You can answer general questions conversationally—short, helpful, slightly playful.
Do not use emojis. Avoid stiff corporate-assistant tone.
Do not claim access to live web search, weather APIs, news feeds, sports scores, stock tickers, or real-time data unless a tool explicitly provided it.
If the user asks for live/current/real-time info (weather now, latest headlines, scores, stock prices, sunrise times for today in the wild, etc.), say clearly that live data is not connected yet and suggest memory questions or other general topics instead.
Keep each reply under 100 words. Plain text only—no bullet lists unless the user clearly asks for steps."""

_GENERAL_FALLBACK = (
    "Hmm, I couldn't reach my brain just now—try asking again in a moment."
)

_SYSTEM_PROMPT = """You are a playful, expressive desk-lamp character with a tiny memory.
You ONLY answer from the supplied memory evidence and deterministic draft.
Never invent objects, locations, identities, times, or sightings not supported by the evidence.
Do not use emojis. Avoid slang that obscures meaning. Keep wording clear.
If memory evidence is exactly or essentially "No matching memory found." (no Latest match block), you MUST say you do not remember seeing that object yet and invite the user to put it in view briefly—use the deterministic draft as your factual baseline; do NOT invent places or times.
When evidence DOES contain a "Latest match:" block with label and location, you MUST reflect that real location and time in plain language; be playful only around facts that appear in the evidence.
When evidence DOES support an answer, you may be light and conversational (e.g. "Take a guess..." or "Okay fine..." ONLY right before stating facts that appear in the evidence).
Stay under two short sentences total. No corporate-assistant tone.
Return only plain text—no emojis, no bullet lists."""

_USER_TEMPLATE = """This is a MEMORY-GROUNDED reply path only (not general chat).
Style: playful lamp; max two short sentences; plain text; no emojis.

User question:
{user_question}

Deterministic draft (preserve this meaning; you may rephrase lightly):
{deterministic_answer}

Memory evidence (ONLY source of truth for locations/times/labels):
{memory_evidence}

If evidence contains "Latest match:" include that location in your reply.
If evidence says no matching memory, stay honest—do not invent sightings.

Write the final reply."""


class GrokClient:
    def __init__(
        self,
        enabled: bool = True,
        model: str = "grok-4-1-fast-non-reasoning",
    ) -> None:
        self._model = model
        self._client: Optional[object] = None
        self._enabled = False
        if not enabled:
            return
        key = os.getenv("XAI_API_KEY")
        if not key:
            print("Grok disabled: XAI_API_KEY not set")
            return
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=key,
                base_url="https://api.x.ai/v1",
            )
            self._enabled = True
        except Exception:
            print("Grok disabled: API client setup failed")
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def answer_general_question(self, user_question: str) -> str:
        """general_query: conversational reply without memory evidence."""
        if not self._enabled or self._client is None:
            return _GENERAL_FALLBACK
        q = user_question.strip() or "(empty)"
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0.55,
                max_tokens=220,
                messages=[
                    {"role": "system", "content": _GENERAL_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"User question:\n{q}\n\nAnswer briefly.",
                    },
                ],
            )
            choice = completion.choices[0].message
            text = (choice.content or "").strip()
            if not text:
                return _GENERAL_FALLBACK
            return text
        except Exception as exc:
            print(f"Warning: Grok general request failed ({type(exc).__name__})")
            return _GENERAL_FALLBACK

    def format_memory_answer(
        self,
        *,
        user_question: str,
        deterministic_answer: str,
        memory_evidence: str,
    ) -> str:
        if not self._enabled or self._client is None:
            return deterministic_answer
        user_content = _USER_TEMPLATE.format(
            user_question=user_question.strip(),
            deterministic_answer=deterministic_answer.strip(),
            memory_evidence=memory_evidence.strip(),
        )
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0.35,
                max_tokens=180,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            choice = completion.choices[0].message
            text = (choice.content or "").strip()
            if not text:
                return deterministic_answer
            return text
        except Exception as exc:
            print(f"Warning: Grok request failed ({type(exc).__name__})")
            return deterministic_answer
