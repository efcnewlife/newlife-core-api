"""
System setting test stubs.
"""

from zoneinfo import ZoneInfo


class StubSettingService:
    """Minimal SettingService stub for facility consumers."""

    def __init__(self, timezone_name: str = "America/Toronto", max_booking_lines: int = 3):
        self._timezone_name = timezone_name
        self._max_booking_lines = max_booking_lines

    async def get_facility_timezone(self) -> ZoneInfo:
        return ZoneInfo(self._timezone_name)

    async def get_max_booking_lines(self) -> int:
        return self._max_booking_lines
