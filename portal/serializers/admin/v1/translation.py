"""
Shared translation request serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AdminTranslationInput(BaseModel):
    """Shared translation input model."""

    locale_id: UUID = Field(..., serialization_alias="localeId", description="Locale ID")
    name: str = Field(..., description="Name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


def validate_unique_locale_ids(translations: Optional[list[AdminTranslationInput]]) -> Optional[list[AdminTranslationInput]]:
    """Validate locale IDs are unique inside one payload."""
    if not translations:
        return translations
    locale_ids = [item.locale_id for item in translations]
    if len(locale_ids) != len(set(locale_ids)):
        raise ValueError("Duplicate locale_id in translations")
    return translations
