"""
Rental rate serializers.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.domain.facility.constants import RentalRateBillingUnit
from portal.serializers.admin.v1.facility.translation import (
    AdminFacilityTranslationInput,
    AdminFacilityTranslationItem,
    validate_unique_facility_locale_ids,
)
from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRentalRateQuery(GenericQueryBaseModel):
    """Paginated rental rate list filters."""

    facility_id: Optional[UUID] = Field(default=None)


class AdminRentalRateItem(UUIDBaseModel):
    """Rental rate item."""

    facility_id: UUID = Field(..., serialization_alias="facilityId", description="Room ID")
    billing_unit: str = Field(..., serialization_alias="billingUnit", description="Billing unit")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount", description="Unit amount")
    currency: str = Field(..., description="Currency")
    is_default: bool = Field(False, serialization_alias="isDefault", description="Default rate flag")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    applicability: Optional[dict] = Field(None, description="JSON applicability rule; null = always eligible")
    effective_from: Optional[date] = Field(None, serialization_alias="effectiveFrom", description="Effective from")
    effective_to: Optional[date] = Field(None, serialization_alias="effectiveTo", description="Effective to")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    remark: Optional[str] = Field(None, description="Remark")
    name: Optional[str] = Field(None, description="Display name")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    translations: list[AdminFacilityTranslationItem] = Field(default_factory=list, description="Translations")


class AdminRentalRatePages(PaginationBaseResponseModel):
    """Paginated rental rates."""

    items: list[AdminRentalRateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateList(BaseModel):
    """Rental rate list."""

    items: list[AdminRentalRateItem] = Field(default_factory=list, description="Items")


class AdminRentalRateWrite(BaseModel):
    """Rental rate write."""

    facility_id: UUID = Field(..., description="Room ID")
    billing_unit: RentalRateBillingUnit = Field(
        RentalRateBillingUnit.HOURLY,
        description="Billing unit",
    )
    unit_amount: Decimal = Field(..., description="Unit amount")
    currency: str = Field("CAD", description="Currency")
    is_default: bool = Field(False, description="Default rate flag")
    is_active: bool = Field(True, description="Active flag")
    applicability: Optional[dict] = Field(None, description="JSON applicability rule; null = always eligible")
    effective_from: Optional[date] = Field(None, description="Effective from")
    effective_to: Optional[date] = Field(None, description="Effective to")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    name: Optional[str] = Field(None, description="Display name")
    translations: Optional[list[AdminFacilityTranslationInput]] = Field(None, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_facility_locale_ids(value)


class AdminRentalRateCreate(AdminRentalRateWrite):
    """Create rental rate."""

    translations: list[AdminFacilityTranslationInput] = Field(..., min_length=1, description="Translations")


class AdminRentalRateUpdate(AdminRentalRateWrite):
    """Update rental rate."""


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
    room_lines: list[AdminPreviewQuoteRoomLine] = Field(
        default_factory=list,
        description="Room lines",
    )
    surcharge_codes: list[str] = Field(
        default_factory=list,
        description="Surcharge codes",
    )


class AdminPreviewQuoteRoomLineResult(BaseModel):
    """Preview quote room line result."""

    facility_id: UUID = Field(..., serialization_alias="facilityId", description="Room ID")
    billed_hours: Decimal = Field(..., serialization_alias="billedHours", description="Billed hours")
    pricing_tier_used: str = Field(..., serialization_alias="pricingTierUsed", description="Pricing tier")
    rental_rate_id: Optional[UUID] = Field(None, serialization_alias="rentalRateId", description="Rental rate ID")
    line_subtotal: Decimal = Field(..., serialization_alias="lineSubtotal", description="Line subtotal")


class AdminPreviewQuoteResponse(BaseModel):
    """Preview quote response."""

    subtotal_amount: Decimal = Field(..., serialization_alias="subtotalAmount", description="Subtotal")
    discount_percent: Decimal = Field(..., serialization_alias="discountPercent", description="Discount percent")
    discount_amount: Decimal = Field(..., serialization_alias="discountAmount", description="Discount amount")
    surcharge_amount: Decimal = Field(..., serialization_alias="surchargeAmount", description="Surcharge amount")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount", description="Quoted amount")
    currency: str = Field(..., description="Currency")
    room_lines: list[AdminPreviewQuoteRoomLineResult] = Field(
        default_factory=list,
        serialization_alias="roomLines",
        description="Room lines",
    )
