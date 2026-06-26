"""
Admin Locale Serializer
"""
from typing import Optional

from pydantic import Field, BaseModel

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminLocaleItem(UUIDBaseModel):
    """Locale row for admin list API."""

    language_code: str = Field(..., serialization_alias="languageCode", description="Language code")
    script_code: Optional[str] = Field(None, serialization_alias="scriptCode", description="Script code")
    region_code: Optional[str] = Field(None, serialization_alias="regionCode", description="Region code")
    name: Optional[str] = Field(None, description="Locale name")
    native_name: Optional[str] = Field(None, serialization_alias="nativeName", description="Native locale name")
    is_active: bool = Field(True, serialization_alias="isActive", description="Is locale active")
    is_default: bool = Field(False, serialization_alias="isDefault", description="Is default locale")


class AdminLocaleList(BaseModel):
    """LocaleList"""

    items: list[AdminLocaleItem] = Field(..., description="Items")
