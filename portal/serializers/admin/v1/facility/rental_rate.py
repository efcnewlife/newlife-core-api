"""
Rental rate serializers (room bindings; price from template).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRentalRateQuery(GenericQueryBaseModel):
    """Paginated rental rate list filters."""

    facility_id: Optional[UUID] = Field(default=None)


class AdminRentalRateTemplateEmbed(BaseModel):
    """Embedded template summary on a rate binding."""

    id: UUID = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    billing_unit: str = Field(..., serialization_alias="billingUnit", description="Billing unit")
    applicability: Optional[dict] = Field(None, description="Applicability rule")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount", description="Template unit price")
    currency: str = Field(..., description="Template currency")
    is_default: bool = Field(False, serialization_alias="isDefault", description="Default flag")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")


class AdminRentalRateItem(UUIDBaseModel):
    """Rental rate binding item (price comes from embedded template)."""

    facility_id: UUID = Field(..., serialization_alias="facilityId", description="Room ID")
    template_id: UUID = Field(..., serialization_alias="templateId", description="Template ID")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    template: Optional[AdminRentalRateTemplateEmbed] = Field(None, description="Embedded template")


class AdminRentalRatePages(PaginationBaseResponseModel):
    """Paginated rental rates."""

    items: list[AdminRentalRateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateList(BaseModel):
    """Rental rate list."""

    items: list[AdminRentalRateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateWrite(BaseModel):
    """Rental rate binding write (room only)."""

    facility_id: UUID = Field(..., description="Room ID")
    template_id: UUID = Field(..., description="Template ID")
    is_active: bool = Field(True, description="Active flag")


class AdminRentalRateCreate(AdminRentalRateWrite):
    """Create rental rate binding."""


class AdminRentalRateUpdate(AdminRentalRateWrite):
    """Update rental rate binding."""


class AdminPreviewQuoteRoomLine(BaseModel):
    """Preview quote room line input."""

    facility_id: UUID = Field(..., description="Room ID")
    billed_hours: Decimal = Field(..., description="Billed hours")


class AdminPreviewQuoteRequest(BaseModel):
    """Preview quote request."""

    booking_type: str = Field(..., description="Booking type")
    is_mission_aligned: bool = Field(False, description="Mission aligned")
    currency: str = Field("CAD", description="Currency")
    as_of_date: Optional[date] = Field(None, description="Pricing as-of date")
    room_lines: list[AdminPreviewQuoteRoomLine] = Field(default_factory=list, description="Room lines")
    surcharge_codes: list[str] = Field(default_factory=list, description="Surcharge codes")


class AdminPreviewQuoteRoomLineResult(BaseModel):
    """Preview quote room line result with rule snapshot."""

    facility_id: UUID = Field(..., serialization_alias="facilityId", description="Room ID")
    billed_hours: Decimal = Field(..., serialization_alias="billedHours", description="Billed hours")
    rental_rate_name: str = Field(..., serialization_alias="rentalRateName", description="Rule display name")
    billing_unit: str = Field(..., serialization_alias="billingUnit", description="Billing unit")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount", description="Unit amount")
    currency: str = Field(..., description="Currency")
    applicability: Optional[dict] = Field(None, description="Applicability rule snapshot")
    is_default: bool = Field(False, serialization_alias="isDefault", description="Default flag snapshot")
    line_subtotal: Decimal = Field(..., serialization_alias="lineSubtotal", description="Line subtotal")


class AdminPreviewQuoteResponse(BaseModel):
    """Preview quote response."""

    subtotal_amount: Decimal = Field(..., serialization_alias="subtotalAmount", description="Subtotal")
    discount_percent: Decimal = Field(..., serialization_alias="discountPercent", description="Discount percent")
    discount_amount: Decimal = Field(..., serialization_alias="discountAmount", description="Discount amount")
    surcharge_amount: Decimal = Field(..., serialization_alias="surchargeAmount", description="Surcharge amount")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount", description="Quoted amount")
    currency: str = Field(..., description="Currency")
    room_lines: list[AdminPreviewQuoteRoomLineResult] = Field(default_factory=list, serialization_alias="roomLines", description="Room lines")
