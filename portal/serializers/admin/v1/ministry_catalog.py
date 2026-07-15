"""
Ministry catalog admin API serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminMinistryTypeItem(UUIDBaseModel):
    """Ministry type catalog item."""

    code: str = Field(..., description="Stable ministry type code")
    name: Optional[str] = Field(None, description="Localized ministry type name")


class AdminMinistryTypeList(BaseModel):
    """Active ministry types."""

    items: list[AdminMinistryTypeItem] = Field(default_factory=list, description="Items")


class AdminTargetAudienceItem(UUIDBaseModel):
    """Target audience catalog item."""

    code: str = Field(..., description="Stable target audience code")
    name: Optional[str] = Field(None, description="Localized target audience name")


class AdminTargetAudienceList(BaseModel):
    """Active target audiences."""

    items: list[AdminTargetAudienceItem] = Field(default_factory=list, description="Items")
