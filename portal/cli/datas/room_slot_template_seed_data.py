"""
Default Room Slot Template (opening hours) seed rows, church-confirmed.
Applied per seeded room only when the room has no Room Slot Template yet.
"""

from datetime import time
from typing import Any

from portal.domain.facility.constants import DayOfWeek

default_room_slot_template_seed_rows: list[dict[str, Any]] = [
    {
        "name": "Default opening hours (Mon-Sat)",
        "days": [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY],
        "start_time": time(8, 0),
        "end_time": time(22, 0),
        "slot_duration_minutes": 60,
    },
    {"name": "Default opening hours (Sun)", "days": [DayOfWeek.SUNDAY], "start_time": time(14, 0), "end_time": time(22, 0), "slot_duration_minutes": 60},
]
