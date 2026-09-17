"""
Bilingual Priority Ministry override email subjects and template helpers.
"""

from datetime import date
from uuid import UUID

from portal.application.facility.results import RoomDetailResult
from portal.application.org.results import TranslationItemResult

EN_LOCALE_ID = UUID("019dd0c8-69fa-7657-87bb-3b7255f5c5ae")
ZH_TW_LOCALE_ID = UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a")
ZH_CN_LOCALE_ID = UUID("019dd0c8-7c12-727f-878f-16807adf39e8")

OVERRIDE_SUBJECT = "Church Activity Booking override / 教會活動預訂覆寫"
TEMPLATE_BOOKING_OVERRIDE = "email/facility/booking_override.html"
EXPIRY_SUBJECT = "Pending-payment Booking expired / 待付款預訂已逾期"
TEMPLATE_BOOKING_PAYMENT_HOLD_EXPIRED = "email/facility/booking_payment_hold_expired.html"


def resolve_bilingual_activity_names(translations: list[TranslationItemResult], fallback_name: str | None) -> tuple[str, str]:
    by_locale = {item.locale_id: item.name for item in translations if item.name}
    fallback = (fallback_name or "Church Activity").strip()
    english_name = by_locale.get(EN_LOCALE_ID) or fallback
    chinese_name = by_locale.get(ZH_TW_LOCALE_ID) or by_locale.get(ZH_CN_LOCALE_ID) or english_name
    return english_name, chinese_name


def format_override_date_en(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def format_override_date_zh(value: date) -> str:
    return f"{value.year}年{value.month}月{value.day}日"


def room_name_for_locale(room: RoomDetailResult | None, locale_id: UUID, fallback: str) -> str:
    if room is None:
        return fallback
    translations: list[TranslationItemResult] = room.translations or []
    for item in translations:
        if item.locale_id == locale_id and item.name:
            return item.name
    return room.name or room.code or fallback


def dedupe_emails(emails: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for email in emails:
        normalized = (email or "").strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
