"""
Legal Document seed rows (built-in Product x Kind catalog).
"""

from portal.domain.content.constants import LegalDocumentKind, ProductCode

seed_legal_documents: list[dict] = [
    {"product": ProductCode.FACILITY_BOOKING.value, "kind": LegalDocumentKind.TERMS_OF_SERVICE.value},
    {"product": ProductCode.FACILITY_BOOKING.value, "kind": LegalDocumentKind.PRIVACY_POLICY.value},
    {"product": ProductCode.PORTAL.value, "kind": LegalDocumentKind.TERMS_OF_SERVICE.value},
    {"product": ProductCode.PORTAL.value, "kind": LegalDocumentKind.PRIVACY_POLICY.value},
]
