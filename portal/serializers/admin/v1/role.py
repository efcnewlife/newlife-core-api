"""
Role serializers
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

import ujson
from pydantic import Field, BaseModel, model_validator, field_validator

from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.admin.v1.translation import (
    AdminTranslationInput,
    validate_unique_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel


class AdminRolePermission(UUIDBaseModel):
    """PermissionBase"""
    resource_name: str = Field(..., serialization_alias="resourceName", description="Resource name")
    name: str = Field(..., description="Permission name")
    code: str = Field(..., description="Code")

    @model_validator(mode="before")
    def validate_json_string(cls, values):
        """

        :param values:
        :return:
        """
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        return values


class AdminRoleBase(UUIDBaseModel):
    """RoleBase"""
    code: str = Field(..., description="Role code")
    name: Optional[str] = Field(None, description="Role name")


class AdminRoleItem(AdminRoleBase):
    """RoleItem"""
    is_active: bool = Field(True, serialization_alias="isActive", description="Is role active")


class AdminRoleTableItem(AdminRoleItem):
    """RoleTableItem"""
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Create at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Update at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")
    permissions: list[AdminRolePermission] = Field(..., description="Permissions")


class AdminRolePages(PaginationBaseResponseModel):
    """RolePages"""
    items: Optional[list[AdminRoleTableItem]] = Field(..., description="Role Items")


class AdminRoleList(BaseModel):
    """RoleList"""
    items: Optional[list[AdminRoleBase]] = Field(..., description="Role Items")


class AdminRoleWrite(BaseModel):
    """RoleWrite"""
    code: str = Field(..., description="Role code")
    name: Optional[str] = Field(None, description="Role name")
    is_active: bool = Field(True, description="Is role active")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")
    permissions: list[UUID] = Field(..., description="Permissions")
    translations: Optional[list[AdminTranslationInput]] = Field(None, description="Localized content")

    @field_validator("translations")
    @classmethod
    def validate_translations_locale_ids(cls, value: Optional[list[AdminTranslationInput]]) -> Optional[list[AdminTranslationInput]]:
        return validate_unique_locale_ids(value)


class AdminRoleCreate(AdminRoleWrite):
    """RoleCreate"""

    @model_validator(mode="after")
    def validate_legacy_or_translations(self):
        if self.translations:
            return self
        if self.name:
            return self
        raise ValueError("Either translations or name is required")


class AdminRoleUpdate(AdminRoleWrite):
    """RoleUpdate"""
    pass


class AdminRoleBulkDelete(BaseModel):
    """RoleBulkDelete"""
    ids: list[UUID] = Field(..., description="Role IDs to delete")


class AdminRolePermissionAssign(BaseModel):
    """Assign or revoke permissions to a role"""
    permission_ids: list[UUID] = Field(..., serialization_alias="permissionIds", description="Permission IDs to assign or revoke")
