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
