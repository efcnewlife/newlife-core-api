"""
Domain-layer Pydantic mixins (snake_case, no API serialization aliases).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import ujson
from pydantic import BaseModel, Field, field_serializer, model_validator


class JsonStringParseModel(BaseModel):
    """Parse JSON string values before validation (e.g. asyncpg jsonb array elements)."""

    @model_validator(mode="before")
    @classmethod
    def parse_json_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON string: {error}") from error
        return values


class UUIDBaseModel(BaseModel):
    """UUID identifier with string serialization for JSON."""

    id: UUID = Field(default_factory=uuid4)

    @field_serializer("id")
    def serialize_uuid(self, value: UUID, _info) -> Optional[str]:
        if value is None:
            return None
        return str(value)


UUIDModel = UUIDBaseModel


class AuditModel(BaseModel):
    """Audit fields for domain entities."""

    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    created_by_id: Optional[UUID] = Field(default=None)
    updated_by_id: Optional[UUID] = Field(default=None)


class DeleteModel(BaseModel):
    """Soft-delete fields for domain entities."""

    is_deleted: bool = Field(default=False)
    delete_reason: Optional[str] = Field(default=None)


class DescriptionModel(BaseModel):
    """Description field for domain entities."""

    description: Optional[str] = Field(default=None)


class RemarkModel(BaseModel):
    """Remark field for domain entities."""

    remark: Optional[str] = Field(default=None)


class BaseEntityModel(AuditModel, DeleteModel, DescriptionModel, RemarkModel, UUIDModel):
    """Combined base for auditable domain entities."""
