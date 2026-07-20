"""
Map between content file API serializers and application commands/results.
"""
from fastapi import UploadFile

from portal.application.content.commands import (
    BulkDeleteFilesCommand,
    FilePagesQueryCommand,
    UploadFileCommand,
)
from portal.application.content.results import (
    BatchUploadFilesResult,
    BulkDeleteFilesResult,
    FileBaseResult,
    FileCategoryStatsResult,
    FileGridItemResult,
    FilePageResult,
    FileSummaryResult,
    UploadFileResult,
)
from portal.domain.content.constants import FileUploadSource
from portal.serializers.admin.v1.file import (
    AdminBatchFileUploadResponseModel,
    AdminBulkActionResponseModel,
    AdminFailedUploadFile,
    AdminFileBase,
    AdminFileBulkAction,
    AdminFileCategoryStats,
    AdminFileGridItem,
    AdminFilePages,
    AdminFileQuery,
    AdminFileSummary,
    AdminFileUploadResponseModel,
)
from portal.serializers.mixins.model_mixins import UUIDBaseModel


async def upload_file_to_command(
    upload_file: UploadFile,
    upload_source: FileUploadSource = FileUploadSource.ADMIN,
) -> UploadFileCommand:
    content = await upload_file.read()
    return UploadFileCommand(
        filename=upload_file.filename or "unknown_file",
        content=content,
        content_type=upload_file.content_type,
        upload_source=upload_source,
    )


async def upload_files_to_commands(
    upload_files: list[UploadFile],
    upload_source: FileUploadSource = FileUploadSource.ADMIN,
) -> list[UploadFileCommand]:
    commands: list[UploadFileCommand] = []
    for upload_file in upload_files:
        commands.append(await upload_file_to_command(upload_file, upload_source=upload_source))
    return commands


def pages_query_to_command(model: AdminFileQuery) -> FilePagesQueryCommand:
    return FilePagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        keyword=model.keyword,
        media_category=model.media_category,
    )


def bulk_action_to_command(model: AdminFileBulkAction) -> BulkDeleteFilesCommand:
    return BulkDeleteFilesCommand(ids=model.ids)


def file_base_result_to_api(result: FileBaseResult) -> AdminFileBase:
    return AdminFileBase(
        id=result.id,
        original_name=result.original_name,
        key=result.key,
        storage=result.storage,
        bucket=result.bucket,
        region=result.region,
        content_type=result.content_type,
        extension=result.extension,
        size_bytes=result.size_bytes,
    )


def file_grid_item_to_api(result: FileGridItemResult) -> AdminFileGridItem:
    return AdminFileGridItem(
        id=result.id,
        original_name=result.original_name,
        key=result.key,
        storage=result.storage,
        bucket=result.bucket,
        region=result.region,
        content_type=result.content_type,
        extension=result.extension,
        size_bytes=result.size_bytes,
        url=result.url,
        created_at=result.created_at,
    )


def file_category_stats_to_api(result: FileCategoryStatsResult) -> AdminFileCategoryStats:
    return AdminFileCategoryStats(
        count=result.count,
        size_bytes=result.size_bytes,
    )


def file_summary_result_to_api(result: FileSummaryResult) -> AdminFileSummary:
    return AdminFileSummary(
        images=file_category_stats_to_api(result.images),
        files=file_category_stats_to_api(result.files),
        total=file_category_stats_to_api(result.total),
    )


def file_page_result_to_api(result: FilePageResult) -> AdminFilePages:
    return AdminFilePages(
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        items=[file_grid_item_to_api(item) for item in result.items],
    )


def upload_file_result_to_api(result: UploadFileResult) -> AdminFileUploadResponseModel:
    return AdminFileUploadResponseModel(id=result.id, duplicate=result.duplicate)


def batch_upload_result_to_api(result: BatchUploadFilesResult) -> AdminBatchFileUploadResponseModel:
    return AdminBatchFileUploadResponseModel(
        uploaded_files=[UUIDBaseModel(id=item.id) for item in result.uploaded_files],
        failed_files=[
            AdminFailedUploadFile(filename=item.filename, error=item.error)
            for item in result.failed_files
        ],
    )


def bulk_delete_result_to_api(result: BulkDeleteFilesResult) -> AdminBulkActionResponseModel:
    failed_items = None
    if result.failed_items:
        failed_items = [file_base_result_to_api(item) for item in result.failed_items]
    return AdminBulkActionResponseModel(
        success_count=result.success_count,
        failed_items=failed_items,
    )
