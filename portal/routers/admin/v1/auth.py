"""
Admin authentication HTTP routes.
"""
import uuid

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Response, Cookie, status

from portal.config import settings
from portal.container import Container
from portal.handlers.admin.auth import AdminAuthHandler
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins import (
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    LogoutResponse
)
from portal.serializers.admin.v1.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    MicrosoftIdTokenRequest,
    AdminInfo,
)

router: AuthRouter = AuthRouter(is_admin=True)


if settings.is_dev:
    @router.post(
        path="/local/login",
        status_code=status.HTTP_200_OK,
        include_in_schema=False,
        require_auth=False
    )
    @inject
    async def admin_local_login(
        response: Response,
        login_data: AdminLoginRequest,
        device_id: uuid.UUID = Cookie(None, alias="device_id"),
        admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler])
    ):
        """
        Admin login
        """
        if not device_id:
            device_id = uuid.uuid4()
        try:
            result = await admin_auth_handler.login_without_validate(
                login_data=login_data,
                device_id=device_id
            )
        except Exception as e:
            raise e
        else:
            response.set_cookie(
                key="device_id",
                value=str(device_id),
                max_age=3600 * 24 * 365,  # 1 year
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
            )
            return result


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    response_model_by_alias=True,
    require_auth=False,
)
@inject
async def admin_login(
    body: AdminLoginRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    return await admin_auth_handler.login_with_password(body.email, body.password)


@router.post(
    "/login/microsoft",
    response_model=AdminLoginResponse,
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
    require_auth=False,
)
@inject
async def admin_refresh_token(
    body: RefreshTokenRequest,
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
):
    return await admin_auth_handler.refresh_token(body.refresh_token)


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
    response_model=AdminInfo,
    response_model_by_alias=True,
)
@inject
async def admin_me(
    admin_auth_handler: AdminAuthHandler = Depends(Provide[Container.admin_auth_handler]),
) -> AdminInfo:
    return await admin_auth_handler.admin_profile()
