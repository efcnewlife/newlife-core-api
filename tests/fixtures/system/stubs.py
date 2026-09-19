"""
System setting test stubs.
"""

from zoneinfo import ZoneInfo

from portal.application.system.results import RecurringBookingAvailabilityWindowResult, RecurringBookingTestBookerAllowlistResult


class StubSettingService:
    """Minimal SettingService stub for facility consumers."""

    def __init__(
        self,
        timezone_name: str = "America/Toronto",
        max_booking_lines: int = 3,
        availability_amount: int = 4,
        availability_unit: str = "weeks",
        min_recurring_booking_weeks: int = 4,
        pending_payment_hold_days: int = 3,
        test_window_override: bool = False,
        test_booker_email_addresses: list[str] | None = None,
        test_booker_email_suffixes: list[str] | None = None,
    ):
        self._timezone_name = timezone_name
        self._max_booking_lines = max_booking_lines
        self._availability_amount = availability_amount
        self._availability_unit = availability_unit
        self._min_recurring_booking_weeks = min_recurring_booking_weeks
        self._pending_payment_hold_days = pending_payment_hold_days
        self._test_window_override = test_window_override
        self._test_booker_email_addresses = test_booker_email_addresses or []
        self._test_booker_email_suffixes = test_booker_email_suffixes or []

    async def get_facility_timezone(self) -> ZoneInfo:
        return ZoneInfo(self._timezone_name)

    async def get_max_booking_lines(self) -> int:
        return self._max_booking_lines

    async def get_recurring_booking_availability_window(self):
        return RecurringBookingAvailabilityWindowResult(amount=self._availability_amount, unit=self._availability_unit)

    async def get_min_recurring_booking_weeks(self) -> int:
        return self._min_recurring_booking_weeks

    async def get_pending_payment_hold_days(self) -> int:
        return self._pending_payment_hold_days

    async def get_recurring_booking_test_window_override(self) -> bool:
        return self._test_window_override

    async def get_recurring_booking_test_booker_allowlist(self):
        return RecurringBookingTestBookerAllowlistResult(email_addresses=self._test_booker_email_addresses, email_suffixes=self._test_booker_email_suffixes)
