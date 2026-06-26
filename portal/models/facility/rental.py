"""
Facility rental rate, discount, surcharge, and policy models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.constants import RentalRateBillingUnit
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, DescriptionMixin, RemarkMixin, SortableMixin
from portal.models.system_locale import SystemLocale
from portal.models.facility.room import FacilityRoom


class FacilityRentalRate(ModelBase, AuditMixin, SortableMixin, DeletedMixin):
    """Per-room fee schedule row."""
    __extra_table_args__ = (
        sa.CheckConstraint("unit_amount >= 0", name="unit_amount_non_negative"),
        sa.UniqueConstraint("facility_id", "billing_unit", "effective_from", name="uq_rental_rate_facility_unit_effective"),
        sa.Index("ix_rental_rate_facility_active", "facility_id", "is_active"),
    )

    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Room ID",
    )
    billing_unit = Column(
        sa.String(32),
        nullable=False,
        server_default=RentalRateBillingUnit.HOURLY.value,
        comment="Billing unit (RentalRateBillingUnit)",
    )
    unit_amount = Column(sa.Numeric(12, 2), nullable=False, comment="Unit price")
    currency = Column(sa.String(8), nullable=False, server_default="CAD", comment="Currency code")
    is_default = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="Fallback row for pricing (usually hourly)",
    )
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    effective_from = Column(sa.Date, comment="Price version effective start")
    effective_to = Column(sa.Date, comment="Price version effective end")

    room = relationship("FacilityRoom", passive_deletes=True)
    translations = relationship(
        "FacilityRentalRateTranslation",
        back_populates="rental_rate",
        passive_deletes=True,
    )


class FacilityRentalRateTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Localized rental rate display content."""
    __extra_table_args__ = (
        sa.UniqueConstraint("rental_rate_id", "locale_id"),
    )

    rental_rate_id = Column(
        UUID,
        sa.ForeignKey(FacilityRentalRate.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Rental rate ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Display name")

    rental_rate = relationship("FacilityRentalRate", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class FacilityRentalDiscountRule(ModelBase, AuditMixin, DeletedMixin):
    """Rental discount rule definition (PDF section 4b-4c)."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Discount code (RentalDiscountCode)")
    percent_off = Column(sa.Numeric(5, 2), nullable=False, comment="Discount percent (e.g. 20.00, 30.00)")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    description = Column(sa.String(500), comment="Policy description")


class FacilityRentalSurcharge(ModelBase, AuditMixin, RemarkMixin, DeletedMixin):
    """Rental surcharge catalog item."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Surcharge code (RentalSurchargeCode)")
    charge_type = Column(
        sa.String(32),
        nullable=False,
        comment="Charge type (RentalSurchargeChargeType)",
    )
    unit_amount = Column(sa.Numeric(12, 2), nullable=False, comment="Unit amount")
    currency = Column(sa.String(8), nullable=False, server_default="CAD", comment="Currency code")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    applies_to_booking_type = Column(
        sa.String(32),
        comment="Optional booking type filter (e.g. one_time for deposit)",
    )


class FacilityRentalPolicySetting(ModelBase, AuditMixin, DeletedMixin):
    """Rental policy parameter (minimum fee, daily flat threshold, etc.)."""
    __extra_table_args__ = (
        sa.UniqueConstraint("setting_key", "facility_id"),
    )

    setting_key = Column(sa.String(64), nullable=False, comment="Setting key (RentalPolicySettingKey)")
    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Room ID; NULL = global default",
    )
    amount = Column(sa.Numeric(12, 2), nullable=False, comment="Setting amount or numeric value")
    currency = Column(sa.String(8), nullable=False, server_default="CAD", comment="Currency code")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    room = relationship("FacilityRoom", passive_deletes=True)
