"""
Legal Document repository.
"""

from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from portal.application.content.commands import LegalDocumentPagesQueryCommand
from portal.application.content.results import LegalDocumentDetailResult, LegalDocumentListItemResult
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import ContentLegalDocument, ContentLegalDocumentTranslation, SystemLocale
from portal.models.mixins.context import apply_audit_fields_to_rows


class LegalDocumentRepository:
    """SQLAlchemy-backed Legal Document repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _translations_agg():
        translation_json = sa.cast(
            sa.func.json_build_object(
                sa.cast("locale_id", sa.VARCHAR(16)),
                ContentLegalDocumentTranslation.locale_id,
                sa.cast("body", sa.VARCHAR(8)),
                ContentLegalDocumentTranslation.body,
            ),
            JSONB,
        )
        return sa.func.coalesce(
            sa.func.array_agg(sa.distinct(translation_json)).filter(ContentLegalDocumentTranslation.id.isnot(None)), sa.cast(sa.text("'{}'"), sa.ARRAY(JSONB))
        ).label("translations")

    async def fetch_pages(self, command: LegalDocumentPagesQueryCommand) -> tuple[list[LegalDocumentListItemResult], int]:
        items, count = await (
            self._session.select(
                ContentLegalDocument.id,
                ContentLegalDocument.product,
                ContentLegalDocument.kind,
                ContentLegalDocument.effective_date,
                ContentLegalDocument.created_at,
                ContentLegalDocument.created_by,
                ContentLegalDocument.updated_at,
                ContentLegalDocument.updated_by,
                ContentLegalDocument.is_deleted,
                ContentLegalDocument.delete_reason,
            )
            .select_from(ContentLegalDocument)
            .where(ContentLegalDocument.is_deleted == command.deleted)
            .where(command.product is not None, lambda: ContentLegalDocument.product == command.product)
            .where(command.kind is not None, lambda: ContentLegalDocument.kind == command.kind)
            .order_by_with(tables=[ContentLegalDocument], order_by=command.order_by, descending=command.descending)
            .limit(command.page_size)
            .offset(command.page * command.page_size)
            .fetchpages(no_order_by=False, as_model=LegalDocumentListItemResult)
        )
        return items or [], count

    async def get_by_id(self, document_id: UUID, *, include_deleted: bool = False) -> Optional[LegalDocumentDetailResult]:
        query = (
            self._session.select(
                ContentLegalDocument.id,
                ContentLegalDocument.product,
                ContentLegalDocument.kind,
                ContentLegalDocument.effective_date,
                ContentLegalDocument.created_at,
                ContentLegalDocument.created_by,
                ContentLegalDocument.updated_at,
                ContentLegalDocument.updated_by,
                ContentLegalDocument.is_deleted,
                ContentLegalDocument.delete_reason,
                self._translations_agg(),
            )
            .select_from(ContentLegalDocument)
            .outerjoin(ContentLegalDocumentTranslation, ContentLegalDocumentTranslation.legal_document_id == ContentLegalDocument.id)
            .where(ContentLegalDocument.id == document_id)
            .group_by(ContentLegalDocument.id)
        )
        if not include_deleted:
            query = query.where(ContentLegalDocument.is_deleted == False)
        return await query.fetchrow(as_model=LegalDocumentDetailResult)

    async def get_by_product_kind(self, product: str, kind: str, *, include_deleted: bool = False) -> Optional[LegalDocumentDetailResult]:
        query = (
            self._session.select(
                ContentLegalDocument.id,
                ContentLegalDocument.product,
                ContentLegalDocument.kind,
                ContentLegalDocument.effective_date,
                ContentLegalDocument.created_at,
                ContentLegalDocument.created_by,
                ContentLegalDocument.updated_at,
                ContentLegalDocument.updated_by,
                ContentLegalDocument.is_deleted,
                ContentLegalDocument.delete_reason,
                self._translations_agg(),
            )
            .select_from(ContentLegalDocument)
            .outerjoin(ContentLegalDocumentTranslation, ContentLegalDocumentTranslation.legal_document_id == ContentLegalDocument.id)
            .where(ContentLegalDocument.product == product)
            .where(ContentLegalDocument.kind == kind)
            .group_by(ContentLegalDocument.id)
        )
        if not include_deleted:
            query = query.where(ContentLegalDocument.is_deleted == False)
        return await query.fetchrow(as_model=LegalDocumentDetailResult)

    async def insert_document(self, payload: dict[str, Any]) -> None:
        await self._session.insert(ContentLegalDocument).values(payload).execute()

    async def update_document(self, document_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(ContentLegalDocument)
            .values(**values)
            .where(ContentLegalDocument.id == document_id)
            .where(ContentLegalDocument.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_soft(self, document_id: UUID, reason: Optional[str]) -> int:
        result = await (
            self._session.update(ContentLegalDocument)
            .values(is_deleted=True, delete_reason=reason)
            .where(ContentLegalDocument.id == document_id)
            .where(ContentLegalDocument.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_hard(self, document_id: UUID) -> int:
        result = await self._session.delete(ContentLegalDocument).where(ContentLegalDocument.id == document_id).execute()
        return affected_rows(result)

    async def restore(self, document_ids: list[UUID]) -> int:
        if not document_ids:
            return 0
        result = await (
            self._session.update(ContentLegalDocument)
            .values(is_deleted=False, delete_reason=None)
            .where(ContentLegalDocument.id.in_(document_ids))
            .where(ContentLegalDocument.is_deleted == True)
            .execute()
        )
        return affected_rows(result)

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        active_locale_ids = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id.in_(locale_ids))
            .where(SystemLocale.is_active == True)
            .where(SystemLocale.is_deleted == False)
            .fetchvals()
        )
        return set(active_locale_ids)

    async def fetch_default_locale_id(self) -> Optional[UUID]:
        return await self._session.select(SystemLocale.id).where(SystemLocale.is_default == True).where(SystemLocale.is_deleted == False).limit(1).fetchval()

    async def upsert_translations(self, document_id: UUID, rows: list[dict[str, Any]]) -> None:
        payloads = [dict(legal_document_id=document_id, **row) for row in rows]
        payloads = apply_audit_fields_to_rows(payloads)
        await (
            self._session.insert(ContentLegalDocumentTranslation)
            .values(payloads)
            .on_conflict_do_update(index_elements=["legal_document_id", "locale_id"], set_=dict(body=sa.literal_column("excluded.body")))
            .execute()
        )
