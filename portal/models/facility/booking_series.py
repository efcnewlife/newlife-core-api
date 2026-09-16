"""
Recurring Booking Series model.
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.constants import BookingStatus
from portal.libs.database.orm import ModelBase
from portal.models.auth.user import AuthUser
from portal.models.mixins import AuditMixin, DeletedMixin, RemarkMixin


class FacilityBookingSeries(ModelBase, AuditMixin, RemarkMixin, DeletedMixin):
    """Recurring Booking Series parent; occupancy lives on materialized Booking Occurrences."""

    __extra_table_args__ = (
        sa.CheckConstraint("last_occurrence_date >= first_occurrence_date", name="last_on_or_after_first"),
        sa.CheckConstraint("local_end_time > local_start_time", name="end_after_start"),
        sa.Index("ix_booking_series_user_id_status", "user_id", "status"),
        sa.Index("ix_booking_series_payment_hold_expires_at", "payment_hold_expires_at"),
    )

    user_id = Column(UUID, sa.ForeignKey(AuthUser.id, ondelete="NO ACTION"), nullable=False, index=True, comment="Booker user ID")
    ministry_id = Column(UUID, sa.ForeignKey("org.ministry.id", ondelete="SET NULL"), nullable=True, index=True, comment="Ministry reference (optional)")
    first_occurrence_date = Column(sa.Date, nullable=False, comment="First weekly occurrence date (facility local)")
    last_occurrence_date = Column(sa.Date, nullable=False, comment="Last weekly occurrence date (facility local)")
    local_start_time = Column(sa.Time, nullable=False, comment="Shared local start time for every occurrence line")
    local_end_time = Column(sa.Time, nullable=False, comment="Shared local end time for every occurrence line")
    status = Column(sa.String(32), nullable=False, server_default=BookingStatus.PENDING_PAYMENT.value, index=True, comment="Series status")
    payment_hold_expires_at = Column(sa.DateTime(timezone=True), nullable=True, comment="When an unpaid Pending-payment Series hold expires")
    billed_hours = Column(sa.Numeric(8, 2), comment="Sum of billed hours across occurrences")
    subtotal_amount = Column(sa.Numeric(12, 2), comment="Series pre-discount subtotal")
    discount_percent = Column(sa.Numeric(5, 2), comment="Applied discount percent snapshot")
    discount_amount = Column(sa.Numeric(12, 2), comment="Series discount amount")
    surcharge_amount = Column(sa.Numeric(12, 2), comment="Series surcharge subtotal")
    quoted_amount = Column(sa.Numeric(12, 2), comment="Series payment total")
    currency = Column(sa.String(8), comment="Currency code aligned with rental rates")
    is_mission_aligned = Column(sa.Boolean, nullable=False, server_default=sa.text("false"), comment="Mission-aligned discount eligibility")
    is_priority = Column(sa.Boolean, nullable=False, server_default=sa.text("false"), comment="Priority Ministry snapshot at create")

    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
    ministry = relationship("OrgMinistry", passive_deletes=True)
    bookings = relationship("FacilityBooking", back_populates="series", passive_deletes=True)
