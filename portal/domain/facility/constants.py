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

# Max inclusive span for Booking range query (Calendar / Grid visible window).
BOOKING_RANGE_MAX_DAYS = 62

# Max images in one Room gallery.
ROOM_GALLERY_MAX_FILES = 10

# Hard product cap on Booking lines (not a Policy Setting).
MAX_BOOKING_LINES = 3


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


class RoomBlackoutKind(str, Enum):
    """Room blackout recurrence kind."""

    ONE_OFF = "one_off"
    RECURRING = "recurring"


class BookingErrorCode(str, Enum):
    """Machine-readable booking create/update error codes for clients."""

    SCHEDULING_CONFLICT = "FACILITY_BOOKING_SCHEDULING_CONFLICT"
    ROOM_BLACKOUT = "FACILITY_BOOKING_ROOM_BLACKOUT"


class FacilityErrorCode(str, Enum):
    """Machine-readable facility admin error codes for clients."""

    ROOM_NOT_FOUND = "FACILITY_ROOM_NOT_FOUND"
    ROOM_CODE_EXISTS = "FACILITY_ROOM_CODE_EXISTS"
    SLOT_TEMPLATE_NOT_FOUND = "FACILITY_SLOT_TEMPLATE_NOT_FOUND"
    SLOT_TEMPLATE_OVERLAP = "FACILITY_SLOT_TEMPLATE_OVERLAP"
    BLACKOUT_NOT_FOUND = "FACILITY_BLACKOUT_NOT_FOUND"
    BLACKOUT_OVERLAP = "FACILITY_BLACKOUT_OVERLAP"
    RENTAL_RATE_NOT_FOUND = "FACILITY_RENTAL_RATE_NOT_FOUND"
    RENTAL_RATE_EXISTS = "FACILITY_RENTAL_RATE_EXISTS"
    RENTAL_RATE_TEMPLATE_NOT_FOUND = "FACILITY_RENTAL_RATE_TEMPLATE_NOT_FOUND"
    RENTAL_RATE_TEMPLATE_NAME_EXISTS = "FACILITY_RENTAL_RATE_TEMPLATE_NAME_EXISTS"
    RENTAL_RATE_TEMPLATE_IN_USE = "FACILITY_RENTAL_RATE_TEMPLATE_IN_USE"
    BOOKING_NOT_FOUND = "FACILITY_BOOKING_NOT_FOUND"
    BOOKING_INVALID_TIME_RANGE = "FACILITY_BOOKING_INVALID_TIME_RANGE"
    BOOKING_ROOMS_REQUIRED = "FACILITY_BOOKING_ROOMS_REQUIRED"
    BOOKING_MAX_ROOMS = "FACILITY_BOOKING_MAX_ROOMS"
    BOOKING_MINISTRY_INACTIVE = "FACILITY_BOOKING_MINISTRY_INACTIVE"
    BOOKING_RANGE_WINDOW_TOO_LARGE = "FACILITY_BOOKING_RANGE_WINDOW_TOO_LARGE"
    BOOKING_LINE_CROSS_MIDNIGHT = "FACILITY_BOOKING_LINE_CROSS_MIDNIGHT"
    BOOKING_LINES_NOT_SAME_DAY = "FACILITY_BOOKING_LINES_NOT_SAME_DAY"
    BOOKING_DUPLICATE_LINE = "FACILITY_BOOKING_DUPLICATE_LINE"
