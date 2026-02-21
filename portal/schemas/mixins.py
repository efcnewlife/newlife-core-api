"""
Model for Mixins
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import ujson
from pydantic import BaseModel, Field, field_serializer, model_validator


class UUIDBaseModel(BaseModel):
    """
    UUID Base Model
    """
    id: Optional[UUID] = Field(default_factory=uuid4)

    @field_serializer("id")
    def serialize_uuid(self, value: UUID, _info) -> Optional[str]:
        """

        :param value:
        :param _info:
        :return:
        """
        if value is None:
            return None
        return str(value)


class JSONStringMixinModel(BaseModel):
    """
    JSON String Mixin Model
    """
    @model_validator(mode="before")
    def validate_ujson_string(cls, values):
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


class SortableMixinModel(BaseModel):
    """
    Sortable Mixin Model
    """
    sequence: Optional[int] = Field(default=None, description="Display sort, small to large, positive sort, default value current timestamp")


class AuditMixinModel(BaseModel):
    """
    Audit Mixin Model
    """
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp in ISO format")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp in ISO format")
    created_by: Optional[str] = Field(default=None, description="User who created the record")
    updated_by: Optional[str] = Field(default=None, description="User who last updated the record")
    created_by_id: Optional[UUID] = Field(default=None, description="ID of the user who created the record")
    updated_by_id: Optional[UUID] = Field(default=None, description="ID of the user who last updated the record")

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: Optional[datetime], _info) -> Optional[str]:
        """
        Serialize datetime to ISO format string
        :param value:
        :param _info:
        :return:
        """
        return value.isoformat() if value else None


class DeleteMixinModel(BaseModel):
    """
    Delete Mixin Model
    """
    is_deleted: bool = Field(default=False, description="Is the record deleted")
    delete_reason: Optional[str] = Field(default=None, description="Reason for deletion")


class DescriptionMixinModel(BaseModel):
    """
    Description Mixin Model
    """
    description: Optional[str] = Field(default=None, description="Description of the record")


class RemarkMixinModel(BaseModel):
    """
    Remark Mixin Model
    """
    remark: Optional[str] = Field(default=None, description="Remark for the record")


class BaseMixinModel(AuditMixinModel, DeleteMixinModel, DescriptionMixinModel, RemarkMixinModel):
    """
    Base Mixin Model that combines all mixins
    """
