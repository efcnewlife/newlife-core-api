"""
Locale model
"""
import sqlalchemy as sa
from sqlalchemy import Column

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, SortableMixin, RemarkMixin


class SystemLocale(ModelBase, AuditMixin, DeletedMixin, SortableMixin, RemarkMixin):
    """System Locale Model"""
    __extra_table_args__ = (
        sa.UniqueConstraint("language_code", "script_code", "region_code"),
    )
    __schema__ = "public"
    language_code = Column(sa.String(16), nullable=False, comment="Language code (e.g., en, zh, etc.)")
    script_code = Column(sa.String(16), comment="Script code (e.g., Latn, Hant, etc.)")
    region_code = Column(sa.String(16), comment="Region code (e.g., US, TW, etc.)")
    name = Column(sa.String(64), comment="Locale name")
    native_name = Column(sa.String(64), comment="Native locale name")
    is_active = Column(sa.Boolean, default=True, comment="Is locale active")
    is_default = Column(sa.Boolean, default=False, comment="Is default locale")
