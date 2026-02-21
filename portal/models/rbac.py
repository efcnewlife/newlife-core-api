"""
RBAC models: roles, resources, verbs, permissions and their associations.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.consts.enums import ResourceType
from portal.libs.database.orm import ModelBase, Base
from .mixins import BaseMixin, SortableMixin
from .relationships import PortalUserRole, PortalRolePermission


class PortalRole(ModelBase, BaseMixin):
    """Portal Role Model for RBAC"""
    code = Column(sa.String(32), nullable=False, unique=True, comment="Role code")
    name = Column(sa.String(64), comment="Role name")
    is_active = Column(sa.Boolean, default=True, comment="Is role active")
    # Relationships
    users = relationship("PortalUser", secondary=lambda: PortalUserRole.__table__, back_populates="roles", passive_deletes=True)
    permissions = relationship("PortalPermission", secondary=lambda: PortalRolePermission.__table__, back_populates="roles", passive_deletes=True)


class PortalResource(ModelBase, BaseMixin, SortableMixin):
    """
    Portal Resource Model for RBAC
    Example:
        key: SYSTEM_USER, SYSTEM_ROLE, SYSTEM_PERMISSION
        code: system:user, system:role, system:permission
    """
    pid = Column(UUID, sa.ForeignKey("portal_resource.id", ondelete="CASCADE"), comment="Parent resource id")
    name = Column(sa.String(64), comment="Resource name")
    key = Column(sa.String(128), nullable=False, unique=True, comment="Resource key and front-end corresponding")
    code = Column(sa.String(32), nullable=False, unique=True, comment="Resource code (e.g., user, course, article)")
    icon = Column(sa.String(32), comment="Resource icon")
    path = Column(sa.String(256), comment="Resource path")
    type = Column(sa.Integer, default=ResourceType.GENERAL.value, nullable=False, comment="Resource type, Enum: ResourceType")
    is_visible = Column(sa.Boolean, nullable=False, server_default=sa.text("true"), comment="Is resource visible")
    children = relationship("PortalResource", passive_deletes=True)


class PortalVerb(ModelBase, BaseMixin):
    """Portal Verb Model for RBAC"""
    action = Column(sa.String(32), nullable=False, unique=True, comment="Verb action (e.g., create, read, update, delete)")
    display_name = Column(sa.String(64), comment="Display name")
    is_active = Column(sa.Boolean, default=True, comment="Is verb active")


class PortalPermission(ModelBase, BaseMixin):
    """Portal Permission Model for RBAC"""
    __extra_table_args__ = (
        sa.UniqueConstraint("resource_id", "verb_id"),
    )
    resource_id = Column(UUID, sa.ForeignKey(PortalResource.id, ondelete="CASCADE"), nullable=False, comment="Resource ID", index=True)
    verb_id = Column(UUID, sa.ForeignKey(PortalVerb.id, ondelete="CASCADE"), nullable=False, comment="Verb ID", index=True)
    code = Column(sa.String(128), nullable=False, unique=True, comment="Permission Code (e.g., user:read)")
    display_name = Column(sa.String(128), comment="Display name")
    is_active = Column(sa.Boolean, default=True, comment="Is permission active")

    # Relationships
    roles = relationship("PortalRole", secondary=lambda: PortalRolePermission.__table__, back_populates="permissions", passive_deletes=True)


