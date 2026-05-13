"""Paths relative to the repository root.

Run ``python scripts/run_app.py`` from anywhere with cwd set to repo root so
``simulator/`` exports and these paths resolve consistently.
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """``src/lelamp/paths.py`` → parents[2] is the repo root."""
    return Path(__file__).resolve().parents[2]


def models_dir() -> Path:
    return repo_root() / "models"


def default_memory_jsonl() -> Path:
    return repo_root() / "runtime" / "memory" / "object_memory.jsonl"


def default_metrics_dir() -> Path:
    return repo_root() / "runtime" / "metrics"


def simulator_dir() -> Path:
    return repo_root() / "simulator"
