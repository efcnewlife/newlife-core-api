"""
Demo ministry seed data.

Every localized name carries the ``seed: Demo `` prefix so the seed command can
replace only demo ministries and leave admin-created ministries untouched.

Ministry Type and target audience are referenced by stable catalog code, not by
localized name. Alpha 2026 is an Annual Ministry: one record per year with the
year in the name. Weekly programs that pause for a season keep a single ministry
and bound the weekly pattern with a Seasonal schedule instead.
"""

from datetime import date, time
from typing import Any, Optional

from portal.domain.facility.constants import DayOfWeek
from portal.domain.org.catalog_codes import (
    MINISTRY_TYPE_INTERNAL,
    MINISTRY_TYPE_OUTREACH,
    MINISTRY_TYPE_WORSHIP,
    TARGET_AUDIENCE_ADULTS,
    TARGET_AUDIENCE_ALL_AGES,
    TARGET_AUDIENCE_CHILDREN,
    TARGET_AUDIENCE_FAMILY,
    TARGET_AUDIENCE_YOUTHS,
)

SEED_NAME_PREFIX = "seed: Demo "
SEED_LOCALE_CODES = ("en", "zh-TW", "zh-CN")

DEMO_PRIMARY_USER_EMAIL = "seed.ministry.primary@local.test"
DEMO_SECONDARY_USER_EMAIL = "seed.ministry.secondary@local.test"
DEMO_SECONDARY_2_USER_EMAIL = "seed.ministry.secondary2@local.test"

demo_ministry_user_seed_rows: list[dict[str, Any]] = [
    {"email": DEMO_PRIMARY_USER_EMAIL, "first_name": "Seed", "last_name": "Primary"},
    {"email": DEMO_SECONDARY_USER_EMAIL, "first_name": "Seed", "last_name": "Secondary"},
    {"email": DEMO_SECONDARY_2_USER_EMAIL, "first_name": "Seed", "last_name": "Secondary Two"},
]


def secondary_steward_emails_for_ministry_index(index: int, *, total: int) -> list[str]:
    """
    First half of the ordered ministry list gets two secondaries; the rest get one.

    Shares the same steward emails across all demo ministries.
    """
    if total <= 0:
        raise ValueError("total must be positive")
    if index < 0 or index >= total:
        raise ValueError(f"index {index} out of range for total {total}")
    if index < total // 2:
        return [DEMO_SECONDARY_USER_EMAIL, DEMO_SECONDARY_2_USER_EMAIL]
    return [DEMO_SECONDARY_USER_EMAIL]


# Demo calendar year is 2026.
SUMMER_FROM = date(2026, 6, 1)
SUMMER_TO = date(2026, 8, 31)
SCHOOL_YEAR_FROM = date(2026, 9, 1)
SCHOOL_YEAR_TO = date(2027, 5, 31)
ALPHA_FROM = date(2026, 9, 1)
ALPHA_TO = date(2026, 9, 30)


def _schedule(
    *,
    days_of_week: Optional[list[int]] = None,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None,
    effective_from: Optional[date] = None,
    effective_to: Optional[date] = None,
) -> dict[str, Any]:
    """Build one schedule row. Empty start/end times mean the time is TBA."""
    return {
        "days_of_week": list(days_of_week or []),
        "start_time": start_time,
        "end_time": end_time,
        "effective_from": effective_from,
        "effective_to": effective_to,
    }


def _translation(name: str, schedule_note: Optional[str] = None) -> dict[str, Any]:
    """Build one localized row, prefixing the name so demo rows stay recognizable."""
    return {"name": f"{SEED_NAME_PREFIX}{name}", "schedule_note": schedule_note}


def _ministry(
    *,
    ministry_type_code: str,
    target_audience_codes: list[str],
    translations: dict[str, dict[str, Any]],
    schedules: list[dict[str, Any]],
    has_priority_booking: bool = False,
) -> dict[str, Any]:
    return {
        "ministry_type_code": ministry_type_code,
        "target_audience_codes": list(target_audience_codes),
        "has_priority_booking": has_priority_booking,
        "translations": translations,
        "schedules": schedules,
    }


