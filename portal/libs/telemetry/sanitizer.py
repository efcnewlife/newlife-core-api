"""
Sentry payload sanitization: allowlist what leaves the process, drop or scrub the rest.

Events keep only diagnostic structure (exception types, stack frames without locals, the internal user ID,
route, and method). Exception values never leave the process because their text can embed SQL parameters,
emails, or names. Logs keep their template; values are kept only when they are numbers, booleans, or UUIDs.
"""

import re
from typing import Any, Optional

FILTERED = "[Filtered]"

_EVENT_KEYS = frozenset(
    {
        "event_id",
        "timestamp",
        "level",
        "platform",
        "environment",
        "release",
        "dist",
        "server_name",
        "sdk",
        "logger",
        "message",
        "transaction",
        "fingerprint",
        "tags",
        "user",
        "contexts",
        "exception",
    }
)
_CONTEXT_KEYS = frozenset({"runtime", "trace"})
_FRAME_KEYS = frozenset({"filename", "abs_path", "module", "function", "lineno", "colno", "in_app", "pre_context", "context_line", "post_context"})
_MECHANISM_KEYS = frozenset({"type", "handled", "synthetic", "exception_id", "parent_id", "is_exception_group", "source"})

_LOG_ATTRIBUTE_KEYS = frozenset({"logger.name", "server.address", "sentry.origin", "sentry.environment", "sentry.release", "sentry.message.template"})
_LOG_ATTRIBUTE_PREFIXES = ("code.", "sentry.sdk.")
_LOG_PARAMETER_PREFIX = "sentry.message.parameter."

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_SENSITIVE_KEY = r"[\w.-]*(?:password|passwd|secret|token|api_?key|authorization|cookie|session|email|phone|mobile|name|remark|address)[\w.-]*"
_TEXT_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\[parameters:[^\n]*"), f"[parameters: {FILTERED}]"),
    (re.compile(r"DETAIL:[^\n]*"), f"DETAIL: {FILTERED}"),
    (re.compile(r"(?i)\b(?:bearer|basic)\s+[\w.~+/=-]+"), FILTERED),
    (re.compile(r"eyJ[\w-]+\.[\w-]+(?:\.[\w-]*)?"), FILTERED),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), FILTERED),
    (re.compile(rf"(?i)\b({_SENSITIVE_KEY})([\"']?\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&)]+)"), rf"\1\2{FILTERED}"),
    (re.compile(r"(?<=[\w/])\?[^\s#]*=[^\s#]*"), f"?{FILTERED}"),
    (re.compile(r"(?<![\w-])(?!\d{4}-\d{2}-\d{2})\+?\(?\d(?:[\s().-]{0,2}\d){8,14}(?![\w-])"), FILTERED),
)
# Untemplated log bodies (f-strings, logged exceptions) have no parameter boundary, so every key=value is a value.
_ANY_KEY_VALUE = re.compile(r"\b([\w.-]+)(\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&)]+)")


def scrub_text(text: str) -> str:
    """
    Mask secrets and PII that free-form text may carry (emails, phones, tokens, sensitive key/value pairs).
    :param text:
    :return:
    """
    for pattern, replacement in _TEXT_RULES:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in frame.items() if key in _FRAME_KEYS}


def _sanitize_exception_value(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = {key: value[key] for key in ("type", "module") if key in value}
    if "mechanism" in value:
        sanitized["mechanism"] = {key: item for key, item in value["mechanism"].items() if key in _MECHANISM_KEYS}
    stacktrace = value.get("stacktrace")
    if stacktrace:
        sanitized["stacktrace"] = {"frames": [_sanitize_frame(frame) for frame in stacktrace.get("frames", [])]}
    return sanitized


def sanitize_event(event: dict[str, Any], _hint: Any = None) -> Optional[dict[str, Any]]:
    """
    before_send: keep only allowlisted event fields; exception text, locals, request data, and extras are dropped.
    :param event:
    :param _hint:
    :return:
    """
    sanitized = {key: value for key, value in event.items() if key in _EVENT_KEYS}
    if "contexts" in sanitized:
        sanitized["contexts"] = {key: value for key, value in sanitized["contexts"].items() if key in _CONTEXT_KEYS}
    user_id = (sanitized.pop("user", None) or {}).get("id")
    if user_id is not None:
        sanitized["user"] = {"id": str(user_id)}
    if "exception" in sanitized:
        sanitized["exception"] = {"values": [_sanitize_exception_value(value) for value in sanitized["exception"].get("values", [])]}
    if isinstance(sanitized.get("message"), str):
        sanitized["message"] = scrub_text(sanitized["message"])
    return sanitized


def _is_safe_log_parameter(value: Any) -> bool:
    if isinstance(value, (bool, int, float)):
        return True
    return isinstance(value, str) and _UUID.fullmatch(value) is not None


def sanitize_log(log: dict[str, Any], _hint: Any = None) -> Optional[dict[str, Any]]:
    """
    before_send_log: send the message template instead of the formatted body, and keep only safe parameters.
    :param log:
    :param _hint:
    :return:
    """
    attributes = log.get("attributes", {})
    template = attributes.get("sentry.message.template")
    kept: dict[str, Any] = {}
    for key, value in attributes.items():
        if key.startswith(_LOG_PARAMETER_PREFIX):
            if _is_safe_log_parameter(value):
                kept[key] = value
        elif key in _LOG_ATTRIBUTE_KEYS or key.startswith(_LOG_ATTRIBUTE_PREFIXES):
            kept[key] = value
    if template is not None:
        kept["sentry.message.template"] = log["body"] = scrub_text(str(template))
    else:
        log["body"] = _ANY_KEY_VALUE.sub(rf"\1\2{FILTERED}", scrub_text(str(log.get("body", ""))))
    log["attributes"] = kept
    return log


def drop_breadcrumb(_breadcrumb: dict[str, Any], _hint: Any = None) -> None:
    """
    before_breadcrumb: breadcrumbs are not collected; raw HTTP logs must not ride along on events.
    :return:
    """
    return None
