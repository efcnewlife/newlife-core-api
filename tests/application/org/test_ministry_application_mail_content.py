"""
Tests for ministry application bilingual mail content helpers.
"""

from datetime import datetime, timezone
from uuid import uuid4

from portal.application.org.ministry_application_mail_content import (
    EN_LOCALE_ID,
    ZH_TW_LOCALE_ID,
    build_application_summary_context,
    format_submitted_at_toronto,
    resolve_bilingual_ministry_names,
)
from portal.application.org.results import MinistryDetailResult, MinistryMemberResult, MinistryTypeResult, TargetAudienceResult, TranslationItemResult
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus


def test_resolve_bilingual_ministry_names_uses_locale_translations():
    en_name = "Youth Ministry"
    zh_name = "青年事工"
    translations = [TranslationItemResult(locale_id=EN_LOCALE_ID, name=en_name), TranslationItemResult(locale_id=ZH_TW_LOCALE_ID, name=zh_name)]
    english_name, chinese_name = resolve_bilingual_ministry_names(translations, fallback_name="Fallback")
    assert english_name == en_name
    assert chinese_name == zh_name


def test_format_submitted_at_toronto_converts_utc_to_toronto():
    submitted_at = datetime(2026, 1, 15, 18, 30, tzinfo=timezone.utc)
    display = format_submitted_at_toronto(submitted_at)
    assert "2026-01-15" in display
    assert "EST" in display or "EDT" in display


def test_build_application_summary_context_includes_key_fields():
    applicant_user_id = uuid4()
    ministry = MinistryDetailResult(
        id=uuid4(),
        name="Badminton",
        status=MinistryStatus.PENDING_APPROVAL.value,
        ministry_type_name="Sports",
        submitted_at=datetime(2026, 1, 15, 18, 30, tzinfo=timezone.utc),
        has_priority_booking=False,
        is_active=True,
        target_audiences=[TargetAudienceResult(id=uuid4(), code="youth", name="Youth")],
        members=[
            MinistryMemberResult(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY.value, display_name="Primary Steward"),
            MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value, display_name="Secondary"),
        ],
    )
    summary = build_application_summary_context(ministry=ministry, applicant_display_name="Jane Applicant")
    assert summary.ministry_type_name == "Sports"
    assert summary.applicant_display_name == "Jane Applicant"
    assert summary.target_audience_names == "Youth"
    assert summary.primary_steward_display_name == "Primary Steward"
    assert "2026-01-15" in summary.submitted_at_display
