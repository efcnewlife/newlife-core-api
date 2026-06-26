"""
Stub repositories for facility application unit tests.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from asyncpg import UniqueViolationError

from portal.application.facility.commands import (
    BookingPagesQueryCommand,
    MemberPagesQueryCommand,
    OverrideLogPagesQueryCommand,
    PagesQueryCommand,
)
from portal.application.facility.results import (
    BookingDetailResult,
    DiscountRuleResult,
    MemberDetailResult,
    MinistryDetailResult,
    OverrideLogResult,
    RentalRateResult,
    RoomDetailResult,
    RoomSlotTemplateResult,
    SurchargeResult,
)
from portal.domain.facility.constants import RentalPolicySettingKey
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository


class StubRentalRepository:
    """In-memory rental catalog and rate stub."""

    def __init__(
        self,
        rates_by_facility: dict[UUID, list[RentalRateResult]] | None = None,
        discount_rules: list[DiscountRuleResult] | None = None,
        surcharges: list[SurchargeResult] | None = None,
        policy_amounts: dict[tuple[str, UUID | None], Decimal] | None = None,
        insert_raises_unique: bool = False,
        update_discount_affected: int = 1,
        update_surcharge_affected: int = 1,
        update_policy_affected: int = 1,
    ):
        self.rates_by_facility = rates_by_facility or {}
        self.discount_rules = discount_rules or []
        self.surcharges = surcharges or []
        self.policy_amounts = policy_amounts or {}
        self.insert_raises_unique = insert_raises_unique
        self.update_discount_affected = update_discount_affected
        self.update_surcharge_affected = update_surcharge_affected
        self.update_policy_affected = update_policy_affected
        self.insert_discount_calls: list[dict] = []
        self.insert_surcharge_calls: list[dict] = []
        self.insert_rate_calls: list[dict] = []
        self.fetch_active_locale_ids_result: list[UUID] = []
        self.discount_rules_by_id: dict[UUID, DiscountRuleResult] = {}
        self.surcharges_by_id: dict[UUID, SurchargeResult] = {}

    async def list_active_rates_for_facility(
        self,
        facility_id: UUID,
        as_of_date=None,
    ) -> list[RentalRateResult]:
        return list(self.rates_by_facility.get(facility_id, []))

    async def list_discount_rules(self) -> list[DiscountRuleResult]:
        return list(self.discount_rules)

    async def list_surcharges(self) -> list[SurchargeResult]:
        return list(self.surcharges)

    async def get_policy_amount(
        self,
        key: RentalPolicySettingKey | str,
        facility_id: UUID | None,
    ) -> Decimal | None:
        setting_key = key.value if hasattr(key, "value") else key
        return self.policy_amounts.get((setting_key, facility_id))

    @staticmethod
    def pick_rate_for_line(
        rates: list[RentalRateResult],
        billed_hours: Decimal,
        daily_flat_threshold: Decimal,
    ):
        return RentalRepository.pick_rate_for_line(rates, billed_hours, daily_flat_threshold)

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return RentalRepository.is_unique_violation(exc)

    async def insert_discount_rule(self, payload: dict) -> None:
        self.insert_discount_calls.append(payload)
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def update_discount_rule(self, rule_id: UUID, values: dict) -> int:
        return self.update_discount_affected

    async def get_discount_rule_by_id(self, rule_id: UUID) -> DiscountRuleResult | None:
        return self.discount_rules_by_id.get(rule_id)

    async def delete_discount_rule_soft(self, rule_id: UUID, reason: str | None) -> None:
        pass

    async def insert_surcharge(self, payload: dict) -> None:
        self.insert_surcharge_calls.append(payload)
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def update_surcharge(self, surcharge_id: UUID, values: dict) -> int:
        return self.update_surcharge_affected

    async def get_surcharge_by_id(self, surcharge_id: UUID) -> SurchargeResult | None:
        return self.surcharges_by_id.get(surcharge_id)

    async def delete_surcharge_soft(self, surcharge_id: UUID, reason: str | None) -> None:
        pass

    async def list_policy_settings(self, facility_id: UUID | None = None) -> list:
        return []

    async def get_policy_setting_by_id(self, setting_id: UUID):
        return None

    async def update_policy_setting(self, setting_id: UUID, values: dict) -> int:
        return self.update_policy_affected

    async def insert_rate(self, payload: dict) -> None:
        self.insert_rate_calls.append(payload)
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def fetch_rate_pages(self, command, locale_id, facility_id=None):
        return [], 0

    async def list_rates(self, facility_id, locale_id):
        return []

    async def get_rate_by_id(self, rate_id: UUID, locale_id=None):
        return None

    async def update_rate(self, rate_id: UUID, values: dict) -> int:
        return 0

    async def delete_rate_hard(self, rate_id: UUID) -> None:
        pass

    async def delete_rate_soft(self, rate_id: UUID, reason: str | None) -> None:
        pass

    async def restore_rate(self, rate_id: UUID) -> None:
        pass

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> list[UUID]:
        return self.fetch_active_locale_ids_result or locale_ids

    async def upsert_rate_translations(self, rows: list) -> None:
        pass


class StubRoomRepository:
    """In-memory room stub."""

    def __init__(
        self,
        existing_ids: set[UUID] | None = None,
        room_by_id: dict[UUID, RoomDetailResult] | None = None,
        insert_raises_unique: bool = False,
        update_affected: int = 1,
    ):
        self.existing_ids = existing_ids or set()
        self.room_by_id = room_by_id or {}
        self.insert_raises_unique = insert_raises_unique
        self.update_affected = update_affected
        self.insert_calls: list[dict] = []
        self.upsert_translation_calls: list = []

    async def exists_by_id(self, room_id: UUID) -> bool:
        return room_id in self.existing_ids

    async def get_by_id(self, room_id: UUID, locale_id=None) -> RoomDetailResult | None:
        return self.room_by_id.get(room_id)

    async def insert_room(self, payload: dict) -> None:
        self.insert_calls.append(payload)
        self.existing_ids.add(payload["id"])
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def update_room(self, room_id: UUID, values: dict) -> int:
        return self.update_affected

    async def delete_hard(self, room_id: UUID) -> None:
        pass

    async def delete_soft(self, room_id: UUID, reason: str | None) -> None:
        pass

    async def restore_room(self, room_id: UUID) -> None:
        pass

    async def fetch_pages(self, command, locale_id):
        return [], 0

    async def list_active(self, locale_id):
        return []

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> list[UUID]:
        return locale_ids

    async def upsert_translations(self, rows: list) -> None:
        self.upsert_translation_calls.append(rows)

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository

        return RoomRepository.is_unique_violation(exc)


class StubBookingRepository:
    """In-memory booking stub."""

    def __init__(
        self,
        exists: bool = True,
        booking_meta: dict | None = None,
        has_overlap: bool = False,
        detail: BookingDetailResult | None = None,
    ):
        self.exists = exists
        self.booking_meta = booking_meta or {
            "booking_type": "one_time",
            "currency": "CAD",
        }
        self.has_overlap = has_overlap
        self.detail = detail
        self.cancel_calls: list[dict] = []
        self.update_header_calls: list[dict] = []
        self.replace_rooms_calls: list = []
        self.replace_slots_calls: list = []

    async def exists_by_id(self, booking_id: UUID) -> bool:
        return self.exists

    async def get_detail(self, booking_id: UUID, locale_id=None) -> BookingDetailResult | None:
        return self.detail

    async def get_booking_type_and_flags(self, booking_id: UUID):
        if not self.exists:
            return None
        return self.booking_meta

    async def has_confirmed_slot_overlap(
        self,
        facility_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_booking_id: UUID | None = None,
    ) -> bool:
        return self.has_overlap

    async def cancel_booking(
        self,
        booking_id: UUID,
        cancelled_by_id: UUID | None,
        cancel_reason: str | None,
        cancel_slots: bool,
    ) -> None:
        self.cancel_calls.append(
            dict(
                booking_id=booking_id,
                cancelled_by_id=cancelled_by_id,
                cancel_reason=cancel_reason,
                cancel_slots=cancel_slots,
            )
        )

    async def update_booking_header(self, booking_id: UUID, values: dict) -> None:
        self.update_header_calls.append(values)

    async def replace_booking_rooms(self, booking_id: UUID, rows: list) -> None:
        self.replace_rooms_calls.append(rows)

    async def replace_booking_slots(self, booking_id: UUID, rows: list) -> None:
        self.replace_slots_calls.append(rows)

    async def fetch_pages(self, command: BookingPagesQueryCommand, locale_id):
        return [], 0


class StubRoomSlotTemplateRepository:
    """In-memory slot template stub."""

    def __init__(
        self,
        candidates: list[RoomSlotTemplateResult] | None = None,
        template_by_id: dict[UUID, RoomSlotTemplateResult] | None = None,
        update_affected: int = 1,
    ):
        self.candidates = candidates or []
        self.template_by_id = template_by_id or {}
        self.update_affected = update_affected
        self.insert_calls: list[dict] = []
        self.list_candidates_calls = 0

    @staticmethod
    def effective_dates_overlap(left_from, left_to, right_from, right_to) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import (
            RoomSlotTemplateRepository,
        )

        return RoomSlotTemplateRepository.effective_dates_overlap(
            left_from, left_to, right_from, right_to
        )

    @staticmethod
    def time_ranges_overlap(left_start, left_end, right_start, right_end) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import (
            RoomSlotTemplateRepository,
        )

        return RoomSlotTemplateRepository.time_ranges_overlap(
            left_start, left_end, right_start, right_end
        )

    async def list_active_overlapping_candidates(
        self,
        facility_id: UUID,
        days_of_week_mask: int,
        exclude_template_id: UUID | None = None,
    ) -> list[RoomSlotTemplateResult]:
        self.list_candidates_calls += 1
        return [
            item
            for item in self.candidates
            if item.id != exclude_template_id
            and (item.days_of_week_mask & days_of_week_mask) != 0
        ]

    async def get_by_id(self, template_id: UUID) -> RoomSlotTemplateResult | None:
        return self.template_by_id.get(template_id)

    async def insert_template(self, payload: dict) -> None:
        self.insert_calls.append(payload)

    async def update_template(self, template_id: UUID, values: dict) -> int:
        return self.update_affected

    async def delete_hard(self, template_id: UUID) -> None:
        pass

    async def delete_soft(self, template_id: UUID, reason: str | None) -> None:
        pass

    async def restore_template(self, template_id: UUID) -> None:
        pass

    async def fetch_pages(self, command, locale_id, facility_id=None):
        return [], 0

    async def list_by_facility(self, facility_id: UUID):
        return []


class StubMinistryRepository:
    """In-memory ministry stub."""

    def __init__(
        self,
        ministry_by_id: dict[UUID, MinistryDetailResult] | None = None,
        insert_raises_unique: bool = False,
        update_affected: int = 1,
    ):
        self.ministry_by_id = ministry_by_id or {}
        self.insert_raises_unique = insert_raises_unique
        self.update_affected = update_affected
        self.insert_calls: list[dict] = []
        self.replace_members_calls: list[dict] = []
        self.replace_user_ministries_calls: list[dict] = []

    async def get_by_id(self, ministry_id: UUID) -> MinistryDetailResult | None:
        return self.ministry_by_id.get(ministry_id)

    async def insert_ministry(self, payload: dict) -> None:
        self.insert_calls.append(payload)
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def update_ministry(self, ministry_id: UUID, values: dict) -> int:
        return self.update_affected

    async def delete_hard(self, ministry_id: UUID) -> None:
        pass

    async def delete_soft(self, ministry_id: UUID, reason: str | None) -> None:
        pass

    async def restore_ministry(self, ministry_id: UUID) -> None:
        pass

    async def fetch_pages(self, command: PagesQueryCommand, locale_id):
        return [], 0

    async def list_active(self, locale_id):
        return []

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> list[UUID]:
        return locale_ids

    async def upsert_translations(self, rows: list) -> None:
        pass

    async def replace_members(
        self,
        ministry_id: UUID,
        members: list[dict],
    ) -> None:
        self.replace_members_calls.append(
            dict(ministry_id=ministry_id, members=members)
        )

    async def replace_user_ministries(
        self,
        user_id: UUID,
        ministry_ids: list[UUID],
    ) -> None:
        self.replace_user_ministries_calls.append(
            dict(user_id=user_id, ministry_ids=ministry_ids)
        )

    async def fetch_member_pages(self, command, locale_id):
        return [], 0

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        from portal.infrastructure.persistence.repositories.facility.ministry_repository import MinistryRepository

        return MinistryRepository.is_unique_violation(exc)


class StubMemberRepository:
    """In-memory member stub."""

    def __init__(self, member_by_id: dict[UUID, MemberDetailResult] | None = None):
        self.member_by_id = member_by_id or {}

    async def get_detail(self, user_id: UUID, locale_id=None) -> MemberDetailResult | None:
        return self.member_by_id.get(user_id)

    async def fetch_pages(self, command: MemberPagesQueryCommand, locale_id):
        return [], 0


class StubOverrideLogRepository:
    """In-memory override log stub."""

    def __init__(self, items: list[OverrideLogResult] | None = None, total: int = 0):
        self.items = items or []
        self.total = total

    async def fetch_pages(self, command: OverrideLogPagesQueryCommand, locale_id):
        return self.items, self.total


class StubPricingService:
    """Fixed quote for booking service tests."""

    def __init__(self, quote_result):
        self.quote_result = quote_result
        self.preview_calls: list = []

    async def preview_quote(self, command):
        self.preview_calls.append(command)
        return self.quote_result
