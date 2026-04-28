"""
RBAC models: roles, resources, verbs, permissions and their associations.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.consts.enums import ResourceType
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, SortableMixin, DescriptionMixin, RemarkMixin
from portal.models.system_locale import SystemLocale
from .relationships import AuthUserRole, AuthRolePermission


class AuthRole(ModelBase, AuditMixin, DeletedMixin):
    """Portal Role Model for RBAC"""
    code = Column(sa.String(32), nullable=False, unique=True, comment="Role code")
    is_active = Column(sa.Boolean, default=True, comment="Is role active")

    # Relationships
    translations = relationship("AuthRoleTranslation", back_populates="role", passive_deletes=True)
    users = relationship("AuthUser", secondary=lambda: AuthUserRole.__table__, back_populates="roles", passive_deletes=True)
    permissions = relationship("AuthPermission", secondary=lambda: AuthRolePermission.__table__, back_populates="roles", passive_deletes=True)


class AuthRoleTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Auth Role Translation Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("role_id", "locale_id"),
    )
    role_id = Column(UUID, sa.ForeignKey(AuthRole.id, ondelete="CASCADE"), nullable=False, comment="Role ID", index=True)
    locale_id = Column(UUID, sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"), nullable=False, comment="Locale ID", index=True)
    name = Column(sa.String(64), nullable=False, comment="Role name")

    # Relationships
    role = relationship("AuthRole", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class AuthResource(ModelBase, AuditMixin, DeletedMixin, SortableMixin):
    """
    Portal Resource Model for RBAC
    Example:
        key: SYSTEM_USER, SYSTEM_ROLE, SYSTEM_PERMISSION
        code: system:user, system:role, system:permission
    """
    pid = Column(UUID, sa.ForeignKey("auth.resource.id", ondelete="CASCADE"), comment="Parent resource id")
    key = Column(sa.String(128), nullable=False, unique=True, comment="Resource key and front-end corresponding")
    code = Column(sa.String(32), nullable=False, unique=True, comment="Resource code (e.g., user, course, article)")
    icon = Column(sa.String(32), comment="Resource icon")
    path = Column(sa.String(256), comment="Resource path")
    type = Column(sa.Integer, default=ResourceType.GENERAL.value, nullable=False, comment="Resource type, Enum: ResourceType")
    is_visible = Column(sa.Boolean, nullable=False, server_default=sa.text("true"), comment="Is resource visible")
    
    # Relationships
    children = relationship("AuthResource", passive_deletes=True)
    translations = relationship("AuthResourceTranslation", back_populates="resource", passive_deletes=True)


class AuthResourceTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Auth Resource Translation Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("resource_id", "locale_id"),
    )

    resource_id = Column(UUID, sa.ForeignKey(AuthResource.id, ondelete="CASCADE"), nullable=False, comment="Resource ID", index=True)
    locale_id = Column(UUID, sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"), nullable=False, comment="Locale ID", index=True)
    name = Column(sa.String(64), nullable=False, comment="Resource name")

    # Relationships
    resource = relationship("AuthResource", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class AuthVerb(ModelBase, AuditMixin, DeletedMixin):
    """Portal Verb Model for RBAC"""
    action = Column(sa.String(32), nullable=False, unique=True, comment="Verb action (e.g., create, read, update, delete)")
    is_active = Column(sa.Boolean, default=True, comment="Is verb active")
    
    # Relationships
    translations = relationship("AuthVerbTranslation", back_populates="verb", passive_deletes=True)


class AuthVerbTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Auth Verb Translation Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("verb_id", "locale_id"),
    )

    verb_id = Column(UUID, sa.ForeignKey(AuthVerb.id, ondelete="CASCADE"), nullable=False, comment="Verb ID", index=True)
    locale_id = Column(UUID, sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"), nullable=False, comment="Locale ID", index=True)
    name = Column(sa.String(64), nullable=False, comment="Verb name")

    # Relationships
    verb = relationship("AuthVerb", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class AuthPermission(ModelBase, AuditMixin, DeletedMixin):
    """Portal Permission Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("resource_id", "verb_id"),
    )
    resource_id = Column(UUID, sa.ForeignKey(AuthResource.id, ondelete="CASCADE"), nullable=False, comment="Resource ID", index=True)
    verb_id = Column(UUID, sa.ForeignKey(AuthVerb.id, ondelete="CASCADE"), nullable=False, comment="Verb ID", index=True)
    code = Column(sa.String(128), nullable=False, unique=True, comment="Permission Code (e.g., user:read)")
    is_active = Column(sa.Boolean, default=True, comment="Is permission active")

    # Relationships
    roles = relationship("AuthRole", secondary=lambda: AuthRolePermission.__table__, back_populates="permissions", passive_deletes=True)
    translations = relationship("AuthPermissionTranslation", back_populates="permission", passive_deletes=True)


class AuthPermissionTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Auth Permission Translation Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("permission_id", "locale_id"),
    )

    permission_id = Column(UUID, sa.ForeignKey(AuthPermission.id, ondelete="CASCADE"), nullable=False, comment="Permission ID", index=True)
    locale_id = Column(UUID, sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"), nullable=False, comment="Locale ID", index=True)
    name = Column(sa.String(128), nullable=False, comment="Permission name")

    # Relationships
    permission = relationship("AuthPermission", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


