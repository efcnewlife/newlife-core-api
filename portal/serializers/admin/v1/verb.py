"""
Verb serializers
"""

from typing import Optional

from pydantic import Field, BaseModel

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminVerbItem(UUIDBaseModel):
    """VerbItem"""
    action: str = Field(..., description="Action")
    name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Description")


class AdminVerbList(BaseModel):
    """VerbList"""
    items: Optional[list[AdminVerbItem]] = Field(..., description="Verbs")
