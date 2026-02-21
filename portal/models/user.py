"""
User-related models: account, profile, third-party provider and auth.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from portal.libs.consts.enums import Gender
from portal.libs.database.orm import ModelBase
from .mixins import AuditMixin, DeletedMixin, RemarkMixin, DescriptionMixin
from .relationships import PortalUserRole


class PortalUser(ModelBase, RemarkMixin, DeletedMixin, AuditMixin):
    """Portal User Model"""
    phone_number = Column(
        sa.String(16),
        nullable=False,
        unique=True,
        comment="Phone number, unique identifier"
    )
    email = Column(sa.String(255), nullable=True, unique=True, comment="Email, unique identifier")
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
        "PortalRole",
        secondary=PortalUserRole.__table__,
        back_populates="users",
        passive_deletes=True,
    )


class PortalUserProfile(ModelBase, AuditMixin, DescriptionMixin):
    """Portal User Profile Model"""
    user_id = Column(
        UUID,
        sa.ForeignKey(PortalUser.id, ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="User ID",
        index=True
    )
    display_name = Column(sa.String(64), comment="Display name")
    gender = Column(sa.Integer, default=Gender.UNKNOWN.value, comment="Refer to Gender enum")


class PortalThirdPartyProvider(ModelBase, DeletedMixin, AuditMixin, RemarkMixin):
    """Portal Third Party Provider Model"""
    name = Column(sa.String(16), nullable=False, unique=True, comment="Provider name, Enum: Provider")


class PortalUserThirdPartyAuth(ModelBase, DeletedMixin, AuditMixin):
    """Portal User Third Party Auth Model"""
    __extra_table_args__ = (
        sa.UniqueConstraint("user_id", "provider_id", "provider_uid"),
    )
    user_id = Column(
        UUID,
        sa.ForeignKey(PortalUser.id, ondelete="CASCADE", name="fk_user_third_party_auth_user"),
        nullable=False,
        comment="User ID",
        index=True
    )
    provider_id = Column(
        UUID,
        sa.ForeignKey(PortalThirdPartyProvider.id, ondelete="CASCADE", name="fk_user_third_party_auth_provider"),
        nullable=False,
        comment="Provider ID",
        index=True
    )
    provider_uid = Column(sa.String(255), nullable=False, comment="Provider UID")
    access_token = Column(sa.String(255), comment="Access token")
    refresh_token = Column(sa.String(255), comment="Refresh token")
    token_expires_at = Column(sa.TIMESTAMP(timezone=True), comment="Token expiration time")
    additional_data = Column(JSONB, comment="Additional data")
