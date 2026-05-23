"""
Schema of Locale model (backward-compatible re-exports).
"""
from typing import Optional

from pydantic import Field

from portal.domain.common.mixins import UUIDModel
from portal.domain.locale.entities import Locale


class SLocale(UUIDModel):
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

    @classmethod
    def from_locale(cls, locale: Locale) -> "SLocale":
        return cls.model_validate(locale.model_dump())
