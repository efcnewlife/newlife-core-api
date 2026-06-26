"""
Facility translation serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AdminFacilityTranslationInput(BaseModel):
    """Facility translation input."""

    locale_id: UUID = Field(..., description="Locale ID")
    name: str = Field(..., description="Name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


class AdminFacilityTranslationItem(BaseModel):
    """Facility translation response item."""

    locale_id: UUID = Field(..., serialization_alias="localeId", description="Locale ID")
    name: str = Field(..., description="Name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


def validate_unique_facility_locale_ids(
    translations: Optional[list[AdminFacilityTranslationInput]],
) -> Optional[list[AdminFacilityTranslationInput]]:
    if not translations:
        return translations
    locale_ids = [item.locale_id for item in translations]
    if len(locale_ids) != len(set(locale_ids)):
        raise ValueError("Duplicate locale_id in translations")
    return translations

