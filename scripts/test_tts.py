"""pyttsx3 checks — run: ``python scripts/test_tts.py`` from repo root."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)


def _configure_engine(engine: object) -> None:
    engine.setProperty("rate", 175)
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


def _speak_fresh_engine(text: str) -> None:
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


def print_voices() -> bool:
    print("=== Voice list ===")
    try:
        import pyttsx3
    except Exception as exc:
        print(f"ERROR: could not import pyttsx3 ({type(exc).__name__})")
        return False

    try:
        engine = pyttsx3.init()
    except Exception as exc:
        print(f"ERROR: pyttsx3.init() failed ({type(exc).__name__}: {exc})")
        return False

    voices = engine.getProperty("voices") or []
    print(f"Available voices ({len(voices)}):")
    for i, v in enumerate(voices):
        vid = getattr(v, "id", "")
        name = getattr(v, "name", "")
        print(f"  [{i}] name={name!r} id={vid!r}")
    try:
        engine.stop()
    except Exception:
        pass
    return True


def run_three_sync_utterances() -> None:
    print("\n=== Three sequential utterances (fresh engine each) ===")
    phrases = [
        "First voice test.",
        "Second voice test.",
        "Third voice test.",
    ]
    for i, phrase in enumerate(phrases, start=1):
        print(f"\n--- Speaking {i}/3 ---")
        try:
            _speak_fresh_engine(phrase)
        except Exception as exc:
            print(f"ERROR: utterance {i} failed ({type(exc).__name__}: {exc})")
            return
        print("--- Finished ---")
        if i < len(phrases):
            time.sleep(1.0)
    print("\nIf you heard all three phrases, sync multi-test passed.\n")


def _wait_utterance_done(voice: object, timeout: float = 60.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if voice.is_speaking():
            break
        time.sleep(0.02)
    while voice.is_speaking() and time.time() - t0 < timeout:
        time.sleep(0.05)


def run_voice_output_async_smoke() -> None:
    print("\n=== VoiceOutput async smoke (three speak_async calls) ===")
    from lelamp.voice_output import VoiceOutput

    voice = VoiceOutput()
    if not voice.is_available():
        print("SKIP: VoiceOutput not available")
        return

    tests = [
        "First async test.",
        "Second async test.",
        "Third async test.",
    ]
    for i, phrase in enumerate(tests, start=1):
        print(f"\n--- Async {i}/3 ---")
        voice.speak_async(phrase)
        time.sleep(0.05)
        _wait_utterance_done(voice)
        time.sleep(0.15)

    voice.close()
    print("\nIf you heard all three async phrases, VoiceOutput test passed.\n")


def _print_troubleshooting() -> None:
    print("Windows / audio troubleshooting:")
    print("  - Confirm the default playback device (Settings > System > Sound).")
    print("  - Turn system volume up; unmute.")
    print("  - Play sound from another app (e.g. browser video) to verify output.")
    print("  - Run this script outside Cursor in normal PowerShell or cmd.exe")
    print("    (some integrated terminals do not route audio as expected).")
    print("  - pyttsx3 on Windows uses SAPI5; ensure Windows features / voices work.")
    print("  - PyAudio is only needed for microphone/voice-input tests, not TTS.")
    print("  - If only the first line speaks, re-run after voice_output changes.")


def main() -> None:
    print("=== leLampCV TTS full test ===\n")
    if not print_voices():
        _print_troubleshooting()
        return

    print("\n--- Single phrase (legacy path) ---")
    try:
        _speak_fresh_engine(
            "LeLamp voice test. If you can hear this, text to speech is working."
        )
    except Exception as exc:
        print(f"ERROR: single phrase failed ({type(exc).__name__}: {exc})")
        _print_troubleshooting()
        return
    print("--- Finished single phrase ---\n")

    run_three_sync_utterances()
    run_voice_output_async_smoke()

    _print_troubleshooting()


if __name__ == "__main__":
    main()
