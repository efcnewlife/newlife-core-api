"""
Bilingual ministry application email subjects and template context helpers.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.org.results import MinistryDetailResult, TranslationItemResult
from portal.domain.org.constants import MinistryMemberRole

EN_LOCALE_ID = UUID("019dd0c8-69fa-7657-87bb-3b7255f5c5ae")
ZH_TW_LOCALE_ID = UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a")
ZH_CN_LOCALE_ID = UUID("019dd0c8-7c12-727f-878f-16807adf39e8")

TORONTO_TZ = ZoneInfo("America/Toronto")

APPLICANT_SUBMIT_SUBJECT = "Ministry Application Submitted / 事工申請已提交"
INCUMBENT_NOTIFICATION_SUBJECT = "Ministry Application Pending Your Approval / 事工申請待您核准"
APPLICANT_APPROVED_SUBJECT = "Ministry Application Approved / 事工申請已核准"
APPLICANT_REJECTED_SUBJECT = "Ministry Application Declined / 事工申請未通過"
INCUMBENT_STAFF_DECISION_SUBJECT = "Ministry Application Decision on Your Behalf / 事工申請代為決定通知"

TEMPLATE_APPLICANT_SUBMIT_CONFIRMATION = "email/ministry/applicant_submit_confirmation.html"
TEMPLATE_INCUMBENT_NOTIFICATION = "email/ministry/incumbent_notification.html"
TEMPLATE_APPLICANT_DECISION_APPROVED = "email/ministry/applicant_decision_approved.html"
TEMPLATE_APPLICANT_DECISION_REJECTED = "email/ministry/applicant_decision_rejected.html"
TEMPLATE_INCUMBENT_STAFF_DECISION_NOTIFICATION = "email/ministry/incumbent_staff_decision_notification.html"


@dataclass(frozen=True)
class ApplicationSummaryContext:
    """Structured application summary for incumbent notification email."""

    ministry_type_name: str
    applicant_display_name: str
    submitted_at_display: str
    target_audience_names: str
    primary_steward_display_name: str


def resolve_bilingual_ministry_names(translations: list[TranslationItemResult], fallback_name: str | None) -> tuple[str, str]:
    """Return (english_name, chinese_name) from ministry translations."""
    by_locale = {item.locale_id: item.name for item in translations if item.name}
    fallback = (fallback_name or "Ministry Application").strip()
    english_name = by_locale.get(EN_LOCALE_ID) or fallback
    chinese_name = by_locale.get(ZH_TW_LOCALE_ID) or by_locale.get(ZH_CN_LOCALE_ID) or english_name
    return english_name, chinese_name


def format_submitted_at_toronto(submitted_at: Optional[datetime]) -> str:
    """Format submitted_at in America/Toronto for email display."""
    if submitted_at is None:
        return "—"
    aware = submitted_at if submitted_at.tzinfo is not None else submitted_at.replace(tzinfo=timezone.utc)
    local = aware.astimezone(TORONTO_TZ)
    return local.strftime("%Y-%m-%d %H:%M %Z")


def build_application_summary_context(*, ministry: MinistryDetailResult, applicant_display_name: str) -> ApplicationSummaryContext:
    """Build application summary block for incumbent notification email."""
    ministry_type_name = ministry.ministry_type_name or ministry.ministry_type_code or "—"
    audience_names = [item.name or item.code for item in ministry.target_audiences if item.name or item.code]
    target_audience_names = ", ".join(audience_names) if audience_names else "—"
    primary_steward = next((member for member in ministry.members if member.member_role == MinistryMemberRole.PRIMARY.value), None)
    primary_steward_display_name = "—"
    if primary_steward:
        primary_steward_display_name = primary_steward.display_name or primary_steward.email or "—"
    return ApplicationSummaryContext(
        ministry_type_name=ministry_type_name,
        applicant_display_name=applicant_display_name,
        submitted_at_display=format_submitted_at_toronto(ministry.submitted_at),
        target_audience_names=target_audience_names,
        primary_steward_display_name=primary_steward_display_name,
    )


async def resolve_user_display_name(user_repository, user_id: Optional[UUID], *, fallback: str = "Applicant") -> str:
    """Resolve a user-facing display name from profile or email."""
    if not user_id:
        return fallback
    profile = await user_repository.get_detail_by_id(user_id)
    if profile and profile.preferred_name:
        return profile.preferred_name
    sensitive = await user_repository.get_sensitive_by_id(user_id)
    if sensitive and sensitive.email:
        return sensitive.email
    return fallback


async def resolve_staff_display_name(user_repository, user_id: UUID) -> str:
    """Resolve staff name for email copy without exposing personal email."""
    profile = await user_repository.get_detail_by_id(user_id)
    if profile and profile.preferred_name:
        return profile.preferred_name
    return "Church staff"
