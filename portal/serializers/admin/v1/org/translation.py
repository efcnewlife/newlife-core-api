"""
Org translation serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AdminOrgTranslationInput(BaseModel):
    """Org ministry translation input."""

    locale_id: UUID = Field(..., description="Locale ID")
    name: str = Field(..., description="Name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


class AdminOrgTranslationItem(BaseModel):
    """Org ministry translation response item."""

    locale_id: UUID = Field(..., serialization_alias="localeId", description="Locale ID")
    name: str = Field(..., description="Name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


class AdminPositionTranslationInput(BaseModel):
    """Position translation input."""

    locale_id: UUID = Field(..., description="Locale ID")
    name: str = Field(..., description="Position name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


class AdminPositionTranslationItem(BaseModel):
    """Position translation response item."""

    locale_id: UUID = Field(..., serialization_alias="localeId", description="Locale ID")
    name: str = Field(..., description="Position name")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


def validate_unique_org_locale_ids(
    translations: Optional[list[AdminOrgTranslationInput]],
) -> Optional[list[AdminOrgTranslationInput]]:
    if not translations:
        return translations
    locale_ids = [item.locale_id for item in translations]
    if len(locale_ids) != len(set(locale_ids)):
        raise ValueError("Duplicate locale_id in translations")
    return translations


def validate_unique_position_locale_ids(
    translations: Optional[list[AdminPositionTranslationInput]],
) -> Optional[list[AdminPositionTranslationInput]]:
    if not translations:
        return translations
    locale_ids = [item.locale_id for item in translations]
    if len(locale_ids) != len(set(locale_ids)):
        raise ValueError("Duplicate locale_id in translations")
    return translations
