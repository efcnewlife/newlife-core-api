"""
Facility room slot template models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin
from portal.models.facility.room import FacilityRoom


class FacilityRoomSlotTemplate(ModelBase, AuditMixin, DeletedMixin):
    """Weekly slot template for a room."""
    __extra_table_args__ = (
        sa.CheckConstraint(
            "(days_of_week_mask & 127) != 0",
            name="days_of_week_mask_nonzero",
        ),
        sa.CheckConstraint(
            "(days_of_week_mask & ~127) = 0",
            name="days_of_week_mask_valid_bits",
        ),
        sa.CheckConstraint(
            "start_time < end_time",
            name="start_before_end",
        ),
        sa.CheckConstraint(
            "slot_duration_minutes > 0",
            name="slot_duration_positive",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to",
            name="effective_date_order",
        ),
        sa.Index("ix_room_slot_template_facility_active", "facility_id", "is_active"),
        sa.Index("ix_room_slot_template_facility_id", "facility_id"),
    )

    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=False,
        comment="Room ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Template label (admin)")
    days_of_week_mask = Column(
        sa.SmallInteger,
        nullable=False,
        comment="Bitmask of ISO weekdays: bit0=Monday(0) ... bit6=Sunday(6)",
    )
    start_time = Column(sa.Time, nullable=False, comment="Local start time")
    end_time = Column(sa.Time, nullable=False, comment="Local end time")
    slot_duration_minutes = Column(sa.Integer, nullable=False, comment="Grid step in minutes (e.g. 60)")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    effective_from = Column(sa.Date, comment="Seasonal effective start (inclusive)")
    effective_to = Column(sa.Date, comment="Seasonal effective end (inclusive)")

    room = relationship("FacilityRoom", passive_deletes=True)