ministry_seed_rows: list[dict[str, Any]] = [
    _ministry(
        ministry_type_code=MINISTRY_TYPE_OUTREACH,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS],
        has_priority_booking=True,
        translations={"en": _translation("Alpha 2026", "Sept"), "zh-TW": _translation("啟發 2026", "九月"), "zh-CN": _translation("启发 2026", "九月")},
        schedules=[_schedule(effective_from=ALPHA_FROM, effective_to=ALPHA_TO)],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS],
        has_priority_booking=True,
        translations={"en": _translation("Badminton"), "zh-TW": _translation("羽毛球"), "zh-CN": _translation("羽毛球")},
        schedules=[_schedule(days_of_week=[DayOfWeek.SUNDAY], start_time=time(13, 30), end_time=time(16, 30))],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_CHILDREN, TARGET_AUDIENCE_YOUTHS],
        translations={"en": _translation("Basketball"), "zh-TW": _translation("籃球"), "zh-CN": _translation("篮球")},
        schedules=[_schedule(days_of_week=[DayOfWeek.SATURDAY], start_time=time(14, 0), end_time=time(18, 0))],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_CHILDREN, TARGET_AUDIENCE_ADULTS],
        translations={
            "en": _translation("Chinese School", "Adults: conversation class only"),
            "zh-TW": _translation("中文學校", "成人僅會話班"),
            "zh-CN": _translation("中文学校", "成人仅会话班"),
        },
        schedules=[
            _schedule(
                days_of_week=[DayOfWeek.SATURDAY], start_time=time(14, 0), end_time=time(16, 0), effective_from=SCHOOL_YEAR_FROM, effective_to=SCHOOL_YEAR_TO
            )
        ],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS],
        translations={"en": _translation("Pickleball"), "zh-TW": _translation("皮克球"), "zh-CN": _translation("皮克球")},
        schedules=[_schedule(days_of_week=[DayOfWeek.TUESDAY, DayOfWeek.THURSDAY, DayOfWeek.SATURDAY], start_time=time(9, 30), end_time=time(12, 0))],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_ALL_AGES],
        translations={"en": _translation("Softball"), "zh-TW": _translation("壘球"), "zh-CN": _translation("垒球")},
        schedules=[
            _schedule(
                days_of_week=[DayOfWeek.SATURDAY, DayOfWeek.SUNDAY],
                start_time=time(15, 0),
                end_time=time(18, 0),
                effective_from=SUMMER_FROM,
                effective_to=SUMMER_TO,
            )
        ],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS],
        translations={"en": _translation("Stretching"), "zh-TW": _translation("拉筋班"), "zh-CN": _translation("拉筋班")},
        schedules=[
            _schedule(
                days_of_week=[DayOfWeek.THURSDAY], start_time=time(20, 30), end_time=time(21, 30), effective_from=SCHOOL_YEAR_FROM, effective_to=SCHOOL_YEAR_TO
            )
        ],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_OUTREACH,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS, TARGET_AUDIENCE_FAMILY],
        translations={
            "en": _translation("Supporting SOSO Ministry", "Or special occasion"),
            "zh-TW": _translation("支援 SOSO 事工", "或特殊節日"),
            "zh-CN": _translation("支援 SOSO 事工", "或特殊节日"),
        },
        schedules=[_schedule(days_of_week=[DayOfWeek.MONDAY], start_time=time(10, 0), end_time=time(15, 0))],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_WORSHIP,
        target_audience_codes=[TARGET_AUDIENCE_ALL_AGES],
        translations={"en": _translation("Choir"), "zh-TW": _translation("詩班"), "zh-CN": _translation("诗班")},
        schedules=[_schedule(days_of_week=[DayOfWeek.SUNDAY], start_time=time(9, 0), end_time=time(10, 30))],
    ),
    _ministry(
        ministry_type_code=MINISTRY_TYPE_INTERNAL,
        target_audience_codes=[TARGET_AUDIENCE_ADULTS],
        translations={"en": _translation("Prayer"), "zh-TW": _translation("禱告"), "zh-CN": _translation("祷告")},
        schedules=[_schedule(days_of_week=[DayOfWeek.WEDNESDAY], start_time=time(19, 30), end_time=time(21, 0))],
    ),
]
