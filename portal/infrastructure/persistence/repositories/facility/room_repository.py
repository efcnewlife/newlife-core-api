"""
Facility room repository.
"""
from typing import Any, Optional
from uuid import UUID

import ujson
import sqlalchemy as sa
from asyncpg import UniqueViolationError
from sqlalchemy.dialects.postgresql import JSONB

from portal.application.facility.results import RoomDetailResult, RoomListItemResult, TranslationItemResult
from portal.application.rbac.commands import PagesQueryCommand
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import FacilityRoom, FacilityRoomTranslation, SystemLocale
from portal.models.mixins.context import apply_audit_fields_to_rows


class RoomRepository:
    """SQLAlchemy-backed facility room repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _translations_agg():
        translation_json = sa.cast(
            sa.func.json_build_object(
                sa.cast("locale_id", sa.VARCHAR(16)), FacilityRoomTranslation.locale_id,
                sa.cast("name", sa.VARCHAR(8)), FacilityRoomTranslation.name,
                sa.cast("description", sa.VARCHAR(16)), FacilityRoomTranslation.description,
                sa.cast("remark", sa.VARCHAR(8)), FacilityRoomTranslation.remark,
            ),
            JSONB,
        )
        return sa.func.coalesce(
            sa.func.array_agg(sa.distinct(translation_json)).filter(FacilityRoomTranslation.id.isnot(None)),
            sa.cast(sa.text("'{}'"), sa.ARRAY(JSONB)),
        ).label("translations")

    @staticmethod
    def _locale_scoped_max(column, locale_id: Optional[UUID]):
        if locale_id:
            return sa.func.max(
                sa.case(
                    (FacilityRoomTranslation.locale_id == locale_id, column),
                    else_=None,
                )
            )
        return sa.func.max(column)

    def _detail_select(self, locale_id: Optional[UUID] = None):
        return self._session.select(
            FacilityRoom.id,
            FacilityRoom.code,
            sa.func.coalesce(
                self._locale_scoped_max(FacilityRoomTranslation.name, locale_id),
                FacilityRoom.code,
            ).label("name"),
            FacilityRoom.room_number,
            FacilityRoom.capacity,
            FacilityRoom.is_active,
            FacilityRoom.sequence,
            FacilityRoom.created_at,
            FacilityRoom.created_by,
            FacilityRoom.updated_at,
            FacilityRoom.updated_by,
            FacilityRoom.delete_reason,
            self._locale_scoped_max(FacilityRoomTranslation.description, locale_id).label("description"),
            self._translations_agg(),
        ).select_from(FacilityRoom)

    def _detail_query(self, locale_id: Optional[UUID] = None, all_locales: bool = False):
        query = self._detail_select(locale_id)
        if all_locales:
            return query.outerjoin(
                FacilityRoomTranslation,
                FacilityRoomTranslation.room_id == FacilityRoom.id,
            )
        if locale_id:
            return query.outerjoin(
                FacilityRoomTranslation,
                sa.and_(
                    FacilityRoomTranslation.room_id == FacilityRoom.id,
                    FacilityRoomTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(FacilityRoomTranslation, sa.false())

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[RoomDetailResult], int]:
        """
        Paginated room list.
        """
        items, count = await (
            self._detail_query(locale_id)
            .where(FacilityRoom.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    FacilityRoom.code.ilike(f"%{model.keyword}%"),
                    FacilityRoomTranslation.name.ilike(f"%{model.keyword}%"),
                ),
            )
            .group_by(FacilityRoom.id)
            .order_by_with(
                tables=[FacilityRoom],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RoomDetailResult)
        )
        return self._normalize_items(items), count

    async def list_active(self, locale_id: Optional[UUID]) -> list[RoomListItemResult]:
        """
        Active rooms for dropdown.
        """
        query = self._session.select(
            FacilityRoom.id,
            FacilityRoom.code,
            sa.func.coalesce(sa.func.max(FacilityRoomTranslation.name), FacilityRoom.code).label("name"),
            FacilityRoom.room_number,
            FacilityRoom.is_active,
        ).select_from(FacilityRoom)
        if locale_id:
            query = query.outerjoin(
                FacilityRoomTranslation,
                sa.and_(
                    FacilityRoomTranslation.room_id == FacilityRoom.id,
                    FacilityRoomTranslation.locale_id == locale_id,
                ),
            )
        else:
            query = query.outerjoin(FacilityRoomTranslation, sa.false())
        rooms: list[RoomListItemResult] = await (
            query.where(FacilityRoom.is_deleted == False)
            .where(FacilityRoom.is_active == True)
            .group_by(FacilityRoom.id)
            .order_by(FacilityRoom.sequence)
            .fetch(as_model=RoomListItemResult)
        )
        return rooms or []

    async def get_by_id(
        self,
        room_id: UUID,
        locale_id: Optional[UUID],
        all_locales: bool = False,
    ) -> Optional[RoomDetailResult]:
        """
        Room detail by id.
        """
        room: Optional[RoomDetailResult] = await (
            self._detail_query(locale_id, all_locales)
            .where(FacilityRoom.id == room_id)
            .group_by(FacilityRoom.id)
            .fetchrow(as_model=RoomDetailResult)
        )
        return self._normalize_row(room)

    @staticmethod
    def _parse_translations(raw: Any) -> list[TranslationItemResult]:
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
                TranslationItemResult(
                    locale_id=entry.get("locale_id") or entry.get("localeId"),
                    name=entry.get("name", ""),
                    description=entry.get("description"),
                    remark=entry.get("remark"),
                )
            )
        return items

    def _normalize_row(self, row: Optional[RoomDetailResult]) -> Optional[RoomDetailResult]:
        if not row:
            return None
        data = row.model_dump()
        translations = data.pop("translations", None)
        data["translations"] = self._parse_translations(translations)
        return RoomDetailResult.model_validate(data)

    def _normalize_items(self, items: list[RoomDetailResult]) -> list[RoomDetailResult]:
        return [self._normalize_row(item) for item in items if item]

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        active_locale_ids = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id.in_(locale_ids))
            .where(SystemLocale.is_active == True)
            .where(SystemLocale.is_deleted == False)
            .fetchvals()
        )
        return set(active_locale_ids)

    async def insert_room(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRoom).values(payload).execute()

    async def update_room(self, room_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRoom)
            .values(**values)
            .where(FacilityRoom.id == room_id)
            .where(FacilityRoom.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        rows = apply_audit_fields_to_rows(rows)
        await (
            self._session.insert(FacilityRoomTranslation)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["room_id", "locale_id"],
                set_=dict(
                    name=sa.literal_column("excluded.name"),
                    description=sa.literal_column("excluded.description"),
                    remark=sa.literal_column("excluded.remark"),
                ),
            )
            .execute()
        )

    async def delete_soft(self, room_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRoom)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRoom.id == room_id)
            .execute()
        )

    async def delete_hard(self, room_id: UUID) -> None:
        await self._session.delete(FacilityRoom).where(FacilityRoom.id == room_id).execute()

    async def restore_room(self, room_id: UUID) -> None:
        await (
            self._session.update(FacilityRoom)
            .values(is_deleted=False, delete_reason=None)
            .where(FacilityRoom.id == room_id)
            .execute()
        )

    async def exists_by_id(self, room_id: UUID) -> bool:
        row_id = await (
            self._session.select(FacilityRoom.id)
            .where(FacilityRoom.id == room_id)
            .where(FacilityRoom.is_deleted == False)
            .fetchval()
        )
        return row_id is not None

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
