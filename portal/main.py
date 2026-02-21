"""
main application - Template
"""
from collections import defaultdict

from fastapi import Request, status, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse

from portal.apps import get_main_application
from portal.config import settings
from portal.exceptions.responses import ApiBaseException
from portal.libs.contexts.request_session_context import get_request_session

__all__ = ["app"]

app = get_main_application()


@app.get("/")
async def root():
    """Root path redirects to /docs in development"""
    if settings.is_dev:
        return RedirectResponse(url="/docs")
    return {"message": f"Welcome to {settings.APP_NAME} API"}


@app.exception_handler(HTTPException)
async def root_http_exception_handler(request: Request, exc: HTTPException):
    """
    HTTP exception handler
    :param request:
    :param exc:
    :return:
    """
    session = get_request_session()
    if session is not None:
        await session.rollback()
    return await http_exception_handler(request, exc)


@app.exception_handler(ApiBaseException)
async def root_api_exception_handler(request: Request, exc: ApiBaseException):
    """
    API exception handler
    :param request:
    :param exc:
    :return:
    """
    session = get_request_session()
    if session is not None:
        await session.rollback()
    content = defaultdict()
    content["detail"] = exc.detail
    if settings.is_dev:
        content["debug_detail"] = exc.debug_detail
        content["url"] = str(request.url)
    return JSONResponse(content=content, status_code=exc.status_code)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc):
    """
    Generic exception handler
    :param request:
    :param exc:
    :return:
    """
    content = defaultdict()
    content["detail"] = {"message": "Internal Server Error", "url": str(request.url)}
    if settings.is_dev:
        content["debug_detail"] = f"{exc.__class__.__name__}: {exc}"
    return JSONResponse(
        content=content, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
