"""
Scheduled Mock Ministry inventory for `seed-mock-users`.

Ten display-density Ministries reuse the established scenario labels and weekly
schedules. Readable names receive the shared Mock run identity at seed time.
"""

from dataclasses import dataclass
from datetime import date, time
from typing import Optional

from portal.domain.facility.constants import DayOfWeek

MOCK_MINISTRY_COUNT = 10
REQUIRED_STEWARD_COUNT = 3


def ministry_purpose(label: str) -> str:
    """Return the inventory purpose for one scheduled Mock Ministry label."""
    return f"Ministry list display: {label}"


@dataclass(frozen=True)
class MockMinistrySchedule:
    """One weekly or seasonal schedule attached to a Mock Ministry."""

    days_of_week: tuple[int, ...]
    start_time: Optional[time]
    end_time: Optional[time]
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


@dataclass(frozen=True)
class MockMinistryPlan:
    """One scheduled Mock Ministry before identities are minted."""

    label: str
    purpose: str
    schedule: MockMinistrySchedule


def build_mock_ministry_plans(*, year: int) -> list[MockMinistryPlan]:
    """Return the ten scheduled Mock Ministry plans for a generation year."""
    summer_from = date(year, 6, 1)
    summer_to = date(year, 8, 31)
    school_year_from = date(year, 9, 1)
    school_year_to = date(year + 1, 5, 31)
    alpha_from = date(year, 9, 1)
    alpha_to = date(year, 9, 30)
    return [
        MockMinistryPlan(label="Alpha", purpose=ministry_purpose("Alpha"), schedule=MockMinistrySchedule((), None, None, alpha_from, alpha_to)),
        MockMinistryPlan(
            label="Badminton", purpose=ministry_purpose("Badminton"), schedule=MockMinistrySchedule((DayOfWeek.SUNDAY,), time(13, 30), time(16, 30))
        ),
        MockMinistryPlan(
            label="Basketball", purpose=ministry_purpose("Basketball"), schedule=MockMinistrySchedule((DayOfWeek.SATURDAY,), time(14, 0), time(18, 0))
        ),
        MockMinistryPlan(
            label="Chinese School",
            purpose=ministry_purpose("Chinese School"),
            schedule=MockMinistrySchedule((DayOfWeek.SATURDAY,), time(14, 0), time(16, 0), school_year_from, school_year_to),
        ),
        MockMinistryPlan(
            label="Pickleball",
            purpose=ministry_purpose("Pickleball"),
            schedule=MockMinistrySchedule((DayOfWeek.TUESDAY, DayOfWeek.THURSDAY, DayOfWeek.SATURDAY), time(9, 30), time(12, 0)),
        ),
        MockMinistryPlan(
            label="Softball",
            purpose=ministry_purpose("Softball"),
            schedule=MockMinistrySchedule((DayOfWeek.SATURDAY, DayOfWeek.SUNDAY), time(15, 0), time(18, 0), summer_from, summer_to),
        ),
        MockMinistryPlan(
            label="Stretching",
            purpose=ministry_purpose("Stretching"),
            schedule=MockMinistrySchedule((DayOfWeek.THURSDAY,), time(20, 30), time(21, 30), school_year_from, school_year_to),
        ),
        MockMinistryPlan(
            label="Supporting SOSO Ministry",
            purpose=ministry_purpose("Supporting SOSO Ministry"),
            schedule=MockMinistrySchedule((DayOfWeek.MONDAY,), time(10, 0), time(15, 0)),
        ),
        MockMinistryPlan(label="Choir", purpose=ministry_purpose("Choir"), schedule=MockMinistrySchedule((DayOfWeek.SUNDAY,), time(9, 0), time(10, 30))),
        MockMinistryPlan(label="Prayer", purpose=ministry_purpose("Prayer"), schedule=MockMinistrySchedule((DayOfWeek.WEDNESDAY,), time(19, 30), time(21, 0))),
    ]


def ministry_display_name(*, label: str, run_identity: str) -> str:
    """Return the readable Mock Ministry label that carries the run identity."""
    return f"Mock {label} ({run_identity})"


def secondary_steward_emails_for_index(index: int, steward_emails: list[str], *, ministry_count: int = MOCK_MINISTRY_COUNT) -> list[str]:
    """Primary is steward 0; remaining stewards are secondaries, with the third on the first half."""
    if len(steward_emails) < REQUIRED_STEWARD_COUNT:
        raise ValueError("Mock Ministry inventory requires three steward Testing accounts.")
    secondaries = [steward_emails[1]]
    first_half_end = ministry_count // 2
    if index < first_half_end:
        secondaries.append(steward_emails[2])
    return secondaries
