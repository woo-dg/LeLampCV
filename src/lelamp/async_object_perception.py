"""Background-thread YOLO inference so the webcam loop never waits on detect()."""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from .object_perception import ObjectPerception, ObjectPerceptionResult


class AsyncObjectPerception:
    """Queues frames from the main thread; worker runs ``ObjectPerception.detect``."""

    def __init__(
        self,
        detector: ObjectPerception,
        interval_seconds: float = 1.0,
    ) -> None:
        self._detector = detector
        self.interval_seconds = interval_seconds
        self._q: queue.Queue[Optional[object]] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._latest = ObjectPerceptionResult(objects=[], debug_text="waiting…")
        self._done_seq = 0
        self._memory_applied_seq = 0
        self._last_inference_ms = 0.0
        self._last_inference_ts = 0.0
        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="async-object-detect",
        )
        self._thread.start()

    @property
    def last_inference_ms(self) -> float:
        with self._lock:
            return self._last_inference_ms

    @property
    def last_inference_timestamp(self) -> float:
        with self._lock:
            return self._last_inference_ts

    def has_completed_inference(self) -> bool:
        with self._lock:
            return self._done_seq > 0

    def submit_frame(self, frame_bgr: object) -> float:
        """Enqueue a BGR frame copy. If the worker is busy (queue full), skip."""
        t0 = time.perf_counter()
        try:
            self._q.put_nowait(frame_bgr.copy())
        except queue.Full:
            pass
        return (time.perf_counter() - t0) * 1000.0

    def get_latest_result(self) -> ObjectPerceptionResult:
        with self._lock:
            return ObjectPerceptionResult(
                objects=list(self._latest.objects),
                debug_text=self._latest.debug_text,
            )

    def take_memory_update_if_new(self) -> Optional[ObjectPerceptionResult]:
        """Return a snapshot for ``add_sightings`` once per completed inference."""
        with self._lock:
            if self._done_seq <= self._memory_applied_seq:
                return None
            self._memory_applied_seq = self._done_seq
            return ObjectPerceptionResult(
                objects=list(self._latest.objects),
                debug_text=self._latest.debug_text,
            )

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                break
            if self._stop.is_set():
                break
            frame_bgr = item
            t0 = time.perf_counter()
            try:
                result = self._detector.detect(frame_bgr)
            except Exception as exc:
                result = ObjectPerceptionResult(
                    objects=[],
                    debug_text=f"async detection error: {type(exc).__name__}",
                )
            inf_ms = (time.perf_counter() - t0) * 1000.0
            with self._lock:
                self._latest = result
                self._last_inference_ms = inf_ms
                self._last_inference_ts = time.time()
                self._done_seq += 1

    def close(self) -> None:
        self._stop.set()
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=5.0)
