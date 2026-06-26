"""
Bitmask helpers for ISO weekday selection (Monday=0 through Sunday=6).
"""
from portal.domain.facility.constants import DayOfWeek

VALID_DAY_MASK = (1 << 7) - 1  # bits 0-6


def day_to_bit(day: int) -> int:
    """Return the bitmask bit for a single ISO weekday (0-6)."""
    if day < DayOfWeek.MONDAY or day > DayOfWeek.SUNDAY:
        raise ValueError(f"day must be between {DayOfWeek.MONDAY} and {DayOfWeek.SUNDAY}, got {day}")
    return 1 << day


def days_to_mask(days: list[int]) -> int:
    """Encode unique ISO weekdays (0-6) into a bitmask. At least one day required."""
    if not days:
        raise ValueError("days must contain at least one weekday")
    unique_days = sorted(set(days))
    mask = 0
    for day in unique_days:
        mask |= day_to_bit(day)
    return mask


def mask_to_days(mask: int) -> list[int]:
    """Decode a bitmask into sorted ISO weekday integers (0-6)."""
    if mask <= 0 or (mask & ~VALID_DAY_MASK) != 0:
        raise ValueError(f"invalid days_of_week_mask: {mask}")
    return [day for day in range(DayOfWeek.MONDAY, DayOfWeek.SUNDAY + 1) if mask & day_to_bit(day)]


def masks_share_day(left: int, right: int) -> bool:
    """Return True when two masks share at least one weekday."""
    return (left & right) != 0
