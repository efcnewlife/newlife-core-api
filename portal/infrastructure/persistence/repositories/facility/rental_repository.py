"""
Facility rental catalog repository.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError

from portal.application.facility.results import DiscountRuleResult, PolicySettingResult, RentalRateResult, RentalRateTemplateResult, SurchargeResult
from portal.application.rbac.commands import PagesQueryCommand
from portal.domain.facility.constants import RentalPolicySettingKey, RentalRateBillingUnit
from portal.domain.facility.rate_applicability import RateSelectionContext, matches_applicability
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import FacilityRentalDiscountRule, FacilityRentalPolicySetting, FacilityRentalRate, FacilityRentalRateTemplate, FacilityRentalSurcharge


class RentalRepository:
    """SQLAlchemy-backed rental rate and catalog repository."""

    def __init__(self, session: Session):
        self._session = session

    def _rate_select(self):
        return (
            self._session.select(
                FacilityRentalRate.id,
                FacilityRentalRate.facility_id,
                FacilityRentalRate.template_id,
                FacilityRentalRate.is_active,
                FacilityRentalRate.created_at,
                FacilityRentalRate.created_by,
                FacilityRentalRate.updated_at,
                FacilityRentalRate.updated_by,
                FacilityRentalRate.delete_reason,
                FacilityRentalRateTemplate.unit_amount,
                FacilityRentalRateTemplate.currency,
                FacilityRentalRateTemplate.name.label("template_name"),
                FacilityRentalRateTemplate.billing_unit,
                FacilityRentalRateTemplate.applicability,
                FacilityRentalRateTemplate.is_default,
                FacilityRentalRateTemplate.is_active.label("template_is_active"),
            )
            .select_from(FacilityRentalRate)
            .join(FacilityRentalRateTemplate, FacilityRentalRateTemplate.id == FacilityRentalRate.template_id)
        )

    def _template_select(self):
        return self._session.select(
            FacilityRentalRateTemplate.id,
            FacilityRentalRateTemplate.name,
            FacilityRentalRateTemplate.billing_unit,
            FacilityRentalRateTemplate.applicability,
            FacilityRentalRateTemplate.unit_amount,
            FacilityRentalRateTemplate.currency,
            FacilityRentalRateTemplate.is_default,
            FacilityRentalRateTemplate.is_active,
            FacilityRentalRateTemplate.created_at,
            FacilityRentalRateTemplate.created_by,
            FacilityRentalRateTemplate.updated_at,
            FacilityRentalRateTemplate.updated_by,
            FacilityRentalRateTemplate.delete_reason,
        )

    async def fetch_template_pages(self, model: PagesQueryCommand) -> tuple[list[RentalRateTemplateResult], int]:
        query = (
            self._template_select()
            .where(FacilityRentalRateTemplate.is_deleted == model.deleted)
            .where(model.keyword, lambda: FacilityRentalRateTemplate.name.ilike(f"%{model.keyword}%"))
        )
        items, count = await (
            query.order_by_with(tables=[FacilityRentalRateTemplate], order_by=model.order_by, descending=model.descending)
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RentalRateTemplateResult)
        )
        return items or [], count

    async def list_templates(self, active_only: bool = True) -> list[RentalRateTemplateResult]:
        query = self._template_select().where(FacilityRentalRateTemplate.is_deleted == False)
        if active_only:
            query = query.where(FacilityRentalRateTemplate.is_active == True)
        items: list[RentalRateTemplateResult] = await query.order_by(FacilityRentalRateTemplate.name).fetch(as_model=RentalRateTemplateResult)
        return items or []

    async def get_template_by_id(self, template_id: UUID) -> Optional[RentalRateTemplateResult]:
        return await (
            self._template_select()
            .where(FacilityRentalRateTemplate.id == template_id)
            .where(FacilityRentalRateTemplate.is_deleted == False)
            .fetchrow(as_model=RentalRateTemplateResult)
        )

    async def count_rates_for_template(self, template_id: UUID) -> int:
        count = await (
            self._session.select(sa.func.count())
            .select_from(FacilityRentalRate)
            .where(FacilityRentalRate.template_id == template_id)
            .where(FacilityRentalRate.is_deleted == False)
            .fetchval()
        )
        return int(count or 0)

    async def insert_template(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRentalRateTemplate).values(payload).execute()

    async def update_template(self, template_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRentalRateTemplate)
            .values(**values)
            .where(FacilityRentalRateTemplate.id == template_id)
            .where(FacilityRentalRateTemplate.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_template_soft(self, template_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRentalRateTemplate)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRentalRateTemplate.id == template_id)
            .execute()
        )

    async def restore_template(self, template_id: UUID) -> None:
        await (
            self._session.update(FacilityRentalRateTemplate)
            .values(is_deleted=False, delete_reason=None)
            .where(FacilityRentalRateTemplate.id == template_id)
            .execute()
        )

    async def fetch_rate_pages(self, model: PagesQueryCommand, facility_id: Optional[UUID] = None) -> tuple[list[RentalRateResult], int]:
        query = (
            self._rate_select()
            .where(FacilityRentalRate.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    FacilityRentalRateTemplate.name.ilike(f"%{model.keyword}%"), FacilityRentalRateTemplate.billing_unit.ilike(f"%{model.keyword}%")
                ),
            )
        )
        if facility_id is not None:
            query = query.where(FacilityRentalRate.facility_id == facility_id)
        items, count = await (
            query.order_by_with(tables=[FacilityRentalRate, FacilityRentalRateTemplate], order_by=model.order_by, descending=model.descending)
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RentalRateResult)
        )
        return items or [], count

    async def list_rates(self, facility_id: Optional[UUID]) -> list[RentalRateResult]:
        query = self._rate_select().where(FacilityRentalRate.is_deleted == False).where(FacilityRentalRate.is_active == True)
        if facility_id is not None:
            query = query.where(FacilityRentalRate.facility_id == facility_id)
        items: list[RentalRateResult] = await query.order_by(FacilityRentalRateTemplate.name).fetch(as_model=RentalRateResult)
        return items or []

    async def get_rate_by_id(self, rate_id: UUID) -> Optional[RentalRateResult]:
        return await self._rate_select().where(FacilityRentalRate.id == rate_id).fetchrow(as_model=RentalRateResult)

    async def list_active_rates_for_facility(self, facility_id: UUID, as_of_date: Optional[date]) -> list[RentalRateResult]:
        """Return active room bindings for the facility (price from joined template)."""
        _ = as_of_date
        room_rows: list[RentalRateResult] = await (
            self._rate_select()
            .where(FacilityRentalRate.is_deleted == False)
            .where(FacilityRentalRate.is_active == True)
            .where(FacilityRentalRateTemplate.is_deleted == False)
            .where(FacilityRentalRateTemplate.is_active == True)
            .where(FacilityRentalRate.facility_id == facility_id)
            .fetch(as_model=RentalRateResult)
        )
        return room_rows or []

    @staticmethod
    def template_to_rate_candidate(template: RentalRateTemplateResult) -> RentalRateResult:
        """Build a pricing candidate from an active template (no room binding)."""
        return RentalRateResult(
            id=template.id,
            facility_id=None,
            template_id=template.id,
            is_active=template.is_active,
            unit_amount=template.unit_amount,
            currency=template.currency,
            template_name=template.name,
            billing_unit=template.billing_unit,
            applicability=template.applicability,
            is_default=template.is_default,
            template_is_active=template.is_active,
        )

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

    async def delete_rate_soft(self, rate_id: UUID, reason: Optional[str]) -> None:
        await self._session.update(FacilityRentalRate).values(is_deleted=True, delete_reason=reason).where(FacilityRentalRate.id == rate_id).execute()

    async def delete_rate_hard(self, rate_id: UUID) -> None:
        await self._session.delete(FacilityRentalRate).where(FacilityRentalRate.id == rate_id).execute()

    async def restore_rate(self, rate_id: UUID) -> None:
        await self._session.update(FacilityRentalRate).values(is_deleted=False, delete_reason=None).where(FacilityRentalRate.id == rate_id).execute()

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
            query = query.where(sa.or_(FacilityRentalPolicySetting.facility_id == facility_id, FacilityRentalPolicySetting.facility_id.is_(None)))
        items: list[PolicySettingResult] = await query.order_by(FacilityRentalPolicySetting.setting_key).fetch(as_model=PolicySettingResult)
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

    async def get_policy_amount(self, setting_key: RentalPolicySettingKey, facility_id: Optional[UUID]) -> Optional[Decimal]:
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

    async def get_active_discount_percent(self, booking_type: str, is_mission_aligned: bool) -> Decimal:
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
    def pick_rate_for_line(rates: list[RentalRateResult], billed_hours: Decimal, allow_first_active: bool = True) -> tuple[Optional[RentalRateResult], str]:
        ctx = RateSelectionContext(billed_hours=billed_hours)
        eligible = [rate for rate in rates if rate.is_active and matches_applicability(rate.applicability, ctx)]
        if not eligible:
            default_rate = next((rate for rate in rates if rate.is_default and rate.is_active), None)
            if default_rate:
                return default_rate, default_rate.billing_unit or RentalRateBillingUnit.HOURLY.value
            if allow_first_active:
                active = [rate for rate in rates if rate.is_active]
                if active:
                    first = active[0]
                    return first, first.billing_unit or RentalRateBillingUnit.HOURLY.value
            return None, RentalRateBillingUnit.HOURLY.value

        def _sort_key(rate: RentalRateResult) -> tuple:
            has_rule = 0 if rate.applicability else 1
            default_rank = 0 if rate.is_default else 1
            return (has_rule, default_rank)

        chosen = sorted(eligible, key=_sort_key)[0]
        return chosen, chosen.billing_unit or RentalRateBillingUnit.HOURLY.value

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
