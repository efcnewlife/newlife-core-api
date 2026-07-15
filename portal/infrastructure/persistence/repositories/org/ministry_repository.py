"""
Org ministry repository.
"""
from typing import Any, Optional
from uuid import UUID

import ujson
import sqlalchemy as sa
from asyncpg import UniqueViolationError

from portal.application.org.results import (
    MinistryApprovalResult,
    MinistryDetailResult,
    MinistryListItemResult,
    MinistryMemberResult,
    MinistryScheduleResult,
    MinistryTypeResult,
    TargetAudienceResult,
    TranslationItemResult,
)
from portal.application.rbac.commands import PagesQueryCommand
from portal.domain.org.constants import MinistryApprovalStatus, MinistryMemberRole, MinistryStatus
from portal.infrastructure.persistence.repositories.shared.translation_queries import (
    default_locale_subquery,
    locale_scoped_max,
    ministry_name_fallback,
    ministry_translations_agg,
)
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthUser,
    AuthUserProfile,
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistrySchedule,
    OrgMinistryTargetAudience,
    OrgMinistryTranslation,
    OrgMinistryType,
    OrgMinistryTypeTranslation,
    SystemLocale,
)
from portal.models.mixins.context import apply_audit_fields_to_rows


class MinistryRepository:
    """SQLAlchemy-backed org ministry repository."""

    def __init__(self, session: Session):
        self._session = session

    def _ministry_type_name_expr(self, locale_id: Optional[UUID]):
        name_expr = locale_scoped_max(OrgMinistryTypeTranslation.name, OrgMinistryTypeTranslation, locale_id)
        if locale_id is None:
            name_expr = sa.func.coalesce(
                name_expr,
                sa.func.max(
                    sa.case(
                        (
                            OrgMinistryTypeTranslation.locale_id == default_locale_subquery(),
                            OrgMinistryTypeTranslation.name,
                        ),
                        else_=None,
                    )
                ),
            )
        return name_expr

    def _detail_select(self, locale_id: Optional[UUID] = None):
        ministry_type_name = self._ministry_type_name_expr(locale_id)
        return self._session.select(
            OrgMinistry.id,
            ministry_name_fallback(locale_id).label("name"),
            OrgMinistry.status,
            OrgMinistry.owner_position_id,
            OrgMinistry.ministry_type_id,
            OrgMinistryType.code.label("ministry_type_code"),
            ministry_type_name.label("ministry_type_name"),
            OrgMinistry.has_priority_booking,
            OrgMinistry.is_active,
            OrgMinistry.sequence,
            OrgMinistry.submitted_at,
            OrgMinistry.submitted_by_id,
            OrgMinistry.approved_at,
            OrgMinistry.approved_by_id,
            OrgMinistry.rejected_at,
            OrgMinistry.rejected_by_id,
            OrgMinistry.rejection_reason,
            OrgMinistry.created_at,
            OrgMinistry.created_by,
            OrgMinistry.updated_at,
            OrgMinistry.updated_by,
            OrgMinistry.delete_reason,
            ministry_translations_agg(),
        ).select_from(OrgMinistry).outerjoin(
            OrgMinistryType,
            OrgMinistryType.id == OrgMinistry.ministry_type_id,
        ).outerjoin(
            OrgMinistryTypeTranslation,
            OrgMinistryTypeTranslation.ministry_type_id == OrgMinistryType.id,
        )

    def _detail_query(self, locale_id: Optional[UUID] = None, all_locales: bool = False):
        query = self._detail_select(locale_id)
        if all_locales:
            return query.outerjoin(
                OrgMinistryTranslation,
                OrgMinistryTranslation.ministry_id == OrgMinistry.id,
            )
        if locale_id:
            return query.outerjoin(
                OrgMinistryTranslation,
                sa.and_(
                    OrgMinistryTranslation.ministry_id == OrgMinistry.id,
                    OrgMinistryTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(OrgMinistryTranslation, sa.false())

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
                    schedule_note=entry.get("schedule_note") or entry.get("scheduleNote"),
                )
            )
        return items

    def _normalize_row(self, row: Optional[MinistryDetailResult]) -> Optional[MinistryDetailResult]:
        if not row:
            return None
        data = row.model_dump()
        translations = data.pop("translations", None)
        data["translations"] = self._parse_translations(translations)
        ministry_type_code = data.pop("ministry_type_code", None)
        ministry_type_name = data.pop("ministry_type_name", None)
        ministry_type_id = data.get("ministry_type_id")
        ministry_type = data.get("ministry_type")
        if ministry_type_id and ministry_type_code and not ministry_type:
            data["ministry_type"] = MinistryTypeResult(
                id=ministry_type_id,
                code=ministry_type_code,
                name=ministry_type_name,
            )
        return MinistryDetailResult.model_validate(data)

    def _normalize_items(self, items: list[MinistryDetailResult]) -> list[MinistryDetailResult]:
        return [self._normalize_row(item) for item in items if item]

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[MinistryDetailResult], int]:
        keyword_exists = sa.exists(
            sa.select(1)
            .select_from(OrgMinistryTranslation)
            .where(OrgMinistryTranslation.ministry_id == OrgMinistry.id)
            .where(OrgMinistryTranslation.name.ilike(f"%{model.keyword}%"))
        )
        query = self._detail_query(locale_id).where(OrgMinistry.is_deleted == model.deleted)
        query = query.where(model.keyword, lambda: keyword_exists)
        items, count = await (
            query.group_by(OrgMinistry.id, OrgMinistryType.id, OrgMinistryType.code)
            .order_by_with(
                tables=[OrgMinistry],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MinistryDetailResult)
        )
        return self._normalize_items(items), count

    async def fetch_approval_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[MinistryDetailResult], int]:
        query = (
            self._detail_query(locale_id)
            .where(OrgMinistry.is_deleted == False)
            .where(OrgMinistry.status == MinistryStatus.PENDING_APPROVAL.value)
        )
        items, count = await (
            query.group_by(OrgMinistry.id, OrgMinistryType.id, OrgMinistryType.code)
            .order_by_with(
                tables=[OrgMinistry],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MinistryDetailResult)
        )
        return self._normalize_items(items), count

    async def fetch_approval_request_pages(
        self,
        model: PagesQueryCommand,
    ) -> tuple[list[MinistryApprovalResult], int]:
        items, count = await (
            self._session.select(
                OrgMinistryApproval.id,
                OrgMinistryApproval.ministry_id,
                OrgMinistryApproval.owner_position_id,
                OrgMinistryApproval.status,
                OrgMinistryApproval.requested_by_id,
                OrgMinistryApproval.resolved_by_id,
                OrgMinistryApproval.decided_at,
                OrgMinistryApproval.comment,
                OrgMinistryApproval.created_at,
            )
            .select_from(OrgMinistryApproval)
            .where(OrgMinistryApproval.status == MinistryApprovalStatus.PENDING.value)
            .order_by_with(
                tables=[OrgMinistryApproval],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MinistryApprovalResult)
        )
        return items or [], count

    async def list_active(self, locale_id: Optional[UUID]) -> list[MinistryListItemResult]:
        query = self._session.select(
            OrgMinistry.id,
            ministry_name_fallback(locale_id).label("name"),
            OrgMinistry.status,
            OrgMinistry.has_priority_booking,
            OrgMinistry.is_active,
        ).select_from(OrgMinistry)
        if locale_id:
            query = query.outerjoin(
                OrgMinistryTranslation,
                sa.and_(
                    OrgMinistryTranslation.ministry_id == OrgMinistry.id,
                    OrgMinistryTranslation.locale_id == locale_id,
                ),
            )
        else:
            query = query.outerjoin(OrgMinistryTranslation, sa.false())
        items: list[MinistryListItemResult] = await (
            query.where(OrgMinistry.is_deleted == False)
            .where(OrgMinistry.is_active == True)
            .where(OrgMinistry.status == MinistryStatus.ACTIVE.value)
            .group_by(OrgMinistry.id)
            .order_by(OrgMinistry.sequence)
            .fetch(as_model=MinistryListItemResult)
        )
        return items or []

    async def get_by_id(
        self,
        ministry_id: UUID,
        locale_id: Optional[UUID] = None,
        all_locales: bool = False,
    ) -> Optional[MinistryDetailResult]:
        row: Optional[MinistryDetailResult] = await (
            self._detail_query(locale_id, all_locales)
            .where(OrgMinistry.id == ministry_id)
            .group_by(OrgMinistry.id, OrgMinistryType.id, OrgMinistryType.code)
            .fetchrow(as_model=MinistryDetailResult)
        )
        normalized = self._normalize_row(row)
        if not normalized:
            return None
        members = await self.list_members(ministry_id)
        schedules = await self.list_schedules(ministry_id)
        target_audiences = await self.list_target_audiences(ministry_id, locale_id)
        return normalized.model_copy(
            update={
                "members": members,
                "schedules": schedules,
                "target_audiences": target_audiences,
            }
        )

    async def get_status(self, ministry_id: UUID) -> Optional[str]:
        status = await (
            self._session.select(OrgMinistry.status)
            .where(OrgMinistry.id == ministry_id)
            .where(OrgMinistry.is_deleted == False)
            .fetchval()
        )
        return status

    async def is_user_booking_member(self, ministry_id: UUID, user_id: UUID) -> bool:
        member_id = await (
            self._session.select(OrgMinistryMember.user_id)
            .where(OrgMinistryMember.ministry_id == ministry_id)
            .where(OrgMinistryMember.user_id == user_id)
            .where(
                OrgMinistryMember.member_role.in_(
                    [
                        MinistryMemberRole.PRIMARY.value,
                        MinistryMemberRole.SECONDARY.value,
                    ]
                )
            )
            .fetchval()
        )
        return member_id is not None

    async def list_members(self, ministry_id: UUID) -> list[MinistryMemberResult]:
        display_name = sa.func.coalesce(AuthUserProfile.preferred_name, AuthUser.email)
        rows: list[MinistryMemberResult] = await (
            self._session.select(
                OrgMinistryMember.user_id,
                OrgMinistryMember.member_role,
                OrgMinistryMember.remark,
                OrgMinistryMember.contact_email,
                AuthUser.email,
                display_name.label("display_name"),
            )
            .select_from(OrgMinistryMember)
            .outerjoin(AuthUser, AuthUser.id == OrgMinistryMember.user_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(OrgMinistryMember.ministry_id == ministry_id)
            .fetch(as_model=MinistryMemberResult)
        )
        return rows or []

    async def list_owned_ministries(self, user_id: UUID) -> list[UUID]:
        ministry_ids = await (
            self._session.select(OrgMinistryMember.ministry_id)
            .where(OrgMinistryMember.user_id == user_id)
            .where(
                OrgMinistryMember.member_role.in_(
                    [
                        MinistryMemberRole.PRIMARY.value,
                        MinistryMemberRole.SECONDARY.value,
                    ]
                )
            )
            .fetchvals()
        )
        return ministry_ids or []

    async def list_owned_active(self, user_id: UUID, locale_id: Optional[UUID]) -> list[MinistryListItemResult]:
        query = (
            self._session.select(
                OrgMinistry.id,
                ministry_name_fallback(locale_id).label("name"),
                OrgMinistry.status,
                OrgMinistry.has_priority_booking,
                OrgMinistry.is_active,
            )
            .select_from(OrgMinistry)
            .join(OrgMinistryMember, OrgMinistryMember.ministry_id == OrgMinistry.id)
        )
        if locale_id:
            query = query.outerjoin(
                OrgMinistryTranslation,
                sa.and_(
                    OrgMinistryTranslation.ministry_id == OrgMinistry.id,
                    OrgMinistryTranslation.locale_id == locale_id,
                ),
            )
        else:
            query = query.outerjoin(OrgMinistryTranslation, sa.false())
        items: list[MinistryListItemResult] = await (
            query.where(OrgMinistryMember.user_id == user_id)
            .where(
                OrgMinistryMember.member_role.in_(
                    [
                        MinistryMemberRole.PRIMARY.value,
                        MinistryMemberRole.SECONDARY.value,
                    ]
                )
            )
            .where(OrgMinistry.is_deleted == False)
            .where(OrgMinistry.status == MinistryStatus.ACTIVE.value)
            .group_by(OrgMinistry.id)
            .order_by(OrgMinistry.sequence)
            .fetch(as_model=MinistryListItemResult)
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

    async def insert_ministry(self, payload: dict[str, Any]) -> None:
        await self._session.insert(OrgMinistry).values(payload).execute()

    async def update_ministry(self, ministry_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(OrgMinistry)
            .values(**values)
            .where(OrgMinistry.id == ministry_id)
            .where(OrgMinistry.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        rows = apply_audit_fields_to_rows(rows)
        await (
            self._session.insert(OrgMinistryTranslation)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["ministry_id", "locale_id"],
                set_=dict(
                    name=sa.literal_column("excluded.name"),
                    description=sa.literal_column("excluded.description"),
                    remark=sa.literal_column("excluded.remark"),
                    schedule_note=sa.literal_column("excluded.schedule_note"),
                ),
            )
            .execute()
        )

    async def replace_members(
        self,
        ministry_id: UUID,
        members: list[dict[str, Any]],
    ) -> None:
        await (
            self._session.delete(OrgMinistryMember)
            .where(OrgMinistryMember.ministry_id == ministry_id)
            .execute()
        )
        if not members:
            return
        await (
            self._session.insert(OrgMinistryMember)
            .values(
                [
                    {
                        "ministry_id": ministry_id,
                        "user_id": member["user_id"],
                        "member_role": member["member_role"],
                        "remark": member.get("remark"),
                        "contact_email": member.get("contact_email"),
                    }
                    for member in members
                ]
            )
            .execute()
        )

    async def replace_user_ministries(
        self,
        user_id: UUID,
        ministry_ids: list[UUID],
    ) -> None:
        await (
            self._session.delete(OrgMinistryMember)
            .where(OrgMinistryMember.user_id == user_id)
            .execute()
        )
        if not ministry_ids:
            return
        await (
            self._session.insert(OrgMinistryMember)
            .values(
                [
                    {
                        "user_id": user_id,
                        "ministry_id": ministry_id,
                        "member_role": MinistryMemberRole.SECONDARY.value,
                    }
                    for ministry_id in ministry_ids
                ]
            )
            .execute()
        )

    async def list_schedules(self, ministry_id: UUID) -> list[MinistryScheduleResult]:
        from portal.domain.facility.days_of_week_mask import mask_to_days

        rows = await (
            self._session.select(
                OrgMinistrySchedule.id,
                OrgMinistrySchedule.days_of_week_mask,
                OrgMinistrySchedule.start_time,
                OrgMinistrySchedule.end_time,
                OrgMinistrySchedule.effective_from,
                OrgMinistrySchedule.effective_to,
                OrgMinistrySchedule.sequence,
            )
            .where(OrgMinistrySchedule.ministry_id == ministry_id)
            .order_by(OrgMinistrySchedule.sequence, OrgMinistrySchedule.created_at)
            .fetch()
        )
        results = []
        for row in rows or []:
            mask = row.get("days_of_week_mask")
            days_of_week = []
            if mask is not None:
                try:
                    days_of_week = mask_to_days(mask)
                except ValueError:
                    days_of_week = []
            results.append(
                MinistryScheduleResult(
                    id=row["id"],
                    days_of_week_mask=mask,
                    days_of_week=days_of_week,
                    start_time=row.get("start_time"),
                    end_time=row.get("end_time"),
                    effective_from=row.get("effective_from"),
                    effective_to=row.get("effective_to"),
                    sequence=row.get("sequence"),
                )
            )
        return results

    async def upsert_schedules(self, ministry_id: UUID, rows: list[dict[str, Any]]) -> None:
        await (
            self._session.delete(OrgMinistrySchedule)
            .where(OrgMinistrySchedule.ministry_id == ministry_id)
            .execute()
        )
        if not rows:
            return
        await (
            self._session.insert(OrgMinistrySchedule)
            .values([dict(ministry_id=ministry_id, **row) for row in rows])
            .execute()
        )

    async def list_target_audiences(
        self,
        ministry_id: UUID,
        locale_id: Optional[UUID],
    ) -> list[TargetAudienceResult]:
        from portal.infrastructure.persistence.repositories.org.target_audience_repository import (
            TargetAudienceRepository,
        )

        return await TargetAudienceRepository(self._session).list_for_ministry(ministry_id, locale_id)

    async def upsert_target_audiences(self, ministry_id: UUID, audience_ids: list[UUID]) -> None:
        await (
            self._session.delete(OrgMinistryTargetAudience)
            .where(OrgMinistryTargetAudience.ministry_id == ministry_id)
            .execute()
        )
        if not audience_ids:
            return
        await (
            self._session.insert(OrgMinistryTargetAudience)
            .values(
                [
                    dict(ministry_id=ministry_id, target_audience_id=audience_id)
                    for audience_id in audience_ids
                ]
            )
            .execute()
        )

    async def insert_approval(self, payload: dict[str, Any]) -> None:
        await self._session.insert(OrgMinistryApproval).values(payload).execute()

    async def update_approval(
        self,
        ministry_id: UUID,
        status: str,
        resolved_by_id: Optional[UUID],
        decided_at,
        comment: Optional[str],
    ) -> None:
        await (
            self._session.update(OrgMinistryApproval)
            .values(
                status=status,
                resolved_by_id=resolved_by_id,
                decided_at=decided_at,
                comment=comment,
            )
            .where(OrgMinistryApproval.ministry_id == ministry_id)
            .where(OrgMinistryApproval.status == MinistryApprovalStatus.PENDING.value)
            .execute()
        )

    async def fetch_member_pages(self, model, locale_id: Optional[UUID]) -> tuple[list, int]:
        from portal.application.facility.results import MinistryMemberRowResult

        display_name = sa.func.coalesce(AuthUserProfile.preferred_name, AuthUser.email)
        member_filter = sa.and_(
            AuthUser.is_admin == False,
            AuthUser.is_deleted == False,
        )
        items, count = await (
            self._session.select(
                AuthUser.id.label("user_id"),
                AuthUser.email,
                display_name.label("display_name"),
            )
            .select_from(AuthUser)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(member_filter)
            .where(
                model.ministry_id,
                lambda: sa.exists(
                    sa.select(1).where(
                        OrgMinistryMember.user_id == AuthUser.id,
                        OrgMinistryMember.ministry_id == model.ministry_id,
                    )
                ),
            )
            .where(
                model.keyword,
                lambda: sa.or_(
                    AuthUser.email.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.first_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.last_name.ilike(f"%{model.keyword}%"),
                ),
            )
            .order_by_with(
                tables=[AuthUser],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MinistryMemberRowResult)
        )
        enriched = []
        for item in items or []:
            ministry_ids = await self._list_ministry_ids_for_user(item.user_id)
            enriched.append(
                MinistryMemberRowResult(
                    user_id=item.user_id,
                    email=item.email,
                    display_name=item.display_name,
                    ministry_ids=ministry_ids,
                    ministry_names=[],
                )
            )
        return enriched, count

    async def _list_ministry_ids_for_user(self, user_id: UUID) -> list[UUID]:
        rows = await (
            self._session.select(OrgMinistryMember.ministry_id)
            .where(OrgMinistryMember.user_id == user_id)
            .fetch()
        )
        return [row["ministry_id"] for row in rows or []]

    async def delete_soft(self, ministry_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(OrgMinistry)
            .values(is_deleted=True, delete_reason=reason)
            .where(OrgMinistry.id == ministry_id)
            .execute()
        )

    async def delete_hard(self, ministry_id: UUID) -> None:
        await (
            self._session.delete(OrgMinistryMember)
            .where(OrgMinistryMember.ministry_id == ministry_id)
            .execute()
        )
        await (
            self._session.delete(OrgMinistryApproval)
            .where(OrgMinistryApproval.ministry_id == ministry_id)
            .execute()
        )
        await self._session.delete(OrgMinistry).where(OrgMinistry.id == ministry_id).execute()

    async def restore_ministry(self, ministry_id: UUID) -> None:
        await (
            self._session.update(OrgMinistry)
            .values(is_deleted=False, delete_reason=None)
            .where(OrgMinistry.id == ministry_id)
            .execute()
        )

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
