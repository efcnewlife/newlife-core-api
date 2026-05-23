"""
RBAC application results.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.rbac.entities import (
    PermissionDetail,
    PermissionListItem,
    PermissionPageItem,
    RoleDetail,
    RoleListItem,
    ResourceDetail,
    ResourceItem,
    ResourceTreeNode,
    VerbListItem,
)
from portal.libs.consts.enums import Gender


class VerbListResult(BaseModel):
    """Result of listing verbs for the current locale."""

    items: list[VerbListItem] = Field(default_factory=list)


class CreateIdResult(BaseModel):
    """Created entity id."""

    id: UUID = Field(...)


class RolePageResult(BaseModel):
    """Paginated role list."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RoleDetail] = Field(default_factory=list)


class RoleListResult(BaseModel):
    """Active roles for dropdown."""

    items: list[RoleListItem] = Field(default_factory=list)


class RoleDetailResult(RoleDetail):
    """Single role detail result."""


class ResourceDetailResult(ResourceDetail):
    """Single resource detail result."""


class ResourceListResult(BaseModel):
    """Flat resource list."""

    items: list[ResourceItem] = Field(default_factory=list)


class ResourceTreeResult(BaseModel):
    """Hierarchical resource tree."""

    items: list[ResourceTreeNode] = Field(default_factory=list)


class AdminUserListItem(BaseModel):
    """Admin user list row."""

    id: UUID = Field(...)
    phone_number: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)


class AdminUserTableRow(BaseModel):
    """Admin user table row."""

    id: UUID = Field(...)
    phone_number: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    preferred_name: Optional[str] = Field(default=None)
    preferred_locale_id: Optional[UUID] = Field(default=None)
    gender: Optional[Gender] = Field(default=None)


class AdminUserPageResult(BaseModel):
    """Paginated admin users."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[AdminUserTableRow] = Field(default_factory=list)


class AdminUserListResult(BaseModel):
    """Admin user dropdown list."""

    items: list[AdminUserListItem] = Field(default_factory=list)


class AdminUserDetailResult(AdminUserTableRow):
    """Admin user detail."""


class AdminUserRolesResult(BaseModel):
    """Role ids assigned to a user."""

    role_ids: list[UUID] = Field(default_factory=list)


class PermissionPageResult(BaseModel):
    """Paginated permission list."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[PermissionPageItem] = Field(default_factory=list)


class PermissionListResult(BaseModel):
    """Cached permission list for current locale."""

    items: list[PermissionListItem] = Field(default_factory=list)


class PermissionDetailResult(PermissionDetail):
    """Single permission detail result."""
