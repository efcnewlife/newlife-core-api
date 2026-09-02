"""
Member authentication HTTP routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.auth.commands import LogoutCommand, MicrosoftLoginCommand, MockLoginCommand, RefreshTokenCommand
from portal.application.auth.login_service import LoginService
from portal.application.auth.mappers import member_login_result_to_api, member_profile_result_to_api, token_result_to_api
from portal.application.auth.microsoft_auth_service import MicrosoftAuthService
from portal.application.auth.mock_login_auth_service import MockLoginAuthService
from portal.application.auth.refresh_token_service import RefreshTokenService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.apis.v1.auth import MemberInfo, MemberLoginResponse, MicrosoftIdTokenRequest, MockLoginRequest
from portal.serializers.mixins import LogoutRequest, LogoutResponse, RefreshTokenRequest, TokenResponse

router: AuthRouter = AuthRouter()


@router.post(
    "/mock-login",
    response_model=MemberLoginResponse,
    response_model_by_alias=True,
    require_auth=False,
    responses={401: {"description": "Unauthorized", "content": {"application/json": {"example": {"detail": "Unauthorized"}}}}},
)
@inject
async def member_mock_login(body: MockLoginRequest, mock_login_auth_service: MockLoginAuthService = Depends(Provide[Container.mock_login_auth_service])):
    result = await mock_login_auth_service.mock_member_login(MockLoginCommand(email=body.email))
    return member_login_result_to_api(result)


@router.post(
    "/login/microsoft",
    response_model=MemberLoginResponse,
    response_model_by_alias=True,
    require_auth=False,
    responses={
        401: {"description": "Unauthorized", "content": {"application/json": {"example": {"detail": "Invalid authorization token"}}}},
        403: {"description": "Forbidden", "content": {"application/json": {"example": {"detail": "Unknown or missing web app Origin"}}}},
    },
)
@inject
async def member_microsoft_login(
    body: MicrosoftIdTokenRequest, microsoft_auth_service: MicrosoftAuthService = Depends(Provide[Container.microsoft_auth_service])
):
    result = await microsoft_auth_service.microsoft_member_login(MicrosoftLoginCommand(id_token=body.id_token))
    return member_login_result_to_api(result)


@router.post("/refresh", response_model=TokenResponse, response_model_by_alias=True, require_auth=False)
@inject
async def member_refresh_token(body: RefreshTokenRequest, refresh_token_service: RefreshTokenService = Depends(Provide[Container.refresh_token_service])):
    result = await refresh_token_service.refresh_member_token(RefreshTokenCommand(refresh_token=body.refresh_token))
    return token_result_to_api(result)


@router.post("/logout", response_model=LogoutResponse, response_model_by_alias=True)
@inject
async def member_logout(body: LogoutRequest, refresh_token_service: RefreshTokenService = Depends(Provide[Container.refresh_token_service])):
    await refresh_token_service.logout_member(LogoutCommand(access_token=body.access_token, refresh_token=body.refresh_token))
    return LogoutResponse(message="Logged out")


@router.get("/me", response_model=MemberInfo, response_model_by_alias=True)
@inject
async def member_me(login_service: LoginService = Depends(Provide[Container.login_service])) -> MemberInfo:
    result = await login_service.member_profile()
    return member_profile_result_to_api(result)
