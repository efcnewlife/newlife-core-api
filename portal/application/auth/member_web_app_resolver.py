"""
Resolve member web app from the current request context.
"""
from typing import Optional

from portal.domain.auth.member_web_app import MemberWebAppRegistry
from portal.exceptions.responses import ForbiddenException
from portal.libs.contexts.request_context import get_request_context


def resolve_request_app_code(registry: MemberWebAppRegistry, *, required: bool = True) -> Optional[str]:
    """
    Resolve app_code from Origin (preferred) or Referer on the current request.
    :param registry:
    :param required:
    :return:
    """
    req_ctx = get_request_context()
    origin = None
    referer = None
    if req_ctx and req_ctx.headers:
        origin = req_ctx.headers.origin
        referer = req_ctx.headers.referer
    app_code = registry.resolve_app_code(origin=origin, referer=referer)
    if required and not app_code:
        raise ForbiddenException(detail="Unknown or missing web app Origin")
    return app_code
