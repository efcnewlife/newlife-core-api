"""
Member person model.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin


class MemberPerson(ModelBase, AuditMixin):
    """Church member pastoral record (optional link to auth user)."""
    user_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
        comment="Linked auth user ID",
    )
    legal_name = Column(sa.String(255), comment="Legal name")

    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)
