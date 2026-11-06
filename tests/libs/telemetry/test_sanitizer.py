"""
Sentry payload sanitization rules.
"""

from uuid import uuid4

import pytest

from portal.libs.telemetry.sanitizer import FILTERED, drop_breadcrumb, sanitize_event, sanitize_log, scrub_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail jane.doe+x@example.com now", f"mail {FILTERED} now"),
        ("call +886 912 345 678 now", f"call {FILTERED} now"),
        ("call 0912-345-678", f"call {FILTERED}"),
        ("call (626) 555-1234", f"call {FILTERED}"),
        ("Authorization: Bearer abc.def-ghi", f"Authorization: {FILTERED}"),
        ("token eyJhbGciOi.eyJzdWIi.c2ln here", f"token {FILTERED} here"),
        ("password=hunter2, ok", f"password={FILTERED}, ok"),
        ('"first_name": "Jane"', f'"first_name": {FILTERED}'),
        ("GET /api/v1/x?email=a&page=2 done", f"GET /api/v1/x?{FILTERED} done"),
        ("[SQL: INSERT x]\n[parameters: ('Jane', 'a')]", f"[SQL: INSERT x]\n[parameters: {FILTERED}]"),
        ("dup\nDETAIL:  Key (email)=(j) already exists.", f"dup\nDETAIL: {FILTERED}"),
    ],
)
def test_scrub_text_masks_secrets_and_pii(text: str, expected: str):
    assert scrub_text(text) == expected


@pytest.mark.parametrize("text", [f"series {uuid4()} expired", "sweep at 2026-10-27 12:00", "retry 3 of 5", "what?"])
def test_scrub_text_keeps_ids_dates_and_counts(text: str):
    assert scrub_text(text) == text


def test_sanitize_event_keeps_diagnostic_structure_only():
    event = {
        "event_id": "e",
        "level": "error",
        "environment": "stg",
        "release": "newlife-core-api@5ba2c79",
        "transaction": "/api/v1/x/{id}",
        "user": {"id": "u-1", "email": "jane@example.com", "username": "jane", "ip_address": "1.2.3.4"},
        "request": {"url": "http://x/?token=t", "data": {"password": "p"}, "headers": {"Authorization": "Bearer t"}},
        "extra": {"sys.argv": ["secret"]},
        "breadcrumbs": {"values": [{"message": "body"}]},
        "contexts": {"runtime": {"name": "CPython"}, "trace": {"trace_id": "t"}, "response": {"body": "x"}},
        "exception": {
            "values": [
                {
                    "type": "IntegrityError",
                    "module": "sqlalchemy.exc",
                    "value": "Key (email)=(jane@example.com)",
                    "mechanism": {"type": "generic", "handled": False, "data": {"secret": "s"}},
                    "stacktrace": {"frames": [{"function": "f", "lineno": 1, "context_line": "x()", "vars": {"password": "p"}}]},
                }
            ]
        },
    }

    assert sanitize_event(event) == {
        "event_id": "e",
        "level": "error",
        "environment": "stg",
        "release": "newlife-core-api@5ba2c79",
        "transaction": "/api/v1/x/{id}",
        "user": {"id": "u-1"},
        "contexts": {"runtime": {"name": "CPython"}, "trace": {"trace_id": "t"}},
        "exception": {
            "values": [
                {
                    "type": "IntegrityError",
                    "module": "sqlalchemy.exc",
                    "mechanism": {"type": "generic", "handled": False},
                    "stacktrace": {"frames": [{"function": "f", "lineno": 1, "context_line": "x()"}]},
                }
            ]
        },
    }


def test_sanitize_event_without_user_id_drops_user():
    assert "user" not in sanitize_event({"user": {"email": "jane@example.com"}})


def test_sanitize_log_sends_template_and_only_safe_parameters():
    series_id = str(uuid4())
    log = {
        "body": f"Expiry email failed for series {series_id} to jane@example.com",
        "attributes": {
            "sentry.message.template": "Expiry email failed for series %s to %s",
            "sentry.message.parameter.0": series_id,
            "sentry.message.parameter.1": "jane@example.com",
            "sentry.message.parameter.2": 3,
            "sentry.environment": "stg",
            "code.function.name": "send",
            "user.email": "jane@example.com",
            "custom.extra": "Jane",
        },
    }

    sanitized = sanitize_log(log)

    assert sanitized["body"] == "Expiry email failed for series %s to %s"
    assert sanitized["attributes"] == {
        "sentry.message.template": "Expiry email failed for series %s to %s",
        "sentry.message.parameter.0": series_id,
        "sentry.message.parameter.2": 3,
        "sentry.environment": "stg",
        "code.function.name": "send",
    }


def test_sanitize_log_masks_every_value_in_untemplated_bodies():
    log = {"body": "Error in handler H for event E: detail=Jane note='call me'", "attributes": {}}

    assert sanitize_log(log)["body"] == f"Error in handler H for event E: detail={FILTERED} note={FILTERED}"


def test_breadcrumbs_are_dropped():
    assert drop_breadcrumb({"message": "body"}) is None
