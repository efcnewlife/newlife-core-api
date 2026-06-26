"""
RBAC audit logging via background events.
"""
import dataclasses
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from portal.events.publisher import publish_event_in_background
from portal.events.types import AdminOperationLogEvent
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import get_request_context
from portal.libs.contexts.user_context import get_user_context
from portal.libs.logger import logger


class RbacAuditService:
    """Publish admin operation audit events."""

    @classmethod
    def normalize_for_audit_json(cls, value: Any) -> Any:
        """
        Recursively convert values to JSON-serializable forms for portal_log JSONB.
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return cls.normalize_for_audit_json(value.value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, time):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): cls.normalize_for_audit_json(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.normalize_for_audit_json(v) for v in value]
        if isinstance(value, set):
            return [cls.normalize_for_audit_json(v) for v in value]
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex()
        try:
            if isinstance(value, BaseModel):
                return cls.normalize_for_audit_json(value.model_dump(mode="json"))
        except ImportError:
            pass
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return cls.normalize_for_audit_json(dataclasses.asdict(value))
        return str(value)

    @staticmethod
    def compute_changed_fields_shallow(
        old_data: dict[str, Any],
        new_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        First-level diff between two dicts (already normalized).
        """
        keys = set(old_data.keys()) | set(new_data.keys())
        out: list[dict[str, Any]] = []
        for key in sorted(keys):
            old_val: Optional[Any] = old_data[key] if key in old_data else None
            new_val: Optional[Any] = new_data[key] if key in new_data else None
            if old_val != new_val:
                out.append({"field": key, "old": old_val, "new": new_val})
        return out

    def create_log(
        self,
        operation_type: OperationType,
        record_id: Optional[UUID] = None,
        operation_code: Optional[str] = None,
        old_data: Optional[dict[str, Any]] = None,
        new_data: Optional[dict[str, Any]] = None,
        changed_fields: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """
        Schedule AdminOperationLogEvent in the background.
        """
        try:
            resolved_old_data = old_data
            resolved_new_data = new_data
            resolved_changed_fields = changed_fields
            if (
                changed_fields is None
                and isinstance(old_data, dict)
                and isinstance(new_data, dict)
            ):
                try:
                    resolved_old_data = self.normalize_for_audit_json(old_data)
                    resolved_new_data = self.normalize_for_audit_json(new_data)
                    if isinstance(resolved_old_data, dict) and isinstance(resolved_new_data, dict):
                        resolved_changed_fields = self.compute_changed_fields_shallow(
                            resolved_old_data,
                            resolved_new_data,
                        )
                    else:
                        resolved_old_data = old_data
                        resolved_new_data = new_data
                        resolved_changed_fields = None
                        logger.warning(
                            "audit_log_payload normalize did not return dict for old/new; "
                            "falling back to raw payloads without changed_fields"
                        )
                except Exception:
                    resolved_old_data = old_data
                    resolved_new_data = new_data
                    resolved_changed_fields = None
                    logger.exception(
                        "audit_log_payload normalize or diff failed; "
                        "falling back to raw payloads without changed_fields"
                    )
            user_ctx = get_user_context()
            created_by = user_ctx.username if user_ctx and user_ctx.username else None
            created_by_id = user_ctx.user_id if user_ctx and user_ctx.user_id else None
            req_ctx = get_request_context()
            ip_address = None
            user_agent = None
            if req_ctx:
                ip_address = req_ctx.ip or req_ctx.client_ip
                user_agent = req_ctx.headers.user_agent if req_ctx.headers else None
            publish_event_in_background(
                event=AdminOperationLogEvent(
                    operation_type=operation_type,
                    record_id=record_id,
                    operation_code=operation_code,
                    old_data=resolved_old_data,
                    new_data=resolved_new_data,
                    changed_fields=resolved_changed_fields,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    created_by=created_by,
                    created_by_id=created_by_id,
                )
            )
        except Exception as e:
            logger.warning("RbacAuditService.create_log failed: %s", e)
