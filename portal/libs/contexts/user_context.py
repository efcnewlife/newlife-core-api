"""
User Context (per-request)
"""
from contextvars import ContextVar, Token
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from portal.libs.consts.enums import Gender


class UserContext(BaseModel):
    """Per-request user information"""
    user_id: Optional[UUID] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    verified: bool = False
    is_active: bool = False
    is_superuser: bool = False
    is_admin: bool = False
    last_login_at: Optional[datetime] = None
    display_name: Optional[str] = None
    gender: Optional[Gender] = None
    is_ministry: bool = False
    login_admin: bool = False
    # token
    token: Optional[str] = None
    token_payload: Optional[dict] = None
    # other
    username: Optional[str] = None


user_context_var: ContextVar[UserContext] = ContextVar("UserContext")


def set_user_context(context: UserContext) -> Token:
    """
    Set the user context for current request.
    Prefer initializing this once in middleware and mutate thereafter.
    """
    return user_context_var.set(context)


def get_user_context() -> Optional[UserContext]:
    """
    Get current request's user context. Middleware should have set it.
    """
    try:
        return user_context_var.get()
    except LookupError:
        return None


def reset_user_context(token) -> None:
    """
    Reset the user context for current request.
    :param token:
    :return:
    """
    user_context_var.reset(token)
