import os
from typing import Optional

import queue
import threading
import time
from datetime import datetime, timezone

import cv2

from .async_object_perception import AsyncObjectPerception
from .behavior import behavior_for_state
from .behavior_exporter import export_behavior_command
from .conversation import (
    MEMORY_LAST_SEEN_QUERY,
    MEMORY_LIST_QUERY,
    MEMORY_LOCATION_QUERY,
    ConversationManager,
    ConversationResult,
)
from .conversation_exporter import export_latest_conversation
from .google_sheets_logger import GoogleSheetsBehaviorLogger
from .grok_client import GrokClient
from .memory import ObjectMemory
from .metrics import EngagementTrial, LatencySample, MetricsLogger
from .object_perception import ObjectPerception, ObjectPerceptionResult
from .perception import FacePerception
from .state_manager import EngagementStateManager
from .visualizer import draw_perception
from .voice_input import VoiceInput
from .voice_output import VoiceOutput

GOOGLE_CREDENTIALS_JSON = os.getenv("LELAMP_GOOGLE_CREDENTIALS", "").strip()
GOOGLE_SPREADSHEET_ID = os.getenv("LELAMP_SPREADSHEET_ID", "").strip()
_sheets_ok = (
    bool(GOOGLE_CREDENTIALS_JSON and GOOGLE_SPREADSHEET_ID)
    and os.path.isfile(GOOGLE_CREDENTIALS_JSON)
)
ENABLE_GOOGLE_SHEETS_LOGGING = _sheets_ok
ENABLE_BEHAVIOR_EXPORT = True
ENABLE_PERCEPTION_DEBUG = True
ENABLE_OBJECT_DETECTION = True
ENABLE_VOICE_OUTPUT = True
ENABLE_VOICE_INPUT = True
ENABLE_CONVERSATION_EXPORT = True
ENABLE_METRICS = True
METRICS_LATENCY_LOG_INTERVAL_SECONDS = 1.0
METRICS_EXPECTED_MIN_SETTLE_S = 0.75
OBJECT_DETECTION_INTERVAL_SECONDS = 1.0

MIRROR_CAMERA_VIEW = True

ANSWER_DURATION_S = 3.0

LOG_INTERVAL_SECONDS = 0.5

_FPS_SMOOTH_ALPHA = 0.15
_PERF_PRINT_INTERVAL_S = 3.0

SHOW_CONVERSATION_MEMORY_EVIDENCE_DEBUG = os.getenv(
    "LELAMP_SHOW_MEMORY_EVIDENCE", ""
).strip().lower() in ("1", "true", "yes")


def _memory_location_debug_line(cr: ConversationResult) -> str:
    if not cr.memory_found:
        return "Memory found: no"
    label = ""
    loc = ""
    for line in cr.memory_evidence.splitlines():
        if line.startswith("label="):
            label = line.split("=", 1)[1].strip()
        elif line.startswith("location="):
            loc = line.split("=", 1)[1].strip()
    if label and loc:
        return f"Memory found: {label} at {loc}"
    return "Memory found: yes"


def _print_conversation_turn(cr: ConversationResult) -> None:
    print(f"Conversation mode: {cr.mode}")
    if cr.mode == MEMORY_LOCATION_QUERY:
        print(_memory_location_debug_line(cr))
    elif cr.mode in (MEMORY_LIST_QUERY, MEMORY_LAST_SEEN_QUERY):
        print(f"Memory found: {'yes' if cr.memory_found else 'no'}")
    if SHOW_CONVERSATION_MEMORY_EVIDENCE_DEBUG and cr.memory_evidence:
        print(cr.memory_evidence)


def _stdin_reader(question_queue: queue.Queue[str]) -> None:
    while True:
        try:
            question_queue.put(input())
        except EOFError:
            break


