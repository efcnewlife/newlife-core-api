"""
Facility booking draft models.
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.domain.facility.booking_title import BOOKING_TITLE_MAX_LENGTH, BOOKING_TITLE_MIN_LENGTH
from portal.libs.database.orm import ModelBase
from portal.models.auth.user import AuthUser
from portal.models.facility.room import FacilityRoom
from portal.models.mixins import AuditMixin


class FacilityBookingDraft(ModelBase, AuditMixin):
    """Standalone, non-locking snapshot of a member's proposed Booking lines (ADR 0018)."""

    __extra_table_args__ = (
        sa.Index("ix_booking_draft_user_id", "user_id"),
        sa.CheckConstraint(
            f"char_length(btrim(title)) >= {BOOKING_TITLE_MIN_LENGTH} AND char_length(title) <= {BOOKING_TITLE_MAX_LENGTH}", name="title_length"
        ),
    )

    user_id = Column(UUID, sa.ForeignKey(AuthUser.id, ondelete="CASCADE"), nullable=False, index=True, comment="Creating member; only this user may read/edit")
    title = Column(sa.String(BOOKING_TITLE_MAX_LENGTH), nullable=False, comment="Booker-owned plain-text label")
    date = Column(sa.Date, nullable=False, comment="Local calendar day common to all lines")
    ministry_id = Column(UUID, sa.ForeignKey("org.ministry.id", ondelete="SET NULL"), nullable=True, comment="Ministry reference (optional)")

    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
    ministry = relationship("OrgMinistry", passive_deletes=True)
    lines = relationship("FacilityBookingDraftLine", back_populates="booking_draft", passive_deletes=True, order_by="FacilityBookingDraftLine.sequence")


class FacilityBookingDraftLine(ModelBase, AuditMixin):
    """One proposed room interval on a Booking Draft."""

    __extra_table_args__ = (
        sa.CheckConstraint("end_at > start_at", name="end_after_start"),
        sa.Index("ix_booking_draft_line_booking_draft_id", "booking_draft_id"),
    )

    booking_draft_id = Column(UUID, sa.ForeignKey(FacilityBookingDraft.id, ondelete="CASCADE"), nullable=False, comment="Booking Draft ID")
    facility_id = Column(UUID, sa.ForeignKey(FacilityRoom.id, ondelete="NO ACTION"), nullable=False, comment="Selected room ID")
    sequence = Column(sa.Integer, nullable=False, server_default=sa.text("0"), comment="Display order")
    start_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Line interval start (UTC)")
    end_at = Column(sa.DateTime(timezone=True), nullable=False, comment="Line interval end (UTC)")

    booking_draft = relationship("FacilityBookingDraft", back_populates="lines", passive_deletes=True)
    room = relationship("FacilityRoom", passive_deletes=True)
