"""
FileService unit tests with stub ports.
"""
from uuid import uuid4

import pytest
from azure.core.exceptions import AzureError

from portal.application.content.commands import (
    BulkDeleteFilesCommand,
    FilePagesQueryCommand,
    UpdateFileAssociationCommand,
    UploadFileCommand,
)
from portal.application.content.file_service import FileService
from portal.application.content.results import (
    FileBaseResult,
    FileDetailResult,
    FileGridItemResult,
)
from portal.domain.content.constants import FileStatus, FileUploadSource
from portal.exceptions.responses import ApiBaseException, BadRequestException


class StubFileRepository:
    def __init__(self):
        self.files: dict = {}
        self.associations: dict = {}
        self.insert_calls: list = []
        self.status_updates: list = []
        self.deleted_keys: list = []

    async def fetch_pages(self, command):
        items = [
            FileGridItemResult(
                id=f.id,
                original_name=f.original_name,
                key=f.key,
                storage=f.storage,
                bucket=f.bucket,
                region=f.region,
                content_type=f.content_type,
                extension=f.extension,
                size_bytes=f.size_bytes,
            )
            for f in self.files.values()
            if f.status != FileStatus.DELETED
        ]
        return items, len(items)

    async def fetch_summary(self):
        from portal.application.content.results import FileCategoryStatsResult, FileSummaryResult

        items = [f for f in self.files.values() if f.status != FileStatus.DELETED]
        images = [f for f in items if f.content_type and f.content_type.startswith("image/")]
        files = [f for f in items if not f.content_type or not f.content_type.startswith("image/")]
        images_stats = FileCategoryStatsResult(
            count=len(images),
            size_bytes=sum(f.size_bytes or 0 for f in images),
        )
        files_stats = FileCategoryStatsResult(
            count=len(files),
            size_bytes=sum(f.size_bytes or 0 for f in files),
        )
        return FileSummaryResult(
            images=images_stats,
            files=files_stats,
            total=FileCategoryStatsResult(
                count=images_stats.count + files_stats.count,
                size_bytes=images_stats.size_bytes + files_stats.size_bytes,
            ),
        )

    async def get_by_id(self, file_id):
        return self.files.get(file_id)

    async def get_by_sha256(self, checksum_sha256):
        for item in self.files.values():
            if item.checksum_sha256 == checksum_sha256 and item.status != FileStatus.DELETED:
                return item
        return None

    async def get_by_md5_size_content_type(self, checksum_md5, size_bytes, content_type):
        for item in self.files.values():
            if (
                item.checksum_md5 == checksum_md5
                and item.size_bytes == size_bytes
                and item.content_type == content_type
                and item.status != FileStatus.DELETED
            ):
                return item
        return None

    async def insert_file(self, payload):
        self.insert_calls.append(payload)
        detail = FileDetailResult(
            id=payload["id"],
            original_name=payload["original_name"],
            key=payload["key"],
            storage=payload["storage"],
            bucket=payload["bucket"],
            region=payload["region"],
            content_type=payload.get("content_type"),
            extension=payload.get("extension"),
            size_bytes=payload.get("size_bytes"),
            checksum_md5=payload.get("checksum_md5"),
            checksum_sha256=payload.get("checksum_sha256"),
            width=payload.get("width"),
            height=payload.get("height"),
            status=payload.get("status"),
            version=1,
            is_public=payload.get("is_public"),
            source=payload.get("source"),
        )
        self.files[payload["id"]] = detail

    async def update_status(self, file_id, status):
        self.status_updates.append((file_id, status))
        if file_id in self.files:
            self.files[file_id].status = status
        return 1

    async def mark_deleted_by_keys(self, keys):
        self.deleted_keys.extend(keys)
        count = 0
        for item in self.files.values():
            if item.key in keys:
                item.status = FileStatus.DELETED
                count += 1
        return count

    async def list_by_ids(self, file_ids):
        return [
            FileBaseResult(
                id=f.id,
                original_name=f.original_name,
                key=f.key,
                storage=f.storage,
                bucket=f.bucket,
                region=f.region,
                content_type=f.content_type,
                extension=f.extension,
                size_bytes=f.size_bytes,
            )
            for fid, f in self.files.items()
            if fid in file_ids
        ]

    async def replace_associations(self, resource_id, resource_name, file_ids):
        self.associations[resource_id] = list(file_ids)

    async def fetch_by_resource_id(self, resource_id):
        file_ids = self.associations.get(resource_id, [])
        return [
            FileGridItemResult(
                id=f.id,
                original_name=f.original_name,
                key=f.key,
                storage=f.storage,
                bucket=f.bucket,
                region=f.region,
                content_type=f.content_type,
                extension=f.extension,
                size_bytes=f.size_bytes,
            )
            for fid, f in self.files.items()
            if fid in file_ids and f.status != FileStatus.DELETED
        ]

    async def fetch_associations_by_resource_ids(self, resource_ids):
        return []


class StubFileStorage:
    def __init__(self, fail_put: bool = False, delete_success: bool = True):
        self.fail_put = fail_put
        self.delete_success = delete_success
        self.put_calls: list = []
        self.delete_calls: list = []

    @property
    def storage_name(self) -> str:
        return "azure_blob"

    @property
    def bucket(self) -> str:
        return "files"

    @property
    def region(self) -> str:
        return "eastus"

    @property
    def blob_prefix(self) -> str:
        return "original_files/dev"

    async def put_object(self, *, key, body, content_type, metadata, cache_control=None):
        self.put_calls.append({"key": key, "body": body, "content_type": content_type})
        if self.fail_put:
            raise AzureError("upload failed")

    async def delete_objects(self, keys):
        self.delete_calls.append(keys)
        if self.delete_success:
            return list(keys)
        return []

    async def generate_signed_read_url(self, *, key, bucket=None, expiry_seconds=3600):
        return f"https://example.blob.core.windows.net/{bucket or self.bucket}/{key}?sas=1"


