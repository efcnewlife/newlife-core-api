"""
Ministry schedule validation helpers.
"""
from portal.application.org.commands import MinistryScheduleCommand
from portal.domain.facility.days_of_week_mask import days_to_mask
from portal.exceptions.responses import BadRequestException


def encode_schedule_days_mask(days_of_week: list[int]) -> int | None:
    if not days_of_week:
        return None
    return days_to_mask(days_of_week)


def is_schedule_time_tba(schedule: MinistryScheduleCommand) -> bool:
    """Empty start/end times mean time is to be announced."""
    return schedule.start_time is None and schedule.end_time is None


def validate_ministry_schedules(schedules: list[MinistryScheduleCommand]) -> None:
    for index, schedule in enumerate(schedules):
        prefix = f"schedules[{index}]"
        if not schedule.days_of_week and not schedule.effective_from:
            raise BadRequestException(detail=f"{prefix}: days_of_week or effective_from is required")
        if bool(schedule.start_time) != bool(schedule.end_time):
            raise BadRequestException(detail=f"{prefix}: start_time and end_time must both be set or both be empty")
        if schedule.start_time and schedule.end_time and schedule.start_time >= schedule.end_time:
            raise BadRequestException(detail=f"{prefix}: start_time must be before end_time")
        if (
            schedule.effective_from
            and schedule.effective_to
            and schedule.effective_from > schedule.effective_to
        ):
            raise BadRequestException(detail=f"{prefix}: effective_from must be on or before effective_to")


def build_schedule_payloads(schedules: list[MinistryScheduleCommand]) -> list[dict]:
    rows = []
    for index, schedule in enumerate(schedules):
        days_of_week_mask = encode_schedule_days_mask(schedule.days_of_week)
        rows.append(
            dict(
                days_of_week_mask=days_of_week_mask,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                effective_from=schedule.effective_from,
                effective_to=schedule.effective_to,
                sequence=schedule.sequence if schedule.sequence is not None else float(index),
            )
        )
    return rows
