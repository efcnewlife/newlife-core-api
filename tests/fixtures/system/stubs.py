"""
System setting test stubs.
"""

from zoneinfo import ZoneInfo


class StubSettingService:
    """Minimal SettingService stub for facility consumers."""

    def __init__(
        self,
        timezone_name: str = "America/Toronto",
        max_booking_lines: int = 3,
        availability_amount: int = 4,
        availability_unit: str = "weeks",
        min_recurring_booking_weeks: int = 4,
        pending_payment_hold_hours: int = 72,
    ):
        self._timezone_name = timezone_name
        self._max_booking_lines = max_booking_lines
        self._availability_amount = availability_amount
        self._availability_unit = availability_unit
        self._min_recurring_booking_weeks = min_recurring_booking_weeks
        self._pending_payment_hold_hours = pending_payment_hold_hours

    async def get_facility_timezone(self) -> ZoneInfo:
        return ZoneInfo(self._timezone_name)

    async def get_max_booking_lines(self) -> int:
        return self._max_booking_lines

    async def get_recurring_booking_availability_window(self):
        from portal.application.system.results import RecurringBookingAvailabilityWindowResult

        return RecurringBookingAvailabilityWindowResult(amount=self._availability_amount, unit=self._availability_unit)

    async def get_min_recurring_booking_weeks(self) -> int:
        return self._min_recurring_booking_weeks

    async def get_pending_payment_hold_hours(self) -> int:
        return self._pending_payment_hold_hours
