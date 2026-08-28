"""
Bilingual ministry application submit email content (EN block first, then ZH).
"""

from uuid import UUID

from portal.application.org.results import TranslationItemResult

EN_LOCALE_ID = UUID("019dd0c8-69fa-7657-87bb-3b7255f5c5ae")
ZH_TW_LOCALE_ID = UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a")
ZH_CN_LOCALE_ID = UUID("019dd0c8-7c12-727f-878f-16807adf39e8")


def resolve_bilingual_ministry_names(translations: list[TranslationItemResult], fallback_name: str | None) -> tuple[str, str]:
    """Return (english_name, chinese_name) from ministry translations."""
    by_locale = {item.locale_id: item.name for item in translations if item.name}
    fallback = (fallback_name or "Ministry Application").strip()
    english_name = by_locale.get(EN_LOCALE_ID) or fallback
    chinese_name = by_locale.get(ZH_TW_LOCALE_ID) or by_locale.get(ZH_CN_LOCALE_ID) or english_name
    return english_name, chinese_name


def build_applicant_submit_confirmation_html(*, ministry_name_en: str, ministry_name_zh: str, my_ministry_url: str) -> str:
    return f"""<div>
<p>Hello,</p>
<p>Your ministry application for <strong>{_escape_html(ministry_name_en)}</strong> has been submitted and is pending approval.</p>
<p><a href="{_escape_html(my_ministry_url)}">View My Ministry</a></p>
<hr />
<p>您好，</p>
<p>您的事工申請「<strong>{_escape_html(ministry_name_zh)}</strong>」已成功提交，正在等待核准。</p>
<p><a href="{_escape_html(my_ministry_url)}">查看我的事工</a></p>
</div>"""


def build_incumbent_notification_html(*, ministry_name_en: str, ministry_name_zh: str, applicant_display_name: str, approval_detail_url: str) -> str:
    return f"""<div>
<p>Hello,</p>
<p><strong>{_escape_html(applicant_display_name)}</strong> submitted a ministry application for <strong>{_escape_html(ministry_name_en)}</strong>.</p>
<p><a href="{_escape_html(approval_detail_url)}">Review application</a></p>
<hr />
<p>您好，</p>
<p><strong>{_escape_html(applicant_display_name)}</strong> 提交了事工申請「<strong>{_escape_html(ministry_name_zh)}</strong>」。</p>
<p><a href="{_escape_html(approval_detail_url)}">審核申請</a></p>
</div>"""


APPLICANT_SUBMIT_SUBJECT = "Ministry Application Submitted / 事工申請已提交"
INCUMBENT_NOTIFICATION_SUBJECT = "Ministry Application Pending Your Approval / 事工申請待您核准"
APPLICANT_APPROVED_SUBJECT = "Ministry Application Approved / 事工申請已核准"
APPLICANT_REJECTED_SUBJECT = "Ministry Application Declined / 事工申請未通過"


def build_applicant_approved_html(*, ministry_name_en: str, ministry_name_zh: str, my_ministry_url: str) -> str:
    return f"""<div>
<p>Hello,</p>
<p>Your ministry application for <strong>{_escape_html(ministry_name_en)}</strong> has been approved.</p>
<p><a href="{_escape_html(my_ministry_url)}">View My Ministry</a></p>
<hr />
<p>您好，</p>
<p>您的事工申請「<strong>{_escape_html(ministry_name_zh)}</strong>」已獲核准。</p>
<p><a href="{_escape_html(my_ministry_url)}">查看我的事工</a></p>
</div>"""


def build_applicant_rejected_html(*, ministry_name_en: str, ministry_name_zh: str, rejection_reason: str, my_ministry_url: str) -> str:
    return f"""<div>
<p>Hello,</p>
<p>Your ministry application for <strong>{_escape_html(ministry_name_en)}</strong> was not approved.</p>
<p>Reason: {_escape_html(rejection_reason)}</p>
<p><a href="{_escape_html(my_ministry_url)}">View My Ministry</a></p>
<hr />
<p>您好，</p>
<p>您的事工申請「<strong>{_escape_html(ministry_name_zh)}</strong>」未獲核准。</p>
<p>原因：{_escape_html(rejection_reason)}</p>
<p><a href="{_escape_html(my_ministry_url)}">查看我的事工</a></p>
</div>"""


def _escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
