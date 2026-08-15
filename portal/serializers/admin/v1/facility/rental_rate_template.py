"""
Rental rate template serializers.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.facility.constants import RentalRateBillingUnit
from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRentalRateTemplateQuery(GenericQueryBaseModel):
    """Paginated rental rate template list filters."""


class AdminRentalRateTemplateItem(UUIDBaseModel):
    """Rental rate template item."""

    name: str = Field(..., description="Display name")
    billing_unit: str = Field(..., serialization_alias="billingUnit", description="Billing unit")
    applicability: Optional[dict] = Field(None, description="JSON applicability rule; null = always eligible")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount", description="Default unit price")
    currency: str = Field(..., description="Currency code")
    is_default: bool = Field(False, serialization_alias="isDefault", description="Default template flag")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")


class AdminRentalRateTemplatePages(PaginationBaseResponseModel):
    """Paginated rental rate templates."""

    items: list[AdminRentalRateTemplateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateTemplateList(BaseModel):
    """Rental rate template list."""

    items: list[AdminRentalRateTemplateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateTemplateWrite(BaseModel):
    """Rental rate template write."""

    name: str = Field(..., description="Display name")
    billing_unit: RentalRateBillingUnit = Field(RentalRateBillingUnit.HOURLY, description="Billing unit")
    applicability: Optional[dict] = Field(None, description="JSON applicability rule; null = always eligible")
    unit_amount: Decimal = Field(..., description="Default unit price")
    currency: str = Field("CAD", description="Currency code")
    is_default: bool = Field(False, description="Default template flag")
    is_active: bool = Field(True, description="Active flag")


class AdminRentalRateTemplateCreate(AdminRentalRateTemplateWrite):
    """Create rental rate template."""


class AdminRentalRateTemplateUpdate(AdminRentalRateTemplateWrite):
    """Update rental rate template."""
