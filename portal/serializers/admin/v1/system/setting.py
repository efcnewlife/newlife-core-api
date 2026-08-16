"""
Admin system setting serializers.
"""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import AuditMixinModel, UUIDBaseModel


class AdminSettingQuery(BaseModel):
    """List filter."""

    namespace: Optional[str] = Field(default=None)
    deleted: bool = Field(default=False)


class AdminSettingByKeyQuery(BaseModel):
    """Lookup by namespace + key."""

    namespace: str = Field(...)
    setting_key: str = Field(...)


class AdminSettingCreate(BaseModel):
    """Create setting."""

    namespace: str = Field(...)
    setting_key: str = Field(...)
    value_type: str = Field(...)
    value: Any = Field(...)
    remark: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)


class AdminSettingUpdate(BaseModel):
    """Update setting value."""

    value: Any = Field(...)
    remark: Optional[str] = Field(default=None)


class AdminSettingBulkAction(BaseModel):
    """Bulk restore action."""

    ids: list[UUID] = Field(...)


class AdminSettingItem(UUIDBaseModel, AuditMixinModel):
    """Setting response item."""

    namespace: str = Field(...)
    setting_key: str = Field(..., serialization_alias="settingKey")
    value_type: str = Field(..., serialization_alias="valueType")
    value: Any = Field(...)
    is_built_in: bool = Field(default=False, serialization_alias="isBuiltIn")
    is_active: bool = Field(default=True, serialization_alias="isActive")
    remark: Optional[str] = Field(default=None)


class AdminSettingList(BaseModel):
    """Setting list response."""

    items: list[AdminSettingItem] = Field(default_factory=list)
