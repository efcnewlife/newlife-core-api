"""
Facility booking models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.constants import BookingSlotStatus, BookingStatus
from portal.libs.database.orm import ModelBase
from portal.models.auth.user import AuthUser
from portal.models.facility.rental import FacilityRentalRate, FacilityRentalSurcharge
from portal.models.facility.room import FacilityRoom
from portal.models.mixins import AuditCreatedMixin, AuditMixin, DeletedMixin, RemarkMixin


class FacilityBooking(ModelBase, AuditMixin, RemarkMixin, DeletedMixin):
    """Facility booking master record."""
    __extra_table_args__ = (
        sa.CheckConstraint("end_at > start_at", name="end_after_start"),
        sa.Index("ix_booking_facility_id_start_at", "facility_id", "start_at"),
        sa.Index("ix_booking_user_id_status", "user_id", "status"),
        sa.Index("ix_booking_status_start_at", "status", "start_at"),
    )

    user_id = Column(
        UUID,
        sa.ForeignKey(AuthUser.id, ondelete="NO ACTION"),
        nullable=False,
        index=True,
        comment="Booker user ID",
    )
    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"),
        nullable=True,
        index=True,
        comment="Optional primary room for list filters; multi-room lines use booking_room",
    )
    ministry_id = Column(
        UUID,
        sa.ForeignKey("org.ministry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Ministry reference (optional)",
    )
    booking_type = Column(sa.String(32), nullable=False, comment="Booking type (BookingType)")
    start_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Booking start (UTC)")
    end_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Booking end (UTC)")
    recurrence_rule = Column(
        sa.String(255),
        comment="iCal RRULE string (RFC 5545); series anchor is start_at",
    )
    recurrence_end_at = Column(sa.DateTime(timezone=True), comment="Recurrence series end")
    status = Column(
        sa.String(32),
        nullable=False,
        server_default=BookingStatus.DRAFT.value,
        index=True,
        comment="Booking status (BookingStatus)",
    )
    is_mission_aligned = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="Mission-aligned discount eligibility (PDF section 4c)",
    )
    billed_hours = Column(sa.Numeric(8, 2), comment="Total billed hours snapshot")
    subtotal_amount = Column(sa.Numeric(12, 2), comment="Pre-discount subtotal snapshot")
    discount_percent = Column(sa.Numeric(5, 2), comment="Applied discount percent snapshot (0/20/30)")
    discount_amount = Column(sa.Numeric(12, 2), comment="Discount amount snapshot")
    surcharge_amount = Column(sa.Numeric(12, 2), comment="Surcharge subtotal snapshot")
    quoted_amount = Column(sa.Numeric(12, 2), comment="Final quoted amount after floor rules")
    deposit_amount = Column(sa.Numeric(12, 2), comment="Deposit amount snapshot (not collected in this phase)")
    currency = Column(sa.String(8), comment="Currency code aligned with rental rates")
    cancelled_at = Column(sa.DateTime(timezone=True), comment="Cancellation timestamp")
    cancelled_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who cancelled the booking",
    )
    cancel_reason = Column(sa.String(500), comment="Cancellation reason")

    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
    room = relationship("FacilityRoom", foreign_keys=[facility_id], passive_deletes=True)
    ministry = relationship("OrgMinistry", passive_deletes=True)
    booking_rooms = relationship(
        "FacilityBookingRoom",
        back_populates="booking",
        passive_deletes=True,
    )
    booking_slots = relationship(
        "FacilityBookingSlot",
        back_populates="booking",
        passive_deletes=True,
    )
    booking_surcharges = relationship(
        "FacilityBookingSurcharge",
        back_populates="booking",
        passive_deletes=True,
    )
    override_logs = relationship(
        "FacilityBookingOverrideLog",
        back_populates="booking",
        foreign_keys="FacilityBookingOverrideLog.facility_booking_id",
        passive_deletes=True,
    )


class FacilityBookingRoom(ModelBase, AuditMixin):
    """Selected room line on a booking with per-room pricing snapshot."""
    __extra_table_args__ = (
        sa.CheckConstraint("end_at > start_at", name="end_after_start"),
        sa.UniqueConstraint("facility_booking_id", "facility_id", name="uq_booking_room_booking_facility"),
        sa.Index("ix_booking_room_booking_id", "facility_booking_id"),
        sa.Index("ix_booking_room_facility_id", "facility_id"),
    )

    facility_booking_id = Column(
        UUID,
        sa.ForeignKey(FacilityBooking.id, ondelete="CASCADE"),
        nullable=False,
        comment="Booking ID",
    )
    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"),
        nullable=False,
        comment="Selected room ID",
    )
    sequence = Column(sa.Integer, nullable=False, server_default=sa.text("0"), comment="Display order")
    start_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Room interval start (UTC)")
    end_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Room interval end (UTC)")
    billed_hours = Column(sa.Numeric(8, 2), comment="Billed hours for this room line")
    pricing_tier_used = Column(sa.String(32), comment="Pricing tier used (hourly or daily_flat)")
    rental_rate_id = Column(
        UUID,
        sa.ForeignKey(FacilityRentalRate.id, ondelete="SET NULL"),
        nullable=True,
        comment="Applied rental rate row",
    )
    line_subtotal = Column(sa.Numeric(12, 2), comment="Pre-discount room line subtotal")

    booking = relationship("FacilityBooking", back_populates="booking_rooms", passive_deletes=True)
    room = relationship("FacilityRoom", passive_deletes=True)
    rental_rate = relationship("FacilityRentalRate", passive_deletes=True)


class FacilityBookingSlot(ModelBase, AuditMixin):
    """Expanded booking slot for occupancy and overlap checks."""
    __extra_table_args__ = (
        sa.CheckConstraint("end_at > start_at", name="end_after_start"),
        sa.Index("ix_booking_slot_facility_id_start_at_end_at", "facility_id", "start_at", "end_at"),
        sa.Index("ix_booking_slot_booking_id", "facility_booking_id"),
    )

    facility_booking_id = Column(
        UUID,
        sa.ForeignKey(FacilityBooking.id, ondelete="CASCADE"),
        nullable=False,
        comment="Booking ID",
    )
    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"),
        nullable=False,
        comment="Room ID (denormalized for queries)",
    )
    start_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Slot start (UTC)")
    end_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Slot end (UTC)")
    status = Column(
        sa.String(32),
        nullable=False,
        server_default=BookingSlotStatus.CONFIRMED.value,
        comment="Slot status (BookingSlotStatus)",
    )

    booking = relationship("FacilityBooking", back_populates="booking_slots", passive_deletes=True)
    room = relationship("FacilityRoom", passive_deletes=True)


class FacilityBookingSurcharge(ModelBase, AuditCreatedMixin):
    """Applied surcharge line on a booking with pricing snapshot."""
    facility_booking_id = Column(
        UUID,
        sa.ForeignKey(FacilityBooking.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Booking ID",
    )
    rental_surcharge_id = Column(
        UUID,
        sa.ForeignKey(FacilityRentalSurcharge.id, ondelete="NO ACTION"),
        nullable=False,
        comment="Rental surcharge catalog ID",
    )
    quantity = Column(sa.Numeric(10, 2), nullable=False, comment="Quantity (hours or programs)")
    unit_amount = Column(sa.Numeric(12, 2), nullable=False, comment="Unit amount snapshot")
    line_amount = Column(sa.Numeric(12, 2), nullable=False, comment="Line amount snapshot")

    booking = relationship("FacilityBooking", back_populates="booking_surcharges", passive_deletes=True)
    rental_surcharge = relationship("FacilityRentalSurcharge", passive_deletes=True)


class FacilityBookingOverrideLog(ModelBase, AuditCreatedMixin):
    """Ministry priority override audit log (append-only)."""
    __extra_table_args__ = (
        sa.Index("ix_booking_override_log_created_at", "created_at"),
        sa.Index("ix_booking_override_log_facility_id_created_at", "facility_id", "created_at"),
        sa.Index("ix_booking_override_log_overridden_by_id", "overridden_by_id"),
    )

    facility_booking_id = Column(
        UUID,
        sa.ForeignKey(FacilityBooking.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Override target booking ID",
    )
    overridden_booking_id = Column(
        UUID,
        sa.ForeignKey(FacilityBooking.id, ondelete="SET NULL"),
        nullable=True,
        comment="Overridden booking ID",
    )
    overridden_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="NO ACTION"),
        nullable=False,
        comment="User who performed the override",
    )
    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"),
        nullable=False,
        comment="Room ID (denormalized for admin filters)",
    )
    outcome = Column(sa.String(32), nullable=False, comment="Override outcome (OverrideOutcome)")
    reason = Column(sa.String(500), comment="Override reason")

    booking = relationship(
        "FacilityBooking",
        back_populates="override_logs",
        foreign_keys=[facility_booking_id],
        passive_deletes=True,
    )
    overridden_booking = relationship(
        "FacilityBooking",
        foreign_keys=[overridden_booking_id],
        passive_deletes=True,
    )
    overridden_by = relationship("AuthUser", foreign_keys=[overridden_by_id], passive_deletes=True)
    room = relationship("FacilityRoom", passive_deletes=True)
