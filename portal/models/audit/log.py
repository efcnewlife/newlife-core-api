"""
Model of the system log table
"""
import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditCreatedMixin, RemarkMixin


class AuditLog(ModelBase, AuditCreatedMixin, RemarkMixin):
    """Portal Log Model for tracking data record changes"""
    record_id = Column(UUID, comment="Record ID in the audited table")
    operation_type = Column(
        sa.String(32),
        nullable=False,
        comment="Operation type string (OperationType.value). refer to libs.consts.enums.OperationType",
    )
    operation_code = Column(sa.String(64), comment="Operation code(default use table name)")
    old_data = Column(JSONB, comment="Complete old record data")
    new_data = Column(JSONB, comment="Complete new record data")
    changed_fields = Column(JSONB, comment="Only the fields that changed with old/new values")
    ip_address = Column(sa.String(45), comment="Client IP address")
    user_agent = Column(sa.String(512), comment="User agent string")