def main() -> None:
    lines = [
        "Keyboard:",
        "  q  quit",
        "  c  calibrate gaze",
        "  r  reset calibration",
    ]
    if ENABLE_METRICS:
        lines.extend(
            [
                "  1  metrics: expected ENGAGED",
                "  2  metrics: expected DISENGAGED",
                "  0  metrics: clear expected label",
                "  m  metrics: log trial (warns if label age < 0.75s)",
                "  n  metrics: log trial only if label settled ≥ 0.75s",
            ]
        )
    print("\n".join(lines) + "\n")
    if MIRROR_CAMERA_VIEW:
        print("Camera mirror view: enabled")
    else:
        print("Camera mirror view: disabled")

    perception = FacePerception()
    state_manager = EngagementStateManager()
    sheet_logger = (
        GoogleSheetsBehaviorLogger(GOOGLE_CREDENTIALS_JSON, GOOGLE_SPREADSHEET_ID)
        if ENABLE_GOOGLE_SHEETS_LOGGING
        else None
    )
    if (
        (GOOGLE_CREDENTIALS_JSON or GOOGLE_SPREADSHEET_ID)
        and not ENABLE_GOOGLE_SHEETS_LOGGING
    ):
        print(
            "Google Sheets logging off (need existing file at "
            "LELAMP_GOOGLE_CREDENTIALS and LELAMP_SPREADSHEET_ID)"
        )
    object_perception = ObjectPerception() if ENABLE_OBJECT_DETECTION else None
    async_object_perception: Optional[AsyncObjectPerception] = None
    if ENABLE_OBJECT_DETECTION and object_perception is not None:
        async_object_perception = AsyncObjectPerception(
            object_perception,
            interval_seconds=OBJECT_DETECTION_INTERVAL_SECONDS,
        )

    object_memory = ObjectMemory()
    grok_client = GrokClient()
    conversation = ConversationManager(object_memory, llm_client=grok_client)
    metrics_logger: Optional[MetricsLogger] = (
        MetricsLogger() if ENABLE_METRICS else None
    )
    if ENABLE_METRICS:
        print("Metrics logging enabled (latency ~1 Hz, trials on demand)")
    voice_output: Optional[VoiceOutput]
    if ENABLE_VOICE_OUTPUT:
        voice_output = VoiceOutput()
        if voice_output.is_available():
            print("Voice output enabled")
        else:
            print("Voice output disabled")
    else:
        voice_output = None
        print("Voice output disabled")

    voice_input: Optional[VoiceInput]
    if ENABLE_VOICE_INPUT:
        voice_input = VoiceInput(
            enabled=True,
            speaking_check=lambda: (
                voice_output.is_speaking()
                if voice_output is not None and voice_output.is_available()
                else False
            ),
        )
        if voice_input.is_available():
            print("Voice input enabled (always-on; pauses while lamp speaks)")
        else:
            print("Voice input disabled")
    else:
        voice_input = None
        print("Voice input disabled")

    question_queue: queue.Queue[str] = queue.Queue()

    stdin_thread = threading.Thread(
        target=_stdin_reader,
        args=(question_queue,),
        daemon=True,
        name="stdin-questions",
    )
    stdin_thread.start()

    answer_until_time = 0.0
    latest_answer = ""

    object_result = ObjectPerceptionResult(
        objects=[],
        debug_text="object detection off"
        if not ENABLE_OBJECT_DETECTION
        else "waiting…",
    )
    last_object_submit_time = 0.0

    webcam = cv2.VideoCapture(0)
    timestamp_ms = 0
    last_log_time = 0.0

    fps_smooth = 0.0
    last_frame_ms = 0.0
    last_perf_print = 0.0

    metrics_expected: Optional[str] = None
    metrics_expected_set_time: Optional[float] = None
    last_metrics_latency_ts = 0.0
    pending_submit_ms_for_latency: Optional[float] = None

    frame_ms = 0.0
    perception_ms = 0.0
    state_ms = 0.0
    behavior_ms = 0.0
    export_ms = 0.0

    def emit_engagement_trial(*, force_without_settle: bool) -> None:
        if metrics_logger is None:
            return
        if metrics_expected is None:
            print(
                "Metrics: set expected with 1 (ENGAGED) or 2 (DISENGAGED) "
                "before logging"
            )
            return
        now_t = time.time()
        if metrics_expected_set_time is not None:
            age = now_t - metrics_expected_set_time
            if age < METRICS_EXPECTED_MIN_SETTLE_S:
                if force_without_settle:
                    print(
                        "metrics warning: wait for state to settle before logging trials "
                        f"(label age {age:.2f}s < {METRICS_EXPECTED_MIN_SETTLE_S}s)"
                    )
                else:
                    print(
                        "Metrics: not logging yet, wait for settle "
                        f"({age:.2f}s < {METRICS_EXPECTED_MIN_SETTLE_S}s); "
                        "use m to force-log during transitions"
                    )
                    return
        pred = engagement_prediction
        ok = pred == metrics_expected
        metrics_logger.log_engagement_trial(
            EngagementTrial(
                timestamp=datetime.now(timezone.utc).isoformat(),
                expected=metrics_expected,
                predicted=pred,
                correct=ok,
                notes="",
                fsm_state=state,
                lamp_behavior=behavior_state,
            )
        )
        print(
            "Metrics: logged trial "
            f"expected={metrics_expected} predicted_binary={pred} "
            f"fsm_state={state} lamp_behavior={behavior_state} correct={ok}"
        )

    try:
        while webcam.isOpened():
            t_iter_start = time.perf_counter()

            t_cap = time.perf_counter()
            success, frame = webcam.read()
            if not success:
                break
            if MIRROR_CAMERA_VIEW:
                frame = cv2.flip(frame, 1)  # Mirror the camera feed for a more natural demo/self-view.
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_ms = (time.perf_counter() - t_cap) * 1000.0

            timestamp_ms += 33

            t_perc = time.perf_counter()
            perception_result = perception.detect(frame_rgb, timestamp_ms)
            perception_ms = (time.perf_counter() - t_perc) * 1000.0

            t_state = time.perf_counter()
            engagement = state_manager.update(
                face_detected=perception_result.face_detected,
                looking_at_camera=perception_result.looking_at_camera,
                current_time=time.time(),
            )
            state_ms = (time.perf_counter() - t_state) * 1000.0
            state = engagement.state
            attention_variant = engagement.attention_variant
            engagement_prediction = engagement.debounced_engagement

            now = time.time()
            listening_overlay = (
                voice_input.is_listening()
                if voice_input is not None and voice_input.is_available()
                else False
            )

            while True:
                try:
                    qn = question_queue.get_nowait()
                except queue.Empty:
                    break
                cr = conversation.answer_with_metadata(qn)
                ans = cr.answer
                print(f"User: {qn.strip()}")
                print(f"Lamp: {ans}")
                _print_conversation_turn(cr)
                latest_answer = ans
                answer_until_time = time.time() + ANSWER_DURATION_S
                if ENABLE_CONVERSATION_EXPORT:
                    export_latest_conversation(
                        question=qn.strip(),
                        result=cr,
                        listening=listening_overlay,
                    )
                if voice_output is not None and voice_output.is_available():
                    print("Speaking answer...")
                    voice_output.speak_async(ans)

            if (
                voice_input is not None
                and voice_input.is_available()
            ):
                voice_text = voice_input.poll_result()
                if voice_text is not None:
                    cr = conversation.answer_with_metadata(voice_text)
                    ans = cr.answer
                    print(f"User voice: {voice_text.strip()}")
                    print(f"Lamp: {ans}")
                    _print_conversation_turn(cr)
                    latest_answer = ans
                    answer_until_time = time.time() + ANSWER_DURATION_S
                    if ENABLE_CONVERSATION_EXPORT:
                        export_latest_conversation(
                            question=voice_text.strip(),
                            result=cr,
                            listening=listening_overlay,
                        )
                    if voice_output is not None and voice_output.is_available():
                        print("Speaking answer...")
                        voice_output.speak_async(ans)

            voice_ok = (
                ENABLE_VOICE_OUTPUT
                and voice_output is not None
                and voice_output.is_available()
            )
            speaking = voice_output.is_speaking() if voice_output is not None else False
            behavior_state = (
                "ANSWERING"
                if (
                    now < answer_until_time
                    or (voice_ok and speaking)
                )
                else state
            )
            replying = (
                now < answer_until_time or (voice_ok and speaking)
            ) and bool(latest_answer)

            t_behavior = time.perf_counter()
            behavior_command = behavior_for_state(
                behavior_state,
                variant=attention_variant if behavior_state == "ATTENTION_SEEKING" else None,
            )
            behavior_ms = (time.perf_counter() - t_behavior) * 1000.0

            export_ms = 0.0
            if ENABLE_BEHAVIOR_EXPORT:
                t_export = time.perf_counter()
                export_behavior_command(
                    behavior_command,
                    listening=listening_overlay,
                )
                export_ms = (time.perf_counter() - t_export) * 1000.0

            if (
                sheet_logger is not None
                and sheet_logger.enabled
                and (now - last_log_time) >= LOG_INTERVAL_SECONDS
            ):
                sheet_logger.append_row(
                    state=state,
                    cmd=behavior_command,
                    perception=perception_result,
                )
                last_log_time = now

            if async_object_perception is not None:
                if (
                    now - last_object_submit_time
                    >= OBJECT_DETECTION_INTERVAL_SECONDS
                ):
                    pending_submit_ms_for_latency = async_object_perception.submit_frame(
                        frame
                    )
                    last_object_submit_time = now
                object_result = async_object_perception.get_latest_result()
                mem_update = async_object_perception.take_memory_update_if_new()
                if mem_update is not None:
                    object_memory.add_sightings(mem_update.objects, state)

            metrics_age_s: Optional[float] = None
            if (
                ENABLE_METRICS
                and metrics_expected is not None
                and metrics_expected_set_time is not None
            ):
                metrics_age_s = max(0.0, now - metrics_expected_set_time)

            metrics_overlay = metrics_expected if ENABLE_METRICS else ""
            draw_perception(
                frame,
                perception_result,
                state,
                fps=fps_smooth if ENABLE_PERCEPTION_DEBUG else None,
                frame_ms=last_frame_ms if ENABLE_PERCEPTION_DEBUG else None,
                show_debug=ENABLE_PERCEPTION_DEBUG,
                object_result=object_result if ENABLE_OBJECT_DETECTION else None,
                latest_answer=latest_answer if replying else None,
                listening=listening_overlay,
                behavior_variant=attention_variant,
                engagement_prediction=engagement_prediction,
                metrics_expected_label=metrics_overlay or "",
                metrics_expected_age_s=metrics_age_s,
            )

            elapsed = time.perf_counter() - t_iter_start
            last_frame_ms = elapsed * 1000.0
            total_loop_ms = last_frame_ms
            inst_fps = 1.0 / elapsed if elapsed > 1e-9 else 0.0
            if fps_smooth <= 0.0:
                fps_smooth = inst_fps
            else:
                fps_smooth = (
                    _FPS_SMOOTH_ALPHA * inst_fps
                    + (1.0 - _FPS_SMOOTH_ALPHA) * fps_smooth
                )

            if ENABLE_METRICS and metrics_logger is not None:
                if (
                    now - last_metrics_latency_ts
                    >= METRICS_LATENCY_LOG_INTERVAL_SECONDS
                ):
                    obj_submit_log = pending_submit_ms_for_latency
                    pending_submit_ms_for_latency = None
                    obj_inf_log = None
                    if (
                        async_object_perception is not None
                        and async_object_perception.has_completed_inference()
                    ):
                        obj_inf_log = async_object_perception.last_inference_ms

                    metrics_logger.log_latency(
                        LatencySample(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            frame_ms=frame_ms,
                            perception_ms=perception_ms,
                            state_ms=state_ms,
                            behavior_ms=behavior_ms,
                            object_submit_ms=obj_submit_log,
                            object_inference_ms=obj_inf_log,
                            export_ms=export_ms,
                            total_loop_ms=total_loop_ms,
                        )
                    )
                    last_metrics_latency_ts = now

            if ENABLE_PERCEPTION_DEBUG:
                if now - last_perf_print >= _PERF_PRINT_INTERVAL_S:
                    print(
                        f"perf: FPS ~ {fps_smooth:.1f}  frame_ms ~ {last_frame_ms:.1f}"
                    )
                    last_perf_print = now

            cv2.imshow("Webcam", frame)
            key = cv2.waitKey(5) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                perception.start_calibration()
            elif key == ord("r"):
                perception.reset_calibration()
            elif key == ord("1"):
                if ENABLE_METRICS:
                    metrics_expected = "ENGAGED"
                    metrics_expected_set_time = time.time()
                    print("Metrics: expected label = ENGAGED")
            elif key == ord("2"):
                if ENABLE_METRICS:
                    metrics_expected = "DISENGAGED"
                    metrics_expected_set_time = time.time()
                    print("Metrics: expected label = DISENGAGED")
            elif key == ord("0"):
                if ENABLE_METRICS:
                    metrics_expected = None
                    metrics_expected_set_time = None
                    print("Metrics: expected label cleared")
            elif key == ord("m"):
                if ENABLE_METRICS:
                    emit_engagement_trial(force_without_settle=True)
            elif key == ord("n"):
                if ENABLE_METRICS:
                    emit_engagement_trial(force_without_settle=False)
    finally:
        if ENABLE_METRICS and metrics_logger is not None:
            metrics_logger.write_summary()
            print("Metrics: wrote runtime/metrics/summary.md")
        if voice_output is not None:
            voice_output.close()
        if voice_input is not None:
            voice_input.close()
        if sheet_logger is not None:
            sheet_logger.close_session()
        webcam.release()
        perception.close()
        if async_object_perception is not None:
            async_object_perception.close()
        if object_perception is not None:
            object_perception.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
