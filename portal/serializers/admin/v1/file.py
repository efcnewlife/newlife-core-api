"""
File Serializer
"""
from typing import Optional

from pydantic import BaseModel, Field

from portal.libs.consts.enums import FileStatus, FileUploadSource
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import OrderByQueryBaseModel, PaginationBaseResponseModel


class AdminFileBase(UUIDBaseModel):
    """File Base Model"""
    original_name: str = Field(..., description="Original file name", serialization_alias="originalName")
    key: str = Field(..., description="Key")
    storage: str = Field(..., description="Storage")
    bucket: str = Field(..., description="Bucket")
    region: str = Field(..., description="Region")
    content_type: Optional[str] = Field(None, description="Content type", serialization_alias="contentType")
    extension: Optional[str] = Field(None, description="File extension")
    size_bytes: Optional[int] = Field(None, description="Size in bytes", serialization_alias="sizeBytes")


class AdminFileDetail(AdminFileBase):
    """File Base Model"""
    checksum_md5: Optional[str] = Field(None, description="MD5 checksum")
    checksum_sha256: Optional[str] = Field(None, description="SHA256 checksum")
    width: Optional[int] = Field(None, description="Width")
    height: Optional[int] = Field(None, description="Height")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    status: Optional[FileStatus] = Field(None, description="File status")
    version: Optional[int] = Field(None, description="File version")
    is_public: Optional[bool] = Field(None, description="Is public")
    source: Optional[FileUploadSource] = Field(None, description="Source")


class AdminFileGridItem(AdminFileBase):
    """File Grid Item"""
    url: Optional[str] = Field(None, description="URL")


class AdminFileQuery(OrderByQueryBaseModel):
    """FileQuery"""
    keyword: Optional[str] = Field(None, description="Keyword filter")


class AdminFilePages(PaginationBaseResponseModel):
    """File Pages"""
    items: Optional[list[AdminFileGridItem]] = Field(..., description="Items")


class AdminFailedUploadFile(BaseModel):
    """Fail Upload File"""
    filename: str = Field(..., description="File name")
    error: str = Field(..., description="Error message")


class AdminBatchFileUploadResponseModel(BaseModel):
    """Batch File Upload Response Model"""
    uploaded_files: list[UUIDBaseModel] = Field(..., description="Uploaded files")
    failed_files: list[AdminFailedUploadFile] = Field(..., description="Failed files")


class AdminFileUploadResponseModel(UUIDBaseModel):
    """File Upload Response Model"""
    duplicate: Optional[bool] = Field(None, description="Is duplicate")


class AdminBulkActionResponseModel(BaseModel):
    """Bulk Action Response Model"""
    success_count: int = Field(..., description="Count of items affected")
    failed_items: Optional[list[AdminFileBase]] = Field(None, description="Failed items")
