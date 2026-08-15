"""
System setting domain entities.
"""

from typing import Any

import ujson
from pydantic import Field, field_validator

from portal.domain.common.mixins import AuditModel, DeleteModel, RemarkModel, UUIDModel


class Setting(UUIDModel, AuditModel, DeleteModel, RemarkModel):
    """System setting row."""

    namespace: str = Field(...)
    setting_key: str = Field(...)
    value_type: str = Field(...)
    value: Any = Field(...)
    is_built_in: bool = Field(default=False)
    is_active: bool = Field(default=True)

    @field_validator("value", mode="before")
    @classmethod
    def parse_jsonb_value(cls, value: Any) -> Any:
        """Decode asyncpg JSONB text (e.g. '"America/Toronto"') into a Python value."""
        if isinstance(value, str):
            try:
                return ujson.loads(value)
            except ujson.JSONDecodeError:
                return value
        return value
