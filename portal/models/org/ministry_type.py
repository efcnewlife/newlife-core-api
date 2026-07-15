"""
Organization ministry type catalog models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DescriptionMixin, SortableMixin
from portal.models.system_locale import SystemLocale


class OrgMinistryType(ModelBase, AuditMixin, SortableMixin):
    """Ministry type catalog (outreach, internal, worship, etc.)."""
    code = Column(sa.String(64), nullable=False, unique=True, comment="Stable ministry type code")
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )

    translations = relationship(
        "OrgMinistryTypeTranslation",
        back_populates="ministry_type",
        passive_deletes=True,
    )


class OrgMinistryTypeTranslation(ModelBase, AuditMixin, DescriptionMixin):
    """Localized ministry type label."""
    __extra_table_args__ = (
        sa.UniqueConstraint("ministry_type_id", "locale_id"),
    )

    ministry_type_id = Column(
        UUID,
        sa.ForeignKey("org.ministry_type.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ministry type ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Localized ministry type name")

    ministry_type = relationship("OrgMinistryType", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")
