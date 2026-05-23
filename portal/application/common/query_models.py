"""
Shared query and delete command models for application services.
"""
import uuid
from typing import Optional

import pydantic
from pydantic import BaseModel, Field


class DeleteQueryBaseModel(BaseModel):
    """Filter for deleted-only listings."""

    deleted: bool = Field(False, description="Deleted items only")


class PaginationQueryBaseModel(BaseModel):
    """Pagination parameters."""

    page: int = Field(0, description="Page number")
    page_size: int = Field(10, description="Page size", serialization_alias="pageSize")


class OrderByQueryBaseModel(PaginationQueryBaseModel):
    """Pagination with ordering."""

    order_by: Optional[str] = Field(None, description="Order by field", serialization_alias="orderBy")
    descending: bool = Field(False, description="Descending order")


class KeywordQueryBaseModel(BaseModel):
    """Keyword filter."""

    keyword: Optional[str] = Field(None, description="Keyword filter")


class GenericQueryBaseModel(OrderByQueryBaseModel, DeleteQueryBaseModel, KeywordQueryBaseModel):
    """Combined list query parameters."""


class DeleteBaseModel(BaseModel):
    """Soft or permanent delete command."""

    reason: Optional[str] = Field(None, description="Delete reason")
    permanent: bool = Field(False, description="Permanent delete")

    @pydantic.model_validator(mode="after")
    def validate_reason(self):
        """Require reason for non-permanent delete."""
        if not self.permanent and self.reason is None:
            raise ValueError("Reason is required for non-permanent delete")
        return self


class ChangeSequence(BaseModel):
    """Reorder command for sortable resources."""

    id: uuid.UUID = Field(..., description="Resource ID")
    sequence: float = Field(..., description="New sequence")
    another_id: uuid.UUID = Field(..., description="Another resource ID to swap sequence with", serialization_alias="anotherId")
    another_sequence: float = Field(..., description="Another resource's current sequence", serialization_alias="anotherSequence")


class BulkAction(BaseModel):
    """Bulk action command."""

    ids: list[uuid.UUID] = Field(..., description="Resource IDs for bulk action")


class PaginationBaseResponseModel(BaseModel):
    """Paginated list response base."""

    page: int = Field(..., description="Page number")
    page_size: int = Field(..., description="Page size", serialization_alias="pageSize")
    total: int = Field(..., description="Total number of items")

    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "items"):
            raise ValueError("items field is required")
        super().__init_subclass__(**kwargs)
