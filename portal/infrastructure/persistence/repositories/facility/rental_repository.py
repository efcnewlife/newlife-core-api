"""
Facility rental catalog repository.
"""
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import ujson
import sqlalchemy as sa
from asyncpg import UniqueViolationError
from sqlalchemy.dialects.postgresql import JSONB

from portal.application.facility.results import (
    DiscountRuleResult,
    PolicySettingResult,
    RentalRateResult,
    SurchargeResult,
    TranslationItemResult,
)
from portal.application.rbac.commands import PagesQueryCommand
from portal.domain.facility.constants import RentalPolicySettingKey, RentalRateBillingUnit
from portal.domain.facility.rate_applicability import RateSelectionContext, matches_applicability
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    FacilityRentalDiscountRule,
    FacilityRentalPolicySetting,
    FacilityRentalRate,
    FacilityRentalRateTranslation,
    FacilityRentalSurcharge,
    SystemLocale,
)
from portal.models.mixins.context import apply_audit_fields_to_rows


class RentalRepository:
    """SQLAlchemy-backed rental rate and catalog repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _rate_translations_agg():
        translation_json = sa.cast(
            sa.func.json_build_object(
                sa.cast("locale_id", sa.VARCHAR(16)), FacilityRentalRateTranslation.locale_id,
                sa.cast("name", sa.VARCHAR(8)), FacilityRentalRateTranslation.name,
                sa.cast("description", sa.VARCHAR(16)), FacilityRentalRateTranslation.description,
                sa.cast("remark", sa.VARCHAR(8)), FacilityRentalRateTranslation.remark,
            ),
            JSONB,
        )
        return sa.func.coalesce(
            sa.func.array_agg(sa.distinct(translation_json)).filter(FacilityRentalRateTranslation.id.isnot(None)),
            sa.cast(sa.text("'{}'"), sa.ARRAY(JSONB)),
        ).label("translations")

    @staticmethod
    def _locale_scoped_max(column, locale_id: Optional[UUID]):
        if locale_id:
            return sa.func.max(
                sa.case(
                    (FacilityRentalRateTranslation.locale_id == locale_id, column),
                    else_=None,
                )
            )
        return sa.func.max(column)

    def _rate_select(self, locale_id: Optional[UUID] = None):
        return self._session.select(
            FacilityRentalRate.id,
            FacilityRentalRate.facility_id,
            FacilityRentalRate.billing_unit,
            FacilityRentalRate.unit_amount,
            FacilityRentalRate.currency,
            FacilityRentalRate.is_default,
            FacilityRentalRate.is_active,
            FacilityRentalRate.applicability,
            FacilityRentalRate.effective_from,
            FacilityRentalRate.effective_to,
            FacilityRentalRate.sequence,
            self._locale_scoped_max(FacilityRentalRateTranslation.name, locale_id).label("name"),
            self._locale_scoped_max(FacilityRentalRateTranslation.remark, locale_id).label("remark"),
            FacilityRentalRate.created_at,
            FacilityRentalRate.created_by,
            FacilityRentalRate.updated_at,
            FacilityRentalRate.updated_by,
            FacilityRentalRate.delete_reason,
            self._rate_translations_agg(),
        ).select_from(FacilityRentalRate)

    def _rate_query(self, locale_id: Optional[UUID] = None, all_locales: bool = False):
        query = self._rate_select(locale_id)
        if all_locales:
            return query.outerjoin(
                FacilityRentalRateTranslation,
                FacilityRentalRateTranslation.rental_rate_id == FacilityRentalRate.id,
            )
        if locale_id:
            return query.outerjoin(
                FacilityRentalRateTranslation,
                sa.and_(
                    FacilityRentalRateTranslation.rental_rate_id == FacilityRentalRate.id,
                    FacilityRentalRateTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(FacilityRentalRateTranslation, sa.false())

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

    def _normalize_rate(self, row: Optional[RentalRateResult]) -> Optional[RentalRateResult]:
        if not row:
            return None
        data = row.model_dump()
        translations = data.pop("translations", None)
        data["translations"] = self._parse_translations(translations)
        return RentalRateResult.model_validate(data)

    def _normalize_rates(self, rows: list[RentalRateResult]) -> list[RentalRateResult]:
        return [self._normalize_rate(row) for row in rows if row]

    async def fetch_rate_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
        facility_id: Optional[UUID] = None,
    ) -> tuple[list[RentalRateResult], int]:
        query = (
            self._rate_query(locale_id)
            .where(FacilityRentalRate.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    FacilityRentalRateTranslation.name.ilike(f"%{model.keyword}%"),
                    FacilityRentalRateTranslation.description.ilike(f"%{model.keyword}%"),
                    FacilityRentalRateTranslation.remark.ilike(f"%{model.keyword}%"),
                ),
            )
        )
        if facility_id:
            query = query.where(FacilityRentalRate.facility_id == facility_id)
        items, count = await (
            query.group_by(FacilityRentalRate.id)
            .order_by_with(
                tables=[FacilityRentalRate],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RentalRateResult)
        )
        return self._normalize_rates(items), count

    async def list_rates(
        self,
        facility_id: Optional[UUID],
        locale_id: Optional[UUID],
    ) -> list[RentalRateResult]:
        query = (
            self._rate_query(locale_id)
            .where(FacilityRentalRate.is_deleted == False)
            .where(FacilityRentalRate.is_active == True)
        )
        if facility_id:
            query = query.where(FacilityRentalRate.facility_id == facility_id)
        items: list[RentalRateResult] = await query.group_by(FacilityRentalRate.id).order_by(
            FacilityRentalRate.sequence
        ).fetch(as_model=RentalRateResult)
        return self._normalize_rates(items)

    async def get_rate_by_id(
        self,
        rate_id: UUID,
        locale_id: Optional[UUID],
        all_locales: bool = False,
    ) -> Optional[RentalRateResult]:
        row: Optional[RentalRateResult] = await (
            self._rate_query(locale_id, all_locales)
            .where(FacilityRentalRate.id == rate_id)
            .group_by(FacilityRentalRate.id)
            .fetchrow(as_model=RentalRateResult)
        )
        return self._normalize_rate(row)

    async def list_active_rates_for_facility(
        self,
        facility_id: UUID,
        as_of_date: Optional[date],
    ) -> list[RentalRateResult]:
        query = (
            self._session.select(
                FacilityRentalRate.id,
                FacilityRentalRate.facility_id,
                FacilityRentalRate.billing_unit,
                FacilityRentalRate.unit_amount,
                FacilityRentalRate.currency,
                FacilityRentalRate.is_default,
                FacilityRentalRate.is_active,
                FacilityRentalRate.applicability,
                FacilityRentalRate.effective_from,
                FacilityRentalRate.effective_to,
                FacilityRentalRate.sequence,
            )
            .where(FacilityRentalRate.is_deleted == False)
            .where(FacilityRentalRate.is_active == True)
            .where(FacilityRentalRate.facility_id == facility_id)
        )
        if as_of_date:
            query = query.where(
                sa.or_(FacilityRentalRate.effective_from.is_(None), FacilityRentalRate.effective_from <= as_of_date)
            ).where(
                sa.or_(FacilityRentalRate.effective_to.is_(None), FacilityRentalRate.effective_to >= as_of_date)
            )
        rows: list[RentalRateResult] = await query.fetch(as_model=RentalRateResult)
        return rows or []

    async def insert_rate(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRentalRate).values(payload).execute()

    async def update_rate(self, rate_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRentalRate)
            .values(**values)
            .where(FacilityRentalRate.id == rate_id)
            .where(FacilityRentalRate.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def upsert_rate_translations(self, rows: list[dict[str, Any]]) -> None:
        rows = apply_audit_fields_to_rows(rows)
        await (
            self._session.insert(FacilityRentalRateTranslation)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["rental_rate_id", "locale_id"],
                set_=dict(
                    name=sa.literal_column("excluded.name"),
                    description=sa.literal_column("excluded.description"),
                    remark=sa.literal_column("excluded.remark"),
                ),
            )
            .execute()
        )

    async def delete_rate_soft(self, rate_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRentalRate)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRentalRate.id == rate_id)
            .execute()
        )

    async def delete_rate_hard(self, rate_id: UUID) -> None:
        await self._session.delete(FacilityRentalRate).where(FacilityRentalRate.id == rate_id).execute()

    async def restore_rate(self, rate_id: UUID) -> None:
        await (
            self._session.update(FacilityRentalRate)
            .values(is_deleted=False, delete_reason=None)
            .where(FacilityRentalRate.id == rate_id)
            .execute()
        )

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        active_locale_ids = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id.in_(locale_ids))
            .where(SystemLocale.is_active == True)
            .where(SystemLocale.is_deleted == False)
            .fetchvals()
        )
        return set(active_locale_ids)

    async def list_discount_rules(self) -> list[DiscountRuleResult]:
        items: list[DiscountRuleResult] = await (
            self._session.select(
                FacilityRentalDiscountRule.id,
                FacilityRentalDiscountRule.code,
                FacilityRentalDiscountRule.percent_off,
                FacilityRentalDiscountRule.is_active,
                FacilityRentalDiscountRule.description,
                FacilityRentalDiscountRule.created_at,
                FacilityRentalDiscountRule.updated_at,
            )
            .where(FacilityRentalDiscountRule.is_deleted == False)
            .order_by(FacilityRentalDiscountRule.code)
            .fetch(as_model=DiscountRuleResult)
        )
        return items or []

    async def get_discount_rule_by_id(self, rule_id: UUID) -> Optional[DiscountRuleResult]:
        return await (
            self._session.select(
                FacilityRentalDiscountRule.id,
                FacilityRentalDiscountRule.code,
                FacilityRentalDiscountRule.percent_off,
                FacilityRentalDiscountRule.is_active,
                FacilityRentalDiscountRule.description,
                FacilityRentalDiscountRule.created_at,
                FacilityRentalDiscountRule.updated_at,
            )
            .where(FacilityRentalDiscountRule.id == rule_id)
            .where(FacilityRentalDiscountRule.is_deleted == False)
            .fetchrow(as_model=DiscountRuleResult)
        )

    async def insert_discount_rule(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRentalDiscountRule).values(payload).execute()

    async def update_discount_rule(self, rule_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRentalDiscountRule)
            .values(**values)
            .where(FacilityRentalDiscountRule.id == rule_id)
            .where(FacilityRentalDiscountRule.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_discount_rule_soft(self, rule_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRentalDiscountRule)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRentalDiscountRule.id == rule_id)
            .execute()
        )

    async def list_surcharges(self) -> list[SurchargeResult]:
        items: list[SurchargeResult] = await (
            self._session.select(
                FacilityRentalSurcharge.id,
                FacilityRentalSurcharge.code,
                FacilityRentalSurcharge.charge_type,
                FacilityRentalSurcharge.unit_amount,
                FacilityRentalSurcharge.currency,
                FacilityRentalSurcharge.is_active,
                FacilityRentalSurcharge.applies_to_booking_type,
                FacilityRentalSurcharge.remark,
                FacilityRentalSurcharge.created_at,
                FacilityRentalSurcharge.updated_at,
            )
            .where(FacilityRentalSurcharge.is_deleted == False)
            .order_by(FacilityRentalSurcharge.code)
            .fetch(as_model=SurchargeResult)
        )
        return items or []

    async def get_surcharge_by_id(self, surcharge_id: UUID) -> Optional[SurchargeResult]:
        return await (
            self._session.select(
                FacilityRentalSurcharge.id,
                FacilityRentalSurcharge.code,
                FacilityRentalSurcharge.charge_type,
                FacilityRentalSurcharge.unit_amount,
                FacilityRentalSurcharge.currency,
                FacilityRentalSurcharge.is_active,
                FacilityRentalSurcharge.applies_to_booking_type,
                FacilityRentalSurcharge.remark,
                FacilityRentalSurcharge.created_at,
                FacilityRentalSurcharge.updated_at,
            )
            .where(FacilityRentalSurcharge.id == surcharge_id)
            .where(FacilityRentalSurcharge.is_deleted == False)
            .fetchrow(as_model=SurchargeResult)
        )

    async def insert_surcharge(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRentalSurcharge).values(payload).execute()

    async def update_surcharge(self, surcharge_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRentalSurcharge)
            .values(**values)
            .where(FacilityRentalSurcharge.id == surcharge_id)
            .where(FacilityRentalSurcharge.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_surcharge_soft(self, surcharge_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRentalSurcharge)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRentalSurcharge.id == surcharge_id)
            .execute()
        )

    async def list_policy_settings(self, facility_id: Optional[UUID] = None) -> list[PolicySettingResult]:
        query = self._session.select(
            FacilityRentalPolicySetting.id,
            FacilityRentalPolicySetting.setting_key,
            FacilityRentalPolicySetting.facility_id,
            FacilityRentalPolicySetting.amount,
            FacilityRentalPolicySetting.currency,
            FacilityRentalPolicySetting.is_active,
            FacilityRentalPolicySetting.created_at,
            FacilityRentalPolicySetting.updated_at,
        ).where(FacilityRentalPolicySetting.is_deleted == False)
        if facility_id is not None:
            query = query.where(
                sa.or_(
                    FacilityRentalPolicySetting.facility_id == facility_id,
                    FacilityRentalPolicySetting.facility_id.is_(None),
                )
            )
        items: list[PolicySettingResult] = await query.order_by(
            FacilityRentalPolicySetting.setting_key
        ).fetch(as_model=PolicySettingResult)
        return items or []

    async def get_policy_setting_by_id(self, setting_id: UUID) -> Optional[PolicySettingResult]:
        return await (
            self._session.select(
                FacilityRentalPolicySetting.id,
                FacilityRentalPolicySetting.setting_key,
                FacilityRentalPolicySetting.facility_id,
                FacilityRentalPolicySetting.amount,
                FacilityRentalPolicySetting.currency,
                FacilityRentalPolicySetting.is_active,
                FacilityRentalPolicySetting.created_at,
                FacilityRentalPolicySetting.updated_at,
            )
            .where(FacilityRentalPolicySetting.id == setting_id)
            .where(FacilityRentalPolicySetting.is_deleted == False)
            .fetchrow(as_model=PolicySettingResult)
        )

    async def get_policy_amount(
        self,
        setting_key: RentalPolicySettingKey,
        facility_id: Optional[UUID],
    ) -> Optional[Decimal]:
        if facility_id:
            facility_amount = await (
                self._session.select(FacilityRentalPolicySetting.amount)
                .where(FacilityRentalPolicySetting.setting_key == setting_key.value)
                .where(FacilityRentalPolicySetting.facility_id == facility_id)
                .where(FacilityRentalPolicySetting.is_active == True)
                .where(FacilityRentalPolicySetting.is_deleted == False)
                .fetchval()
            )
            if facility_amount is not None:
                return Decimal(str(facility_amount))
        global_amount = await (
            self._session.select(FacilityRentalPolicySetting.amount)
            .where(FacilityRentalPolicySetting.setting_key == setting_key.value)
            .where(FacilityRentalPolicySetting.facility_id.is_(None))
            .where(FacilityRentalPolicySetting.is_active == True)
            .where(FacilityRentalPolicySetting.is_deleted == False)
            .fetchval()
        )
        if global_amount is None:
            return None
        return Decimal(str(global_amount))

    async def update_policy_setting(self, setting_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRentalPolicySetting)
            .values(**values)
            .where(FacilityRentalPolicySetting.id == setting_id)
            .where(FacilityRentalPolicySetting.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def get_active_discount_percent(
        self,
        booking_type: str,
        is_mission_aligned: bool,
    ) -> Decimal:
        rules = await self.list_discount_rules()
        active = {rule.code: rule for rule in rules if rule.is_active}
        if is_mission_aligned and "mission_aligned" in {code for code in active}:
            mission_code = "mission_aligned"
            for rule in rules:
                if rule.code == mission_code and rule.is_active:
                    return Decimal(str(rule.percent_off))
        if booking_type == "recurring":
            for rule in rules:
                if rule.code == "recurring_weekly_monthly" and rule.is_active:
                    return Decimal(str(rule.percent_off))
        return Decimal("0")

    @staticmethod
    def pick_rate_for_line(
        rates: list[RentalRateResult],
        billed_hours: Decimal,
    ) -> tuple[Optional[RentalRateResult], str]:
        ctx = RateSelectionContext(billed_hours=billed_hours)
        eligible = [
            rate
            for rate in rates
            if rate.is_active and matches_applicability(rate.applicability, ctx)
        ]
        if not eligible:
            default_rate = next((rate for rate in rates if rate.is_default and rate.is_active), None)
            if default_rate:
                return default_rate, default_rate.billing_unit
            active = [rate for rate in rates if rate.is_active]
            if active:
                first = active[0]
                return first, first.billing_unit
            return None, RentalRateBillingUnit.HOURLY.value

        def _sort_key(rate: RentalRateResult) -> tuple:
            has_rule = 0 if rate.applicability else 1
            sequence = rate.sequence if rate.sequence is not None else float("inf")
            default_rank = 0 if rate.is_default else 1
            return (has_rule, sequence, default_rank)

        chosen = sorted(eligible, key=_sort_key)[0]
        return chosen, chosen.billing_unit

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
