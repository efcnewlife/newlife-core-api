"""
System setting application commands.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand

__all__ = [
    "BulkIdsCommand",
    "CreateSettingCommand",
    "DeleteCommand",
    "UpdateSettingCommand",
]


class UpdateSettingCommand(BaseModel):
    """Update setting value (and optional remark)."""

    value: Any = Field(...)
    remark: Optional[str] = Field(default=None)


class CreateSettingCommand(BaseModel):
    """Create a non-built-in system setting."""

    namespace: str = Field(...)
    setting_key: str = Field(...)
    value_type: str = Field(...)
    value: Any = Field(...)
    remark: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
