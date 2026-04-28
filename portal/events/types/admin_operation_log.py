"""
Admin operation audit log event (persisted to PortalLog by event handler).
"""
from typing import Any, Optional
from uuid import UUID

from portal.libs.consts.enums import OperationType
from portal.events.base import BaseEvent


class AdminOperationLogEvent(BaseEvent):
    """
    Emitted when an admin operation should be recorded in portal_log.
    """

    operation_type: OperationType
    record_id: Optional[UUID] = None
    operation_code: Optional[str] = None
    old_data: Optional[dict[str, Any]] = None
    new_data: Optional[dict[str, Any]] = None
    changed_fields: Optional[list[dict[str, Any]]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_by: Optional[str] = None
    created_by_id: Optional[UUID] = None
