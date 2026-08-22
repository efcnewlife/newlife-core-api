"""
Content domain constants and enums.
"""

from enum import IntEnum, StrEnum

CONTENT_FILE_TABLE = "file"
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
