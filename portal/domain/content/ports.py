"""
Content domain ports.
"""
from typing import Any, Optional, Protocol
from uuid import UUID

from portal.application.content.commands import FilePagesQueryCommand
from portal.application.content.results import (
    FileBaseResult,
    FileDetailResult,
    FileGridItemResult,
    FileSummaryResult,
    SignedUrlFileByResourceResult,
)


class FileRepositoryPort(Protocol):
    """Persist and query file metadata and associations."""

    async def fetch_pages(
        self,
        command: FilePagesQueryCommand,
    ) -> tuple[list[FileGridItemResult], int]:
        ...

    async def fetch_summary(self) -> FileSummaryResult:
        ...

    async def get_by_id(self, file_id: UUID) -> Optional[FileDetailResult]:
        ...

    async def get_by_sha256(self, checksum_sha256: str) -> Optional[FileDetailResult]:
        ...

    async def get_by_md5_size_content_type(
        self,
        checksum_md5: str,
        size_bytes: int,
        content_type: str,
    ) -> Optional[FileDetailResult]:
        ...

    async def insert_file(self, payload: dict[str, Any]) -> None:
        ...

    async def update_status(self, file_id: UUID, status: int) -> int:
        ...

    async def mark_deleted_by_keys(self, keys: list[str]) -> int:
        ...

    async def list_by_ids(self, file_ids: list[UUID]) -> list[FileBaseResult]:
        ...

    async def replace_associations(
        self,
        resource_id: UUID,
        resource_name: Optional[str],
        file_ids: list[UUID],
    ) -> None:
        ...

    async def fetch_by_resource_id(self, resource_id: UUID) -> list[FileGridItemResult]:
        ...

    async def fetch_associations_by_resource_ids(
        self,
        resource_ids: list[UUID],
    ) -> list[SignedUrlFileByResourceResult]:
        ...


class FileStoragePort(Protocol):
    """Object storage backend for file blobs."""

    @property
    def storage_name(self) -> str:
        ...

    @property
    def bucket(self) -> str:
        ...

    @property
    def region(self) -> str:
        ...

    @property
    def blob_prefix(self) -> str:
        ...

    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
        cache_control: Optional[str] = None,
    ) -> None:
        ...

    async def delete_objects(self, keys: list[str]) -> list[str]:
        """
        Delete objects by key. Returns keys that were successfully deleted.
        """
        ...

    async def generate_signed_read_url(
        self,
        *,
        key: str,
        bucket: Optional[str] = None,
        expiry_seconds: int = 3600,
    ) -> str:
        ...


class FileCachePort(Protocol):
    """Redis cache for signed URLs and association invalidation."""

    async def get_signed_url(self, file_id: UUID) -> Optional[str]:
        ...

    async def set_signed_url(self, file_id: UUID, url: str, expiry_seconds: int) -> None:
        ...

    async def invalidate_signed_url(self, file_id: UUID) -> None:
        ...

    async def invalidate_resource_association(self, resource_id: UUID) -> None:
        ...
