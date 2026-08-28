"""
Tests for ministry application bilingual mail content helpers.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from portal.application.org.ministry_application_mail_content import (
    EN_LOCALE_ID,
    ZH_CN_LOCALE_ID,
    ZH_TW_LOCALE_ID,
    build_application_summary_context,
    format_submitted_at_toronto,
    format_target_audience_names,
    resolve_bilingual_ministry_names,
    resolve_catalog_display_name,
    resolve_ministry_type_names_for_mail,
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


def test_resolve_catalog_display_name_prefers_name_then_code():
    assert resolve_catalog_display_name("Sports", "sports") == "Sports"
    assert resolve_catalog_display_name(None, "sports") == "sports"
    assert resolve_catalog_display_name(None, None) == "—"


def test_format_target_audience_names_joins_locale_labels():
    audiences = [TargetAudienceResult(id=uuid4(), code="all_ages", name="All ages"), TargetAudienceResult(id=uuid4(), code="youth", name="Youth")]
    assert format_target_audience_names(audiences) == "All ages, Youth"
    assert format_target_audience_names([]) == "—"


def test_build_application_summary_context_includes_bilingual_catalog_fields():
    applicant_user_id = uuid4()
    ministry = MinistryDetailResult(
        id=uuid4(),
        name="Badminton",
        status=MinistryStatus.PENDING_APPROVAL.value,
        submitted_at=datetime(2026, 1, 15, 18, 30, tzinfo=timezone.utc),
        has_priority_booking=False,
        is_active=True,
        members=[
            MinistryMemberResult(user_id=applicant_user_id, member_role=MinistryMemberRole.PRIMARY.value, display_name="Primary Steward"),
            MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.SECONDARY.value, display_name="Secondary"),
        ],
    )
    summary = build_application_summary_context(
        ministry=ministry,
        applicant_display_name="Jane Applicant",
        ministry_type_name_en="Sports",
        ministry_type_name_zh="運動事工",
        target_audience_names_en="All ages",
        target_audience_names_zh="全年龄",
    )
    assert summary.ministry_type_name_en == "Sports"
    assert summary.ministry_type_name_zh == "運動事工"
    assert summary.applicant_display_name == "Jane Applicant"
    assert summary.target_audience_names_en == "All ages"
    assert summary.target_audience_names_zh == "全年龄"
    assert summary.primary_steward_display_name == "Primary Steward"
    assert "2026-01-15" in summary.submitted_at_display


class StubMinistryTypeNameLookup:
    def __init__(self, names_by_type_locale: dict[tuple[object, object], str]):
        self.names_by_type_locale = names_by_type_locale

    async def get_translated_name_by_id(self, ministry_type_id, locale_id):
        return self.names_by_type_locale.get((ministry_type_id, locale_id))


@pytest.mark.asyncio
async def test_resolve_ministry_type_names_for_mail_prefers_zh_tw_then_zh_cn():
    ministry_type_id = uuid4()
    lookup = StubMinistryTypeNameLookup({(ministry_type_id, EN_LOCALE_ID): "Sports", (ministry_type_id, ZH_CN_LOCALE_ID): "运动事工"})
    english_name, chinese_name = await resolve_ministry_type_names_for_mail(lookup, ministry_type_id=ministry_type_id, code_fallback="sports")
    assert english_name == "Sports"
    assert chinese_name == "运动事工"
