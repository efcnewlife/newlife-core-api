"""
Admin authentication HTTP routes.
"""
from dependency_injector.wiring import inject, Provide
from fastapi import Depends

from portal.container import Container
from portal.handlers.admin.auth import AdminAuthHandler
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.auth import (
    AdminLoginSuccessResponse,
    AdminPasswordLoginRequest,
    AdminPrincipalResponse,
    LogoutRequest,
    LogoutResponse,
    MicrosoftIdTokenRequest,
    RefreshTokenRequest,
    TokenResponse,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.post(
    "/login",
    response_model=AdminLoginSuccessResponse,
    response_model_by_alias=True,
    require_auth=False,
)
@inject
async def admin_login(
    body: AdminPasswordLoginRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    return await admin_auth_handler.login_with_password(body.email, body.password)


@router.post(
    "/microsoft",
    response_model=AdminLoginSuccessResponse,
    response_model_by_alias=True,
    require_auth=False,
    # TODO: structured response models for specific status codes
    responses={
        401: {
            "description": "Unauthorized",
            "content": {"application/json": {"example": {"detail": "Invalid authorization token"}}},
        },
    }
)
@inject
async def admin_microsoft_login(
    body: MicrosoftIdTokenRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    return await admin_auth_handler.microsoft_login(body.id_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    response_model_by_alias=True,
)
@inject
async def admin_refresh(
    body: RefreshTokenRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    return await admin_auth_handler.refresh_session(body.refresh_token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    response_model_by_alias=True,
)
@inject
async def admin_logout(
    body: LogoutRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    await admin_auth_handler.logout(body.access_token, body.refresh_token)
    return LogoutResponse(message="Logged out")


@router.get(
    "/me",
    response_model=AdminPrincipalResponse,
    response_model_by_alias=True,
)
@inject
async def admin_me(
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
) -> AdminPrincipalResponse:
    return await admin_auth_handler.admin_profile()
