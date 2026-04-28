"""
User Serializers
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.libs.consts.enums import Gender
from portal.schemas.mixins import UUIDBaseModel, JSONStringMixinModel
from portal.schemas.user import SUserDetail
from portal.serializers.mixins import PaginationBaseResponseModel, GenericQueryBaseModel


class AdminUserQuery(GenericQueryBaseModel):
    """UserQuery"""
    verified: Optional[bool] = Field(None, description="Is the user verified")
    is_active: Optional[bool] = Field(None, description="Is the user active")
    is_superuser: Optional[bool] = Field(None, description="Is the user a superuser")
    is_admin: Optional[bool] = Field(None, description="Can the user access the admin panel")
    is_ministry: Optional[bool] = Field(None, description="Is the user a ministry")
    gender: Optional[Gender] = Field(None, description="User's gender")


class AdminUserBase(UUIDBaseModel, JSONStringMixinModel):
    """UserBase"""
    phone_number: Optional[str] = Field(None, description="User's phone number", serialization_alias="phoneNumber")
    email: Optional[str] = Field(None, description="User's email address")
    display_name: Optional[str] = Field(None, description="User's display name", serialization_alias="displayName")


class AdminUserTableItem(SUserDetail):
    """UserTableItem"""
    pass


class AdminUserItem(SUserDetail):
    """UserItem"""
    pass


class AdminUserPages(PaginationBaseResponseModel):
    """UserPages"""
    items: Optional[list[AdminUserTableItem]] = Field(..., description="Items")


class AdminUserList(BaseModel):
    """UserList"""
    items: Optional[list[AdminUserBase]] = Field(..., description="Items")


class AdminUserCreate(BaseModel):
    """UserCreate"""
    phone_number: Optional[str] = Field(..., description="User's phone number")
    email: str = Field(..., description="User's email address")
    verified: bool = Field(False, description="Is the user verified")
    is_active: bool = Field(True, description="Is the user active")
    is_superuser: bool = Field(False, description="Is the user a superuser")
    is_admin: bool = Field(False, description="Can the user access the admin panel")
    display_name: Optional[str] = Field(None, description="User's display name")
    gender: Optional[Gender] = Field(Gender.UNKNOWN, description="User's gender")
    is_ministry: bool = Field(False, description="Is the user a ministry")
    remark: Optional[str] = Field(None, description="Remark")
    password: str = Field(..., min_length=8, description="User's password")
    password_confirm: str = Field(..., min_length=8, description="User's password confirmation")


class AdminUserUpdate(AdminUserCreate):
    """UserUpdate"""
    password: Optional[str] = Field(None, exclude=True)
    password_confirm: Optional[str] = Field(None, exclude=True)


class AdminChangePassword(BaseModel):
    """ChangePassword"""
    old_password: str = Field(..., min_length=8, description="Old password")
    new_password: str = Field(..., min_length=8, description="New password")
    new_password_confirm: str = Field(..., min_length=8, description="New password confirmation")


class AdminUserBulkAction(BaseModel):
    """UserBulkAction"""
    ids: list[UUID] = Field(..., description="User IDs for bulk action")


class AdminUserRoles(BaseModel):
    """UserRole"""
    role_ids: list[UUID] = Field(..., description="User roles")


class AdminBindRole(BaseModel):
    """BindRole"""
    role_ids: list[UUID] = Field(..., description="Role IDs to assign to the user")
