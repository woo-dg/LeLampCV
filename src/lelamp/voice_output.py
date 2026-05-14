"""Non-blocking TTS: edge-tts + pygame file playback when available; pyttsx3 fallback."""

from __future__ import annotations

import asyncio
import os
import queue
import tempfile
import threading
from typing import Literal, Optional

# "auto" tries edge-tts first, then pyttsx3. "edge" / "pyttsx3" force that engine (edge falls back to pyttsx3 if needed).
VOICE_BACKEND: Literal["auto", "edge", "pyttsx3"] = "auto"

# Neural voices (edge-tts). Swap EDGE_TTS_VOICE to try others, e.g.:
# "en-US-JennyNeural", "en-US-GuyNeural", "en-CA-ClaraNeural"
EDGE_TTS_VOICE = "en-US-AriaNeural"
EDGE_TTS_RATE = "+0%"
EDGE_TTS_VOLUME = "+0%"

PYTTSX3_RATE = 175
PYTTSX3_VOLUME = 1.0

_PREVIEW_LEN = 80


def _preview(text: str) -> str:
    t = text.strip().replace("\n", " ")
    if len(t) <= _PREVIEW_LEN:
        return t
    return t[: _PREVIEW_LEN - 3] + "..."


def _configure_pyttsx3_engine(engine: object) -> None:
    engine.setProperty("rate", PYTTSX3_RATE)
    engine.setProperty("volume", PYTTSX3_VOLUME)
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


def _speak_pyttsx3_utterance(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    try:
        _configure_pyttsx3_engine(engine)
        engine.say(text)
        engine.runAndWait()
    finally:
        try:
            engine.stop()
        except Exception:
            pass


def _probe_pyttsx3() -> bool:
    try:
        import pyttsx3
    except Exception:
        return False
    try:
        probe = pyttsx3.init()
        _configure_pyttsx3_engine(probe)
        try:
            probe.stop()
        except Exception:
            pass
        del probe
        return True
    except Exception:
        return False


def _probe_edge_playback() -> bool:
    """Import edge-tts and pygame mixer; no network."""
    try:
        import edge_tts  # noqa: F401
        import pygame

        try:
            pygame.init()
        except Exception:
            pass
        pygame.mixer.init()
        return True
    except Exception:
        return False


def _speak_edge_to_file_play(text: str) -> bool:
    """Generate MP3 via edge-tts, play with pygame.mixer; delete temp file."""
    import edge_tts
    import pygame

    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:

        async def _save() -> None:
            comm = edge_tts.Communicate(
                text,
                voice=EDGE_TTS_VOICE,
                rate=EDGE_TTS_RATE,
                volume=EDGE_TTS_VOLUME,
            )
            await comm.save(path)

        asyncio.run(_save())

        pygame.mixer.music.stop()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            clock.tick(10)
        return True
    except Exception:
        return False
    finally:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            os.remove(path)
        except OSError:
            pass


class VoiceOutput:
    """Worker thread pulls from a queue; edge-tts preferred, pyttsx3 per utterance as fallback."""

    def __init__(self, enabled: bool = True) -> None:
        self._requested_enabled = enabled
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._engine_ready = threading.Event()
        self._engine_failed = threading.Event()
        self._work_q: queue.Queue[Optional[str]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._active_backend: Literal["edge", "pyttsx3"] = "pyttsx3"
        self._edge_disabled_session = False
        self._edge_warning_printed = False
        self._pygame_inited = False

        if not enabled:
            self._engine_failed.set()
            return

        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="voice-output",
        )
        self._thread.start()

        if self._engine_ready.wait(timeout=12.0):
            pass
        elif self._engine_failed.is_set():
            print(
                "VoiceOutput warning: TTS unavailable, "
                "answer shown in terminal only"
            )
        else:
            print("VoiceOutput warning: TTS init timed out")

    @property
    def active_backend(self) -> str:
        """``edge`` or ``pyttsx3`` — reading before ``is_available()`` may reflect defaults."""
        return self._active_backend

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
        if self._pygame_inited:
            try:
                import pygame

                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.mixer.quit()
                pygame.quit()
            except Exception:
                pass
            self._pygame_inited = False

    def _worker(self) -> None:
        if not self._requested_enabled:
            self._engine_failed.set()
            return

        py_ok = _probe_pyttsx3()
        edge_import_ok = _probe_edge_playback()
        if edge_import_ok:
            self._pygame_inited = True

        vb = VOICE_BACKEND.strip().lower()
        if vb not in ("auto", "edge", "pyttsx3"):
            vb = "auto"

        use_edge = False
        if vb == "edge":
            use_edge = edge_import_ok
        elif vb == "auto":
            use_edge = edge_import_ok

        if use_edge:
            self._active_backend = "edge"
            print("VoiceOutput backend: edge")
            if not py_ok:
                print(
                    "VoiceOutput warning: pyttsx3 unavailable; "
                    "edge-only mode (no fallback if edge fails)"
                )
        elif py_ok:
            self._active_backend = "pyttsx3"
            if vb == "pyttsx3":
                print("VoiceOutput backend: pyttsx3")
            else:
                print("VoiceOutput backend: pyttsx3 fallback")
        else:
            print("VoiceOutput warning: pyttsx3 engine probe failed")
            print("TTS unavailable, answer shown in terminal only")
            self._engine_failed.set()
            return

        self._engine_ready.set()

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
                spoken = False
                try_edge = (
                    self._active_backend == "edge"
                    and not self._edge_disabled_session
                    and edge_import_ok
                )
                if try_edge:
                    spoken = _speak_edge_to_file_play(ut)
                    if not spoken:
                        if not self._edge_warning_printed:
                            print(
                                "VoiceOutput warning: edge backend failed, "
                                "falling back to pyttsx3"
                            )
                            self._edge_warning_printed = True
                        self._edge_disabled_session = True
                        self._active_backend = "pyttsx3"
                if not spoken and py_ok:
                    _speak_pyttsx3_utterance(ut)
                elif not spoken:
                    print(
                        "VoiceOutput warning: speak failed "
                        "(no working backend)"
                    )
            except Exception as exc:
                print(f"VoiceOutput warning: speak failed ({type(exc).__name__})")
            finally:
                self._speaking.clear()
            print("VoiceOutput finished")
