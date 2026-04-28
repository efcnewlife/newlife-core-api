"""
Permission serializers
"""
from typing import Optional
from uuid import UUID

from pydantic import Field, BaseModel, field_validator, model_validator

from portal.schemas.mixins import UUIDBaseModel, JSONStringMixinModel
from portal.serializers.admin.v1.translation import (
    AdminTranslationInput,
    validate_unique_locale_ids,
)
from portal.serializers.mixins import GenericQueryBaseModel, PaginationBaseResponseModel


class AdminPermissionResourceItem(UUIDBaseModel, JSONStringMixinModel):
    """PermissionResourceItem"""
    name: str = Field(..., description="Name")
    key: str = Field(..., description="Key")
    code: str = Field(..., description="Code")


class AdminPermissionVerbItem(UUIDBaseModel, JSONStringMixinModel):
    """PermissionVerbItem"""
    name: str = Field(..., description="Verb name")
    action: str = Field(..., description="Action")


class AdminPermissionBase(UUIDBaseModel):
    """PermissionBase"""
    name: str = Field(..., description="Permission name")
    code: str = Field(..., description="Code")
    is_active: bool = Field(..., serialization_alias="isActive", description="Is active")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")


class AdminPermissionItem(AdminPermissionBase):
    """PermissionItem"""
    resource_id: Optional[UUID] = Field(None, serialization_alias="resourceId", description="Resource ID")
    verb_id: Optional[UUID] = Field(None, serialization_alias="verbId", description="Verb ID")


class AdminPermissionDetail(AdminPermissionBase):
    """PermissionDetail"""
    resource: AdminPermissionResourceItem = Field(..., description="Resource")
    verb: AdminPermissionVerbItem = Field(..., description="Verb")


class AdminPermissionPageItem(AdminPermissionBase):
    """PermissionPageItem"""
    resource_name: str = Field(..., serialization_alias="resourceName", description="Resource name")
    verb_name: str = Field(..., serialization_alias="verbName", description="Verb name")


class AdminPermissionPage(PaginationBaseResponseModel):
    """PermissionPage"""
    items: Optional[list[AdminPermissionPageItem]] = Field(..., description="Permissions")


class AdminPermissionQuery(GenericQueryBaseModel):
    """PermissionQuery"""
    is_active: Optional[bool] = Field(None, description="Is active")


class AdminPermissionWrite(BaseModel):
    """PermissionWrite"""
    name: Optional[str] = Field(None, description="Permission name")
    code: str = Field(..., description="Code")
    resource_id: UUID = Field(..., description="Resource ID")
    verb_id: UUID = Field(..., description="Verb ID")
    is_active: bool = Field(..., description="Is active")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")
    translations: Optional[list[AdminTranslationInput]] = Field(None, description="Localized content")

    @field_validator("translations")
    @classmethod
    def validate_translations_locale_ids(cls, value: Optional[list[AdminTranslationInput]]) -> Optional[list[AdminTranslationInput]]:
        return validate_unique_locale_ids(value)


class AdminPermissionCreate(AdminPermissionWrite):
    """PermissionCreate"""

    @model_validator(mode="after")
    def validate_legacy_or_translations(self):
        if self.translations:
            return self
        if self.name:
            return self
        raise ValueError("Either translations or name is required")


class AdminPermissionUpdate(AdminPermissionWrite):
    """PermissionUpdate"""


class AdminPermissionList(BaseModel):
    """PermissionList"""
    items: Optional[list[AdminPermissionItem]] = Field(..., description="Permissions")


class AdminPermissionBulkAction(BaseModel):
    """PermissionBulkAction"""
    ids: list[UUID] = Field(..., description="Permission IDs for bulk action")
