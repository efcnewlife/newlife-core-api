"""
API Context
"""
from contextvars import ContextVar, Token
from typing import Optional

from pydantic import BaseModel

from portal.schemas.auth import FirebaseTokenPayload

auth_context = ContextVar("APIContext")


class APIContext(BaseModel):
    """API Context"""
    model_config = {
        "arbitrary_types_allowed": True
    }
    token: Optional[str] = None
    token_payload: Optional[FirebaseTokenPayload] = None
    uid: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    host: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    verified: Optional[bool] = False


def set_api_context(context: APIContext) -> Token:
    """

    :param context:
    :return:
    """
    return auth_context.set(context)


def get_api_context() -> APIContext:
    """

    :return:
    """
    try:
        return auth_context.get()
    except LookupError:
        return APIContext()
