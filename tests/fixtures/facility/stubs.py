"""
Stub repositories for facility application unit tests.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from asyncpg import UniqueViolationError

from portal.application.content.commands import UpdateFileAssociationCommand
from portal.application.content.results import FileBaseResult, FileGridItemResult
from portal.application.facility.commands import BookingPagesQueryCommand, BookingRangeQueryCommand, OverrideLogPagesQueryCommand, PagesQueryCommand
from portal.application.facility.results import (
    BookingDetailResult,
    BookingDraftDetailResult,
    BookingDraftStoredLineResult,
    BookingListItemResult,
    DiscountRuleResult,
    MinistryDetailResult,
    OverrideLogResult,
    PendingPaymentSeriesListItemResult,
    RecurringOccupyingBookingResult,
    RentalRateResult,
    RoomDetailResult,
    RoomSlotTemplateResult,
    SurchargeResult,
)
from portal.domain.facility.constants import BookingStatus
from portal.domain.facility.recurring import is_pending_payment_hold_active
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository


class StubRentalRepository:
    """In-memory rental catalog and rate stub."""

    def __init__(
        self,
        rates_by_facility: dict[UUID, list[RentalRateResult]] | None = None,
        discount_rules: list[DiscountRuleResult] | None = None,
        surcharges: list[SurchargeResult] | None = None,
        insert_raises_unique: bool = False,
        update_discount_affected: int = 1,
        update_surcharge_affected: int = 1,
    ):
        self.rates_by_facility = rates_by_facility or {}
        self.discount_rules = discount_rules or []
        self.surcharges = surcharges or []
        self.insert_raises_unique = insert_raises_unique
        self.update_discount_affected = update_discount_affected
        self.update_surcharge_affected = update_surcharge_affected
        self.insert_discount_calls: list[dict] = []
        self.insert_surcharge_calls: list[dict] = []
        self.insert_rate_calls: list[dict] = []
        self.insert_template_calls: list[dict] = []
        self.templates_by_id: dict[UUID, Any] = {}
        self.rates_by_id: dict[UUID, RentalRateResult] = {}
        self.count_rates_for_template_result = 0
        self.discount_rules_by_id: dict[UUID, DiscountRuleResult] = {}
        self.surcharges_by_id: dict[UUID, SurchargeResult] = {}

    async def list_active_rates_for_facility(self, facility_id: UUID, as_of_date=None) -> list[RentalRateResult]:
        return list(self.rates_by_facility.get(facility_id, []))

    async def list_discount_rules(self) -> list[DiscountRuleResult]:
        return list(self.discount_rules)

    async def list_surcharges(self) -> list[SurchargeResult]:
        return list(self.surcharges)

    @staticmethod
    def pick_rate_for_line(rates: list[RentalRateResult], billed_hours: Decimal, allow_first_active: bool = True):
        return RentalRepository.pick_rate_for_line(rates, billed_hours, allow_first_active=allow_first_active)

    @staticmethod
    def template_to_rate_candidate(template):
        return RentalRepository.template_to_rate_candidate(template)

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

    async def insert_rate(self, payload: dict) -> None:
        self.insert_rate_calls.append(payload)
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")

    async def fetch_rate_pages(self, command, facility_id=None):
        return [], 0

    async def list_rates(self, facility_id=None):
        return []

    async def get_rate_by_id(self, rate_id: UUID):
        return self.rates_by_id.get(rate_id)

    async def update_rate(self, rate_id: UUID, values: dict) -> int:
        return 1 if rate_id in self.rates_by_id else 0

    async def delete_rate_hard(self, rate_id: UUID) -> None:
        pass

    async def delete_rate_soft(self, rate_id: UUID, reason: str | None) -> None:
        pass

    async def restore_rate(self, rate_id: UUID) -> None:
        pass

    async def get_template_by_id(self, template_id: UUID):
        return self.templates_by_id.get(template_id)

    async def count_rates_for_template(self, template_id: UUID) -> int:
        return self.count_rates_for_template_result

    async def insert_template(self, payload: dict) -> None:
        if self.insert_raises_unique:
            raise UniqueViolationError("duplicate")
        self.insert_template_calls.append(payload)

    async def update_template(self, template_id: UUID, values: dict) -> int:
        return 1 if template_id in self.templates_by_id else 0

    async def delete_template_soft(self, template_id: UUID, reason: str | None) -> None:
        pass

    async def restore_template(self, template_id: UUID) -> None:
        pass

    async def fetch_template_pages(self, command):
        return [], 0

    async def list_templates(self, active_only: bool = True):
        items = list(self.templates_by_id.values())
        if active_only:
            return [item for item in items if getattr(item, "is_active", True)]
        return items


class StubFileService:
    """FileService subset used by RoomService gallery tests."""

    def __init__(self, active_files: dict[UUID, FileBaseResult] | None = None, files_by_resource: dict[UUID, list[FileGridItemResult]] | None = None):
        self.active_files = active_files or {}
        self.files_by_resource = files_by_resource or {}
        self.association_commands: list[UpdateFileAssociationCommand] = []
        self.get_files_calls: list[UUID] = []

    async def list_active_files_by_ids(self, file_ids: list[UUID]) -> list[FileBaseResult]:
        return [self.active_files[file_id] for file_id in file_ids if file_id in self.active_files]

    async def update_file_association(self, command: UpdateFileAssociationCommand) -> None:
        self.association_commands.append(command)

    async def get_files_by_resource_id(self, resource_id: UUID, resource_name: str | None = None) -> list[FileGridItemResult]:
        self.get_files_calls.append(resource_id)
        return list(self.files_by_resource.get(resource_id, []))

    async def get_signed_urls_by_resource_ids(self, resource_ids: list[UUID], resource_name: str | None = None) -> dict[UUID, list[str]]:
        return {resource_id: [file.url for file in self.files_by_resource.get(resource_id, []) if file.url] for resource_id in resource_ids}


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

    async def get_by_id(self, room_id: UUID, locale_id=None, all_locales: bool = False) -> RoomDetailResult | None:
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
        overlapping_slots: set[tuple[UUID, datetime]] | None = None,
        detail: BookingDetailResult | None = None,
        range_items: list[BookingListItemResult] | None = None,
        deleted_ids: set[UUID] | None = None,
        rental_starts: list[datetime] | None = None,
        occupying_bookings: list[RecurringOccupyingBookingResult] | None = None,
    ):
        self.exists = exists
        self.booking_meta = booking_meta or {"booking_type": "one_time", "currency": "CAD"}
        self.has_overlap = has_overlap
        self.overlapping_slots = overlapping_slots or set()
        self.occupying_bookings = occupying_bookings or []
        self.detail = detail
        self.range_items = range_items or []
        self.deleted_ids = deleted_ids or set()
        self.rental_starts = rental_starts or []
        self.cancel_calls: list[dict] = []
        self.override_calls: list[dict] = []
        self.insert_calls: list[dict] = []
        self.update_header_calls: list[dict] = []
        self.replace_rooms_calls: list = []
        self.replace_slots_calls: list = []
        self.fetch_range_calls: list[BookingRangeQueryCommand] = []
        self.series_occurrences: dict[UUID, list[Any]] = {}
        self.confirm_series_calls: list[dict] = []
        self.live_future_series_occurrences: list[Any] = []

    async def exists_by_id(self, booking_id: UUID) -> bool:
        return self.exists

    async def get_detail(self, booking_id: UUID, locale_id=None) -> BookingDetailResult | None:
        if self.detail is None or self.detail.id != booking_id:
            return None
        return self.detail

    async def get_booking_type_and_flags(self, booking_id: UUID):
        if not self.exists:
            return None
        return self.booking_meta

    async def has_confirmed_slot_overlap(self, facility_id: UUID, start_at: datetime, end_at: datetime, exclude_booking_id: UUID | None = None) -> bool:
        occupying = await self.list_occupying_slots(facility_id, start_at, end_at)
        return any(item.booking_id != exclude_booking_id for item in occupying)

    async def list_occupying_slots(self, facility_id: UUID, start_at: datetime, end_at: datetime) -> list[RecurringOccupyingBookingResult]:
        matches = [item for item in self.occupying_bookings if facility_id in item.facility_ids and item.start_at < end_at and item.end_at > start_at]
        if matches:
            return matches
        if self.has_overlap or (facility_id, start_at) in self.overlapping_slots:
            return [
                RecurringOccupyingBookingResult(
                    booking_id=uuid4(),
                    user_id=uuid4(),
                    ministry_id=None,
                    facility_ids=[facility_id],
                    start_at=start_at,
                    end_at=end_at or start_at + timedelta(hours=2),
                )
            ]
        return []

    async def insert_booking(self, payload: dict) -> None:
        self.insert_calls.append(payload)

    async def list_rental_occurrence_starts(self, user_id: UUID, range_start: datetime, range_end: datetime) -> list[datetime]:
        return [start_at for start_at in self.rental_starts if range_start <= start_at < range_end]

    async def cancel_booking(self, booking_id: UUID, cancelled_by_id: UUID | None, cancel_reason: str | None, cancel_slots: bool) -> None:
        self.cancel_calls.append(dict(booking_id=booking_id, cancelled_by_id=cancelled_by_id, cancel_reason=cancel_reason, cancel_slots=cancel_slots))
        for occurrences in self.series_occurrences.values():
            for occurrence in occurrences:
                if occurrence.id == booking_id:
                    occurrence.status = BookingStatus.CANCELLED.value

    async def override_booking(self, booking_id: UUID, overridden_by_id: UUID | None, reason: str | None) -> None:
        self.override_calls.append(dict(booking_id=booking_id, overridden_by_id=overridden_by_id, reason=reason))

    async def list_live_future_series_occurrences(self, now: datetime):
        return [item for item in self.live_future_series_occurrences if item.start_at > now]

    async def list_series_occurrences(self, series_id: UUID):
        return list(self.series_occurrences.get(series_id, []))

    async def confirm_pending_series_bookings(self, series_id: UUID, operator_id: UUID | None) -> None:
        self.confirm_series_calls.append(dict(series_id=series_id, operator_id=operator_id))
        for occurrence in self.series_occurrences.get(series_id, []):
            if getattr(occurrence, "status", None) == BookingStatus.PENDING_PAYMENT.value:
                occurrence.status = BookingStatus.CONFIRMED.value

    async def update_booking_header(self, booking_id: UUID, values: dict) -> None:
        self.update_header_calls.append(values)

    async def replace_booking_rooms(self, booking_id: UUID, rows: list) -> None:
        self.replace_rooms_calls.append(rows)

    async def replace_booking_slots(self, booking_id: UUID, rows: list) -> None:
        self.replace_slots_calls.append(rows)

    async def fetch_pages(self, command: BookingPagesQueryCommand, locale_id):
        return [], 0

    async def fetch_range(self, command: BookingRangeQueryCommand, locale_id) -> list[BookingListItemResult]:
        self.fetch_range_calls.append(command)
        items: list[BookingListItemResult] = []
        for item in self.range_items:
            if item.id in self.deleted_ids:
                continue
            if not (item.start_at < command.date_to and item.end_at > command.date_from):
                continue
            if not command.include_cancelled and item.status == BookingStatus.CANCELLED.value:
                continue
            items.append(item)
        return items


class StubRoomSlotTemplateRepository:
    """In-memory slot template stub."""

    def __init__(
        self, candidates: list[RoomSlotTemplateResult] | None = None, template_by_id: dict[UUID, RoomSlotTemplateResult] | None = None, update_affected: int = 1
    ):
        self.candidates = candidates or []
        self.template_by_id = template_by_id or {}
        self.update_affected = update_affected
        self.insert_calls: list[dict] = []
        self.list_candidates_calls = 0

    @staticmethod
    def effective_dates_overlap(left_from, left_to, right_from, right_to) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import RoomSlotTemplateRepository

        return RoomSlotTemplateRepository.effective_dates_overlap(left_from, left_to, right_from, right_to)

    @staticmethod
    def time_ranges_overlap(left_start, left_end, right_start, right_end) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import RoomSlotTemplateRepository

        return RoomSlotTemplateRepository.time_ranges_overlap(left_start, left_end, right_start, right_end)

    async def list_active_overlapping_candidates(
        self, facility_id: UUID, days_of_week_mask: int, exclude_template_id: UUID | None = None
    ) -> list[RoomSlotTemplateResult]:
        self.list_candidates_calls += 1
        return [item for item in self.candidates if item.id != exclude_template_id and (item.days_of_week_mask & days_of_week_mask) != 0]

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


class StubRoomBlackoutRepository:
    """In-memory room blackout stub."""

    def __init__(
        self,
        candidates: list | None = None,
        blackout_by_id: dict | None = None,
        update_affected: int = 1,
        has_overlap: bool = False,
        overlapping_blackouts: set[tuple[UUID, datetime]] | None = None,
        for_room_day: list | None = None,
    ):
        self.candidates = candidates or []
        self.blackout_by_id = blackout_by_id or {}
        self.update_affected = update_affected
        self.has_overlap = has_overlap
        self.overlapping_blackouts = overlapping_blackouts or set()
        self.for_room_day = for_room_day or []
        self.insert_calls: list[dict] = []
        self.list_candidates_calls = 0

    @staticmethod
    def effective_dates_overlap(left_from, left_to, right_from, right_to) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.effective_dates_overlap(left_from, left_to, right_from, right_to)

    @staticmethod
    def time_ranges_overlap(left_start, left_end, right_start, right_end) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.time_ranges_overlap(left_start, left_end, right_start, right_end)

    @staticmethod
    def scopes_overlap(left_facility_id, right_facility_id) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.scopes_overlap(left_facility_id, right_facility_id)

    @staticmethod
    def applies_on_date(item, target_date):
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.applies_on_date(item, target_date)

    def interval_overlaps_blackout(self, item, facility_id, start_at, end_at, tz) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.interval_overlaps_blackout(self, item, facility_id, start_at, end_at, tz)

    def slot_overlaps_blackouts(self, blackouts, slot_start_local, slot_end_local) -> bool:
        from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository

        return RoomBlackoutRepository.slot_overlaps_blackouts(self, blackouts, slot_start_local, slot_end_local)

    async def list_active_overlapping_candidates(self, facility_id, kind: str, exclude_blackout_id=None):
        self.list_candidates_calls += 1
        return [item for item in self.candidates if getattr(item, "id", None) != exclude_blackout_id and getattr(item, "kind", None) == kind]

    async def list_active_for_room_day(self, facility_id, target_date):
        return list(self.for_room_day)

    async def has_blackout_overlap(self, facility_id, start_at, end_at, tz) -> bool:
        if self.has_overlap:
            return True
        return (facility_id, start_at) in self.overlapping_blackouts

    async def get_by_id(self, blackout_id):
        return self.blackout_by_id.get(blackout_id)

    async def insert_blackout(self, payload: dict) -> None:
        self.insert_calls.append(payload)

    async def update_blackout(self, blackout_id, values: dict) -> int:
        return self.update_affected

    async def delete_hard(self, blackout_id) -> None:
        pass

    async def delete_soft(self, blackout_id, reason: str | None) -> None:
        pass

    async def restore_blackout(self, blackout_id) -> None:
        pass

    async def fetch_pages(self, command, facility_id=None):
        return [], 0

    async def list_by_facility(self, facility_id):
        return []


class StubMinistryRepository:
    """In-memory ministry stub."""

    def __init__(
        self,
        ministry_by_id: dict[UUID, MinistryDetailResult] | None = None,
        insert_raises_unique: bool = False,
        update_affected: int = 1,
        booking_member_user_ids: set[UUID] | None = None,
        members_by_ministry: dict[UUID, list] | None = None,
    ):
        self.ministry_by_id = ministry_by_id or {}
        self.insert_raises_unique = insert_raises_unique
        self.update_affected = update_affected
        self.booking_member_user_ids = booking_member_user_ids
        self.members_by_ministry = members_by_ministry or {}
        self.insert_calls: list[dict] = []
        self.replace_members_calls: list[dict] = []
        self.membership_check_calls: list[dict] = []

    async def get_by_id(self, ministry_id: UUID, locale_id=None, all_locales: bool = False) -> MinistryDetailResult | None:
        return self.ministry_by_id.get(ministry_id)

    async def list_members(self, ministry_id: UUID):
        return self.members_by_ministry.get(ministry_id, [])

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

    async def get_status(self, ministry_id: UUID) -> str | None:
        ministry = self.ministry_by_id.get(ministry_id)
        return getattr(ministry, "status", None) if ministry else None

    async def is_user_booking_member(self, ministry_id: UUID, user_id: UUID) -> bool:
        self.membership_check_calls.append(dict(ministry_id=ministry_id, user_id=user_id))
        if self.booking_member_user_ids is None:
            return True
        return user_id in self.booking_member_user_ids

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> list[UUID]:
        return locale_ids

    async def upsert_translations(self, rows: list) -> None:
        pass

    async def replace_members(self, ministry_id: UUID, members: list[dict]) -> None:
        self.replace_members_calls.append(dict(ministry_id=ministry_id, members=members))

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        from portal.infrastructure.persistence.repositories.facility.ministry_repository import MinistryRepository

        return MinistryRepository.is_unique_violation(exc)


class StubRecurringBookingRepository:
    """In-memory Recurring Booking Series persistence stub."""

    def __init__(self, series_by_id: dict | None = None, lock_acquired: bool = True):
        self.insert_series_calls: list[dict] = []
        self.update_series_calls: list[dict] = []
        self.series_by_id = series_by_id or {}
        self.lock_acquired = lock_acquired
        self.lock_acquire_calls = 0
        self.lock_release_calls = 0

    async def insert_series(self, payload: dict) -> None:
        self.insert_series_calls.append(payload)

    async def get_by_id(self, series_id: UUID, locale_id=None):
        return self.series_by_id.get(series_id)

    async def update_series(self, series_id: UUID, values: dict) -> None:
        self.update_series_calls.append({"id": series_id, **values})
        existing = self.series_by_id.get(series_id)
        if existing is not None:
            self.series_by_id[series_id] = existing.model_copy(update=values)

    async def list_expired_pending_series(self, now: datetime) -> list:
        expired = []
        for series in self.series_by_id.values():
            if getattr(series, "status", BookingStatus.PENDING_PAYMENT.value) != BookingStatus.PENDING_PAYMENT.value:
                continue
            if series.payment_hold_expires_at is None or series.payment_hold_expires_at > now:
                continue
            expired.append(series)
        return expired

    async def list_pending_payment_series(self, now: datetime, locale_id=None) -> list:
        items = []
        for series in self.series_by_id.values():
            if getattr(series, "status", BookingStatus.PENDING_PAYMENT.value) != BookingStatus.PENDING_PAYMENT.value:
                continue
            if not is_pending_payment_hold_active(series.payment_hold_expires_at, now):
                continue
            if isinstance(series, PendingPaymentSeriesListItemResult):
                items.append(series)
                continue
            items.append(
                PendingPaymentSeriesListItemResult(
                    id=series.id,
                    user_id=series.user_id,
                    ministry_id=series.ministry_id,
                    quoted_amount=series.quoted_amount,
                    currency=series.currency,
                    occurrence_count=series.occurrence_count,
                    payment_hold_expires_at=series.payment_hold_expires_at,
                    is_priority=series.is_priority,
                )
            )
        items.sort(key=lambda item: (item.payment_hold_expires_at is None, item.payment_hold_expires_at or now))
        return items

    async def try_acquire_sweep_lock(self) -> bool:
        self.lock_acquire_calls += 1
        return self.lock_acquired

    async def release_sweep_lock(self) -> None:
        self.lock_release_calls += 1


class StubRecurringOverrideNotifier:
    """Records Priority Ministry override notifications."""

    def __init__(self, raise_error: Exception | None = None):
        self.calls: list = []
        self.raise_error = raise_error

    async def notify_priority_override(self, notification) -> None:
        self.calls.append(notification)
        if self.raise_error:
            raise self.raise_error


class StubRecurringExpiryNotifier:
    """Records Pending-payment hold expiry notifications."""

    def __init__(self, raise_error: Exception | None = None):
        self.calls: list = []
        self.raise_error = raise_error

    async def notify_payment_hold_expired(self, notification) -> None:
        self.calls.append(notification)
        if self.raise_error:
            raise self.raise_error


class StubUserReadService:
    """Minimal user lookup stub for church-domain eligibility."""

    def __init__(self, email: str = "booker@efcnewlife.org"):
        self.email = email

    async def get_user_sensitive_by_id(self, user_id: UUID):
        from portal.application.auth.results import UserSensitive

        return UserSensitive(id=user_id, email=self.email)


class StubOverrideLogRepository:
    """In-memory override log stub."""

    def __init__(self, items: list[OverrideLogResult] | None = None, total: int = 0):
        self.items = items or []
        self.total = total
        self.insert_calls: list[list[dict]] = []

    async def fetch_pages(self, command: OverrideLogPagesQueryCommand, locale_id):
        return self.items, self.total

    async def insert_logs(self, rows: list[dict]) -> None:
        self.insert_calls.append(rows)


class StubBookingDraftRepository:
    """In-memory Booking Draft stub."""

    def __init__(self, draft_by_id: dict[UUID, BookingDraftDetailResult] | None = None):
        self.draft_by_id = draft_by_id or {}
        self.insert_draft_calls: list[dict] = []
        self.insert_lines_calls: list[list[dict]] = []
        self.update_header_calls: list[dict] = []
        self.replace_lines_calls: list[list[dict]] = []
        self.delete_draft_calls: list[UUID] = []
        self.delete_all_for_user_calls: list[UUID] = []

    async def insert_draft(self, payload: dict) -> None:
        self.insert_draft_calls.append(payload)
        self.draft_by_id[payload["id"]] = BookingDraftDetailResult(
            id=payload["id"], user_id=payload["user_id"], date=payload["date"], ministry_id=payload.get("ministry_id"), lines=[]
        )

    async def insert_lines(self, line_rows: list[dict]) -> None:
        self.insert_lines_calls.append(line_rows)
        for row in line_rows:
            draft = self.draft_by_id.get(row["booking_draft_id"])
            if draft is not None:
                draft.lines.append(
                    BookingDraftStoredLineResult(facility_id=row["facility_id"], start_at=row["start_at"], end_at=row["end_at"], sequence=row["sequence"])
                )

    async def update_header(self, booking_draft_id: UUID, values: dict) -> None:
        self.update_header_calls.append(values)
        draft = self.draft_by_id.get(booking_draft_id)
        if draft is not None:
            self.draft_by_id[booking_draft_id] = draft.model_copy(update=values)

    async def replace_lines(self, booking_draft_id: UUID, line_rows: list[dict]) -> None:
        self.replace_lines_calls.append(line_rows)
        draft = self.draft_by_id.get(booking_draft_id)
        if draft is not None:
            draft.lines = [
                BookingDraftStoredLineResult(facility_id=row["facility_id"], start_at=row["start_at"], end_at=row["end_at"], sequence=row["sequence"])
                for row in line_rows
            ]

    async def delete_draft(self, booking_draft_id: UUID) -> None:
        self.delete_draft_calls.append(booking_draft_id)
        self.draft_by_id.pop(booking_draft_id, None)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        self.delete_all_for_user_calls.append(user_id)
        self.draft_by_id = {draft_id: draft for draft_id, draft in self.draft_by_id.items() if draft.user_id != user_id}

    async def get_detail(self, booking_draft_id: UUID) -> Optional[BookingDraftDetailResult]:
        return self.draft_by_id.get(booking_draft_id)


class StubPricingService:
    """Fixed quote for booking service tests."""

    def __init__(self, quote_result):
        self.quote_result = quote_result
        self.preview_calls: list = []

    async def preview_quote(self, command):
        self.preview_calls.append(command)
        if len(command.room_lines) <= len(self.quote_result.room_lines):
            return self.quote_result
        template = self.quote_result.room_lines[0]
        room_lines = [
            template.model_copy(update={"facility_id": line.facility_id, "billed_hours": line.billed_hours, "line_subtotal": template.line_subtotal})
            for line in command.room_lines
        ]
        quoted_amount = self.quote_result.quoted_amount * len(command.room_lines)
        return self.quote_result.model_copy(update={"room_lines": room_lines, "quoted_amount": quoted_amount, "subtotal_amount": quoted_amount})
