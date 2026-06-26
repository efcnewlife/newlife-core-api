"""
Facility booking domain constants and enums.
"""
from enum import Enum, IntEnum


class BookingType(str, Enum):
    """Booking recurrence type (one-time vs recurring series)."""

    ONE_TIME = "one_time"
    RECURRING = "recurring"


# recurrence_rule on facility.booking stores iCal RRULE only (RFC 5545), e.g. FREQ=WEEKLY;BYDAY=TU.
# Use booking.start_at as the series DTSTART; recurrence_end_at bounds the series end.


class BookingStatus(str, Enum):
    """Booking lifecycle status."""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    OVERRIDDEN = "overridden"


class BookingSlotStatus(str, Enum):
    """Expanded booking slot occupancy status."""
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class RentalRateBillingUnit(str, Enum):
    """Rental rate billing unit."""
    HOURLY = "hourly"
    DAILY_FLAT = "daily_flat"
    PER_SLOT = "per_slot"
    FLAT_PER_BOOKING = "flat_per_booking"


class RentalDiscountCode(str, Enum):
    """Rental discount rule code."""
    RECURRING_WEEKLY_MONTHLY = "recurring_weekly_monthly"
    MISSION_ALIGNED = "mission_aligned"


class RentalSurchargeCode(str, Enum):
    """Rental surcharge catalog code."""
    DEPOSIT_ONE_TIME = "deposit_one_time"
    DOOR_AUDIO_OPERATOR = "door_audio_operator"
    AUDIO_SYSTEM = "audio_system"


class RentalSurchargeChargeType(str, Enum):
    """Rental surcharge charge type."""
    FLAT = "flat"
    PER_HOUR = "per_hour"
    PER_PROGRAM = "per_program"


class RentalPolicySettingKey(str, Enum):
    """Rental policy setting key."""
    MINIMUM_FEE_DEFAULT = "minimum_fee_default"
    MINIMUM_FEE_GYM = "minimum_fee_gym"
    DAILY_FLAT_MIN_HOURS = "daily_flat_min_hours"
    MAX_ROOMS_PER_BOOKING = "max_rooms_per_booking"


class OverrideOutcome(str, Enum):
    """Ministry priority override outcome."""
    OVERRIDE_APPLIED = "override_applied"
    BOOKING_CANCELLED = "booking_cancelled"
    DISPLACED = "displaced"


class DayOfWeek(IntEnum):
    """ISO weekday (Monday=0 through Sunday=6)."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
