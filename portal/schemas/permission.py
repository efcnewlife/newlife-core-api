"""
Schema for permission
"""
from typing import Optional

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    """Permission Base Schema"""
    code: str = Field(..., description="Permission code")
    resource_code: str = Field(..., description="Resource code")
    action: str = Field(..., description="Action")


class PermissionList(BaseModel):
    """Permission List Schema"""
    permissions: list[PermissionBase] = Field(..., description="List of permissions")
