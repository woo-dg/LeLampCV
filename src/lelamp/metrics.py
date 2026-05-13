"""Local evaluation metrics: latency samples and engagement trials (CSV + summary)."""

from __future__ import annotations

import csv
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import default_metrics_dir


def _count_field(trials: list["EngagementTrial"], attr: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in trials:
        v = (getattr(t, attr, None) or "").strip()
        if not v:
            continue
        out[v] = out.get(v, 0) + 1
    return out


@dataclass
class LatencySample:
    timestamp: str
    frame_ms: float
    perception_ms: float
    state_ms: float
    behavior_ms: float
    object_submit_ms: float | None
    object_inference_ms: float | None
    export_ms: float
    total_loop_ms: float


@dataclass
class EngagementTrial:
    timestamp: str
    expected: str
    predicted: str
    correct: bool
    notes: str
    fsm_state: str = ""
    lamp_behavior: str = ""


class MetricsLogger:
    """Append-only CSV logs and a Markdown summary; failures are warnings only."""

    _LATENCY_FIELDS = [
        "timestamp",
        "frame_ms",
        "perception_ms",
        "state_ms",
        "behavior_ms",
        "object_submit_ms",
        "object_inference_ms",
        "export_ms",
        "total_loop_ms",
    ]
    _TRIAL_FIELDS = [
        "timestamp",
        "expected",
        "predicted",
        "correct",
        "notes",
        "fsm_state",
        "lamp_behavior",
    ]

    def __init__(self, output_dir: str | None = None) -> None:
        self._dir = Path(output_dir or str(default_metrics_dir()))
        self._latency_path = self._dir / "latency_log.csv"
        self._trial_path = self._dir / "engagement_trials.csv"
        self._summary_path = self._dir / "summary.md"
        self._latency_samples: list[LatencySample] = []
        self._trials: list[EngagementTrial] = []
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(
                f"Warning: metrics folder unavailable ({type(exc).__name__}: {exc})"
            )

    def log_latency(self, sample: LatencySample) -> None:
        self._latency_samples.append(sample)
        try:
            write_header = not self._latency_path.is_file()
            with self._latency_path.open("a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=self._LATENCY_FIELDS)
                if write_header:
                    w.writeheader()
                row = asdict(sample)
                for opt in ("object_submit_ms", "object_inference_ms"):
                    v = row.get(opt)
                    row[opt] = "" if v is None else f"{float(v):.6f}"
                for k in (
                    "frame_ms",
                    "perception_ms",
                    "state_ms",
                    "behavior_ms",
                    "export_ms",
                    "total_loop_ms",
                ):
                    row[k] = f"{float(row[k]):.6f}"
                w.writerow(row)
        except OSError as exc:
            print(f"Warning: latency log write failed ({type(exc).__name__})")

    def log_engagement_trial(self, trial: EngagementTrial) -> None:
        self._trials.append(trial)
        try:
            write_header = not self._trial_path.is_file()
            with self._trial_path.open("a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=self._TRIAL_FIELDS)
                if write_header:
                    w.writeheader()
                w.writerow(asdict(trial))
        except OSError as exc:
            print(f"Warning: engagement trial write failed ({type(exc).__name__})")

    def summarize_latency(self) -> dict[str, Any]:
        samples = self._latency_samples
        if not samples:
            return {"count": 0, "fields": {}}

        def stats(vals: list[float]) -> dict[str, float]:
            if not vals:
                return {}
            return {
                "average": statistics.fmean(vals),
                "median": float(statistics.median(vals)),
                "min": min(vals),
                "max": max(vals),
            }

        fields: dict[str, dict[str, float]] = {}
        for name in (
            "frame_ms",
            "perception_ms",
            "state_ms",
            "behavior_ms",
            "export_ms",
            "total_loop_ms",
        ):
            fields[name] = stats([getattr(s, name) for s in samples])

        for opt_name in ("object_submit_ms", "object_inference_ms"):
            vals = [
                float(getattr(s, opt_name))
                for s in samples
                if getattr(s, opt_name) is not None
            ]
            fields[opt_name] = stats(vals) if vals else {}

        return {"count": len(samples), "fields": fields}

    def summarize_engagement(self) -> dict[str, Any]:
        trials = self._trials
        if not trials:
            return {
                "total": 0,
                "correct": 0,
                "overall_accuracy": None,
                "by_expected": {},
                "fsm_counts": {},
                "lamp_counts": {},
            }

        total = len(trials)
        correct = sum(1 for t in trials if t.correct)
        overall = correct / total if total else None

        by_expected: dict[str, dict[str, float | int]] = {}
        for label in ("ENGAGED", "DISENGAGED"):
            sub = [t for t in trials if t.expected == label]
            if not sub:
                by_expected[label] = {"trials": 0, "correct": 0, "accuracy": None}
            else:
                c = sum(1 for t in sub if t.correct)
                by_expected[label] = {
                    "trials": len(sub),
                    "correct": c,
                    "accuracy": c / len(sub),
                }

        return {
            "total": total,
            "correct": correct,
            "overall_accuracy": overall,
            "by_expected": by_expected,
            "fsm_counts": _count_field(trials, "fsm_state"),
            "lamp_counts": _count_field(trials, "lamp_behavior"),
        }

    def write_summary(self) -> None:
        lat = self.summarize_latency()
        eng = self.summarize_engagement()

        lines = [
            "# Evaluation Summary",
            "",
            "## Binary Engagement Reliability",
            "",
            "- **Predicted** column uses debounced binary gaze: **ENGAGED** vs **DISENGAGED** (same signal that drives the state machine before attention/cooldown phases).",
            "- **ATTENTION_SEEKING**, **COOLDOWN**, and optional **ANSWERING** lamp behavior are listed separately — they are not failures of binary engagement when your ground truth is still “disengaged.”",
            "",
        ]

        if eng["total"] == 0:
            lines.append("- No engagement trials recorded.")
        else:
            lines.extend(
                [
                    f"- total trials: {eng['total']}",
                    f"- correct trials: {eng['correct']}",
                    f"- overall accuracy: {eng['overall_accuracy']:.4f}",
                    "",
                    "- accuracy by expected class:",
                ]
            )
            for label in ("ENGAGED", "DISENGAGED"):
                be = eng["by_expected"].get(label, {})
                acc = be.get("accuracy")
                acc_s = "n/a" if acc is None else f"{float(acc):.4f}"
                n = int(be.get("trials", 0))
                lines.append(f"  - {label}: {acc_s} ({n} trials)")

            fc = eng.get("fsm_counts") or {}
            lc = eng.get("lamp_counts") or {}
            if fc:
                lines.extend(["", "- trials logged under FSM behavior **state**:"])
                for k in sorted(fc.keys()):
                    lines.append(f"  - {k}: {fc[k]}")
            if lc:
                lines.extend(["", "- trials logged under **lamp_behavior** (may include ANSWERING):"])
                for k in sorted(lc.keys()):
                    lines.append(f"  - {k}: {lc[k]}")

        lines.extend(["", "## Latency", ""])

        if lat["count"] == 0:
            lines.append("- No latency samples recorded.")
        else:
            lines.append(f"- samples: {lat['count']}")
            lines.append("")
            lines.append(
                "- Main-loop samples exclude blocking YOLO time; "
                "**object_inference_ms** is measured on the background worker."
            )
            lines.append("")
            field_order = [
                "frame_ms",
                "perception_ms",
                "state_ms",
                "behavior_ms",
                "object_submit_ms",
                "object_inference_ms",
                "export_ms",
                "total_loop_ms",
            ]
            for fname in field_order:
                st = lat["fields"].get(fname, {})
                lines.append(f"### {fname}")
                if not st:
                    lines.append("- (no data)")
                else:
                    lines.extend(
                        [
                            f"- average: {st['average']:.4f} ms",
                            f"- median: {st['median']:.4f} ms",
                            f"- min: {st['min']:.4f} ms",
                            f"- max: {st['max']:.4f} ms",
                        ]
                    )
                lines.append("")

        lines.extend(
            [
                "## Notes",
                "",
                "Trials were manually labeled using keyboard controls during live webcam testing.",
                "Prefer **n** (settled log) or wait ≥0.75s after setting expected before **m** to avoid transition-frame bias.",
                "YOLO runs asynchronously; **total_loop_ms** reflects the camera/perception path without blocking on inference.",
                "",
            ]
        )

        text = "\n".join(lines)
        try:
            self._summary_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"Warning: summary write failed ({type(exc).__name__})")
