"""
applications: public ASGI app mounts admin and api sub-applications.
"""
from collections import defaultdict

from fastapi import APIRouter, FastAPI
from fastapi import Request, status, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from portal.config import settings
from portal.container import Container
from portal.exceptions.responses import ApiBaseException
from portal.libs.consts.enums import APIScope
from portal.libs.contexts.request_session_context import get_request_session
from portal.runtime_context import set_runtime_container
from portal.libs.utils.lifespan import lifespan
from portal.middlewares import CoreRequestMiddleware, AuthMiddleware
from portal.routers import admin_api_router, api_router


def _register_cors(application: FastAPI) -> None:
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_origin_regex=settings.CORS_ALLOW_ORIGINS_REGEX,
    )


def _register_core_request_middleware(application: FastAPI) -> None:
    application.add_middleware(CoreRequestMiddleware)


def _register_admin_stack(application: FastAPI) -> None:
    """
    Auth runs inside the admin app so public routes stay unauthenticated.
    :param application:
    :return:
    """
    application.add_middleware(AuthMiddleware)
    _register_core_request_middleware(application)
    _register_cors(application)


def _register_public_stack(application: FastAPI) -> None:
    """

    :param application:
    :return:
    """
    _register_core_request_middleware(application)
    _register_cors(application)


def _register_api_stack(application: FastAPI) -> None:
    """
    App-user API surface: session + CORS only until user auth is implemented.
    :param application:
    :return:
    """
    _register_core_request_middleware(application)
    _register_cors(application)

def _setup_exception_handlers(application: FastAPI) -> None:
    """

    :param application:
    :return:
    """
    @application.exception_handler(HTTPException)
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


    @application.exception_handler(ApiBaseException)
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
        return JSONResponse(
            content=content,
            status_code=exc.status_code,
        )


    @application.exception_handler(Exception)
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
            content=content,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def custom_openapi(scope: APIScope, application: FastAPI):
    def _custom_openapi():
        if not application.openapi_schema:
            from fastapi.openapi.utils import get_openapi
            application.openapi_schema = get_openapi(
                title=f"{settings.APP_NAME} {scope.value} API",
                version=settings.APP_VERSION,
                summary=f"{settings.APP_NAME} {scope.value} API.",
                description=f"{settings.APP_NAME} {scope.value} API documentation.",
                routes=application.routes,
            )
        return application.openapi_schema
    application.openapi = _custom_openapi


def get_admin_application(container: Container) -> FastAPI:
    application = FastAPI(
        title=f"{settings.APP_NAME} Admin API",
        version=settings.APP_VERSION,
    )
    application.container = container
    application.include_router(admin_api_router, prefix="/api")
    _register_admin_stack(application)
    _setup_exception_handlers(application)
    custom_openapi(scope=APIScope.ADMIN, application=application)
    return application


def get_api_application(container: Container) -> FastAPI:
    application = FastAPI(
        title=f"{settings.APP_NAME} App API",
        version=settings.APP_VERSION,
    )
    application.container = container
    application.include_router(api_router)
    _register_api_stack(application)
    _setup_exception_handlers(application)
    custom_openapi(scope=APIScope.API, application=application)
    return application


def get_public_application(container: Container) -> FastAPI:
    application = FastAPI(
        lifespan=lifespan,
        title=f"{settings.APP_NAME} Public API",
        version=settings.APP_VERSION,
    )
    application.container = container

    admin_app = get_admin_application(container)
    api_app = get_api_application(container)
    application.mount("/admin", admin_app)
    application.mount("/api", api_app)

    @application.get("/healthz", operation_id="public_healthz")
    async def public_healthz():
        return {"message": "ok"}

    _register_public_stack(application)
    _setup_exception_handlers(application)
    custom_openapi(scope=APIScope.PUBLIC, application=application)

    return application


def get_main_application() -> FastAPI:
    container = Container()
    application = get_public_application(container)
    set_runtime_container(container)
    return application
