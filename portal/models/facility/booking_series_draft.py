"""
Recurring Series Draft models.
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.booking_title import BOOKING_TITLE_MAX_LENGTH, BOOKING_TITLE_MIN_LENGTH
from portal.libs.database.orm import ModelBase
from portal.models.auth.user import AuthUser
from portal.models.facility.room import FacilityRoom
from portal.models.mixins import AuditMixin


class FacilityBookingSeriesDraft(ModelBase, AuditMixin):
    """Standalone, non-locking snapshot of a member's Recurring Booking Series proposal."""

    __extra_table_args__ = (
        sa.CheckConstraint("last_occurrence_date >= first_occurrence_date", name="last_on_or_after_first"),
        sa.CheckConstraint("local_end_time > local_start_time", name="end_after_start"),
        sa.CheckConstraint(
            f"title IS NULL OR (char_length(btrim(title)) >= {BOOKING_TITLE_MIN_LENGTH} AND char_length(title) <= {BOOKING_TITLE_MAX_LENGTH})",
            name="title_length",
        ),
        sa.Index("ix_booking_series_draft_user_id", "user_id"),
    )

    user_id = Column(UUID, sa.ForeignKey(AuthUser.id, ondelete="CASCADE"), nullable=False, index=True, comment="Creating member; only this user may read/edit")
    title = Column(sa.String(BOOKING_TITLE_MAX_LENGTH), nullable=True, comment="Optional Booker-owned plain-text label before confirm")
    ministry_id = Column(UUID, sa.ForeignKey("org.ministry.id", ondelete="SET NULL"), nullable=True, comment="Ministry reference (optional)")
    first_occurrence_date = Column(sa.Date, nullable=False, comment="First weekly occurrence date (facility local)")
    last_occurrence_date = Column(sa.Date, nullable=False, comment="Last weekly occurrence date (facility local)")
    local_start_time = Column(sa.Time, nullable=False, comment="Shared local start time for every occurrence line")
    local_end_time = Column(sa.Time, nullable=False, comment="Shared local end time for every occurrence line")
    is_mission_aligned = Column(sa.Boolean, nullable=False, server_default=sa.text("false"), comment="Mission-aligned discount eligibility")
    remark = Column(sa.Text, nullable=True, comment="Optional Booker remark")
    surcharge_codes = Column(ARRAY(sa.String(64)), nullable=False, server_default=sa.text("'{}'"), comment="Selected surcharge codes")
    excluded_dates = Column(ARRAY(sa.Date), nullable=False, server_default=sa.text("'{}'"), comment="Permitted excluded occurrence dates")

    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
    ministry = relationship("OrgMinistry", passive_deletes=True)
    rooms = relationship(
        "FacilityBookingSeriesDraftRoom", back_populates="series_draft", passive_deletes=True, order_by="FacilityBookingSeriesDraftRoom.sequence"
    )


class FacilityBookingSeriesDraftRoom(ModelBase, AuditMixin):
    """One proposed room on a Recurring Series Draft; all rooms share the Draft time window."""

    __extra_table_args__ = (sa.Index("ix_booking_series_draft_room_series_draft_id", "series_draft_id"),)

    series_draft_id = Column(UUID, sa.ForeignKey(FacilityBookingSeriesDraft.id, ondelete="CASCADE"), nullable=False, comment="Recurring Series Draft ID")
    facility_id = Column(UUID, sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"), nullable=False, comment="Selected room ID")
    sequence = Column(sa.Integer, nullable=False, server_default=sa.text("0"), comment="Display order")

    series_draft = relationship("FacilityBookingSeriesDraft", back_populates="rooms", passive_deletes=True)
    room = relationship("FacilityRoom", passive_deletes=True)
