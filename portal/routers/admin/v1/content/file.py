"""
Admin content file API routes.
"""
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, UploadFile, status

from portal.application.content.file_service import FileService
from portal.application.content.mappers import (
    batch_upload_result_to_api,
    bulk_action_to_command,
    bulk_delete_result_to_api,
    file_page_result_to_api,
    file_summary_result_to_api,
    pages_query_to_command,
    upload_file_result_to_api,
    upload_file_to_command,
    upload_files_to_commands,
)
from portal.container import Container
from portal.domain.content.constants import FileUploadSource, MediaCategory
from portal.libs.consts.permission import Permission
from portal.libs.depends.file_validation import FileValidation
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.file import (
    AdminBatchFileUploadResponseModel,
    AdminBulkActionResponseModel,
    AdminFileBulkAction,
    AdminFilePages,
    AdminFileQuery,
    AdminFileSummary,
    AdminFileUploadResponseModel,
)

router: AuthRouter = AuthRouter(is_admin=True)

IMAGE_ALLOWED_TYPES = [
    "image/apng",
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/webp",
]

FILE_ALLOWED_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "text/plain",
]

ALLOWED_TYPES_BY_CATEGORY = {
    MediaCategory.IMAGES: IMAGE_ALLOWED_TYPES,
    MediaCategory.FILES: FILE_ALLOWED_TYPES,
}


def _validate_upload_file(file: UploadFile, media_category: MediaCategory) -> UploadFile:
    allowed_types = ALLOWED_TYPES_BY_CATEGORY[media_category]
    return FileValidation(allowed_types=allowed_types)(file)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminFilePages,
    permissions=[Permission.CONTENT_FILE.read],
)
@inject
async def get_file_pages(
    query_model: Annotated[AdminFileQuery, Query()],
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    result = await file_service.get_file_pages(command=pages_query_to_command(query_model))
    return file_page_result_to_api(result)


@router.get(
    path="/summary",
    status_code=status.HTTP_200_OK,
    response_model=AdminFileSummary,
    permissions=[Permission.CONTENT_FILE.read],
)
@inject
async def get_file_summary(
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    result = await file_service.get_file_summary()
    return file_summary_result_to_api(result)


@router.post(
    path="/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminFileUploadResponseModel,
    response_model_exclude_none=True,
    permissions=[Permission.CONTENT_FILE.create],
)
@inject
async def upload_file(
    file: UploadFile,
    media_category: MediaCategory = Query(default=MediaCategory.IMAGES),
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    validated_file = _validate_upload_file(file, media_category)
    command = await upload_file_to_command(validated_file, upload_source=FileUploadSource.ADMIN)
    result = await file_service.upload_file(command)
    return upload_file_result_to_api(result)


@router.post(
    path="/batch_upload",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminBatchFileUploadResponseModel,
    permissions=[Permission.CONTENT_FILE.create],
)
@inject
async def upload_multiple_files(
    files: list[UploadFile],
    media_category: MediaCategory = Query(default=MediaCategory.IMAGES),
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    validated_files = [_validate_upload_file(file, media_category) for file in files]
    commands = await upload_files_to_commands(validated_files, upload_source=FileUploadSource.ADMIN)
    result = await file_service.upload_multiple_files(commands)
    return batch_upload_result_to_api(result)


@router.delete(
    path="/bulk",
    status_code=status.HTTP_200_OK,
    description="For deleting files",
    response_model=AdminBulkActionResponseModel,
    permissions=[Permission.CONTENT_FILE.delete],
)
@inject
async def delete_files(
    model: AdminFileBulkAction,
    file_service: FileService = Depends(Provide[Container.file_service]),
):
    result = await file_service.delete_files(command=bulk_action_to_command(model))
    return bulk_delete_result_to_api(result)
