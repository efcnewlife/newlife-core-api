"""
System setting test stubs.
"""
from zoneinfo import ZoneInfo


class StubSettingService:
    """Minimal SettingService stub for facility consumers."""

    def __init__(self, timezone_name: str = "America/Toronto"):
        self._timezone_name = timezone_name

    async def get_facility_timezone(self) -> ZoneInfo:
        return ZoneInfo(self._timezone_name)
