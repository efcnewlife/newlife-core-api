import uuid

from portal.libs.contexts.user_context import get_user_context


SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

def get_current_username():
    try:
        ctx = get_user_context()
        return ctx.username if ctx and ctx.username else "system"
    except Exception:
        return "system"


def get_current_id():
    try:
        ctx = get_user_context()
        return ctx.user_id if ctx and ctx.user_id else SYSTEM_USER_ID
    except Exception:
        return SYSTEM_USER_ID


def apply_audit_fields_to_rows(rows: list[dict]) -> list[dict]:
    """Populate audit columns on each bulk-insert row (SQLAlchemy defaults apply to first row only)."""
    user_id = get_current_id()
    username = get_current_username()
    enriched = []
    for row in rows:
        enriched.append(
            {
                **row,
                "created_by_id": row.get("created_by_id") or user_id,
                "created_by": row.get("created_by") or username,
                "updated_by_id": row.get("updated_by_id") or user_id,
                "updated_by": row.get("updated_by") or username,
            }
        )
    return enriched