class StubFileCache:
    def __init__(self):
        self.signed_urls: dict = {}
        self.invalidated_urls: list = []
        self.invalidated_associations: list = []

    async def get_signed_url(self, file_id):
        return self.signed_urls.get(file_id)

    async def set_signed_url(self, file_id, url, expiry_seconds):
        self.signed_urls[file_id] = url

    async def invalidate_signed_url(self, file_id):
        self.invalidated_urls.append(file_id)

    async def invalidate_resource_association(self, resource_id):
        self.invalidated_associations.append(resource_id)


class StubRbacAuditService:
    def __init__(self):
        self.logs: list = []

    def create_log(self, *args, **kwargs):
        self.logs.append((args, kwargs))


def _make_service(repo=None, storage=None, cache=None, audit=None):
    return FileService(
        file_repository=repo or StubFileRepository(),
        file_storage=storage or StubFileStorage(),
        file_cache=cache or StubFileCache(),
        rbac_audit_service=audit or StubRbacAuditService(),
    )


def _png_bytes():
    # Minimal valid 1x1 PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.mark.asyncio
async def test_upload_file_success():
    repo = StubFileRepository()
    storage = StubFileStorage()
    audit = StubRbacAuditService()
    service = _make_service(repo=repo, storage=storage, audit=audit)

    result = await service.upload_file(
        UploadFileCommand(
            filename="photo.png",
            content=_png_bytes(),
            content_type="image/png",
            upload_source=FileUploadSource.ADMIN,
        )
    )

    assert result.duplicate is None
    assert len(storage.put_calls) == 1
    assert len(repo.insert_calls) == 1
    assert any(status == FileStatus.UPLOADED for _, status in repo.status_updates)
    assert len(audit.logs) == 1


@pytest.mark.asyncio
async def test_upload_file_duplicate_returns_existing():
    repo = StubFileRepository()
    existing_id = uuid4()
    content = _png_bytes()
    import hashlib

    sha = hashlib.sha256(content).hexdigest()
    repo.files[existing_id] = FileDetailResult(
        id=existing_id,
        original_name="old.png",
        key="original_files/dev/old.png",
        storage="azure_blob",
        bucket="files",
        region="eastus",
        content_type="image/png",
        size_bytes=len(content),
        checksum_sha256=sha,
        status=FileStatus.UPLOADED,
    )
    storage = StubFileStorage()
    service = _make_service(repo=repo, storage=storage)

    result = await service.upload_file(
        UploadFileCommand(
            filename="photo.png",
            content=content,
            content_type="image/png",
        )
    )

    assert result.id == existing_id
    assert result.duplicate is True
    assert storage.put_calls == []


@pytest.mark.asyncio
async def test_upload_file_storage_failure_leaves_uploading():
    repo = StubFileRepository()
    storage = StubFileStorage(fail_put=True)
    service = _make_service(repo=repo, storage=storage)

    with pytest.raises(ApiBaseException) as exc_info:
        await service.upload_file(
            UploadFileCommand(
                filename="photo.png",
                content=_png_bytes(),
                content_type="image/png",
            )
        )

    assert exc_info.value.status_code == 503
    assert len(repo.insert_calls) == 1
    assert not any(status == FileStatus.UPLOADED for _, status in repo.status_updates)


@pytest.mark.asyncio
async def test_delete_files_success():
    repo = StubFileRepository()
    file_id = uuid4()
    repo.files[file_id] = FileDetailResult(
        id=file_id,
        original_name="a.png",
        key="original_files/dev/a.png",
        storage="azure_blob",
        bucket="files",
        region="eastus",
        status=FileStatus.UPLOADED,
    )
    storage = StubFileStorage()
    cache = StubFileCache()
    service = _make_service(repo=repo, storage=storage, cache=cache)

    result = await service.delete_files(BulkDeleteFilesCommand(ids=[file_id]))

    assert result.success_count == 1
    assert file_id in cache.invalidated_urls
    assert repo.files[file_id].status == FileStatus.DELETED


@pytest.mark.asyncio
async def test_delete_files_empty_raises():
    service = _make_service()
    with pytest.raises(BadRequestException, match="No files"):
        await service.delete_files(BulkDeleteFilesCommand(ids=[uuid4()]))


@pytest.mark.asyncio
async def test_get_file_pages_attaches_signed_urls():
    repo = StubFileRepository()
    file_id = uuid4()
    repo.files[file_id] = FileDetailResult(
        id=file_id,
        original_name="a.png",
        key="original_files/dev/a.png",
        storage="azure_blob",
        bucket="files",
        region="eastus",
        status=FileStatus.UPLOADED,
    )
    service = _make_service(repo=repo)

    result = await service.get_file_pages(FilePagesQueryCommand())

    assert result.total == 1
    assert result.items[0].url is not None
    assert "sas=1" in result.items[0].url


@pytest.mark.asyncio
async def test_update_file_association_replaces_and_invalidates_cache():
    repo = StubFileRepository()
    cache = StubFileCache()
    service = _make_service(repo=repo, cache=cache)
    resource_id = uuid4()
    file_id = uuid4()

    await service.update_file_association(
        UpdateFileAssociationCommand(
            file_ids=[file_id],
            resource_id=resource_id,
            resource_name="room",
        )
    )

    assert repo.associations[resource_id] == [file_id]
    assert resource_id in cache.invalidated_associations
