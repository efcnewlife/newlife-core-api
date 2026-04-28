"""
Schema of Locale model.
"""
from typing import Optional
from pydantic import Field

from portal.schemas.mixins import UUIDBaseModel


class SLocale(UUIDBaseModel):
    """
    Schema for Locale model
    """
    language_code: str = Field(..., description="Language code")
    script_code: Optional[str] = Field(None, description="Script code")
    region_code: Optional[str] = Field(None, description="Region code")
    name: Optional[str] = Field(None, description="Locale name")
    native_name: Optional[str] = Field(None, description="Native locale name")
    is_active: bool = Field(True, description="Is locale active")
    is_default: bool = Field(False, description="Is default locale")
