"""
Tests for ministry application bilingual mail content.
"""

from uuid import uuid4

from portal.application.org.ministry_application_mail_content import (
    EN_LOCALE_ID,
    ZH_TW_LOCALE_ID,
    build_applicant_submit_confirmation_html,
    build_incumbent_notification_html,
    resolve_bilingual_ministry_names,
)
from portal.application.org.results import TranslationItemResult


def test_resolve_bilingual_ministry_names_uses_locale_translations():
    en_name = "Youth Ministry"
    zh_name = "青年事工"
    translations = [TranslationItemResult(locale_id=EN_LOCALE_ID, name=en_name), TranslationItemResult(locale_id=ZH_TW_LOCALE_ID, name=zh_name)]
    english_name, chinese_name = resolve_bilingual_ministry_names(translations, fallback_name="Fallback")
    assert english_name == en_name
    assert chinese_name == zh_name


def test_applicant_submit_confirmation_html_is_bilingual_en_then_zh():
    html = build_applicant_submit_confirmation_html(
        ministry_name_en="Badminton", ministry_name_zh="羽毛球", my_ministry_url="http://localhost:5174/my-ministry"
    )
    assert "Badminton" in html
    assert "羽毛球" in html
    assert html.index("Hello,") < html.index("您好")
    assert "http://localhost:5174/my-ministry" in html


def test_incumbent_notification_html_includes_approval_deep_link():
    ministry_id = uuid4()
    approval_url = f"http://localhost:5174/my-ministry/approvals/{ministry_id}"
    html = build_incumbent_notification_html(
        ministry_name_en="Badminton", ministry_name_zh="羽毛球", applicant_display_name="Jane Applicant", approval_detail_url=approval_url
    )
    assert approval_url in html
    assert "Jane Applicant" in html
    assert html.index("Review application") < html.index("審核申請")
