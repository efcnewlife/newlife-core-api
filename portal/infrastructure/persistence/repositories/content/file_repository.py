"""
Content file repository.
"""
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.content.commands import FilePagesQueryCommand
from portal.application.content.results import (
    FileBaseResult,
    FileCategoryStatsResult,
    FileDetailResult,
    FileGridItemResult,
    FileSummaryResult,
    SignedUrlFileByResourceResult,
)
from portal.domain.content.constants import FileStatus, MediaCategory
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import ContentFile, ContentFileAssociation


class FileRepository:
    """SQLAlchemy-backed content file repository."""

    def __init__(self, session: Session):
        self._session = session

    def _base_select(self):
        return self._session.select(
            ContentFile.id,
            ContentFile.original_name,
            ContentFile.key,
            ContentFile.storage,
            ContentFile.bucket,
            ContentFile.region,
            ContentFile.content_type,
            ContentFile.extension,
            ContentFile.size_bytes,
            ContentFile.created_at,
        )

    def _detail_select(self):
        return self._session.select(
            ContentFile.id,
            ContentFile.original_name,
            ContentFile.key,
            ContentFile.storage,
            ContentFile.bucket,
            ContentFile.region,
            ContentFile.content_type,
            ContentFile.extension,
            ContentFile.size_bytes,
            ContentFile.checksum_md5,
            ContentFile.checksum_sha256,
            ContentFile.width,
            ContentFile.height,
            ContentFile.duration_seconds,
            ContentFile.status,
            ContentFile.version,
            ContentFile.is_public,
            ContentFile.source,
        )

    async def fetch_pages(
        self,
        command: FilePagesQueryCommand,
    ) -> tuple[list[FileGridItemResult], int]:
        items, count = await (
            self._base_select()
            .select_from(ContentFile)
            .where(ContentFile.status != FileStatus.DELETED)
            .where(
                command.keyword is not None,
                lambda: ContentFile.original_name.ilike(f"%{command.keyword}%"),
            )
            .where(
                command.media_category == MediaCategory.IMAGES,
                lambda: ContentFile.content_type.ilike("image/%"),
            )
            .where(
                command.media_category == MediaCategory.FILES,
                lambda: sa.or_(
                    ContentFile.content_type.is_(None),
                    ~ContentFile.content_type.ilike("image/%"),
                ),
            )
            .order_by_with(
                tables=[ContentFile],
                order_by=command.order_by,
                descending=command.descending,
            )
            .limit(command.page_size)
            .offset(command.page * command.page_size)
            .fetchpages(no_order_by=False, as_model=FileGridItemResult)
        )
        return items, count

    async def fetch_summary(self) -> FileSummaryResult:
        count_col = sa.func.count(ContentFile.id).label("count")
        size_col = sa.func.coalesce(sa.func.sum(ContentFile.size_bytes), 0).label("size_bytes")

        images_row = await (
            self._session.select(count_col, size_col)
            .select_from(ContentFile)
            .where(ContentFile.status != FileStatus.DELETED)
            .where(ContentFile.content_type.ilike("image/%"))
            .fetchrow()
        )
        files_row = await (
            self._session.select(count_col, size_col)
            .select_from(ContentFile)
            .where(ContentFile.status != FileStatus.DELETED)
            .where(
                sa.or_(
                    ContentFile.content_type.is_(None),
                    ~ContentFile.content_type.ilike("image/%"),
                )
            )
            .fetchrow()
        )
        images = FileCategoryStatsResult(
            count=int((images_row or {}).get("count") or 0),
            size_bytes=int((images_row or {}).get("size_bytes") or 0),
        )
        files = FileCategoryStatsResult(
            count=int((files_row or {}).get("count") or 0),
            size_bytes=int((files_row or {}).get("size_bytes") or 0),
        )
        return FileSummaryResult(
            images=images,
            files=files,
            total=FileCategoryStatsResult(
                count=images.count + files.count,
                size_bytes=images.size_bytes + files.size_bytes,
            ),
        )

    async def get_by_id(self, file_id: UUID) -> Optional[FileDetailResult]:
        return await (
            self._detail_select()
            .where(ContentFile.id == file_id)
            .where(ContentFile.status != FileStatus.DELETED)
            .fetchrow(as_model=FileDetailResult)
        )

    async def get_by_sha256(self, checksum_sha256: str) -> Optional[FileDetailResult]:
        return await (
            self._detail_select()
            .where(ContentFile.checksum_sha256 == checksum_sha256)
            .where(ContentFile.status != FileStatus.DELETED)
            .fetchrow(as_model=FileDetailResult)
        )

    async def get_by_md5_size_content_type(
        self,
        checksum_md5: str,
        size_bytes: int,
        content_type: str,
    ) -> Optional[FileDetailResult]:
        return await (
            self._detail_select()
            .where(ContentFile.checksum_md5 == checksum_md5)
            .where(ContentFile.size_bytes == size_bytes)
            .where(ContentFile.content_type == content_type)
            .where(ContentFile.status != FileStatus.DELETED)
            .fetchrow(as_model=FileDetailResult)
        )

    async def insert_file(self, payload: dict[str, Any]) -> None:
        await (
            self._session.insert(ContentFile)
            .values(payload)
            .on_conflict_do_nothing(index_elements=["bucket", "key"])
            .execute()
        )

    async def update_status(self, file_id: UUID, status: int) -> int:
        result = await (
            self._session.update(ContentFile)
            .values(status=status)
            .where(ContentFile.id == file_id)
            .execute()
        )
        return affected_rows(result)

    async def mark_deleted_by_keys(self, keys: list[str]) -> int:
        if not keys:
            return 0
        result = await (
            self._session.update(ContentFile)
            .values(status=FileStatus.DELETED)
            .where(ContentFile.key.in_(keys))
            .execute()
        )
        return affected_rows(result)

    async def list_by_ids(self, file_ids: list[UUID]) -> list[FileBaseResult]:
        if not file_ids:
            return []
        return await (
            self._base_select()
            .where(ContentFile.id.in_(file_ids))
            .fetch(as_model=FileBaseResult)
        ) or []

    async def replace_associations(
        self,
        resource_id: UUID,
        resource_name: Optional[str],
        file_ids: list[UUID],
    ) -> None:
        await (
            self._session.delete(ContentFileAssociation)
            .where(ContentFileAssociation.resource_id == resource_id)
            .execute()
        )
        if not file_ids:
            return
        rows = [
            {
                "file_id": file_id,
                "resource_id": resource_id,
                "resource_name": resource_name or "",
            }
            for file_id in file_ids
        ]
        await self._session.insert(ContentFileAssociation).values(rows).execute()

    async def fetch_by_resource_id(self, resource_id: UUID) -> list[FileGridItemResult]:
        items = await (
            self._base_select()
            .select_from(ContentFile)
            .join(
                ContentFileAssociation,
                ContentFileAssociation.file_id == ContentFile.id,
            )
            .where(ContentFileAssociation.resource_id == resource_id)
            .where(ContentFile.status != FileStatus.DELETED)
            .order_by(ContentFileAssociation.sequence.asc())
            .fetch(as_model=FileGridItemResult)
        )
        return items or []

    async def fetch_associations_by_resource_ids(
        self,
        resource_ids: list[UUID],
    ) -> list[SignedUrlFileByResourceResult]:
        if not resource_ids:
            return []
        items = await (
            self._session.select(
                ContentFileAssociation.resource_id,
                ContentFile.id,
                ContentFile.original_name,
                ContentFile.key,
                ContentFile.storage,
                ContentFile.bucket,
                ContentFile.region,
                ContentFile.content_type,
                ContentFile.extension,
                ContentFile.size_bytes,
            )
            .select_from(ContentFile)
            .join(
                ContentFileAssociation,
                ContentFileAssociation.file_id == ContentFile.id,
            )
            .where(ContentFileAssociation.resource_id.in_(resource_ids))
            .where(ContentFile.status != FileStatus.DELETED)
            .order_by(ContentFileAssociation.sequence.asc())
            .fetch(as_model=SignedUrlFileByResourceResult)
        )
        return items or []
