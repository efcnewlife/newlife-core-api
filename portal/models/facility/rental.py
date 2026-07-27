"""
Facility rental rate template, rate, discount, surcharge, and policy models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.constants import RentalRateBillingUnit
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, RemarkMixin
from portal.models.facility.room import FacilityRoom


class FacilityRentalRateTemplate(ModelBase, AuditMixin, DeletedMixin):
    """Shared rental billing rule template with default unit amount."""
    __extra_table_args__ = (
        sa.UniqueConstraint("name", name="uq_rental_rate_template_name"),
        sa.CheckConstraint("unit_amount >= 0", name="template_unit_amount_non_negative"),
        sa.Index("ix_rental_rate_template_is_active", "is_active"),
    )

    name = Column(sa.String(255), nullable=False, comment="Display name")
    billing_unit = Column(
        sa.String(32),
        nullable=False,
        server_default=RentalRateBillingUnit.HOURLY.value,
        comment="Billing unit (RentalRateBillingUnit)",
    )
    applicability = Column(
        JSONB,
        comment="JSON applicability rule; null means always eligible",
    )
    unit_amount = Column(
        sa.Numeric(12, 2),
        nullable=False,
        comment="Default / global unit price",
    )
    currency = Column(
        sa.String(8),
        nullable=False,
        server_default="CAD",
        comment="Currency code",
    )
    is_default = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="Fallback template for pricing",
    )
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    rates = relationship(
        "FacilityRentalRate",
        back_populates="template",
        passive_deletes=True,
    )


class FacilityRentalRate(ModelBase, AuditMixin, DeletedMixin):
    """Room binding of a rate template (price always from template)."""
    __extra_table_args__ = (
        sa.UniqueConstraint(
            "facility_id",
            "template_id",
            name="uq_rental_rate_facility_template",
        ),
        sa.Index("ix_rental_rate_facility_active", "facility_id", "is_active"),
        sa.Index("ix_rental_rate_template_id", "template_id"),
    )

    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Room ID",
    )
    template_id = Column(
        UUID,
        sa.ForeignKey(FacilityRentalRateTemplate.id, ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Rate template ID",
    )
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    room = relationship("FacilityRoom", passive_deletes=True)
    template = relationship("FacilityRentalRateTemplate", back_populates="rates", passive_deletes=True)


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
