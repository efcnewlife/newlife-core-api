"""
Rental catalog serializers.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminDiscountRuleItem(UUIDBaseModel):
    """Discount rule item."""

    code: str = Field(..., description="Discount code")
    percent_off: Decimal = Field(..., serialization_alias="percentOff", description="Percent off")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    description: Optional[str] = Field(None, description="Description")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")


class AdminDiscountRuleList(BaseModel):
    """Discount rule list."""

    items: list[AdminDiscountRuleItem] = Field(default_factory=list, description="Items")


class AdminDiscountRuleWrite(BaseModel):
    """Discount rule write."""

    code: str = Field(..., description="Discount code")
    percent_off: Decimal = Field(..., description="Percent off")
    is_active: bool = Field(True, description="Active flag")
    description: Optional[str] = Field(None, description="Description")


class AdminDiscountRuleCreate(AdminDiscountRuleWrite):
    """Create discount rule."""


class AdminDiscountRuleUpdate(AdminDiscountRuleWrite):
    """Update discount rule."""


class AdminSurchargeItem(UUIDBaseModel):
    """Surcharge item."""

    code: str = Field(..., description="Surcharge code")
    charge_type: str = Field(..., serialization_alias="chargeType", description="Charge type")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount", description="Unit amount")
    currency: str = Field(..., description="Currency")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    applies_to_booking_type: Optional[str] = Field(
        None,
        serialization_alias="appliesToBookingType",
        description="Booking type filter",
    )
    remark: Optional[str] = Field(None, description="Remark")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")


class AdminSurchargeList(BaseModel):
    """Surcharge list."""

    items: list[AdminSurchargeItem] = Field(default_factory=list, description="Items")


class AdminSurchargeWrite(BaseModel):
    """Surcharge write."""

    code: str = Field(..., description="Surcharge code")
    charge_type: str = Field(..., description="Charge type")
    unit_amount: Decimal = Field(..., description="Unit amount")
    currency: str = Field("CAD", description="Currency")
    is_active: bool = Field(True, description="Active flag")
    applies_to_booking_type: Optional[str] = Field(
        None,
        description="Booking type filter",
    )
    remark: Optional[str] = Field(None, description="Remark")


class AdminSurchargeCreate(AdminSurchargeWrite):
    """Create surcharge."""


class AdminSurchargeUpdate(AdminSurchargeWrite):
    """Update surcharge."""


class AdminPolicySettingItem(UUIDBaseModel):
    """Policy setting item."""

    setting_key: str = Field(..., serialization_alias="settingKey", description="Setting key")
    facility_id: Optional[UUID] = Field(None, serialization_alias="facilityId", description="Room ID")
    amount: Decimal = Field(..., description="Amount")
    currency: str = Field(..., description="Currency")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")


class AdminPolicySettingList(BaseModel):
    """Policy setting list."""

    items: list[AdminPolicySettingItem] = Field(default_factory=list, description="Items")


class AdminPolicySettingUpdate(BaseModel):
    """Policy setting update."""

    amount: Decimal = Field(..., description="Amount")
    currency: str = Field("CAD", description="Currency")
    is_active: bool = Field(True, description="Active flag")
