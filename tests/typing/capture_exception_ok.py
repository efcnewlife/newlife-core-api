"""
Accepted static shapes for capture_exception (must type-check clean).
"""

from __future__ import annotations

from portal.libs.telemetry import capture_exception


def accepted_calls() -> None:
    try:
        raise RuntimeError("synthetic")
    except RuntimeError as exc:
        capture_exception(exc)

    try:
        raise ValueError("synthetic")
    except Exception as exc:
        capture_exception(exc)
