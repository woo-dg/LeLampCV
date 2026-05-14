from __future__ import annotations

import queue
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import gspread

from .behavior import LampBehaviorCommand
from .perception import FacePerceptionResult

_LEGACY_WORKSHEET_TITLE = "Behavior Log"
# map_behaviour uses "Behavior Log Run N"; older sessions may use "Behaviour Map N".
_RUN_TITLE_PATTERNS = (
    re.compile(r"^(?:Behaviour|Behavior) Log Run (\d+)$", re.IGNORECASE),
    re.compile(r"^(?:Behaviour|Behavior)\s*Map\s*(\d+)\s*$", re.IGNORECASE),
)

_HEADERS = [
    "timestamp",
    "state",
    "behavior_name",
    "variant",
    "pan_angle",
    "tilt_angle",
    "light_color",
    "brightness",
    "motion_description",
    "light_description",
    "reason",
    "face_detected",
    "head_forward",
    "eye_contact",
    "gaze_direction",
    "looking_at_camera",
    "debug_text",
]

_SESSION_END_FILL = "-"

_QUEUE_MAX = 64


def _max_behavior_run_number(spreadsheet: gspread.Spreadsheet) -> int:
    highest = 0
    for ws in spreadsheet.worksheets():
        title = ws.title.strip()
        for pat in _RUN_TITLE_PATTERNS:
            m = pat.match(title)
            if m:
                highest = max(highest, int(m.group(1)))
                break
    return highest


def _existing_worksheet_titles_lower(spreadsheet: gspread.Spreadsheet) -> set[str]:
    return {ws.title.strip().lower() for ws in spreadsheet.worksheets()}


def _add_session_run_worksheet(
    spreadsheet: gspread.Spreadsheet,
    *,
    headers: list[str],
) -> tuple[Any, str]:
    """Create the next ``Behavior Log Run N`` tab (same naming as map_behaviour)."""
    base = _max_behavior_run_number(spreadsheet)
    taken_lower = _existing_worksheet_titles_lower(spreadsheet)
    last_error: Optional[BaseException] = None

    for offset in range(200):
        n = base + 1 + offset
        title = f"Behavior Log Run {n}"
        if title.lower() in taken_lower:
            continue
        try:
            ws = spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=len(headers),
            )
            ws.append_row(headers)
            taken_lower.add(title.lower())
            return ws, title
        except Exception as exc:
            last_error = exc
            msg = str(exc).lower()
            if (
                "already exists" in msg
                or "duplicate" in msg
                or "already been taken" in msg
                or "invalid title" in msg
                or "already created" in msg
            ):
                taken_lower.add(title.lower())
                continue
            raise

    raise RuntimeError(
        f"Could not create Behavior Log Run worksheet after retries: {last_error!r}"
    )


class GoogleSheetsBehaviorLogger:
    """Enqueue rows for a background worker; camera loop never waits on network."""

    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str,
        *,
        create_new_session_sheet: bool = True,
    ) -> None:
        self._worksheet: Optional[Any] = None
        self._enabled = False
        self._queue: Optional[queue.Queue[Any]] = None
        self._worker: Optional[threading.Thread] = None

        path = Path(credentials_path)
        if not path.is_file():
            print("Google Sheets logging disabled")
            return

        try:
            gc = gspread.service_account(filename=str(path.resolve()))
            spreadsheet = gc.open_by_key(spreadsheet_id)

            if create_new_session_sheet:
                ws, title = _add_session_run_worksheet(
                    spreadsheet,
                    headers=_HEADERS,
                )
                print(f"Google Sheets logging enabled: {title}")
            else:
                try:
                    ws = spreadsheet.worksheet(_LEGACY_WORKSHEET_TITLE)
                except gspread.WorksheetNotFound:
                    ws = spreadsheet.add_worksheet(
                        title=_LEGACY_WORKSHEET_TITLE,
                        rows=1000,
                        cols=len(_HEADERS),
                    )
                if not ws.get_all_values():
                    ws.append_row(_HEADERS)
                print(f"Google Sheets logging enabled: {_LEGACY_WORKSHEET_TITLE}")

            self._worksheet = ws
            self._enabled = True
            self._queue = queue.Queue(maxsize=_QUEUE_MAX)
            self._worker = threading.Thread(
                target=self._run_worker,
                daemon=True,
                name="GoogleSheetsBehaviorLogger",
            )
            self._worker.start()
        except Exception as exc:
            print(
                f"Google Sheets logging disabled ({type(exc).__name__}: {exc})"
            )
            self._worksheet = None
            self._enabled = False
            self._queue = None
            self._worker = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _enqueue_row(self, row: list[Any]) -> None:
        if self._queue is None:
            return
        try:
            self._queue.put_nowait(row)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(row)
            except queue.Full:
                print("Warning: Google Sheets queue full; dropping log row")

    def _run_worker(self) -> None:
        worksheet = self._worksheet
        q = self._queue
        if worksheet is None or q is None:
            return
        while True:
            item = q.get()
            if item is None:
                break
            try:
                worksheet.append_row(item, value_input_option="USER_ENTERED")
            except Exception as exc:
                print(
                    f"Warning: Google Sheets logging failed ({type(exc).__name__}: {exc})"
                )

    def append_row(
        self,
        *,
        state: str,
        cmd: LampBehaviorCommand,
        perception: FacePerceptionResult,
    ) -> None:
        if not self._enabled or self._worksheet is None:
            return

        timestamp_iso = datetime.now(timezone.utc).isoformat()
        row = [
            timestamp_iso,
            state,
            cmd.behavior_name,
            cmd.variant,
            cmd.pan_angle,
            cmd.tilt_angle,
            cmd.light_color,
            cmd.brightness,
            cmd.motion_description,
            cmd.light_description,
            cmd.reason,
            perception.face_detected,
            perception.head_forward,
            perception.eye_contact,
            perception.gaze_direction,
            perception.looking_at_camera,
            perception.debug_text,
        ]
        self._enqueue_row(row)

    def close_session(self) -> None:
        if not self._enabled or self._worksheet is None or self._queue is None:
            return
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        row = [
            timestamp_iso,
            "SESSION_END",
            "session_closed",
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            "camera session ended",
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
            _SESSION_END_FILL,
        ]
        self._enqueue_row(row)
        if self._worker is None:
            return
        try:
            self._queue.put(None, timeout=60.0)
        except queue.Full:
            print(
                "Warning: Google Sheets worker queue stuck; SESSION_END may not be written"
            )
        self._worker.join(timeout=15.0)
