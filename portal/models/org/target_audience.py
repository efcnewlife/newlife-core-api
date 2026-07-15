"""
Organization target audience catalog models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DescriptionMixin, SortableMixin
from portal.models.org.ministry import OrgMinistry
from portal.models.system_locale import SystemLocale


class OrgTargetAudience(ModelBase, AuditMixin, SortableMixin):
    """Target audience catalog (children, youths, adults, etc.)."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Stable target audience code")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    translations = relationship(
        "OrgTargetAudienceTranslation",
        back_populates="target_audience",
        passive_deletes=True,
    )
    ministry_links = relationship(
        "OrgMinistryTargetAudience",
        back_populates="target_audience",
        passive_deletes=True,
    )


class OrgTargetAudienceTranslation(ModelBase, AuditMixin, DescriptionMixin):
    """Localized target audience label."""
    __extra_table_args__ = (
        sa.UniqueConstraint("target_audience_id", "locale_id"),
    )

    target_audience_id = Column(
        UUID,
        sa.ForeignKey(OrgTargetAudience.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target audience ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Localized target audience name")

    target_audience = relationship("OrgTargetAudience", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class OrgMinistryTargetAudience(ModelBase, AuditMixin):
    """Ministry to target audience assignment (many-to-many)."""
    __extra_table_args__ = (
        sa.UniqueConstraint("ministry_id", "target_audience_id"),
    )

    ministry_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistry.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ministry ID",
    )
    target_audience_id = Column(
        UUID,
        sa.ForeignKey(OrgTargetAudience.id, ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Target audience ID",
    )

    ministry = relationship("OrgMinistry", back_populates="target_audience_links", passive_deletes=True)
    target_audience = relationship("OrgTargetAudience", back_populates="ministry_links", passive_deletes=True)
