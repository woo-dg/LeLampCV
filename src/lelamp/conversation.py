"""Memory-first Q&A, live-info stub, general chat, structured ConversationResult."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .memory import ObjectMemory, ObjectMemoryEntry
from .object_perception import _normalize_label

MEMORY_LOCATION_QUERY = "MEMORY_LOCATION_QUERY"
MEMORY_LIST_QUERY = "MEMORY_LIST_QUERY"
MEMORY_LAST_SEEN_QUERY = "MEMORY_LAST_SEEN_QUERY"
LIVE_INFO_QUERY = "LIVE_INFO_QUERY"
GENERAL_QUERY = "GENERAL_QUERY"
CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"

_FALLBACK_HELP = "I can answer questions like: where was my bottle?"
_NO_MEMORY_EVIDENCE = "No matching memory found."
_NO_QUESTION_EVIDENCE = "No memory evidence for this question."
_AMBIGUOUS_OBJECT = "What object are you asking about?"
_GENERAL_CHAT_NEEDS_GROK = (
    "I can answer memory questions right now, but general chat needs Grok enabled."
)
_LIVE_INFO_REPLY = (
    "I don't have live weather or web access connected yet, "
    "but I can answer general questions or memory questions."
)

_FILLER_WORDS = frozenset(
    {
        "please",
        "uh",
        "um",
        "like",
        "yo",
        "bro",
        "can",
        "you",
        "could",
        "tell",
        "me",
    }
)

_OBJECT_QUESTION_PREFIXES: tuple[str, ...] = (
    "where did you last see my",
    "where did you see my",
    "have you seen my",
    "do you remember my",
    "did you see my",
    "where was my",
    "where is my",
)

_INVALID_OBJECT_FRAGMENTS = frozenset(
    {
        "",
        "my",
        "the",
        "a",
        "an",
        "is",
        "it",
        "where is my",
        "where was my",
        "where did you last see my",
        "where did you see my",
        "have you seen my",
        "do you remember my",
        "did you see my",
    }
)

_OBJECT_CANONICAL_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"bottle", "water bottle"}),
    frozenset({"phone", "cell phone", "mobile phone", "cellphone"}),
    frozenset({"laptop", "computer"}),
    frozenset({"cup", "mug"}),
    frozenset({"chair"}),
    frozenset({"book", "notebook"}),
)


@dataclass
class ConversationResult:
    answer: str
    mode: str
    object_query: Optional[str]
    memory_found: bool
    memory_evidence: str


def _normalize_object_label(raw: str) -> str:
    t = raw.strip().lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    parts = []
    for w in t.split():
        if w in _FILLER_WORDS:
            continue
        parts.append(w)
    t2 = " ".join(parts)
    return _normalize_label(t2)


def _canonical_object_key(norm: str) -> str:
    if not norm:
        return ""
    for g in _OBJECT_CANONICAL_GROUPS:
        if norm in g:
            return min(g)
    return norm


def _normalize_conversation_text(raw: str) -> str:
    t = raw.strip().lower()
    t = re.sub(r"\bwhere's\b", "where is", t)
    t = re.sub(r"\bwhat's\b", "what is", t)
    t = re.sub(r"\bit's\b", "it is", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    for phrase in ("can you ", "could you ", "tell me ", "please "):
        t = t.replace(phrase, " ")
    t = re.sub(r"\s+", " ", t).strip()
    parts = [w for w in t.split() if w not in _FILLER_WORDS]
    return " ".join(parts)


def _strip_leading_articles(s: str) -> str:
    s = s.strip()
    changed = True
    while changed and s:
        changed = False
        low = s.lower()
        for art in ("my ", "the ", "a ", "an "):
            if low.startswith(art):
                s = s[len(art) :].strip()
                changed = True
                break
    return s


def _extract_prefixed_location(norm: str) -> tuple[bool, str]:
    for pref in _OBJECT_QUESTION_PREFIXES:
        if norm == pref:
            return True, ""
        if norm.startswith(pref + " "):
            rest = norm[len(pref) + 1 :].strip()
            rest = _strip_leading_articles(rest)
            return True, rest.strip()
    return False, ""


def _extract_bare_where_location(norm: str) -> tuple[bool, str]:
    for pref in ("where is ", "where was "):
        stem = pref.rstrip()
        if norm == stem:
            return True, ""
        if norm.startswith(pref):
            rest = norm[len(pref) :].strip()
            rest = _strip_leading_articles(rest)
            return True, rest.strip()
    return False, ""


def _extract_location_query_fragment(norm: str) -> tuple[bool, str]:
    ok, frag = _extract_prefixed_location(norm)
    if ok:
        return True, frag
    return _extract_bare_where_location(norm)


def _is_live_info_query(norm: str) -> bool:
    if "weather" in norm or "forecast" in norm:
        return True
    if "sunrise" in norm or "sunset" in norm:
        return True
    if "the news" in norm:
        return True
    if "stock price" in norm or "stock prices" in norm:
        return True
    if "live score" in norm:
        return True
    if "current time in" in norm:
        return True
    if "current temperature" in norm:
        return True
    if "temperature today" in norm or "temperature outside" in norm:
        return True
    return False


def _format_local_time(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        h = local.hour % 12
        if h == 0:
            h = 12
        am_pm = "AM" if local.hour < 12 else "PM"
        return f"{h}:{local.minute:02d} {am_pm}"
    except (ValueError, TypeError, OSError):
        return ""


def _entry_evidence(entry: ObjectMemoryEntry) -> str:
    return (
        "Latest match:\n"
        f"label={entry.label}\n"
        f"location={entry.location_label}\n"
        f"timestamp={entry.timestamp}\n"
        f"confidence={entry.confidence}\n"
        f"state={entry.state}"
    )


def _evidence_recent_objects(entries: list[ObjectMemoryEntry]) -> str:
    if not entries:
        return _NO_MEMORY_EVIDENCE
    last_by_label: dict[str, ObjectMemoryEntry] = {}
    for e in entries:
        last_by_label[e.label] = e
    lines = [
        f"{lab} at {ent.location_label}"
        for lab, ent in sorted(last_by_label.items())
    ]
    return "Recent objects:\n" + "\n".join(lines)


def _match_quality(
    q: str,
    qk: str,
    ml: str,
    mk: str,
) -> int:
    """Lower is better: 1 exact norm, 2 canonical/alias, 3 substring; 0 no match."""
    if ml == q:
        return 1
    if mk and qk and mk == qk:
        return 2
    if q in ml or ml in q:
        return 3
    return 0


def _find_latest_fuzzy(memory: ObjectMemory, fragment: str) -> Optional[ObjectMemoryEntry]:
    """Prefer exact / alias / substring (in that order), then newest sighting."""
    q = _normalize_object_label(fragment)
    if not q or q in _INVALID_OBJECT_FRAGMENTS:
        return None
    qk = _canonical_object_key(q)

    entries = memory.recent_entries(5000)
    best: Optional[ObjectMemoryEntry] = None
    best_rank: Optional[tuple[int, int]] = None

    for age_idx, ent in enumerate(reversed(entries)):
        ml = _normalize_object_label(ent.label)
        if not ml:
            continue
        mk = _canonical_object_key(ml)
        tier = _match_quality(q, qk, ml, mk)
        if tier == 0:
            continue
        rank = (tier, age_idx)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = ent
    return best


def _no_memory_answer_display_key(fragment: str) -> str:
    k = _normalize_object_label(fragment)
    return k if k else fragment.strip().lower() or "that"


class ConversationManager:
    def __init__(
        self,
        memory: ObjectMemory,
        llm_client: Optional[Any] = None,
    ) -> None:
        self._memory = memory
        self._llm = llm_client

    def _polish_memory_answer(
        self,
        *,
        user_question: str,
        deterministic: str,
        evidence: str,
    ) -> str:
        q = user_question.strip() if user_question.strip() else "(empty)"
        if self._llm is not None and getattr(self._llm, "enabled", False):
            return self._llm.format_memory_answer(
                user_question=q,
                deterministic_answer=deterministic,
                memory_evidence=evidence,
            )
        return deterministic

    def answer(self, user_text: str) -> str:
        return self.answer_with_metadata(user_text).answer

    def answer_with_metadata(self, user_text: str) -> ConversationResult:
        raw_q = user_text.strip()
        norm = _normalize_conversation_text(raw_q)

        if not norm:
            return ConversationResult(
                answer=_FALLBACK_HELP,
                mode=GENERAL_QUERY,
                object_query=None,
                memory_found=False,
                memory_evidence=_NO_QUESTION_EVIDENCE,
            )

        if _is_live_info_query(norm):
            return ConversationResult(
                answer=_LIVE_INFO_REPLY,
                mode=LIVE_INFO_QUERY,
                object_query=None,
                memory_found=False,
                memory_evidence=_NO_QUESTION_EVIDENCE,
            )

        if "what objects" in norm and "see" in norm:
            return self._memory_list_result(raw_q)

        if "what did you last see" in norm:
            return self._memory_last_seen_result(raw_q)

        loc_ok, fragment = _extract_location_query_fragment(norm)
        if loc_ok:
            return self._memory_location_result(raw_q, fragment)

        ans = self._answer_general(raw_q)
        return ConversationResult(
            answer=ans,
            mode=GENERAL_QUERY,
            object_query=None,
            memory_found=False,
            memory_evidence=_NO_QUESTION_EVIDENCE,
        )

    def _memory_location_result(self, raw_q: str, fragment: str) -> ConversationResult:
        frag_stripped = fragment.strip()
        if not frag_stripped:
            return ConversationResult(
                answer=_AMBIGUOUS_OBJECT,
                mode=CLARIFICATION_NEEDED,
                object_query=None,
                memory_found=False,
                memory_evidence=_NO_QUESTION_EVIDENCE,
            )

        qn = _normalize_object_label(frag_stripped)
        if not qn or qn in _INVALID_OBJECT_FRAGMENTS:
            return ConversationResult(
                answer=_AMBIGUOUS_OBJECT,
                mode=CLARIFICATION_NEEDED,
                object_query=frag_stripped,
                memory_found=False,
                memory_evidence=_NO_QUESTION_EVIDENCE,
            )

        entry = _find_latest_fuzzy(self._memory, frag_stripped)
        display_key = _no_memory_answer_display_key(frag_stripped)

        if entry is None:
            det = (
                f"I don't remember seeing your {display_key} yet. "
                "Put it in view for a second and I'll keep track."
            )
            ans = self._polish_memory_answer(
                user_question=raw_q,
                deterministic=det,
                evidence=_NO_MEMORY_EVIDENCE,
            )
            return ConversationResult(
                answer=ans,
                mode=MEMORY_LOCATION_QUERY,
                object_query=frag_stripped,
                memory_found=False,
                memory_evidence=_NO_MEMORY_EVIDENCE,
            )

        when = _format_local_time(entry.timestamp)
        loc = entry.location_label
        disp = entry.label
        if when:
            det = f"I last saw your {disp} at {loc} at {when}."
        else:
            det = f"I last saw your {disp} at {loc}."
        ev = _entry_evidence(entry)
        ans = self._polish_memory_answer(
            user_question=raw_q,
            deterministic=det,
            evidence=ev,
        )
        return ConversationResult(
            answer=ans,
            mode=MEMORY_LOCATION_QUERY,
            object_query=frag_stripped,
            memory_found=True,
            memory_evidence=ev,
        )

    def _memory_list_result(self, raw_q: str) -> ConversationResult:
        entries = self._memory.recent_entries(20)
        ev = _evidence_recent_objects(entries)
        if not entries:
            det = "I haven't logged any objects yet."
        else:
            labels = sorted({e.label for e in entries})
            if len(labels) == 1:
                det = f"In recent memory I noted: {labels[0]}."
            else:
                det = f"In recent memory I noted: {', '.join(labels)}."
        ans = self._polish_memory_answer(
            user_question=raw_q,
            deterministic=det,
            evidence=ev,
        )
        return ConversationResult(
            answer=ans,
            mode=MEMORY_LIST_QUERY,
            object_query=None,
            memory_found=bool(entries),
            memory_evidence=ev,
        )

    def _memory_last_seen_result(self, raw_q: str) -> ConversationResult:
        entries = self._memory.recent_entries(1)
        if not entries:
            det = "I haven't seen anything yet."
            ev = _NO_MEMORY_EVIDENCE
        else:
            e = entries[-1]
            when = _format_local_time(e.timestamp)
            if when:
                det = f"I last noted a {e.label} at {e.location_label} at {when}."
            else:
                det = f"I last noted a {e.label} at {e.location_label}."
            ev = _entry_evidence(e)
        ans = self._polish_memory_answer(
            user_question=raw_q,
            deterministic=det,
            evidence=ev,
        )
        return ConversationResult(
            answer=ans,
            mode=MEMORY_LAST_SEEN_QUERY,
            object_query=None,
            memory_found=bool(entries),
            memory_evidence=ev,
        )

    def _answer_general(self, raw_q: str) -> str:
        llm = self._llm
        if llm is not None and getattr(llm, "enabled", False):
            return llm.answer_general_question(raw_q)
        return _GENERAL_CHAT_NEEDS_GROK
