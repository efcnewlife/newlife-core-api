"""
Content application commands (snake_case, no API serialization aliases).
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.content.constants import FileUploadSource, MediaCategory


class FilePagesQueryCommand(BaseModel):
    """Paginated file list query."""

    page: int = Field(default=0)
    page_size: int = Field(default=10)
    order_by: Optional[str] = Field(default=None)
    descending: bool = Field(default=False)
    keyword: Optional[str] = Field(default=None)
    media_category: Optional[MediaCategory] = Field(default=None)


class BulkDeleteFilesCommand(BaseModel):
    """Bulk soft-delete files."""

    ids: list[UUID] = Field(...)


class PreviewFileAssociationsCommand(BaseModel):
    """List named File associations for selected files."""

    ids: list[UUID] = Field(...)


class UpdateFileAssociationCommand(BaseModel):
    """Replace file associations for a resource."""

    file_ids: list[UUID] = Field(default_factory=list)
    resource_id: UUID = Field(...)
    resource_name: Optional[str] = Field(default=None)


class UploadFileCommand(BaseModel):
    """Upload a single file from already-read bytes."""

    filename: str = Field(...)
    content: bytes = Field(...)
    content_type: Optional[str] = Field(default=None)
    upload_source: FileUploadSource = Field(default=FileUploadSource.ADMIN)
    is_public: bool = Field(default=False)
    check_duplicates: bool = Field(default=True)

    model_config = {"arbitrary_types_allowed": True}


class LegalDocumentPagesQueryCommand(BaseModel):
    """Paginated Legal Document list query."""

    page: int = Field(default=0)
    page_size: int = Field(default=10)
    order_by: Optional[str] = Field(default=None)
    descending: bool = Field(default=False)
    deleted: bool = Field(default=False)
    product: Optional[str] = Field(default=None)
    kind: Optional[str] = Field(default=None)


class LegalDocumentTranslationCommand(BaseModel):
    """Localized Markdown body for one locale."""

    locale_id: UUID = Field(...)
    body: str = Field(default="")


class UpdateLegalDocumentCommand(BaseModel):
    """Replace current Legal Document translation wording."""

    translations: list[LegalDocumentTranslationCommand] = Field(..., min_length=1)
