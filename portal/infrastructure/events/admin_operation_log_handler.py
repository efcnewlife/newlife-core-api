"""
Handler for AdminOperationLogEvent: insert audit log row.
"""
import json
from typing import Any, Optional
from uuid import UUID

from portal.events.base import EventHandler
from portal.events.types import AdminOperationLogEvent
from portal.libs.contexts.user_context import get_user_context
from portal.libs.database import Session
from portal.models import AuditLog
from portal.models.mixins.context import SYSTEM_USER_ID


class AdminOperationLogEventHandler(EventHandler):
    """
    Persists admin operation audit data to audit_log.
    """

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _serialize_jsonb(value: Any) -> Optional[str]:
        """asyncpg JSONB bind expects a JSON string, not a Python dict/list."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value)

    @property
    def event_type(self) -> type[AdminOperationLogEvent]:
        return AdminOperationLogEvent

    async def handle(self, event: AdminOperationLogEvent) -> None:
        created_by, created_by_id = self._resolve_actor(event)

        await (
            self._session.insert(AuditLog)
            .values(
                record_id=event.record_id,
                operation_type=event.operation_type.value,
                operation_code=event.operation_code,
                old_data=self._serialize_jsonb(event.old_data),
                new_data=self._serialize_jsonb(event.new_data),
                changed_fields=self._serialize_jsonb(event.changed_fields),
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                created_by=created_by,
                created_by_id=created_by_id,
            )
            .execute()
        )

    def _resolve_actor(self, event: AdminOperationLogEvent) -> tuple[str, Optional[UUID]]:
        created_by = event.created_by
        created_by_id = event.created_by_id
        if created_by is None or created_by_id is None:
            user_ctx = get_user_context()
            if created_by is None:
                created_by = user_ctx.username if user_ctx and user_ctx.username else "system"
            if created_by_id is None:
                created_by_id = user_ctx.user_id if user_ctx and user_ctx.user_id else SYSTEM_USER_ID
        return created_by, created_by_id
