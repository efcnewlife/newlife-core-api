"""
Boundary tests for Legal Document detail translation aggregate coercion.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import ujson

from portal.application.content.results import LegalDocumentDetailResult
from portal.domain.content.constants import LegalDocumentKind, ProductCode


def _raw_detail_row(*, translations: list) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "product": ProductCode.FACILITY_BOOKING.value,
        "kind": LegalDocumentKind.PRIVACY_POLICY.value,
        "effective_date": date(2026, 1, 1),
        "created_at": now,
        "created_by": None,
        "updated_at": now,
        "updated_by": None,
        "is_deleted": False,
        "delete_reason": None,
        "translations": translations,
    }


def test_legal_document_detail_accepts_string_json_translations():
    locale_en = uuid4()
    locale_zh = uuid4()
    raw = _raw_detail_row(
        translations=[ujson.dumps({"locale_id": str(locale_en), "body": "# Privacy Policy"}), ujson.dumps({"locale_id": str(locale_zh), "body": ""})]
    )

    result = LegalDocumentDetailResult.model_validate(raw)

    bodies = {item.locale_id: item.body for item in result.translations}
    assert bodies[locale_en] == "# Privacy Policy"
    assert bodies[locale_zh] == ""


def test_legal_document_detail_accepts_dict_translations():
    locale_en = uuid4()
    raw = _raw_detail_row(translations=[{"locale_id": locale_en, "body": "# Terms"}])

    result = LegalDocumentDetailResult.model_validate(raw)

    assert len(result.translations) == 1
    assert result.translations[0].locale_id == locale_en
    assert result.translations[0].body == "# Terms"


def test_legal_document_detail_empty_translations():
    raw = _raw_detail_row(translations=[])

    result = LegalDocumentDetailResult.model_validate(raw)

    assert result.translations == []
