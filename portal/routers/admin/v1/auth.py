"""
Admin authentication HTTP routes.
"""
import uuid

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Response, Cookie, status

from portal.application.auth.commands import (
    LoginCommand,
    LoginWithoutValidateCommand,
    LogoutCommand,
    MicrosoftLoginCommand,
    RefreshTokenCommand,
)
from portal.application.auth.login_service import LoginService
from portal.application.auth.mappers import (
    admin_profile_result_to_api,
    login_result_to_api,
    token_result_to_api,
)
from portal.application.auth.microsoft_auth_service import MicrosoftAuthService
from portal.application.auth.refresh_token_service import RefreshTokenService
from portal.config import settings
from portal.container import Container
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
        login_service: LoginService = Depends(Provide[Container.login_service])
    ):
        """
        Admin login (dev only; skips password validation).
        """
        if not device_id:
            device_id = uuid.uuid4()
        try:
            result = await login_service.login_without_validate(
                command=LoginWithoutValidateCommand(email=login_data.email),
                device_id=device_id,
            )
        except Exception as e:
            raise e
        else:
            response.set_cookie(
                key="device_id",
                value=str(device_id),
                max_age=3600 * 24 * 365,
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
            )
            return login_result_to_api(result)


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    response_model_by_alias=True,
    require_auth=False,
)
@inject
async def admin_login(
    body: AdminLoginRequest,
    login_service: LoginService = Depends(Provide[Container.login_service]),
):
    result = await login_service.login_with_password(
        LoginCommand(email=body.email, password=body.password),
    )
    return login_result_to_api(result)


@router.post(
    "/login/microsoft",
    response_model=AdminLoginResponse,
    response_model_by_alias=True,
    require_auth=False,
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
    microsoft_auth_service: MicrosoftAuthService = Depends(Provide[Container.microsoft_auth_service]),
):
    result = await microsoft_auth_service.microsoft_login(
        MicrosoftLoginCommand(id_token=body.id_token),
    )
    return login_result_to_api(result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    response_model_by_alias=True,
    require_auth=False,
)
@inject
async def admin_refresh_token(
    body: RefreshTokenRequest,
    refresh_token_service: RefreshTokenService = Depends(Provide[Container.refresh_token_service]),
):
    result = await refresh_token_service.refresh_token(
        RefreshTokenCommand(refresh_token=body.refresh_token),
    )
    return token_result_to_api(result)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    response_model_by_alias=True,
)
@inject
async def admin_logout(
    body: LogoutRequest,
    refresh_token_service: RefreshTokenService = Depends(Provide[Container.refresh_token_service]),
):
    await refresh_token_service.logout(
        LogoutCommand(access_token=body.access_token, refresh_token=body.refresh_token),
    )
    return LogoutResponse(message="Logged out")


@router.get(
    "/me",
    response_model=AdminInfo,
    response_model_by_alias=True,
)
@inject
async def admin_me(
    login_service: LoginService = Depends(Provide[Container.login_service]),
) -> AdminInfo:
    result = await login_service.admin_profile()
    return admin_profile_result_to_api(result)
