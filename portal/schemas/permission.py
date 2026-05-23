"""
Schema for permission (legacy re-exports; prefer portal.domain.rbac.entities).
"""
from pydantic import BaseModel, Field

from portal.domain.rbac.entities import PermissionRecord

PermissionBase = PermissionRecord


class PermissionList(BaseModel):
    """Permission List Schema"""
    permissions: list[PermissionBase] = Field(..., description="List of permissions")
