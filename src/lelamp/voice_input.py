"""Non-blocking push-to-talk: mic capture runs on a background thread.

Windows: ``pip install PyAudio`` for microphone access.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Optional

_FAILURE = object()


class VoiceInput:
    """Google speech recognition on a worker thread; results polled from main loop."""

    def __init__(self, enabled: bool = True) -> None:
        self._requested_enabled = enabled
        self._recognizer: Optional[Any] = None
        self._sr: Optional[Any] = None
        self._result_q: queue.Queue[Any] = queue.Queue()
        self._guard = threading.Lock()
        self._listening_flag = threading.Event()

        if not enabled:
            return
        try:
            import speech_recognition as sr

            self._sr = sr
            self._recognizer = sr.Recognizer()
        except Exception as exc:
            print(f"VoiceInput warning: ({type(exc).__name__})")
            self._recognizer = None
            self._sr = None

    def is_available(self) -> bool:
        return self._recognizer is not None and self._sr is not None

    def is_listening(self) -> bool:
        return self._listening_flag.is_set()

    def start_listening_async(self) -> None:
        if not self._requested_enabled or not self.is_available():
            return
        with self._guard:
            if self._listening_flag.is_set():
                print("Already listening")
                return
            self._listening_flag.set()
        threading.Thread(
            target=self._listen_worker,
            daemon=True,
            name="voice-input",
        ).start()

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

    def _listen_worker(self) -> None:
        sr = self._sr
        r = self._recognizer
        assert sr is not None and r is not None
        print("Listening...")
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=5.0, phrase_time_limit=6.0)
            text = r.recognize_google(audio)
            if isinstance(text, str) and text.strip():
                self._result_q.put(text.strip())
            else:
                self._result_q.put(_FAILURE)
        except sr.WaitTimeoutError:
            self._result_q.put(_FAILURE)
        except sr.UnknownValueError:
            self._result_q.put(_FAILURE)
        except Exception as exc:
            print(f"VoiceInput warning: ({type(exc).__name__})")
            self._result_q.put(_FAILURE)
        finally:
            self._listening_flag.clear()

