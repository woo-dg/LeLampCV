"""Always-on mic: background thread listens whenever the lamp is not speaking.

Windows: ``pip install PyAudio`` for microphone access.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Optional

_FAILURE = object()


class VoiceInput:
    """Google speech recognition on a worker thread; results polled from main loop."""

    _ambient_noise_done = False

    def __init__(
        self,
        enabled: bool = True,
        *,
        speaking_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._requested_enabled = enabled
        self._recognizer: Optional[Any] = None
        self._sr: Optional[Any] = None
        self._result_q: queue.Queue[Any] = queue.Queue()
        self._listening_flag = threading.Event()
        self._stop = threading.Event()
        self._speaking_check = speaking_check
        self._worker: Optional[threading.Thread] = None

        if not enabled:
            return
        try:
            import speech_recognition as sr

            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.pause_threshold = 0.55
        except Exception as exc:
            print(f"VoiceInput warning: ({type(exc).__name__})")
            self._recognizer = None
            self._sr = None
            return

        self._worker = threading.Thread(
            target=self._continuous_worker,
            daemon=True,
            name="voice-input",
        )
        self._worker.start()

    def is_available(self) -> bool:
        return self._recognizer is not None and self._sr is not None

    def is_listening(self) -> bool:
        return self._listening_flag.is_set()

    def poll_result(self) -> str | None:
        try:
            item = self._result_q.get_nowait()
        except queue.Empty:
            return None
        if item is _FAILURE:
            print("Voice input: no speech recognized")
            return None
        if isinstance(item, str) and item.strip():
            return item.strip()
        print("Voice input: no speech recognized")
        return None

    def close(self) -> None:
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=8.0)

    def _tts_busy(self) -> bool:
        fn = self._speaking_check
        if fn is None:
            return False
        try:
            return bool(fn())
        except Exception:
            return False

    def _continuous_worker(self) -> None:
        sr = self._sr
        r = self._recognizer
        assert sr is not None and r is not None
        print("Voice input: always-on listening (pauses while lamp speaks)")
        try:
            with sr.Microphone() as source:
                if not VoiceInput._ambient_noise_done:
                    try:
                        r.adjust_for_ambient_noise(source, duration=0.35)
                    except Exception:
                        pass
                    VoiceInput._ambient_noise_done = True

                while not self._stop.is_set():
                    while self._tts_busy():
                        if self._stop.wait(0.08):
                            return

                    self._listening_flag.set()
                    audio = None
                    try:
                        audio = r.listen(
                            source,
                            timeout=1.4,
                            phrase_time_limit=14.0,
                        )
                    except sr.WaitTimeoutError:
                        pass
                    except Exception as exc:
                        print(f"VoiceInput warning: ({type(exc).__name__})")
                    finally:
                        self._listening_flag.clear()

                    if audio is None or self._stop.is_set():
                        continue

                    try:
                        text = r.recognize_google(audio)
                        if isinstance(text, str) and text.strip():
                            self._result_q.put(text.strip())
                        else:
                            self._result_q.put(_FAILURE)
                    except sr.UnknownValueError:
                        self._result_q.put(_FAILURE)
                    except Exception as exc:
                        print(f"VoiceInput warning: ({type(exc).__name__})")
                        self._result_q.put(_FAILURE)
        except Exception as exc:
            print(f"VoiceInput fatal: ({type(exc).__name__}: {exc})")
