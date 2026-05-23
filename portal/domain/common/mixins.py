"""
Domain-layer Pydantic mixins (snake_case, no API serialization aliases).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UUIDModel(BaseModel):
    """UUID identifier for domain entities."""

    id: UUID = Field(default_factory=uuid4)


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
