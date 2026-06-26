"""
Facility room models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, DescriptionMixin, RemarkMixin, SortableMixin
from portal.models.system_locale import SystemLocale


class FacilityRoom(ModelBase, AuditMixin, SortableMixin, DeletedMixin):
    """Facility room / venue."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Stable room code")
    room_number = Column(sa.String(16), comment="Physical room number (e.g. 124, G19)")
    capacity = Column(sa.Integer, comment="Capacity (persons)")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        index=True,
        comment="Active flag; inactive rooms cannot accept new bookings",
    )

    __extra_table_args__ = (
        sa.Index("ix_room_is_active_sequence", "is_active", "sequence"),
    )

    translations = relationship(
        "FacilityRoomTranslation",
        back_populates="room",
        passive_deletes=True,
    )


class FacilityRoomTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Localized room content."""
    __extra_table_args__ = (
        sa.UniqueConstraint("room_id", "locale_id"),
    )

    room_id = Column(
        UUID,
        sa.ForeignKey(FacilityRoom.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Room ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Localized room name")

    room = relationship("FacilityRoom", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")
