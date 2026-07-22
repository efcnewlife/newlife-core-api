"""
Facility room blackout models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin
from portal.models.facility.room import FacilityRoom


class FacilityRoomBlackout(ModelBase, AuditMixin, DeletedMixin):
    """Closed / unavailable window for a room or all rooms."""

    __extra_table_args__ = (
        sa.CheckConstraint(
            "kind IN ('one_off', 'recurring')",
            name="kind_valid",
        ),
        sa.CheckConstraint(
            "("
            "kind = 'one_off' AND blackout_date IS NOT NULL AND days_of_week_mask IS NULL"
            ") OR ("
            "kind = 'recurring' AND blackout_date IS NULL AND days_of_week_mask IS NOT NULL "
            "AND (days_of_week_mask & 127) != 0 AND (days_of_week_mask & ~127) = 0"
            ")",
            name="kind_shape",
        ),
        sa.CheckConstraint(
            "start_time < end_time",
            name="start_before_end",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to",
            name="effective_date_order",
        ),
        sa.Index("ix_room_blackout_facility_active", "facility_id", "is_active"),
        sa.Index("ix_room_blackout_kind_date", "kind", "blackout_date"),
        sa.Index("ix_room_blackout_is_active", "is_active"),
    )

    facility_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=True,
        comment="Room ID; NULL means all rooms (campus-wide)",
    )
    name = Column(sa.String(255), nullable=False, comment="Blackout label (admin)")
    reason = Column(sa.String(500), nullable=False, comment="Required admin-only reason")
    kind = Column(
        sa.String(32),
        nullable=False,
        comment="one_off or recurring",
    )
    blackout_date = Column(sa.Date, comment="Local date for one_off blackouts")
    days_of_week_mask = Column(
        sa.SmallInteger,
        comment="Bitmask of ISO weekdays for recurring blackouts: bit0=Monday(0) ... bit6=Sunday(6)",
    )
    start_time = Column(sa.Time, nullable=False, comment="Local start time")
    end_time = Column(sa.Time, nullable=False, comment="Local end time")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    effective_from = Column(sa.Date, comment="Seasonal effective start (inclusive), recurring")
    effective_to = Column(sa.Date, comment="Seasonal effective end (inclusive), recurring")

    room = relationship("FacilityRoom", passive_deletes=True)
