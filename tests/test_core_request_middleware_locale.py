from uuid import UUID

import pytest
from fastapi import Request
from starlette.applications import Starlette
from starlette.responses import Response

from portal.libs.contexts.request_context import get_request_context
from portal.middlewares.core_request import CoreRequestMiddleware


class FakeLocaleService:
    def __init__(self, snapshot: dict, language_map: dict[str, list[str]]):
        self.snapshot = snapshot
        self.language_map = language_map

    async def get_locale_snapshot(self) -> dict:
        return self.snapshot

    async def get_locale_codes_by_language(self, language_code: str) -> list[str]:
        return self.language_map.get(language_code, [])


class FakeDbSession:
    def __init__(self):
        self.committed = False
        self.closed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def close(self):
        self.closed = True

    async def rollback(self):
        self.rolled_back = True


class FakeContainer:
    def __init__(self):
        self.session = FakeDbSession()

    def db_session(self):
        return self.session


def build_request(headers: list[tuple[bytes, bytes]], app: Starlette) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/test",
        "raw_path": b"/test",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "app": app,
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope=scope, receive=receive)


@pytest.mark.asyncio
async def test_parse_accept_language_order():
    parsed = CoreRequestMiddleware._parse_accept_language(
        "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5"
    )
    assert parsed == ["fr-ch", "fr", "en", "de", "*"]


@pytest.mark.asyncio
async def test_locale_detector_exact_match():
    middleware = CoreRequestMiddleware(app=Starlette())
    handler = FakeLocaleService(
        snapshot={
            "active_locales": ["en-US", "fr-CH"],
            "default_locale": "en-US",
            "normalized_map": {"en-us": "en-US", "fr-ch": "fr-CH"},
            "normalized_id_map": {
                "en-us": "00000000-0000-0000-0000-000000000001",
                "fr-ch": "00000000-0000-0000-0000-000000000002",
            },
        },
        language_map={"fr": ["fr-CH"]},
    )
    resolved_code, resolved_id, candidates = await middleware.locale_detector(
        "fr-CH, en;q=0.8",
        locale_service=handler,
    )
    assert resolved_code == "fr-CH"
    assert resolved_id == UUID("00000000-0000-0000-0000-000000000002")
    assert candidates == ["fr-ch", "en"]


@pytest.mark.asyncio
async def test_locale_detector_language_fallback():
    middleware = CoreRequestMiddleware(app=Starlette())
    handler = FakeLocaleService(
        snapshot={
            "active_locales": ["en-US", "fr-CH"],
            "default_locale": "en-US",
            "normalized_map": {"en-us": "en-US", "fr-ch": "fr-CH"},
            "normalized_id_map": {
                "en-us": "00000000-0000-0000-0000-000000000001",
                "fr-ch": "00000000-0000-0000-0000-000000000002",
            },
        },
        language_map={"fr": ["fr-CH"]},
    )
    resolved_code, resolved_id, _ = await middleware.locale_detector(
        "fr-FR, en;q=0.8",
        locale_service=handler,
    )
    assert resolved_code == "fr-CH"
    assert resolved_id == UUID("00000000-0000-0000-0000-000000000002")


@pytest.mark.asyncio
async def test_locale_detector_wildcard_fallback_to_default():
    middleware = CoreRequestMiddleware(app=Starlette())
    handler = FakeLocaleService(
        snapshot={
            "active_locales": ["en-US", "fr-CH"],
            "default_locale": "en-US",
            "normalized_map": {"en-us": "en-US", "fr-ch": "fr-CH"},
            "normalized_id_map": {
                "en-us": "00000000-0000-0000-0000-000000000001",
                "fr-ch": "00000000-0000-0000-0000-000000000002",
            },
        },
        language_map={},
    )
    resolved_code, resolved_id, _ = await middleware.locale_detector(
        "*;q=0.1",
        locale_service=handler,
    )
    assert resolved_code == "en-US"
    assert resolved_id == UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_dispatch_sets_resolved_locale_in_request_context():
    app = Starlette()
    app.container = FakeContainer()
    middleware = CoreRequestMiddleware(app=app)

    async def fake_locale_detector(_accept_language):
        return "en-US", UUID("00000000-0000-0000-0000-000000000001"), ["en-us"]

    middleware.locale_detector = fake_locale_detector  # type: ignore[assignment]

    captured = {}

    async def call_next(_request):
        req_ctx = get_request_context()
        captured["resolved_locale_code"] = req_ctx.resolved_locale_code
        captured["resolved_locale_id"] = req_ctx.resolved_locale_id
        captured["locale_candidates"] = req_ctx.locale_candidates
        captured["accept_language"] = req_ctx.headers.accept_language
        return Response("ok")

    request = build_request(
        headers=[
            (b"host", b"testserver"),
            (b"user-agent", b"pytest"),
            (b"accept-language", b"en-US,en;q=0.9"),
        ],
        app=app,
    )

    response = await middleware.dispatch(request=request, call_next=call_next)
    assert response.status_code == 200
    assert captured["resolved_locale_code"] == "en-US"
    assert captured["resolved_locale_id"] == UUID("00000000-0000-0000-0000-000000000001")
    assert captured["locale_candidates"] == ["en-us"]
    assert captured["accept_language"] == "en-US,en;q=0.9"
    assert app.container.session.committed is True
    assert app.container.session.closed is True
