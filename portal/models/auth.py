"""
Auth-related models: Device and Refresh Token
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from portal.libs.database.orm import ModelBase
from .mixins import AuditMixin, DeletedMixin


class PortalAuthDevice(ModelBase, AuditMixin, DeletedMixin):
    """Auth Device Model"""
    __extra_table_args__ = (
        sa.UniqueConstraint("id", "user_id"),
    )
    user_id = Column(
        UUID,
        sa.ForeignKey("portal_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    first_seen_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="First seen at")
    last_seen_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), server_onupdate=sa.func.now(), comment="Last seen at")
    last_ip = Column(sa.String(45), nullable=True, comment="Last IP")
    last_user_agent = Column(sa.String(512), nullable=True, comment="Last user agent")


class PortalRefreshToken(ModelBase, AuditMixin, DeletedMixin):
    """Refresh Token Model (whitelist)"""
    user_id = Column(UUID, sa.ForeignKey("portal_user.id", ondelete="CASCADE"), nullable=False, index=True, comment="User ID")
    device_id = Column(UUID, sa.ForeignKey(PortalAuthDevice.id, ondelete="SET NULL"), nullable=True, index=True, comment="Device ID")
    family_id = Column(UUID, nullable=False, index=True, comment="Family ID")
    # jti == id (PK)
    parent_id = Column(UUID, sa.ForeignKey("portal_refresh_token.id", ondelete="SET NULL"), nullable=True, index=True, comment="Parent ID")
    replaced_by_id = Column(UUID, sa.ForeignKey("portal_refresh_token.id", ondelete="SET NULL"), nullable=True, index=True, comment="Replaced by ID")
    token_hash = Column(sa.String(128), nullable=False, unique=True, index=True, comment="Token hash")
    expires_at = Column(sa.DateTime(timezone=True), nullable=False, index=True, comment="Expires at")
    last_used_at = Column(sa.DateTime(timezone=True), nullable=True, index=True, comment="Last used at")

    revoked_at = Column(sa.DateTime(timezone=True), nullable=True, comment="Revoked at")
    revoked_reason = Column(sa.String(32), nullable=True, comment="Revoked reason")
    ip = Column(sa.String(45), nullable=True, comment="IP")
    user_agent = Column(sa.String(512), nullable=True, comment="User agent")
