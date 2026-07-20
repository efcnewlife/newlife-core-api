"""
Content file application service.
"""
import asyncio
import base64
import hashlib
import io
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from asyncpg import UniqueViolationError
from azure.core.exceptions import AzureError
from fastapi import status
from PIL import Image

from portal.application.content.commands import (
    BulkDeleteFilesCommand,
    FilePagesQueryCommand,
    UpdateFileAssociationCommand,
    UploadFileCommand,
)
from portal.application.content.results import (
    BatchUploadFilesResult,
    BulkDeleteFilesResult,
    FailedUploadFileResult,
    FileBaseResult,
    FileDetailResult,
    FileGridItemResult,
    FilePageResult,
    FileSummaryResult,
    UploadFileResult,
)
from portal.config import settings
from portal.domain.common.mixins import UUIDBaseModel
from portal.domain.content.constants import CONTENT_FILE_TABLE, FileStatus
from portal.domain.content.ports import FileCachePort, FileRepositoryPort, FileStoragePort
from portal.domain.rbac.ports import RbacAuditPort
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException
from portal.libs.consts.enums import OperationType
from portal.libs.tracing.distributed_trace import distributed_trace


class FileService:
    """Admin content file use cases."""

    def __init__(
        self,
        file_repository: FileRepositoryPort,
        file_storage: FileStoragePort,
        file_cache: FileCachePort,
        rbac_audit_service: RbacAuditPort,
    ):
        self._repository = file_repository
        self._storage = file_storage
        self._cache = file_cache
        self._audit = rbac_audit_service

    @distributed_trace()
    async def get_file_pages(self, command: FilePagesQueryCommand) -> FilePageResult:
        items, count = await self._repository.fetch_pages(command)
        urls = await asyncio.gather(*[self.get_signed_url(file=item) for item in items])
        for item, url in zip(items, urls):
            item.url = url
        return FilePageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    @distributed_trace()
    async def get_file_summary(self) -> FileSummaryResult:
        return await self._repository.fetch_summary()

    @distributed_trace()
    async def upload_file(self, command: UploadFileCommand) -> UploadFileResult:
        try:
            file_content = command.content
            original_filename = command.filename or "unknown_file"
            content_type = command.content_type
            if not content_type:
                content_type, _ = mimetypes.guess_type(original_filename)
                if not content_type:
                    content_type = "application/octet-stream"

            file_size = len(file_content)
            if file_size > settings.MAX_UPLOAD_SIZE:
                raise BadRequestException(detail="File exceeds maximum upload size")

            width, height = None, None
            if content_type.startswith("image/"):
                try:
                    with Image.open(io.BytesIO(file_content)) as img:
                        width, height = img.size
                except Exception:
                    pass

            if command.check_duplicates:
                existing = await self._check_duplicate(
                    file_content=file_content,
                    content_type=content_type,
                    file_size=file_size,
                )
                if existing:
                    return UploadFileResult(id=existing.id, duplicate=True)

            md5_hash = hashlib.md5(file_content).hexdigest()
            sha256_hash = hashlib.sha256(file_content).hexdigest()
            file_id = uuid.uuid4()
            file_extension = Path(original_filename).suffix.lower()
            unique_filename = f"{file_id}{file_extension}"
            blob_key = os.path.join(self._storage.blob_prefix, unique_filename)

            file_data = {
                "id": file_id,
                "original_name": original_filename,
                "key": blob_key,
                "storage": self._storage.storage_name,
                "bucket": self._storage.bucket,
                "region": self._storage.region,
                "content_type": content_type,
                "extension": file_extension.lstrip("."),
                "size_bytes": file_size,
                "checksum_md5": md5_hash,
                "checksum_sha256": sha256_hash,
                "width": width,
                "height": height,
                "status": FileStatus.UPLOADING,
                "is_public": command.is_public,
                "source": command.upload_source,
            }
            await self._repository.insert_file(file_data)

            await self._storage.put_object(
                key=blob_key,
                body=file_content,
                content_type=content_type,
                metadata={
                    "original_name": base64.b64encode(original_filename.encode("utf-8")).decode("ascii"),
                    "original_name_encoding": "base64",
                    "file_id": file_id.hex,
                    "upload_source": str(command.upload_source.value),
                },
                cache_control=settings.AZURE_BLOB_CACHE_CONTROL,
            )
            await self._repository.update_status(file_id, FileStatus.UPLOADED)
        except AzureError as exc:
            raise ApiBaseException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Azure Blob Storage service unavailable",
                debug_detail=str(exc),
            ) from exc
        except UniqueViolationError as exc:
            raise ConflictErrorException(
                detail="File already exists",
                debug_detail=str(exc),
            ) from exc
        except BadRequestException:
            raise
        except ApiBaseException:
            raise
        except Exception as exc:
            raise ApiBaseException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File upload failed",
                debug_detail=str(exc),
            ) from exc
        else:
            self._audit.create_log(
                OperationType.CREATE,
                record_id=file_id,
                operation_code=CONTENT_FILE_TABLE,
                new_data={
                    "id": str(file_id),
                    "original_name": original_filename,
                    "content_type": content_type,
                    "size_bytes": file_size,
                    "source": command.upload_source.value,
                    "is_public": command.is_public,
                },
            )
            return UploadFileResult(id=file_id)

    @distributed_trace()
    async def upload_multiple_files(
        self,
        commands: list[UploadFileCommand],
    ) -> BatchUploadFilesResult:
        uploaded_files: list[UUIDBaseModel] = []
        failed_files: list[FailedUploadFileResult] = []
        for command in commands:
            try:
                result = await self.upload_file(command)
                uploaded_files.append(UUIDBaseModel(id=result.id))
            except Exception as exc:
                failed_files.append(
                    FailedUploadFileResult(
                        filename=command.filename or "unknown_file",
                        error=str(exc),
                    )
                )
        return BatchUploadFilesResult(
            uploaded_files=uploaded_files,
            failed_files=failed_files,
        )

    @distributed_trace()
    async def delete_files(self, command: BulkDeleteFilesCommand) -> BulkDeleteFilesResult:
        files = await self._repository.list_by_ids(command.ids)
        if not files:
            raise BadRequestException(detail="No files to delete")

        file_key_mapping = {file.key: file for file in files}
        keys = [file.key for file in files]
        try:
            success_keys = await self._storage.delete_objects(keys)
        except AzureError as exc:
            raise ApiBaseException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Azure Blob Storage service unavailable",
                debug_detail=str(exc),
            ) from exc

        failed_items = [
            file_key_mapping[key]
            for key in keys
            if key not in success_keys and key in file_key_mapping
        ]
        if success_keys:
            await self._repository.mark_deleted_by_keys(success_keys)
            for key in success_keys:
                file_item = file_key_mapping.get(key)
                if file_item:
                    await self._cache.invalidate_signed_url(file_item.id)
            self._audit.create_log(
                OperationType.DELETE,
                operation_code=CONTENT_FILE_TABLE,
                old_data={"file_keys": success_keys},
                new_data={"status": FileStatus.DELETED.value},
            )
        return BulkDeleteFilesResult(
            success_count=len(success_keys),
            failed_items=failed_items or None,
        )

    @distributed_trace()
    async def update_file_association(self, command: UpdateFileAssociationCommand) -> None:
        try:
            await self._repository.replace_associations(
                resource_id=command.resource_id,
                resource_name=command.resource_name,
                file_ids=command.file_ids,
            )
        finally:
            await self._cache.invalidate_resource_association(command.resource_id)

    @distributed_trace()
    async def get_files_by_resource_id(self, resource_id: UUID) -> list[FileGridItemResult]:
        files = await self._repository.fetch_by_resource_id(resource_id)
        urls = await asyncio.gather(*[self.get_signed_url(file=item) for item in files])
        for item, url in zip(files, urls):
            item.url = url
        return files

    @distributed_trace()
    async def get_signed_urls_by_resource_ids(
        self,
        resource_ids: list[UUID],
    ) -> dict[UUID, list[str]]:
        unique_ids = list(set(resource_ids))
        if not unique_ids:
            return {}
        rows = await self._repository.fetch_associations_by_resource_ids(unique_ids)
        url_by_resource: dict[UUID, list[str]] = {}
        for row in rows:
            signed_url = await self.get_signed_url(file=row)
            if not signed_url:
                continue
            url_by_resource.setdefault(row.resource_id, []).append(signed_url)
        return url_by_resource

    @distributed_trace()
    async def get_signed_url(
        self,
        file_id: Optional[UUID] = None,
        file: Optional[FileBaseResult] = None,
        expiration: Optional[int] = None,
    ) -> Optional[str]:
        expiry = expiration if expiration is not None else settings.SIGNED_URL_EXPIRY_SECONDS
        if file is None:
            if file_id is None:
                return None
            file = await self._repository.get_by_id(file_id)
        if file is None:
            return None

        cached = await self._cache.get_signed_url(file.id)
        if cached:
            return cached

        url = await self._storage.generate_signed_read_url(
            key=file.key,
            bucket=file.bucket,
            expiry_seconds=expiry,
        )
        await self._cache.set_signed_url(file.id, url, expiry)
        return url

    async def _check_duplicate(
        self,
        file_content: bytes,
        content_type: str,
        file_size: int,
    ) -> Optional[FileDetailResult]:
        sha256_hash = hashlib.sha256(file_content).hexdigest()
        existing = await self._repository.get_by_sha256(sha256_hash)
        if existing:
            return existing
        md5_hash = hashlib.md5(file_content).hexdigest()
        return await self._repository.get_by_md5_size_content_type(
            checksum_md5=md5_hash,
            size_bytes=file_size,
            content_type=content_type,
        )
