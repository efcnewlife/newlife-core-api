"""
applications
"""
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from portal.config import settings
from portal.container import Container
from portal.libs.events.publisher import set_global_container
from portal.libs.utils.lifespan import lifespan
from portal.middlewares import CoreRequestMiddleware, AuthMiddleware
from portal.routers import api_router


def register_router(application: FastAPI) -> None:
    """Register router"""
    application.include_router(api_router, prefix="/api")


def register_middleware(application: FastAPI) -> None:
    """Register middleware"""
    application.add_middleware(AuthMiddleware)
    application.add_middleware(CoreRequestMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_origin_regex=settings.CORS_ALLOW_ORIGINS_REGEX,
    )


def get_main_application() -> FastAPI:
    """Get application"""
    application = FastAPI(lifespan=lifespan)

    container = Container()
    application.container = container
    set_global_container(container)

    register_middleware(application=application)
    register_router(application=application)

    def custom_openapi():
        if not application.openapi_schema:
            from fastapi.openapi.utils import get_openapi
            openapi_schema = get_openapi(
                title=settings.APP_NAME.replace("-", " ").title().replace("Api", "API"),
                version=settings.APP_VERSION,
                summary=f"{settings.APP_NAME} API",
                description=f"API documentation for {settings.APP_NAME}",
                routes=application.routes,
            )
            application.openapi_schema = openapi_schema
        return application.openapi_schema

    application.openapi = custom_openapi

    return application