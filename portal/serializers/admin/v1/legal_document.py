"""
Admin Legal Document serializers.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.serializers.mixins import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminLegalDocumentQuery(GenericQueryBaseModel):
    """Paginated Legal Document list filters."""

    product: Optional[str] = Field(default=None)
    kind: Optional[str] = Field(default=None)


class AdminLegalDocumentTranslationInput(BaseModel):
    """Legal Document translation input (Markdown body)."""

    locale_id: UUID = Field(..., description="Locale ID")
    body: str = Field(default="", description="Markdown body")


class AdminLegalDocumentTranslationItem(BaseModel):
    """Legal Document translation response item."""

    locale_id: UUID = Field(..., serialization_alias="localeId", description="Locale ID")
    body: str = Field(default="", description="Markdown body")


class AdminLegalDocumentItem(UUIDBaseModel):
    """Legal Document list item."""

    product: str = Field(..., description="Built-in Product code")
    kind: str = Field(..., description="Legal Document Kind")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")


class AdminLegalDocumentDetail(AdminLegalDocumentItem):
    """Legal Document detail with translations."""

    translations: list[AdminLegalDocumentTranslationItem] = Field(default_factory=list, description="Locale translations")


class AdminLegalDocumentPages(PaginationBaseResponseModel):
    """Paginated Legal Documents."""

    items: list[AdminLegalDocumentItem] = Field(default_factory=list, description="Legal Document items")


class AdminLegalDocumentUpdate(BaseModel):
    """Replace current Legal Document translation wording."""

    translations: list[AdminLegalDocumentTranslationInput] = Field(..., min_length=1, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_unique_locale_ids(cls, value: list[AdminLegalDocumentTranslationInput]) -> list[AdminLegalDocumentTranslationInput]:
        locale_ids = [item.locale_id for item in value]
        if len(locale_ids) != len(set(locale_ids)):
            raise ValueError("Duplicate locale_id in translations")
        return value
