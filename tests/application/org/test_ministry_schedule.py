"""
Ministry schedule validation tests.
"""
from datetime import time

import pytest

from portal.application.org.commands import MinistryScheduleCommand
from portal.application.org.ministry_schedule import validate_ministry_schedules
from portal.exceptions.responses import BadRequestException


def test_validate_schedule_requires_start_and_end_together():
    with pytest.raises(BadRequestException):
        validate_ministry_schedules(
            [
                MinistryScheduleCommand(
                    days_of_week=[0],
                    start_time=time(9, 0),
                )
            ]
        )
