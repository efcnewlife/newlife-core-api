"""
API-layer Pydantic mixins for serializers (camelCase via Field on concrete models).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

import ujson
from pydantic import BaseModel, Field, field_serializer, model_validator

from portal.domain.common.mixins import UUIDModel


class UUIDBaseModel(UUIDModel):
    """UUID base model with string id serialization for JSON responses."""

    @field_serializer("id")
    def serialize_uuid(self, value: UUID, _info) -> Optional[str]:
        if value is None:
            return None
        return str(value)


class JSONStringMixinModel(BaseModel):
    """Parse JSON string columns into dicts before validation."""

    @model_validator(mode="before")
    def validate_ujson_string(cls, values):
        if isinstance(values, str):
            try:
                values = ujson.loads(values)
            except ujson.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")
        return values


class SortableMixinModel(BaseModel):
    """Sortable entity mixin."""

    sequence: Optional[int] = Field(
        default=None,
        description="Display sort, small to large, positive sort, default value current timestamp",
    )


class AuditMixinModel(BaseModel):
    """Audit fields for API response models."""

    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp in ISO format")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp in ISO format")
    created_by: Optional[str] = Field(default=None, description="User who created the record")
    updated_by: Optional[str] = Field(default=None, description="User who last updated the record")
    created_by_id: Optional[UUID] = Field(default=None, description="ID of the user who created the record")
    updated_by_id: Optional[UUID] = Field(default=None, description="ID of the user who last updated the record")

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: Optional[datetime], _info) -> Optional[str]:
        return value.isoformat() if value else None


class DeleteMixinModel(BaseModel):
    """Soft-delete fields for API response models."""

    is_deleted: bool = Field(default=False, description="Is the record deleted")
    delete_reason: Optional[str] = Field(default=None, description="Reason for deletion")


class DescriptionMixinModel(BaseModel):
    """Description field for API response models."""

    description: Optional[str] = Field(default=None, description="Description of the record")


class RemarkMixinModel(BaseModel):
    """Remark field for API response models."""

    remark: Optional[str] = Field(default=None, description="Remark for the record")


class BaseMixinModel(AuditMixinModel, DeleteMixinModel, DescriptionMixinModel, RemarkMixinModel):
    """Combined audit/delete/description/remark mixin for API models."""

    pass
