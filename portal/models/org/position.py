"""
Organization position models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, DescriptionMixin, RemarkMixin, SortableMixin
from portal.models.system_locale import SystemLocale


class OrgPosition(ModelBase, AuditMixin, SortableMixin, DeletedMixin):
    """Church leadership position catalog."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Stable position code")
    can_own_ministry = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="Whether this position can own a ministry",
    )
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    translations = relationship(
        "OrgPositionTranslation",
        back_populates="position",
        passive_deletes=True,
    )
    assignments = relationship(
        "OrgPositionAssignment",
        back_populates="position",
        passive_deletes=True,
    )


class OrgPositionTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Localized position name; team/office store enum codes."""
    __extra_table_args__ = (
        sa.UniqueConstraint("position_id", "locale_id"),
    )

    position_id = Column(
        UUID,
        sa.ForeignKey(OrgPosition.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Position ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    team = Column(sa.String(128), nullable=False, comment="PositionTeam enum code")
    office = Column(sa.String(64), nullable=False, comment="PositionOffice enum code")
    name = Column(sa.String(255), nullable=False, comment="Localized position name")

    position = relationship("OrgPosition", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class OrgPositionAssignment(ModelBase, AuditMixin):
    """Position incumbent history (single current row per position)."""
    __extra_table_args__ = (
        sa.Index("ix_position_assignment_position_id_end_at", "position_id", "end_at"),
    )

    position_id = Column(
        UUID,
        sa.ForeignKey(OrgPosition.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Position ID",
    )
    user_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Incumbent user ID",
    )
    start_at = Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        comment="Assignment start",
    )
    end_at = Column(sa.DateTime(timezone=True), comment="Assignment end; null = current")

    position = relationship("OrgPosition", back_populates="assignments", passive_deletes=True)
    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
