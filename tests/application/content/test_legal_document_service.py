"""
Tests for LegalDocumentService.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import pytest

from portal.application.auth.results import HeaderInfo
from portal.application.content.commands import (
    CreateLegalDocumentCommand,
    LegalDocumentPagesQueryCommand,
    LegalDocumentTranslationCommand,
    UpdateLegalDocumentCommand,
)
from portal.application.content.legal_document_service import LegalDocumentService
from portal.application.content.results import (
    CreateIdResult,
    LegalDocumentDetailResult,
    LegalDocumentListItemResult,
    LegalDocumentPageResult,
    LegalDocumentPublicResult,
    LegalDocumentTranslationItemResult,
)
from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.domain.content.constants import ContentErrorCode, LegalDocumentKind, ProductCode
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from portal.libs.contexts.request_context import RequestContext, reset_request_context, set_request_context


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
        is_deleted=is_deleted,
        delete_reason=None if not is_deleted else "removed",
        translations=list(translations or []),
    )


class StubLegalDocumentRepository:
    def __init__(
        self, rows: list[LegalDocumentDetailResult] | None = None, *, active_locale_ids: set[UUID] | None = None, default_locale_id: UUID | None = None
    ):
        self.rows = {row.id: row for row in (rows or [])}
        self.active_locale_ids = active_locale_ids if active_locale_ids is not None else set()
        self.default_locale_id = default_locale_id
        self.upsert_calls: list[dict[str, Any]] = []
        self.insert_calls: list[dict[str, Any]] = []
        self.delete_soft_calls: list[dict[str, Any]] = []
        self.restore_calls: list[list[UUID]] = []

    async def fetch_pages(self, command: LegalDocumentPagesQueryCommand) -> tuple[list[LegalDocumentListItemResult], int]:
        items = [
            LegalDocumentListItemResult.model_validate(row.model_dump(exclude={"translations"}))
            for row in self.rows.values()
            if row.is_deleted == command.deleted
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
        if row.is_deleted and not include_deleted:
            return None
        return row

    async def get_by_product_kind(self, product: str, kind: str, *, include_deleted: bool = False) -> Optional[LegalDocumentDetailResult]:
        for row in self.rows.values():
            if row.product != product or row.kind != kind:
                continue
            if row.is_deleted and not include_deleted:
                continue
            return row
        return None

    async def insert_document(self, payload: dict[str, Any]) -> None:
        self.insert_calls.append(payload)
        now = datetime.now(timezone.utc)
        document = LegalDocumentDetailResult(
            id=payload["id"],
            product=payload["product"],
            kind=payload["kind"],
            created_at=now,
            created_by=None,
            updated_at=now,
            updated_by=None,
            is_deleted=False,
            delete_reason=None,
            translations=[],
        )
        self.rows[document.id] = document

    async def delete_soft(self, document_id: UUID, reason: Optional[str]) -> int:
        row = self.rows.get(document_id)
        if not row or row.is_deleted:
            return 0
        self.delete_soft_calls.append({"document_id": document_id, "reason": reason})
        self.rows[document_id] = row.model_copy(update={"is_deleted": True, "delete_reason": reason})
        return 1

    async def delete_hard(self, document_id: UUID) -> int:
        if document_id not in self.rows:
            return 0
        del self.rows[document_id]
        return 1

    async def restore(self, document_ids: list[UUID]) -> int:
        self.restore_calls.append(list(document_ids))
        count = 0
        for document_id in document_ids:
            row = self.rows.get(document_id)
            if row and row.is_deleted:
                self.rows[document_id] = row.model_copy(update={"is_deleted": False, "delete_reason": None})
                count += 1
        return count

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        return {locale_id for locale_id in locale_ids if locale_id in self.active_locale_ids}

    async def fetch_default_locale_id(self) -> Optional[UUID]:
        return self.default_locale_id

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


@pytest.mark.asyncio
async def test_create_legal_document_when_absent():
    repository = StubLegalDocumentRepository()
    service = LegalDocumentService(repository)

    result = await service.create_legal_document(
        CreateLegalDocumentCommand(product=ProductCode.FACILITY_BOOKING.value, kind=LegalDocumentKind.PRIVACY_POLICY.value)
    )

    assert isinstance(result, CreateIdResult)
    assert len(repository.insert_calls) == 1
    assert repository.insert_calls[0]["product"] == ProductCode.FACILITY_BOOKING.value
    assert repository.insert_calls[0]["kind"] == LegalDocumentKind.PRIVACY_POLICY.value
    assert result.id in repository.rows


@pytest.mark.asyncio
async def test_create_legal_document_rejects_non_catalog_product_or_kind():
    service = LegalDocumentService(StubLegalDocumentRepository())

    with pytest.raises(BadRequestException, match="catalog"):
        await service.create_legal_document(CreateLegalDocumentCommand(product="unknown-app", kind=LegalDocumentKind.TERMS_OF_SERVICE.value))

    with pytest.raises(BadRequestException, match="catalog"):
        await service.create_legal_document(CreateLegalDocumentCommand(product=ProductCode.PORTAL.value, kind="cookie_policy"))


@pytest.mark.asyncio
async def test_create_legal_document_rejects_when_active_exists():
    existing = _document(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.TERMS_OF_SERVICE.value)
    service = LegalDocumentService(StubLegalDocumentRepository([existing]))

    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_legal_document(CreateLegalDocumentCommand(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.TERMS_OF_SERVICE.value))

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_EXISTS.value


@pytest.mark.asyncio
async def test_create_legal_document_rejects_when_soft_deleted_twin_exists():
    existing = _document(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.PRIVACY_POLICY.value, is_deleted=True)
    service = LegalDocumentService(StubLegalDocumentRepository([existing]))

    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_legal_document(CreateLegalDocumentCommand(product=ProductCode.PORTAL.value, kind=LegalDocumentKind.PRIVACY_POLICY.value))

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_IN_RECYCLE_BIN.value
    assert "restore" in (exc_info.value.detail or "").lower()


@pytest.mark.asyncio
async def test_soft_delete_legal_document():
    document = _document()
    repository = StubLegalDocumentRepository([document])
    service = LegalDocumentService(repository)

    await service.delete_legal_document(document.id, DeleteCommand(reason="cleanup"))

    assert repository.delete_soft_calls == [{"document_id": document.id, "reason": "cleanup"}]
    assert repository.rows[document.id].is_deleted is True


@pytest.mark.asyncio
async def test_restore_legal_document():
    document = _document(is_deleted=True)
    repository = StubLegalDocumentRepository([document])
    service = LegalDocumentService(repository)

    await service.restore_legal_documents(BulkIdsCommand(ids=[document.id]))

    assert repository.restore_calls == [[document.id]]
    assert repository.rows[document.id].is_deleted is False
    assert repository.rows[document.id].delete_reason is None


@pytest.mark.asyncio
async def test_get_public_legal_document_returns_empty_body_for_active_row():
    locale_en = uuid4()
    document = _document(translations=[LegalDocumentTranslationItemResult(locale_id=locale_en, body="")])
    repository = StubLegalDocumentRepository([document], default_locale_id=locale_en)
    service = LegalDocumentService(repository)
    token = set_request_context(RequestContext(headers=HeaderInfo(), resolved_locale_id=locale_en))
    try:
        result = await service.get_public_legal_document(document.product, document.kind)
    finally:
        reset_request_context(token)

    assert isinstance(result, LegalDocumentPublicResult)
    assert result.product == document.product
    assert result.kind == document.kind
    assert result.body == ""


@pytest.mark.asyncio
async def test_get_public_legal_document_not_found_when_missing():
    service = LegalDocumentService(StubLegalDocumentRepository())

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_public_legal_document(ProductCode.FACILITY_BOOKING.value, LegalDocumentKind.TERMS_OF_SERVICE.value)

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value


@pytest.mark.asyncio
async def test_get_public_legal_document_not_found_when_soft_deleted():
    document = _document(is_deleted=True, translations=[LegalDocumentTranslationItemResult(locale_id=uuid4(), body="# gone")])
    service = LegalDocumentService(StubLegalDocumentRepository([document]))

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_public_legal_document(document.product, document.kind)

    assert exc_info.value.error_code == ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value


@pytest.mark.asyncio
async def test_get_public_legal_document_falls_back_to_default_locale_body():
    locale_en = uuid4()
    locale_zh = uuid4()
    document = _document(
        translations=[
            LegalDocumentTranslationItemResult(locale_id=locale_en, body="# Default terms"),
            LegalDocumentTranslationItemResult(locale_id=locale_zh, body="# 條款"),
        ]
    )
    # Preferred locale has no translation row; only en/zh exist — use a third id as resolved.
    locale_missing = uuid4()
    repository = StubLegalDocumentRepository([document], default_locale_id=locale_en)
    service = LegalDocumentService(repository)
    token = set_request_context(RequestContext(headers=HeaderInfo(), resolved_locale_id=locale_missing))
    try:
        result = await service.get_public_legal_document(document.product, document.kind)
    finally:
        reset_request_context(token)

    assert result.body == "# Default terms"


@pytest.mark.asyncio
async def test_get_public_legal_document_uses_resolved_locale_even_when_empty():
    locale_en = uuid4()
    locale_zh = uuid4()
    document = _document(
        translations=[
            LegalDocumentTranslationItemResult(locale_id=locale_en, body="# Default terms"),
            LegalDocumentTranslationItemResult(locale_id=locale_zh, body=""),
        ]
    )
    repository = StubLegalDocumentRepository([document], default_locale_id=locale_en)
    service = LegalDocumentService(repository)
    token = set_request_context(RequestContext(headers=HeaderInfo(), resolved_locale_id=locale_zh))
    try:
        result = await service.get_public_legal_document(document.product, document.kind)
    finally:
        reset_request_context(token)

    assert result.body == ""
