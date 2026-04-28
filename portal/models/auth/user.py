"""
User-related models: account, profile, third-party provider and auth.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from portal.libs.consts.enums import Gender
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, RemarkMixin, DescriptionMixin
from .relationships import AuthUserRole


class AuthUser(ModelBase, RemarkMixin, DeletedMixin, AuditMixin):
    """Auth User Model"""
    email = Column(sa.String(255), nullable=True, unique=True, comment="Email, unique identifier")
    phone_number = Column(
        sa.String(16),
        nullable=True,
        unique=True,
        comment="Phone number, unique identifier"
    )
    password_hash = Column(sa.String(512), nullable=True, comment="Password hash")
    salt = Column(sa.String(128), nullable=True, comment="Salt for password hash")
    verified = Column(sa.Boolean, default=False, comment="Is verified")
    is_active = Column(sa.Boolean, default=True, index=True, comment="Is active")
    is_superuser = Column(sa.Boolean, default=False, comment="Is superuser")  # Top-level admin can access all resources in the admin panel
    is_admin = Column(sa.Boolean, default=False, comment="Is admin")  # Can access the admin panel
    password_changed_at = Column(sa.TIMESTAMP(timezone=True), comment="Password last changed time")
    password_expires_at = Column(sa.TIMESTAMP(timezone=True), comment="Password expiration time")
    last_login_at = Column(sa.TIMESTAMP(timezone=True), comment="Last login")

    # Relationships
    roles = relationship(
        "AuthRole",
        secondary=AuthUserRole.__table__,
        back_populates="users",
        passive_deletes=True,
    )


class AuthUserProfile(ModelBase, AuditMixin, DescriptionMixin):
    """Auth User Profile Model"""
    user_id = Column(
        UUID,
        sa.ForeignKey(AuthUser.id, ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="User ID",
        index=True
    )
    first_name = Column(sa.String(64), nullable=False, comment="First name")
    last_name = Column(sa.String(64), nullable=False, comment="Last name")
    title = Column(sa.String(64), comment="Title")
    gender = Column(sa.Integer, default=Gender.UNKNOWN.value, comment="Refer to Gender enum")
    preferred_name = Column(sa.String(64), comment="Preferred name")
    preferred_language = Column(sa.String(16), comment="Preferred language")


class AuthUserThirdParty(ModelBase, DeletedMixin, AuditMixin):
    """Auth User Third Party Model"""
    __extra_table_args__ = (
        sa.UniqueConstraint("user_id", "provider", "provider_uid"),
    )
    user_id = Column(
        UUID,
        sa.ForeignKey(AuthUser.id, ondelete="CASCADE", name="fk_user_third_party_user"),
        nullable=False,
        comment="User ID",
        index=True
    )
    provider = Column(sa.String(16), nullable=False, comment="Provider name, Enum: ThirdPartyProvider")
    provider_tenant_id = Column(UUID, nullable=False, comment="Provider tenant ID")
    provider_uid = Column(sa.String(255), nullable=False, comment="Provider UID")
    access_token = Column(sa.String(255), comment="Access token")
    refresh_token = Column(sa.String(255), comment="Refresh token")
    token_expires_at = Column(sa.TIMESTAMP(timezone=True), comment="Token expiration time")
    additional_data = Column(JSONB, comment="Additional data")


class AuthDevice(ModelBase, AuditMixin, DeletedMixin):
    """Auth Device Model"""
    __extra_table_args__ = (
        sa.UniqueConstraint("id", "user_id"),
    )
    user_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    first_seen_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="First seen at")
    last_seen_at = Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), server_onupdate=sa.func.now(), comment="Last seen at")
    last_ip = Column(sa.String(45), nullable=True, comment="Last IP")
    last_user_agent = Column(sa.String(512), nullable=True, comment="Last user agent")


class AuthRefreshToken(ModelBase, AuditMixin, DeletedMixin):
    """Auth Refresh Token Model (whitelist)"""
    user_id = Column(UUID, sa.ForeignKey("auth.user.id", ondelete="CASCADE"), nullable=False, index=True, comment="User ID")
    device_id = Column(UUID, sa.ForeignKey(AuthDevice.id, ondelete="SET NULL"), nullable=True, index=True, comment="Device ID")
    family_id = Column(UUID, nullable=False, index=True, comment="Family ID")
    parent_id = Column(UUID, sa.ForeignKey("auth.refresh_token.id", ondelete="SET NULL"), nullable=True, index=True, comment="Parent ID")
    replaced_by_id = Column(UUID, sa.ForeignKey("auth.refresh_token.id", ondelete="SET NULL"), nullable=True, index=True, comment="Replaced by ID")
    token_hash = Column(sa.String(128), nullable=False, unique=True, index=True, comment="Token hash")
    expires_at = Column(sa.DateTime(timezone=True), nullable=False, index=True, comment="Expires at")
    last_used_at = Column(sa.DateTime(timezone=True), nullable=True, index=True, comment="Last used at")

    revoked_at = Column(sa.DateTime(timezone=True), nullable=True, comment="Revoked at")
    revoked_reason = Column(sa.String(32), nullable=True, comment="Revoked reason")
    ip = Column(sa.String(45), nullable=True, comment="IP")
    user_agent = Column(sa.String(512), nullable=True, comment="User agent")
