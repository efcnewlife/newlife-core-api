"""
Content application results (snake_case, no API serialization aliases).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.common.mixins import UUIDBaseModel
from portal.domain.content.constants import FileStatus, FileUploadSource


class FileBaseResult(UUIDBaseModel):
    """Core file metadata."""

    original_name: str = Field(...)
    key: str = Field(...)
    storage: str = Field(...)
    bucket: str = Field(...)
    region: str = Field(...)
    content_type: Optional[str] = Field(default=None)
    extension: Optional[str] = Field(default=None)
    size_bytes: Optional[int] = Field(default=None)


class FileDetailResult(FileBaseResult):
    """Full file metadata."""

    checksum_md5: Optional[str] = Field(default=None)
    checksum_sha256: Optional[str] = Field(default=None)
    width: Optional[int] = Field(default=None)
    height: Optional[int] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)
    status: Optional[FileStatus] = Field(default=None)
    version: Optional[int] = Field(default=None)
    is_public: Optional[bool] = Field(default=None)
    source: Optional[FileUploadSource] = Field(default=None)


class FileGridItemResult(FileBaseResult):
    """File list item with optional signed URL."""

    url: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)


class FileCategoryStatsResult(BaseModel):
    """Aggregate count and size for a media category."""

    count: int = Field(default=0)
    size_bytes: int = Field(default=0)


class FileSummaryResult(BaseModel):
    """Storage summary for images, files, and total."""

    images: FileCategoryStatsResult = Field(default_factory=FileCategoryStatsResult)
    files: FileCategoryStatsResult = Field(default_factory=FileCategoryStatsResult)
    total: FileCategoryStatsResult = Field(default_factory=FileCategoryStatsResult)


class FilePageResult(BaseModel):
    """Paginated file list."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[FileGridItemResult] = Field(default_factory=list)


class UploadFileResult(UUIDBaseModel):
    """Single upload response."""

    duplicate: Optional[bool] = Field(default=None)


class FailedUploadFileResult(BaseModel):
    """Failed batch upload entry."""

    filename: str = Field(...)
    error: str = Field(...)


class BatchUploadFilesResult(BaseModel):
    """Batch upload response."""

    uploaded_files: list[UUIDBaseModel] = Field(default_factory=list)
    failed_files: list[FailedUploadFileResult] = Field(default_factory=list)


class BulkDeleteFilesResult(BaseModel):
    """Bulk delete response."""

    success_count: int = Field(...)
    failed_items: Optional[list[FileBaseResult]] = Field(default=None)


class SignedUrlFileByResourceResult(FileBaseResult):
    """File row joined with resource association."""

    resource_id: UUID = Field(...)
