"""
Rejected static shapes for capture_exception (must fail type-check).
"""

from __future__ import annotations

from portal.libs.telemetry import capture_exception


def rejected_calls() -> None:
    capture_exception("not-an-exception")
    capture_exception(None)
    capture_exception(RuntimeError("synthetic"), "extra")
