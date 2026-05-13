"""Non-blocking TTS via pyttsx3 — fresh engine per utterance (Windows reliability)."""

from __future__ import annotations

import queue
import threading
from typing import Optional

_PREVIEW_LEN = 80
_DEFAULT_RATE = 175


def _preview(text: str) -> str:
    t = text.strip().replace("\n", " ")
    if len(t) <= _PREVIEW_LEN:
        return t
    return t[: _PREVIEW_LEN - 3] + "..."


def _configure_engine(engine: object) -> None:
    engine.setProperty("rate", _DEFAULT_RATE)
    engine.setProperty("volume", 1.0)
    voices = engine.getProperty("voices") or []
    if not voices:
        return
    chosen = voices[0].id
    for v in voices:
        blob = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
        if "english" in blob or "en-us" in blob or "en_gb" in blob:
            chosen = v.id
            break
    engine.setProperty("voice", chosen)


def _speak_one_utterance(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    try:
        _configure_engine(engine)
        engine.say(text)
        engine.runAndWait()
    finally:
        try:
            engine.stop()
        except Exception:
            pass


class VoiceOutput:
    """Worker thread pulls from a queue; each job uses a new pyttsx3 engine."""

    def __init__(self, enabled: bool = True) -> None:
        self._requested_enabled = enabled
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._engine_ready = threading.Event()
        self._engine_failed = threading.Event()
        self._work_q: queue.Queue[Optional[str]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None

        if not enabled:
            self._engine_failed.set()
            return

        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="voice-output",
        )
        self._thread.start()

        if self._engine_ready.wait(timeout=8.0):
            pass
        elif self._engine_failed.is_set():
            print(
                "VoiceOutput warning: TTS unavailable, "
                "answer shown in terminal only"
            )
        else:
            print("VoiceOutput warning: TTS init timed out")

    def is_available(self) -> bool:
        return self._engine_ready.is_set()

    def speak_async(self, text: str) -> None:
        if not self._requested_enabled:
            return
        if not self._engine_ready.is_set():
            print(
                "VoiceOutput warning: speak skipped (TTS not available)"
            )
            return
        s = text.strip()
        if not s:
            return

        while True:
            try:
                self._work_q.get_nowait()
            except queue.Empty:
                break

        pv = _preview(s)
        print(f"VoiceOutput queued: {pv}")
        try:
            self._work_q.put_nowait(s)
        except queue.Full as exc:
            print(f"VoiceOutput warning: queue full ({type(exc).__name__})")

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def close(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        while True:
            try:
                self._work_q.get_nowait()
            except queue.Empty:
                break
        try:
            self._work_q.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=30.0)

    def _worker(self) -> None:
        if not self._requested_enabled:
            self._engine_failed.set()
            return

        try:
            import pyttsx3
        except Exception as exc:
            print(f"VoiceOutput warning: pyttsx3 import failed ({type(exc).__name__})")
            print("TTS unavailable, answer shown in terminal only")
            self._engine_failed.set()
            return

        try:
            probe = pyttsx3.init()
            _configure_engine(probe)
            try:
                probe.stop()
            except Exception:
                pass
            del probe
        except Exception as exc:
            print(f"VoiceOutput warning: engine probe failed ({type(exc).__name__})")
            print("TTS unavailable, answer shown in terminal only")
            self._engine_failed.set()
            return

        self._engine_ready.set()
        print("VoiceOutput enabled")

        while not self._stop.is_set():
            try:
                item = self._work_q.get(timeout=0.4)
            except queue.Empty:
                continue
            if item is None:
                break
            ut = item.strip()
            if not ut:
                continue

            pv = _preview(ut)
            print(f"VoiceOutput speaking: {pv}")
            self._speaking.set()
            try:
                _speak_one_utterance(ut)
            except Exception as exc:
                print(f"VoiceOutput warning: speak failed ({type(exc).__name__})")
            finally:
                self._speaking.clear()
            print("VoiceOutput finished")

