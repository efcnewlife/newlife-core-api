"""
Map between content file API serializers and application commands/results.
"""

from fastapi import UploadFile

from portal.application.content.commands import (
    BulkDeleteFilesCommand,
    CreateLegalDocumentCommand,
    FilePagesQueryCommand,
    LegalDocumentPagesQueryCommand,
    LegalDocumentTranslationCommand,
    PreviewFileAssociationsCommand,
    UpdateLegalDocumentCommand,
    UploadFileCommand,
)
from portal.application.content.results import (
    BatchUploadFilesResult,
    BulkDeleteFilesResult,
    CreateIdResult,
    FileAssociationBindingResult,
    FileAssociationPreviewResult,
    FileBaseResult,
    FileCategoryStatsResult,
    FileGridItemResult,
    FilePageResult,
    FileSummaryResult,
    LegalDocumentDetailResult,
    LegalDocumentListItemResult,
    LegalDocumentPageResult,
    LegalDocumentPublicResult,
    UploadFileResult,
)
from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.domain.content.constants import FileUploadSource
from portal.serializers.admin.v1.file import (
    AdminBatchFileUploadResponseModel,
    AdminBulkActionResponseModel,
    AdminFailedUploadFile,
    AdminFileAssociationBinding,
    AdminFileAssociationPreview,
    AdminFileBase,
    AdminFileBulkAction,
    AdminFileCategoryStats,
    AdminFileGridItem,
    AdminFilePages,
    AdminFileQuery,
    AdminFileSummary,
    AdminFileUploadResponseModel,
)
from portal.serializers.admin.v1.legal_document import (
    AdminLegalDocumentBulkAction,
    AdminLegalDocumentCreate,
    AdminLegalDocumentDetail,
    AdminLegalDocumentItem,
    AdminLegalDocumentPages,
    AdminLegalDocumentQuery,
    AdminLegalDocumentUpdate,
)
from portal.serializers.apis.v1.legal_document import MemberLegalDocumentPublic
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


async def upload_file_to_command(upload_file: UploadFile, upload_source: FileUploadSource = FileUploadSource.ADMIN) -> UploadFileCommand:
    content = await upload_file.read()
    return UploadFileCommand(
        filename=upload_file.filename or "unknown_file", content=content, content_type=upload_file.content_type, upload_source=upload_source
    )


async def upload_files_to_commands(upload_files: list[UploadFile], upload_source: FileUploadSource = FileUploadSource.ADMIN) -> list[UploadFileCommand]:
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


def preview_associations_to_command(model: AdminFileBulkAction) -> PreviewFileAssociationsCommand:
    return PreviewFileAssociationsCommand(ids=model.ids)


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
    return AdminFileCategoryStats(count=result.count, size_bytes=result.size_bytes)


def file_summary_result_to_api(result: FileSummaryResult) -> AdminFileSummary:
    return AdminFileSummary(
        images=file_category_stats_to_api(result.images), files=file_category_stats_to_api(result.files), total=file_category_stats_to_api(result.total)
    )


def file_page_result_to_api(result: FilePageResult) -> AdminFilePages:
    return AdminFilePages(page=result.page, page_size=result.page_size, total=result.total, items=[file_grid_item_to_api(item) for item in result.items])


def upload_file_result_to_api(result: UploadFileResult) -> AdminFileUploadResponseModel:
    return AdminFileUploadResponseModel(id=result.id, duplicate=result.duplicate)


def batch_upload_result_to_api(result: BatchUploadFilesResult) -> AdminBatchFileUploadResponseModel:
    return AdminBatchFileUploadResponseModel(
        uploaded_files=[UUIDBaseModel(id=item.id) for item in result.uploaded_files],
        failed_files=[AdminFailedUploadFile(filename=item.filename, error=item.error) for item in result.failed_files],
    )


def bulk_delete_result_to_api(result: BulkDeleteFilesResult) -> AdminBulkActionResponseModel:
    failed_items = None
    if result.failed_items:
        failed_items = [file_base_result_to_api(item) for item in result.failed_items]
    return AdminBulkActionResponseModel(success_count=result.success_count, failed_items=failed_items)


def association_binding_to_api(result: FileAssociationBindingResult) -> AdminFileAssociationBinding:
    return AdminFileAssociationBinding(
        file_id=result.file_id,
        resource_kind=result.resource_kind,
        resource_id=result.resource_id,
        display_name=result.display_name,
        is_deleted=result.is_deleted,
    )


def association_preview_to_api(result: FileAssociationPreviewResult) -> AdminFileAssociationPreview:
    return AdminFileAssociationPreview(items=[association_binding_to_api(item) for item in result.items])


def legal_document_pages_query_to_command(model: AdminLegalDocumentQuery) -> LegalDocumentPagesQueryCommand:
    return LegalDocumentPagesQueryCommand(
        page=model.page,
        page_size=model.page_size,
        order_by=model.order_by,
        descending=model.descending,
        deleted=model.deleted,
        product=model.product,
        kind=model.kind,
    )


def update_legal_document_to_command(model: AdminLegalDocumentUpdate) -> UpdateLegalDocumentCommand:
    return UpdateLegalDocumentCommand(
        effective_date=model.effective_date,
        translations=[LegalDocumentTranslationCommand(locale_id=item.locale_id, body=item.body) for item in model.translations],
    )


def create_legal_document_to_command(model: AdminLegalDocumentCreate) -> CreateLegalDocumentCommand:
    return CreateLegalDocumentCommand(product=model.product, kind=model.kind, effective_date=model.effective_date)


def delete_legal_document_to_command(model: DeleteBaseModel) -> DeleteCommand:
    return DeleteCommand(reason=model.reason, permanent=model.permanent)


def legal_document_bulk_action_to_command(model: AdminLegalDocumentBulkAction) -> BulkIdsCommand:
    return BulkIdsCommand(ids=model.ids)


def create_id_result_to_api(result: CreateIdResult) -> UUIDBaseModel:
    return UUIDBaseModel(id=result.id)


def legal_document_item_to_api(result: LegalDocumentListItemResult) -> AdminLegalDocumentItem:
    return AdminLegalDocumentItem.model_validate(result.model_dump())


def legal_document_detail_to_api(result: LegalDocumentDetailResult) -> AdminLegalDocumentDetail:
    return AdminLegalDocumentDetail.model_validate(result.model_dump())


def legal_document_page_result_to_api(result: LegalDocumentPageResult) -> AdminLegalDocumentPages:
    return AdminLegalDocumentPages(
        page=result.page, page_size=result.page_size, total=result.total, items=[legal_document_item_to_api(item) for item in result.items]
    )


def legal_document_public_result_to_api(result: LegalDocumentPublicResult) -> MemberLegalDocumentPublic:
    return MemberLegalDocumentPublic(product=result.product, kind=result.kind, body=result.body, effective_date=result.effective_date)
