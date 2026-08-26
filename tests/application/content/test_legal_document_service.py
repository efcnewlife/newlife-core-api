"""
Tests for LegalDocumentService.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from portal.application.content.commands import LegalDocumentPagesQueryCommand, LegalDocumentTranslationCommand, UpdateLegalDocumentCommand
from portal.application.content.legal_document_service import LegalDocumentService
from portal.application.content.results import (
    LegalDocumentDetailResult,
    LegalDocumentListItemResult,
    LegalDocumentPageResult,
    LegalDocumentTranslationItemResult,
)
from portal.domain.content.constants import ContentErrorCode, LegalDocumentKind, ProductCode
from portal.exceptions.responses import BadRequestException, NotFoundException


def _document(
    *,
    product: str = ProductCode.FACILITY_BOOKING.value,
    kind: str = LegalDocumentKind.TERMS_OF_SERVICE.value,
    is_deleted: bool = False,
    translations: list[LegalDocumentTranslationItemResult] | None = None,
) -> LegalDocumentDetailResult:
    now = datetime.now(timezone.utc)
    return LegalDocumentDetailResult(
        id=uuid4(),
        product=product,
        kind=kind,
        created_at=now,
        created_by=None,
        updated_at=now,
        updated_by=None,
        delete_reason=None if not is_deleted else "removed",
        translations=list(translations or []),
    )


class StubLegalDocumentRepository:
    def __init__(self, rows: list[LegalDocumentDetailResult] | None = None, *, active_locale_ids: set[UUID] | None = None):
        self.rows = {row.id: row for row in (rows or [])}
        self.active_locale_ids = active_locale_ids if active_locale_ids is not None else set()
        self.upsert_calls: list[dict[str, Any]] = []

    async def fetch_pages(self, command: LegalDocumentPagesQueryCommand) -> tuple[list[LegalDocumentListItemResult], int]:
        items = [
            LegalDocumentListItemResult.model_validate(row.model_dump(exclude={"translations"}))
            for row in self.rows.values()
            if (row.delete_reason is not None) == command.deleted
        ]
        if command.product is not None:
            items = [item for item in items if item.product == command.product]
        if command.kind is not None:
            items = [item for item in items if item.kind == command.kind]
        return items, len(items)

    async def get_by_id(self, document_id: UUID, *, include_deleted: bool = False) -> Optional[LegalDocumentDetailResult]:
        row = self.rows.get(document_id)
        if not row:
            return None
        if row.delete_reason is not None and not include_deleted:
            return None
        return row

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        return {locale_id for locale_id in locale_ids if locale_id in self.active_locale_ids}

    async def upsert_translations(self, document_id: UUID, rows: list[dict[str, Any]]) -> None:
        self.upsert_calls.append({"document_id": document_id, "rows": rows})
        row = self.rows.get(document_id)
        if not row:
            return
        by_locale = {item.locale_id: item for item in row.translations}
        for payload in rows:
            by_locale[payload["locale_id"]] = LegalDocumentTranslationItemResult(locale_id=payload["locale_id"], body=payload.get("body", ""))
        self.rows[document_id] = row.model_copy(update={"translations": list(by_locale.values())})


@pytest.mark.asyncio
async def test_update_legal_document_replaces_translation_bodies():
    locale_en = uuid4()
    locale_zh = uuid4()
    document = _document(translations=[LegalDocumentTranslationItemResult(locale_id=locale_en, body="old terms")])
    repository = StubLegalDocumentRepository([document], active_locale_ids={locale_en, locale_zh})
    service = LegalDocumentService(repository)

    result = await service.update_legal_document(
        document.id,
        UpdateLegalDocumentCommand(
            translations=[LegalDocumentTranslationCommand(locale_id=locale_en, body="# Terms"), LegalDocumentTranslationCommand(locale_id=locale_zh, body="")]
        ),
    )

    assert isinstance(result, LegalDocumentDetailResult)
    assert len(repository.upsert_calls) == 1
    bodies = {item.locale_id: item.body for item in result.translations}
    assert bodies[locale_en] == "# Terms"
    assert bodies[locale_zh] == ""


@pytest.mark.asyncio
async def test_update_legal_document_not_found():
    service = LegalDocumentService(StubLegalDocumentRepository())

    with pytest.raises(NotFoundException) as exc_info:
        await service.update_legal_document(uuid4(), UpdateLegalDocumentCommand(translations=[LegalDocumentTranslationCommand(locale_id=uuid4(), body="x")]))

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value


@pytest.mark.asyncio
async def test_update_legal_document_rejects_inactive_locale():
    locale_en = uuid4()
    document = _document()
    repository = StubLegalDocumentRepository([document], active_locale_ids=set())
    service = LegalDocumentService(repository)

    with pytest.raises(BadRequestException, match="Invalid or inactive locale_id"):
        await service.update_legal_document(
            document.id, UpdateLegalDocumentCommand(translations=[LegalDocumentTranslationCommand(locale_id=locale_en, body="x")])
        )


@pytest.mark.asyncio
async def test_get_legal_document_pages_filters_product_and_kind():
    matching = _document(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.PRIVACY_POLICY.value)
    other = _document(product=ProductCode.FACILITY_BOOKING.value, kind=LegalDocumentKind.TERMS_OF_SERVICE.value)
    service = LegalDocumentService(StubLegalDocumentRepository([matching, other]))

    result = await service.get_legal_document_pages(
        LegalDocumentPagesQueryCommand(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.PRIVACY_POLICY.value)
    )

    assert isinstance(result, LegalDocumentPageResult)
    assert result.total == 1
    assert result.items[0].id == matching.id
    assert result.items[0].product == ProductCode.PORTAL.value
    assert result.items[0].kind == LegalDocumentKind.PRIVACY_POLICY.value


@pytest.mark.asyncio
async def test_get_legal_document_by_id_returns_translations():
    locale_en = uuid4()
    document = _document(translations=[LegalDocumentTranslationItemResult(locale_id=locale_en, body="hello")])
    service = LegalDocumentService(StubLegalDocumentRepository([document]))

    result = await service.get_legal_document_by_id(document.id)

    assert result.id == document.id
    assert result.translations[0].body == "hello"


@pytest.mark.asyncio
async def test_get_legal_document_by_id_not_found():
    service = LegalDocumentService(StubLegalDocumentRepository())

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_legal_document_by_id(uuid4())

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value
