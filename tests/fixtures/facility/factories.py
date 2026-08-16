"""
Test data factories for facility application tests.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from portal.application.facility.commands import (
    BookingRoomLineCommand,
    CreateBookingCommand,
    CreateDiscountRuleCommand,
    CreateMinistryCommand,
    CreateRentalRateCommand,
    CreateRentalRateTemplateCommand,
    CreateRoomCommand,
    CreateRoomSlotTemplateCommand,
    CreateSurchargeCommand,
    FacilityTranslationCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateBookingCommand,
)
from portal.application.facility.results import (
    DiscountRuleResult,
    MinistryDetailResult,
    PreviewQuoteResult,
    PreviewQuoteRoomLineResult,
    RentalRateResult,
    RentalRateTemplateResult,
    RoomDetailResult,
    RoomSlotTemplateResult,
    SurchargeResult,
)
from portal.application.org.commands import OrgTranslationCommand
from portal.domain.facility.constants import BookingType, RentalDiscountCode, RentalRateBillingUnit, RentalSurchargeChargeType


def new_uuid() -> UUID:
    return uuid4()


def make_translation(locale_id: UUID | None = None, name: str = "Test Room") -> FacilityTranslationCommand:
    return FacilityTranslationCommand(locale_id=locale_id or new_uuid(), name=name)


def make_create_room_command(code: str = "room-a", locale_id: UUID | None = None, name: str = "Room A") -> CreateRoomCommand:
    return CreateRoomCommand(code=code, translations=[make_translation(locale_id, name=name)])


def make_ministry_translation(locale_id: UUID | None = None, name: str = "Youth Ministry") -> OrgTranslationCommand:
    return OrgTranslationCommand(locale_id=locale_id or new_uuid(), name=name)


def make_create_ministry_command(locale_id: UUID | None = None, name: str = "Youth Ministry") -> CreateMinistryCommand:
    return CreateMinistryCommand(translations=[make_ministry_translation(locale_id, name=name)])


def make_rental_rate_template(
    *,
    template_id: UUID | None = None,
    name: str = "Hourly",
    billing_unit: str = RentalRateBillingUnit.HOURLY.value,
    is_default: bool = True,
    is_active: bool = True,
    applicability: dict | None = None,
    unit_amount: Decimal = Decimal("30"),
    currency: str = "CAD",
) -> RentalRateTemplateResult:
    return RentalRateTemplateResult(
        id=template_id or new_uuid(),
        name=name,
        billing_unit=billing_unit,
        applicability=applicability,
        unit_amount=unit_amount,
        currency=currency,
        is_default=is_default,
        is_active=is_active,
    )


def make_rental_rate(
    facility_id: UUID | None = None,
    billing_unit: str = RentalRateBillingUnit.HOURLY.value,
    unit_amount: Decimal = Decimal("10"),
    is_active: bool = True,
    is_default: bool = False,
    rate_id: UUID | None = None,
    template_id: UUID | None = None,
    applicability: dict | None = None,
) -> RentalRateResult:
    resolved_template_id = template_id or new_uuid()
    return RentalRateResult(
        id=rate_id or new_uuid(),
        facility_id=facility_id,
        template_id=resolved_template_id,
        unit_amount=unit_amount,
        currency="CAD",
        is_active=is_active,
        template_name=billing_unit,
        billing_unit=billing_unit,
        applicability=applicability,
        is_default=is_default,
        template_is_active=True,
    )


def make_hourly_and_daily_rates(
    facility_id: UUID | None = None, hourly_amount: Decimal = Decimal("10"), daily_amount: Decimal = Decimal("200")
) -> list[RentalRateResult]:
    return [
        make_rental_rate(
            facility_id=facility_id,
            billing_unit=RentalRateBillingUnit.HOURLY.value,
            unit_amount=hourly_amount,
            is_default=True,
            applicability={"all": [{"op": "hours_lt", "value": 5}]},
        ),
        make_rental_rate(
            facility_id=facility_id,
            billing_unit=RentalRateBillingUnit.DAILY_FLAT.value,
            unit_amount=daily_amount,
            applicability={"all": [{"op": "hours_gte", "value": 5}]},
        ),
    ]


def make_discount_rule(
    code: str = RentalDiscountCode.MISSION_ALIGNED.value, percent_off: Decimal = Decimal("30"), is_active: bool = True
) -> DiscountRuleResult:
    return DiscountRuleResult(id=new_uuid(), code=code, percent_off=percent_off, is_active=is_active)


def make_surcharge(
    code: str = "audio_system", charge_type: str = RentalSurchargeChargeType.PER_HOUR.value, unit_amount: Decimal = Decimal("5"), is_active: bool = True
) -> SurchargeResult:
    return SurchargeResult(id=new_uuid(), code=code, charge_type=charge_type, unit_amount=unit_amount, currency="CAD", is_active=is_active)


def make_preview_quote_command(
    facility_id: UUID | None = None,
    billed_hours: Decimal = Decimal("6"),
    booking_type: BookingType = BookingType.ONE_TIME,
    is_mission_aligned: bool = False,
    surcharge_codes: list[str] | None = None,
) -> PreviewQuoteCommand:
    room_id = facility_id or new_uuid()
    return PreviewQuoteCommand(
        booking_type=booking_type,
        is_mission_aligned=is_mission_aligned,
        currency="CAD",
        room_lines=[PreviewQuoteRoomLineCommand(facility_id=room_id, billed_hours=billed_hours)],
        surcharge_codes=surcharge_codes or [],
    )


def make_preview_quote_result(quoted_amount: Decimal = Decimal("100"), discount_percent: Decimal = Decimal("0")) -> PreviewQuoteResult:
    facility_id = new_uuid()
    return PreviewQuoteResult(
        subtotal_amount=quoted_amount,
        discount_percent=discount_percent,
        discount_amount=Decimal("0"),
        surcharge_amount=Decimal("0"),
        quoted_amount=quoted_amount,
        currency="CAD",
        room_lines=[
            PreviewQuoteRoomLineResult(
                facility_id=facility_id,
                billed_hours=Decimal("2"),
                rental_rate_name="Hourly",
                billing_unit=RentalRateBillingUnit.HOURLY.value,
                unit_amount=Decimal("10"),
                currency="CAD",
                applicability=None,
                is_default=True,
                line_subtotal=quoted_amount,
            )
        ],
    )


def make_room_detail(room_id: UUID | None = None, code: str = "room-a") -> RoomDetailResult:
    return RoomDetailResult(id=room_id or new_uuid(), code=code, name="Room A", is_active=True)


def make_ministry_detail(ministry_id: UUID | None = None) -> MinistryDetailResult:
    return MinistryDetailResult(id=ministry_id or new_uuid(), name="Youth", status="active", is_active=True)


def make_slot_template_result(
    facility_id: UUID,
    days_of_week_mask: int = 1,
    start_time: time = time(9, 0),
    end_time: time = time(12, 0),
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> RoomSlotTemplateResult:
    return RoomSlotTemplateResult(
        id=new_uuid(),
        facility_id=facility_id,
        name="Morning",
        days_of_week_mask=days_of_week_mask,
        start_time=start_time,
        end_time=end_time,
        slot_duration_minutes=60,
        is_active=True,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def make_create_slot_template_command(
    facility_id: UUID, start_time: time = time(9, 0), end_time: time = time(12, 0), is_active: bool = True, days_of_week: list[int] | None = None
) -> CreateRoomSlotTemplateCommand:
    return CreateRoomSlotTemplateCommand(
        facility_id=facility_id,
        name="Morning",
        days_of_week=days_of_week if days_of_week is not None else [0],
        start_time=start_time,
        end_time=end_time,
        slot_duration_minutes=60,
        is_active=is_active,
    )


def make_create_rental_rate_template_command(name: str = "Hourly") -> CreateRentalRateTemplateCommand:
    return CreateRentalRateTemplateCommand(
        name=name,
        billing_unit=RentalRateBillingUnit.HOURLY,
        unit_amount=Decimal("30"),
        currency="CAD",
        is_default=True,
        is_active=True,
        applicability={"all": [{"op": "hours_lt", "value": 5}]},
    )


def make_create_rental_rate_command(facility_id: UUID, template_id: UUID | None = None) -> CreateRentalRateCommand:
    return CreateRentalRateCommand(facility_id=facility_id, template_id=template_id or new_uuid(), is_active=True)


def make_update_booking_command(facility_id: UUID | None = None, start_at: datetime | None = None, end_at: datetime | None = None) -> UpdateBookingCommand:
    room_id = facility_id or new_uuid()
    start = start_at or datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = end_at or datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    return UpdateBookingCommand(start_at=start, end_at=end, rooms=[BookingRoomLineCommand(facility_id=room_id, sequence=0)])


def make_create_booking_command(
    facility_id: UUID | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    user_id: UUID | None = None,
    ministry_id: UUID | None = None,
) -> CreateBookingCommand:
    room_id = facility_id or new_uuid()
    start = start_at or datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = end_at or datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    return CreateBookingCommand(
        start_at=start, end_at=end, user_id=user_id, ministry_id=ministry_id, rooms=[BookingRoomLineCommand(facility_id=room_id, sequence=0)]
    )


def make_create_discount_command(code: str = "mission_aligned") -> CreateDiscountRuleCommand:
    return CreateDiscountRuleCommand(code=code, percent_off=Decimal("30"))


def make_create_surcharge_command(code: str = "audio_system") -> CreateSurchargeCommand:
    return CreateSurchargeCommand(code=code, charge_type=RentalSurchargeChargeType.FLAT.value, unit_amount=Decimal("25"))
