"""
RBAC domain entities.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

import ujson
from pydantic import BaseModel, Field, model_validator

from portal.domain.common.mixins import UUIDModel
from portal.libs.consts.enums import ResourceType


class Verb(UUIDModel):
    """Auth verb with localized display fields."""

    action: str = Field(..., description="Verb action code")
    name: str = Field(..., description="Localized display name")
    description: Optional[str] = Field(None, description="Localized description")


class VerbListItem(UUIDModel):
    """Verb row for list queries."""

    action: str = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(None)


class PermissionRecord(BaseModel):
    """Resolved permission code for authorization (resource + verb)."""

    code: str = Field(..., description="Permission code")
    resource_code: str = Field(..., description="Resource code")
    action: str = Field(..., description="Verb action")


class PermissionResourceRef(UUIDModel):
    """Resource reference on permission detail."""

    name: str = Field(...)
    key: str = Field(...)
    code: str = Field(...)

    @model_validator(mode="before")
    @classmethod
    def validate_json_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON string: {error}") from error
        return values


class PermissionVerbRef(UUIDModel):
    """Verb reference on permission detail."""

    name: str = Field(...)
    action: str = Field(...)

    @model_validator(mode="before")
    @classmethod
    def validate_json_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON string: {error}") from error
        return values


class PermissionListItem(UUIDModel):
    """Permission row for list endpoints."""

    name: str = Field(...)
    code: str = Field(...)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    resource_id: Optional[UUID] = Field(default=None)
    verb_id: Optional[UUID] = Field(default=None)


class PermissionPageItem(PermissionListItem):
    """Permission row for paginated admin list."""

    resource_name: str = Field(...)
    verb_name: str = Field(...)


class PermissionDetail(PermissionListItem):
    """Full permission detail."""

    resource: PermissionResourceRef = Field(...)
    verb: PermissionVerbRef = Field(...)


class RolePermissionSummary(UUIDModel):
    """Permission summary embedded in role detail."""

    resource_name: str = Field(...)
    name: str = Field(...)
    code: str = Field(...)

    @model_validator(mode="before")
    @classmethod
    def validate_json_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON string: {error}") from error
        return values


class RoleListItem(UUIDModel):
    """Role row for dropdown list."""

    code: str = Field(...)
    name: Optional[str] = Field(None)


class RoleItem(RoleListItem):
    """Role row with active flag."""

    is_active: bool = Field(default=True)


class RoleDetail(RoleItem):
    """Full role detail for admin views."""

    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    permissions: list[RolePermissionSummary] = Field(default_factory=list)


class ResourceParent(UUIDModel):
    """Parent resource reference."""

    name: Optional[str] = Field(default=None)
    key: Optional[str] = Field(default=None)
    code: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def validate_json_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON string: {error}") from error
        return values


class ResourceItem(UUIDModel):
    """Flat resource row."""

    pid: Optional[UUID] = Field(default=None)
    name: str = Field(...)
    key: str = Field(...)
    code: str = Field(...)
    icon: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    type: ResourceType = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    sequence: float = Field(...)
    is_deleted: bool = Field(default=False)


class ResourceDetail(ResourceItem):
    """Resource detail with parent reference."""

    parent: Optional[ResourceParent] = Field(default=None)


class ResourceTreeNode(ResourceItem):
    """Resource node for hierarchical trees."""

    children: Optional[list["ResourceTreeNode"]] = Field(default=None)
