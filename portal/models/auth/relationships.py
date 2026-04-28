"""
This module defines the association tables for many-to-many relationships
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from portal.libs.database.orm import Base


class AuthUserRole(Base):
    """Association object for User-Role relationship"""
    user_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete='CASCADE'),
        nullable=False,
        index=True,
        primary_key=True
    )
    role_id = Column(
        UUID,
        sa.ForeignKey("auth.role.id", ondelete='CASCADE'),
        nullable=False,
        index=True,
        primary_key=True
    )


class AuthRolePermission(Base):
    """Association object for Role-Permission relationship"""
    __extra_table_args__ = (
        sa.UniqueConstraint('role_id', 'permission_id'),
    )
    role_id = Column(
        UUID,
        sa.ForeignKey("auth.role.id", ondelete='CASCADE'),
        nullable=False,
        index=True,
        primary_key=True
    )
    permission_id = Column(
        UUID,
        sa.ForeignKey("auth.permission.id", ondelete='CASCADE'),
        nullable=False,
        index=True,
        primary_key=True
    )
    expire_date = Column(sa.DateTime(timezone=True), index=True, comment='Expiration time, can be used for temporary authorization')
