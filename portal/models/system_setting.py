"""
System runtime setting model.
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, RemarkMixin


class SystemSetting(ModelBase, AuditMixin, DeletedMixin, RemarkMixin):
    """System runtime setting (namespace + key + JSON value)."""

    __schema__ = "public"
    __extra_table_args__ = (
        sa.UniqueConstraint("namespace", "setting_key"),
        sa.Index("ix_system_setting_namespace_key_active", "namespace", "setting_key", "is_active"),
    )

    namespace = Column(sa.String(64), nullable=False, comment="Setting namespace")
    setting_key = Column(sa.String(64), nullable=False, comment="Setting key within namespace")
    value_type = Column(sa.String(32), nullable=False, comment="Declared value type (SettingValueType)")
    value = Column(JSONB, nullable=False, comment="JSON value matching value_type")
    is_built_in = Column(sa.Boolean, nullable=False, server_default=sa.text("false"), comment="Built-in settings cannot be deleted")
    is_active = Column(sa.Boolean, nullable=False, server_default=sa.text("true"), index=True, comment="Active flag")
