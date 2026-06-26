"""
Org position repository.
"""
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import ujson
import sqlalchemy as sa
from asyncpg import UniqueViolationError

from portal.application.org.results import (
    AssignablePositionResult,
    PositionDetailResult,
    PositionListItemResult,
    PositionTranslationItemResult,
)
from portal.application.rbac.commands import PagesQueryCommand
from portal.infrastructure.persistence.repositories.shared.translation_queries import (
    locale_scoped_max,
    position_name_fallback,
    position_translations_agg,
)
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthUser,
    AuthUserProfile,
    OrgPosition,
    OrgPositionAssignment,
    OrgPositionTranslation,
    SystemLocale,
)
from portal.models.mixins.context import apply_audit_fields_to_rows


class PositionRepository:
    """SQLAlchemy-backed org position repository."""

    def __init__(self, session: Session):
        self._session = session

    def _detail_select(self, locale_id: Optional[UUID] = None):
        return self._session.select(
            OrgPosition.id,
            OrgPosition.code,
            OrgPosition.can_own_ministry,
            OrgPosition.is_active,
            OrgPosition.sequence,
            OrgPosition.created_at,
            OrgPosition.created_by,
            OrgPosition.updated_at,
            OrgPosition.updated_by,
            OrgPosition.delete_reason,
            locale_scoped_max(OrgPositionTranslation.team, OrgPositionTranslation, locale_id).label("team"),
            locale_scoped_max(OrgPositionTranslation.office, OrgPositionTranslation, locale_id).label("office"),
            position_name_fallback(locale_id).label("name"),
            position_translations_agg(),
        ).select_from(OrgPosition)

    def _detail_query(self, locale_id: Optional[UUID] = None, all_locales: bool = False):
        query = self._detail_select(locale_id)
        if all_locales:
            return query.outerjoin(
                OrgPositionTranslation,
                OrgPositionTranslation.position_id == OrgPosition.id,
            )
        if locale_id:
            return query.outerjoin(
                OrgPositionTranslation,
                sa.and_(
                    OrgPositionTranslation.position_id == OrgPosition.id,
                    OrgPositionTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(OrgPositionTranslation, sa.false())

    @staticmethod
    def _parse_translations(raw: Any) -> list[PositionTranslationItemResult]:
        if not raw:
            return []
        items = []
        for entry in raw:
            if not entry:
                continue
            if isinstance(entry, str):
                try:
                    entry = ujson.loads(entry)
                except ujson.JSONDecodeError:
                    continue
            items.append(
                PositionTranslationItemResult(
                    locale_id=entry.get("locale_id") or entry.get("localeId"),
                    name=entry.get("name", ""),
                    description=entry.get("description"),
                    remark=entry.get("remark"),
                )
            )
        return items

    def _normalize_row(self, row: Optional[PositionDetailResult]) -> Optional[PositionDetailResult]:
        if not row:
            return None
        data = row.model_dump()
        translations = data.pop("translations", None)
        data["translations"] = self._parse_translations(translations)
        data.pop("name", None)
        return PositionDetailResult.model_validate(data)

    def _normalize_items(self, items: list[PositionDetailResult]) -> list[PositionDetailResult]:
        return [self._normalize_row(item) for item in items if item]

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[PositionDetailResult], int]:
        keyword_exists = sa.exists(
            sa.select(1)
            .select_from(OrgPositionTranslation)
            .where(OrgPositionTranslation.position_id == OrgPosition.id)
            .where(
                sa.or_(
                    OrgPositionTranslation.team.ilike(f"%{model.keyword}%"),
                    OrgPositionTranslation.office.ilike(f"%{model.keyword}%"),
                    OrgPositionTranslation.name.ilike(f"%{model.keyword}%"),
                )
            )
        )
        query = self._detail_query(locale_id).where(OrgPosition.is_deleted == model.deleted)
        query = query.where(
            model.keyword,
            lambda: sa.or_(
                OrgPosition.code.ilike(f"%{model.keyword}%"),
                keyword_exists,
            ),
        )
        items, count = await (
            query.group_by(OrgPosition.id)
            .order_by_with(
                tables=[OrgPosition],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=PositionDetailResult)
        )
        normalized = self._normalize_items(items)
        enriched = []
        for item in normalized:
            current_user_id = await self._current_user_id(item.id)
            enriched.append(item.model_copy(update={"current_user_id": current_user_id}))
        return enriched, count

    async def get_by_id(
        self,
        position_id: UUID,
        locale_id: Optional[UUID] = None,
        all_locales: bool = False,
    ) -> Optional[PositionDetailResult]:
        row: Optional[PositionDetailResult] = await (
            self._detail_query(locale_id, all_locales)
            .where(OrgPosition.id == position_id)
            .group_by(OrgPosition.id)
            .fetchrow(as_model=PositionDetailResult)
        )
        normalized = self._normalize_row(row)
        if not normalized:
            return None
        current_user_id = await self._current_user_id(position_id)
        return normalized.model_copy(update={"current_user_id": current_user_id})

    async def _current_user_id(self, position_id: UUID) -> Optional[UUID]:
        return await (
            self._session.select(OrgPositionAssignment.user_id)
            .where(OrgPositionAssignment.position_id == position_id)
            .where(OrgPositionAssignment.end_at.is_(None))
            .order_by(OrgPositionAssignment.start_at.desc())
            .limit(1)
            .fetchval()
        )

    async def list_assignable(self, locale_id: Optional[UUID]) -> list[AssignablePositionResult]:
        display_name = sa.func.coalesce(AuthUserProfile.preferred_name, AuthUser.email)
        query = self._session.select(
            OrgPosition.id,
            OrgPosition.code,
            locale_scoped_max(OrgPositionTranslation.team, OrgPositionTranslation, locale_id).label("team"),
            locale_scoped_max(OrgPositionTranslation.office, OrgPositionTranslation, locale_id).label("office"),
            position_name_fallback(locale_id).label("name"),
            OrgPositionAssignment.user_id.label("incumbent_user_id"),
            display_name.label("incumbent_display_name"),
        ).select_from(OrgPosition)
        if locale_id:
            query = query.outerjoin(
                OrgPositionTranslation,
                sa.and_(
                    OrgPositionTranslation.position_id == OrgPosition.id,
                    OrgPositionTranslation.locale_id == locale_id,
                ),
            )
        else:
            query = query.outerjoin(OrgPositionTranslation, sa.false())
        query = query.outerjoin(
            OrgPositionAssignment,
            sa.and_(
                OrgPositionAssignment.position_id == OrgPosition.id,
                OrgPositionAssignment.end_at.is_(None),
            ),
        ).outerjoin(AuthUser, AuthUser.id == OrgPositionAssignment.user_id).outerjoin(
            AuthUserProfile,
            AuthUserProfile.user_id == AuthUser.id,
        )
        items: list[AssignablePositionResult] = await (
            query.where(OrgPosition.is_deleted == False)
            .where(OrgPosition.is_active == True)
            .where(OrgPosition.can_own_ministry == True)
            .group_by(
                OrgPosition.id,
                OrgPosition.code,
                OrgPositionAssignment.user_id,
                AuthUser.email,
                AuthUserProfile.preferred_name,
            )
            .order_by(OrgPosition.sequence)
            .fetch(as_model=AssignablePositionResult)
        )
        return items or []

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        active_locale_ids = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id.in_(locale_ids))
            .where(SystemLocale.is_active == True)
            .where(SystemLocale.is_deleted == False)
            .fetchvals()
        )
        return set(active_locale_ids)

    async def insert_position(self, payload: dict[str, Any]) -> None:
        await self._session.insert(OrgPosition).values(payload).execute()

    async def update_position(self, position_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(OrgPosition)
            .values(**values)
            .where(OrgPosition.id == position_id)
            .where(OrgPosition.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        rows = apply_audit_fields_to_rows(rows)
        await (
            self._session.insert(OrgPositionTranslation)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["position_id", "locale_id"],
                set_=dict(
                    team=sa.literal_column("excluded.team"),
                    office=sa.literal_column("excluded.office"),
                    name=sa.literal_column("excluded.name"),
                    description=sa.literal_column("excluded.description"),
                    remark=sa.literal_column("excluded.remark"),
                ),
            )
            .execute()
        )

    async def assign_incumbent(
        self,
        position_id: UUID,
        user_id: UUID,
        start_at: Optional[datetime] = None,
    ) -> None:
        now = start_at or datetime.now(timezone.utc)
        await (
            self._session.update(OrgPositionAssignment)
            .values(end_at=now)
            .where(OrgPositionAssignment.position_id == position_id)
            .where(OrgPositionAssignment.end_at.is_(None))
            .execute()
        )
        await (
            self._session.insert(OrgPositionAssignment)
            .values(
                position_id=position_id,
                user_id=user_id,
                start_at=now,
            )
            .execute()
        )

    async def delete_soft(self, position_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(OrgPosition)
            .values(is_deleted=True, delete_reason=reason)
            .where(OrgPosition.id == position_id)
            .execute()
        )

    async def delete_hard(self, position_id: UUID) -> None:
        await (
            self._session.delete(OrgPositionAssignment)
            .where(OrgPositionAssignment.position_id == position_id)
            .execute()
        )
        await self._session.delete(OrgPosition).where(OrgPosition.id == position_id).execute()

    async def restore_position(self, position_id: UUID) -> None:
        await (
            self._session.update(OrgPosition)
            .values(is_deleted=False, delete_reason=None)
            .where(OrgPosition.id == position_id)
            .execute()
        )

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
