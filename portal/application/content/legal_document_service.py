"""
Legal Document application service (admin list/detail/create/update/delete/restore).
"""

from typing import Any
from uuid import UUID, uuid4

from portal.application.content.commands import CreateLegalDocumentCommand, LegalDocumentPagesQueryCommand, UpdateLegalDocumentCommand
from portal.application.content.results import CreateIdResult, LegalDocumentDetailResult, LegalDocumentPageResult
from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.domain.content.constants import ContentErrorCode, LegalDocumentKind, ProductCode
from portal.domain.content.ports import LegalDocumentRepositoryPort
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from portal.libs.tracing.distributed_trace import distributed_trace

_CATALOG_PRODUCTS = {item.value for item in ProductCode}
_CATALOG_KINDS = {item.value for item in LegalDocumentKind}


class LegalDocumentService:
    """Admin Legal Document list, detail, create, living Markdown update, soft-delete, restore."""

    def __init__(self, legal_document_repository: LegalDocumentRepositoryPort):
        self._repository = legal_document_repository

    @staticmethod
    def _build_translation_rows(command: UpdateLegalDocumentCommand) -> list[dict[str, Any]]:
        return [dict(locale_id=item.locale_id, body=item.body) for item in command.translations]

    @staticmethod
    def _assert_catalog_pair(product: str, kind: str) -> None:
        if product not in _CATALOG_PRODUCTS or kind not in _CATALOG_KINDS:
            raise BadRequestException(detail="product and kind must be from the built-in Legal Document catalog", context={"product": product, "kind": kind})

    async def _validate_and_upsert_translations(self, document_id: UUID, translation_rows: list[dict[str, Any]]) -> None:
        if not translation_rows:
            raise BadRequestException(detail="translations are required")
        locale_ids = [item["locale_id"] for item in translation_rows]
        if len(locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Duplicate locale_id in translations")
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        await self._repository.upsert_translations(document_id, translation_rows)

    @distributed_trace()
    async def get_legal_document_pages(self, command: LegalDocumentPagesQueryCommand) -> LegalDocumentPageResult:
        items, count = await self._repository.fetch_pages(command)
        return LegalDocumentPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_legal_document_by_id(self, document_id: UUID) -> LegalDocumentDetailResult:
        row = await self._repository.get_by_id(document_id)
        if not row:
            raise NotFoundException(
                detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
            )
        return row

    @distributed_trace()
    async def create_legal_document(self, command: CreateLegalDocumentCommand) -> CreateIdResult:
        product = command.product.strip()
        kind = command.kind.strip()
        self._assert_catalog_pair(product, kind)
        existing = await self._repository.get_by_product_kind(product, kind, include_deleted=True)
        if existing:
            if existing.is_deleted:
                raise ConflictErrorException(
                    detail="Legal Document exists in recycle bin; restore it instead",
                    error_code=ContentErrorCode.LEGAL_DOCUMENT_IN_RECYCLE_BIN.value,
                    context={"product": product, "kind": kind, "document_id": str(existing.id)},
                )
            raise ConflictErrorException(
                detail="Legal Document for this product and kind already exists",
                error_code=ContentErrorCode.LEGAL_DOCUMENT_EXISTS.value,
                context={"product": product, "kind": kind, "document_id": str(existing.id)},
            )
        document_id = uuid4()
        await self._repository.insert_document(dict(id=document_id, product=product, kind=kind))
        return CreateIdResult(id=document_id)

    @distributed_trace()
    async def update_legal_document(self, document_id: UUID, command: UpdateLegalDocumentCommand) -> LegalDocumentDetailResult:
        existing = await self._repository.get_by_id(document_id)
        if not existing:
            raise NotFoundException(
                detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
            )
        translation_rows = self._build_translation_rows(command)
        await self._validate_and_upsert_translations(document_id, translation_rows)
        updated = await self._repository.get_by_id(document_id)
        if not updated:
            raise NotFoundException(
                detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
            )
        return updated

    @distributed_trace()
    async def delete_legal_document(self, document_id: UUID, command: DeleteCommand) -> None:
        row = await self._repository.get_by_id(document_id, include_deleted=command.permanent)
        if not row:
            raise NotFoundException(
                detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
            )
        if command.permanent:
            affected = await self._repository.delete_hard(document_id)
        else:
            if row.is_deleted:
                raise NotFoundException(
                    detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
                )
            affected = await self._repository.delete_soft(document_id, command.reason)
        if affected < 1:
            raise NotFoundException(
                detail="Legal Document not found", error_code=ContentErrorCode.LEGAL_DOCUMENT_NOT_FOUND.value, context={"document_id": str(document_id)}
            )

    @distributed_trace()
    async def restore_legal_documents(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            return
        affected = await self._repository.restore(command.ids)
        if affected < 1:
            raise NotFoundException(detail="No deleted Legal Documents found to restore")
