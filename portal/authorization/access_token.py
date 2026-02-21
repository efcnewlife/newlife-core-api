"""
Bearer token authentication
"""
from typing import Optional

from dependency_injector.wiring import inject, Provide
from fastapi import Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from portal.container import Container
from portal.exceptions.responses import UnauthorizedException, InvalidTokenException
from portal.handlers import AdminUserHandler, UserHandler
from portal.libs.contexts.user_context import UserContext, set_user_context
from portal.providers.jwt_provider import JWTProvider
from portal.schemas.base import AccessTokenPayload
from portal.schemas.user import SUserDetail, SUserSensitive, SUserThirdParty


class AccessTokenAuth(HTTPBearer):
    """AccessTokenAuth"""

    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin
        super().__init__(auto_error=False)

    async def __call__(self, request: Request):
        result: Optional[HTTPAuthorizationCredentials] = await super().__call__(
            request=request
        )
        if not result:
            raise UnauthorizedException()
        await self.authenticate(request=request, token=result.credentials)

    async def authenticate(self, request: Request, token: str):
        """

        :param request:
        :param token:
        :return:
        """
        if self.is_admin:
            await self.verify_admin(request=request, token=token)
        else:
            await self.verify_user(request=request, token=token)

    @staticmethod
    @inject
    async def verify_admin(
        request: Request,
        token: str,
        jwt_provider: JWTProvider = Provide[Container.jwt_provider],
        admin_user_handler: AdminUserHandler = Provide[Container.admin_user_handler],
    ):
        """

        :param request:
        :param token:
        :param jwt_provider:
        :param admin_user_handler:
        :return:
        """
        payload: AccessTokenPayload = jwt_provider.verify_token(
            token=token,
            is_admin=True
        )
        if not payload:
            raise InvalidTokenException()

        user: SUserSensitive = await admin_user_handler.get_user_detail_by_id(payload.sub)
        if not user:
            raise UnauthorizedException()
        if not user.is_active or not user.is_admin or not user.verified:
            raise UnauthorizedException()
        user_context = UserContext(
            user_id=user.id,
            phone_number=user.phone_number,
            email=user.email,
            verified=user.verified,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_admin=user.is_admin,
            last_login_at=user.last_login_at,
            display_name=user.display_name,
            gender=user.gender,
            is_ministry=user.is_ministry,
            login_admin=True,
            token=token,
            token_payload=payload.model_dump(),
            username=user.email.split("@")[0]
        )
        set_user_context(user_context)

    @staticmethod
    @inject
    async def verify_user(
        request: Request,
        token: str,
        user_handler: UserHandler = Provide[Container.user_handler],
    ):
        """
        TODO: refactor this method, decouple firebase provider from this method and implement own provider for user authentication
        Verify the Firebase token only at user login
        :param request:
        :param token:
        :param user_handler:
        :return:
        """
        try:
            # TODO: implement own provider for user authentication
            pass
        except Exception:
            raise InvalidTokenException()

        try:
            user: SUserDetail = await user_handler.get_user_detail_by_id(payload.sub)
        except Exception:
            raise UnauthorizedException()
        if not user:
            raise UnauthorizedException()
        if not user.is_active or not user.verified:
            raise UnauthorizedException()

        user_context = UserContext(
            user_id=user.id,
            phone_number=user.phone_number,
            email=user.email,
            verified=user.verified,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_admin=user.is_admin,
            last_login_at=user.last_login_at,
            display_name=user.display_name,
            gender=user.gender,
            is_ministry=user.is_ministry,
            login_admin=False,
            token=token,
            # token_payload=payload.model_dump(),
            username=user.email.split("@")[0]
        )
        set_user_context(user_context)
