"""Exercise VoiceOutput (edge-tts + pygame, pyttsx3 fallback) — run from repo root."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)


def _wait_done(voice: object, timeout: float = 120.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if voice.is_speaking():
            break
        time.sleep(0.02)
    while voice.is_speaking() and time.time() - t0 < timeout:
        time.sleep(0.05)


def main() -> None:
    from lelamp import voice_output as vo_mod
    from lelamp.voice_output import VoiceOutput

    print("Voice constants (edit lelamp/voice_output.py to change):")
    print(f"  VOICE_BACKEND={vo_mod.VOICE_BACKEND!r}")
    print(f"  EDGE_TTS_VOICE={vo_mod.EDGE_TTS_VOICE!r}")
    print()

    voice = VoiceOutput()
    if not voice.is_available():
        print("VoiceOutput not available — check edge-tts/pygame/pyttsx3 install.")
        return

    print(f"Selected backend after init: {voice.active_backend!r}")
    lines = (
        "First LeLamp voice test.",
        "Second LeLamp voice test.",
        "Third LeLamp voice test.",
    )
    for i, phrase in enumerate(lines, start=1):
        print(f"\n--- Utterance {i}/3 ---")
        voice.speak_async(phrase)
        time.sleep(0.05)
        _wait_done(voice)
        time.sleep(0.2)

    voice.close()
    print("\nDone. If edge failed mid-run, pyttsx3 may have taken over (see warnings above).")


if __name__ == "__main__":
    main()
