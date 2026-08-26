"""
Content domain constants and enums.
"""

from enum import IntEnum, StrEnum

CONTENT_FILE_TABLE = "file"
CONTENT_LEGAL_DOCUMENT_TABLE = "legal_document"
FILE_RESOURCE_KIND_FACILITY_ROOM = "facility.room"


class MediaCategory(StrEnum):
    """File list category filter."""

    IMAGES = "images"
    FILES = "files"


class FileStatus(IntEnum):
    """File upload / processing status."""

    UPLOADING = 0
    UPLOADED = 1
    PROCESSING = 2
    PROCESSED = 3
    FAILED = 4
    DELETED = 5


class FileUploadSource(IntEnum):
    """Where the file was uploaded from."""

    ADMIN = 0
    APP = 1


class ProductCode(StrEnum):
    """Built-in Product codes that own Legal Documents."""

    FACILITY_BOOKING = "facility-booking"
    PORTAL = "portal"


class LegalDocumentKind(StrEnum):
    """Legal Document Kind (identity with Product, not display title)."""

    TERMS_OF_SERVICE = "terms_of_service"
    PRIVACY_POLICY = "privacy_policy"


class ContentErrorCode(StrEnum):
    """Machine-readable content admin error codes for clients."""

    LEGAL_DOCUMENT_NOT_FOUND = "CONTENT_LEGAL_DOCUMENT_NOT_FOUND"
