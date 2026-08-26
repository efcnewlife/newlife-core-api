"""
Legal Document application service (admin list/detail/update).
"""

from typing import Any
from uuid import UUID

from portal.application.content.commands import LegalDocumentPagesQueryCommand, UpdateLegalDocumentCommand
from portal.application.content.results import LegalDocumentDetailResult, LegalDocumentPageResult
from portal.domain.content.constants import ContentErrorCode
from portal.domain.content.ports import LegalDocumentRepositoryPort
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.libs.tracing.distributed_trace import distributed_trace


class LegalDocumentService:
    """Admin Legal Document list, detail, and living Markdown update."""

    def __init__(self, legal_document_repository: LegalDocumentRepositoryPort):
        self._repository = legal_document_repository

    @staticmethod
    def _build_translation_rows(command: UpdateLegalDocumentCommand) -> list[dict[str, Any]]:
        return [dict(locale_id=item.locale_id, body=item.body) for item in command.translations]

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
