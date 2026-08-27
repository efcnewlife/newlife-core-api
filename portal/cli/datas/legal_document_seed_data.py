"""
Legal Document seed rows (built-in Product x Kind catalog).
"""

from datetime import date

from portal.domain.content.constants import LegalDocumentKind, ProductCode

# Fixed seed Effective Date for new installs; humans backfill existing rows via Alembic.
_SEED_EFFECTIVE_DATE = date(2026, 1, 1)

seed_legal_documents: list[dict] = [
    {"product": ProductCode.FACILITY_BOOKING.value, "kind": LegalDocumentKind.TERMS_OF_SERVICE.value, "effective_date": _SEED_EFFECTIVE_DATE},
    {"product": ProductCode.FACILITY_BOOKING.value, "kind": LegalDocumentKind.PRIVACY_POLICY.value, "effective_date": _SEED_EFFECTIVE_DATE},
    {"product": ProductCode.PORTAL.value, "kind": LegalDocumentKind.TERMS_OF_SERVICE.value, "effective_date": _SEED_EFFECTIVE_DATE},
    {"product": ProductCode.PORTAL.value, "kind": LegalDocumentKind.PRIVACY_POLICY.value, "effective_date": _SEED_EFFECTIVE_DATE},
]
