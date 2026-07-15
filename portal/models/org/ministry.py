"""
Organization ministry models.
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.domain.org.constants import MinistryStatus
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin, DescriptionMixin, RemarkMixin, SortableMixin
from portal.models.org.ministry_type import OrgMinistryType
from portal.models.org.position import OrgPosition
from portal.models.system_locale import SystemLocale


class OrgMinistry(ModelBase, AuditMixin, SortableMixin, DeletedMixin):
    """Ministry organizational unit."""
    __extra_table_args__ = (
        sa.Index("ix_ministry_status_is_active", "status", "is_active"),
    )

    owner_position_id = Column(
        UUID,
        sa.ForeignKey(OrgPosition.id, ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Owning leadership position",
    )
    status = Column(
        sa.String(32),
        nullable=False,
        server_default=MinistryStatus.DRAFT.value,
        index=True,
        comment="Ministry lifecycle status",
    )
    has_priority_booking = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="Priority booking flag",
    )
    is_active = Column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="Active flag",
    )
    submitted_at = Column(sa.DateTime(timezone=True), comment="Submitted for approval at")
    submitted_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who submitted for approval",
    )
    approved_at = Column(sa.DateTime(timezone=True), comment="Approved at")
    approved_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved",
    )
    rejected_at = Column(sa.DateTime(timezone=True), comment="Rejected at")
    rejected_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who rejected",
    )
    rejection_reason = Column(sa.String(500), comment="Rejection reason")
    created_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="Application creator user ID",
    )
    ministry_type_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistryType.id, ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Ministry type catalog ID",
    )

    owner_position = relationship("OrgPosition", foreign_keys=[owner_position_id], passive_deletes=True)
    ministry_type = relationship("OrgMinistryType", passive_deletes=True)
    translations = relationship(
        "OrgMinistryTranslation",
        back_populates="ministry",
        passive_deletes=True,
    )
    members = relationship(
        "OrgMinistryMember",
        back_populates="ministry",
        passive_deletes=True,
    )
    approval_requests = relationship(
        "OrgMinistryApproval",
        back_populates="ministry",
        passive_deletes=True,
    )
    schedules = relationship(
        "OrgMinistrySchedule",
        back_populates="ministry",
        passive_deletes=True,
    )
    target_audience_links = relationship(
        "OrgMinistryTargetAudience",
        back_populates="ministry",
        passive_deletes=True,
    )


class OrgMinistryTranslation(ModelBase, AuditMixin, DescriptionMixin, RemarkMixin):
    """Localized ministry content."""
    __extra_table_args__ = (
        sa.UniqueConstraint("ministry_id", "locale_id"),
    )

    ministry_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistry.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ministry ID",
    )
    locale_id = Column(
        UUID,
        sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Locale ID",
    )
    name = Column(sa.String(255), nullable=False, comment="Localized ministry name")
    schedule_note = Column(sa.String(500), nullable=True, comment="Schedule supplement note per locale")

    ministry = relationship("OrgMinistry", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")


class OrgMinistryMember(ModelBase, AuditMixin, RemarkMixin):
    """Ministry member (primary / secondary stewards who may book on behalf of ministry)."""
    __extra_table_args__ = (
        sa.UniqueConstraint("ministry_id", "user_id"),
        sa.Index("ix_ministry_member_ministry_id", "ministry_id"),
    )

    ministry_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistry.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ministry ID",
    )
    user_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID",
    )
    member_role = Column(sa.String(32), nullable=False, comment="primary or secondary")
    contact_email = Column(sa.String(255), nullable=True, comment="Public contact email override")

    ministry = relationship("OrgMinistry", back_populates="members", passive_deletes=True)
    user = relationship("AuthUser", foreign_keys=[user_id], passive_deletes=True)


class OrgMinistryApproval(ModelBase, AuditMixin):
    """Ministry approval request history."""
    __extra_table_args__ = (
        sa.Index("ix_ministry_approval_ministry_id_status", "ministry_id", "status"),
    )

    ministry_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistry.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Ministry ID",
    )
    owner_position_id = Column(
        UUID,
        sa.ForeignKey(OrgPosition.id, ondelete="SET NULL"),
        nullable=True,
        comment="Snapshot of owner position at submission",
    )
    status = Column(sa.String(32), nullable=False, comment="pending / approved / rejected")
    requested_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="Applicant user ID",
    )
    resolved_by_id = Column(
        UUID,
        sa.ForeignKey("auth.user.id", ondelete="SET NULL"),
        nullable=True,
        comment="Approver user ID",
    )
    decided_at = Column(sa.DateTime(timezone=True), comment="Decision timestamp")
    comment = Column(sa.String(500), comment="Approval comment")

    ministry = relationship("OrgMinistry", back_populates="approval_requests", passive_deletes=True)
    owner_position = relationship("OrgPosition", foreign_keys=[owner_position_id], passive_deletes=True)


class OrgMinistrySchedule(ModelBase, AuditMixin, SortableMixin):
    """Structured weekly schedule for a ministry."""
    __extra_table_args__ = (
        sa.CheckConstraint(
            "days_of_week_mask IS NULL OR (days_of_week_mask & 127) != 0",
            name="ministry_schedule_days_of_week_mask_nonzero",
        ),
        sa.CheckConstraint(
            "days_of_week_mask IS NULL OR (days_of_week_mask & ~127) = 0",
            name="ministry_schedule_days_of_week_mask_valid_bits",
        ),
        sa.CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR start_time < end_time",
            name="ministry_schedule_start_before_end",
        ),
        sa.CheckConstraint(
            "effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to",
            name="ministry_schedule_effective_date_order",
        ),
        sa.Index("ix_ministry_schedule_ministry_id", "ministry_id"),
    )

    ministry_id = Column(
        UUID,
        sa.ForeignKey(OrgMinistry.id, ondelete="CASCADE"),
        nullable=False,
        comment="Ministry ID",
    )
    days_of_week_mask = Column(
        sa.SmallInteger,
        nullable=True,
        comment="Bitmask of ISO weekdays: bit0=Monday(0) ... bit6=Sunday(6)",
    )
    start_time = Column(sa.Time, nullable=True, comment="Local start time")
    end_time = Column(sa.Time, nullable=True, comment="Local end time")
    effective_from = Column(sa.Date, nullable=True, comment="Seasonal effective start (inclusive)")
    effective_to = Column(sa.Date, nullable=True, comment="Seasonal effective end (inclusive)")

    ministry = relationship("OrgMinistry", back_populates="schedules", passive_deletes=True)
