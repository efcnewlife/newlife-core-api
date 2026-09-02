"""
Member mock login for dev/staging QA (passwordless testing accounts).
"""

from typing import Optional

from portal.application.auth.commands import MockLoginCommand
from portal.application.auth.login_service import LoginService
from portal.application.auth.member_web_app_resolver import resolve_request_app_code
from portal.application.auth.results import MemberLoginResult, UserSensitive
from portal.config import settings
from portal.domain.auth.member_web_app import MemberWebAppRegistry
from portal.domain.auth.ports import UserRepositoryPort
from portal.exceptions.responses import UnauthorizedException
from portal.libs.contexts.request_context import get_request_context
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace

MOCK_LOGIN_UNAUTHORIZED_DETAIL = "Unauthorized"


class MockLoginAuthService:
    """Passwordless mock login for registered testing-account emails."""

    def __init__(self, user_repository: UserRepositoryPort, login_service: LoginService, member_web_app_registry: Optional[MemberWebAppRegistry] = None):
        self._repository = user_repository
        self._login_service = login_service
        self._member_web_app_registry = member_web_app_registry

    def _is_enabled(self) -> bool:
        return settings.MOCK_LOGIN_ENABLED and not settings.is_prod

    def _audit(self, *, outcome: str, email: str, reason: str, app_code: Optional[str] = None) -> None:
        logger.info("mock_login attempt outcome=%s email=%s app_code=%s reason=%s", outcome, email, app_code or "-", reason)

    def _fail(self, *, email: str, reason: str, app_code: Optional[str] = None) -> None:
        self._audit(outcome="failure", email=email, reason=reason, app_code=app_code)
        raise UnauthorizedException(detail=MOCK_LOGIN_UNAUTHORIZED_DETAIL)

    def _email_has_testing_suffix(self, email: str) -> bool:
        suffix = settings.TESTING_ACCOUNT_EMAIL_SUFFIX.strip().lower()
        if not suffix:
            return False
        return email.endswith(suffix)

    def _secret_is_valid(self) -> bool:
        configured_secret = (settings.MOCK_LOGIN_SECRET or "").strip()
        req_ctx = get_request_context()
        header_secret = None
        if req_ctx and req_ctx.headers:
            header_secret = req_ctx.headers.mock_login_secret
        provided = (header_secret or "").strip()
        if settings.ENV.lower() == "stg":
            return bool(configured_secret) and provided == configured_secret
        if not configured_secret:
            return True
        return provided == configured_secret

    @distributed_trace()
    async def mock_member_login(self, command: MockLoginCommand) -> MemberLoginResult:
        email = command.email.strip().lower()
        app_code: Optional[str] = None

        if not self._is_enabled():
            self._fail(email=email, reason="disabled")

        if not self._secret_is_valid():
            self._fail(email=email, reason="invalid_secret")

        if not self._email_has_testing_suffix(email):
            self._fail(email=email, reason="invalid_suffix")

        if not self._member_web_app_registry:
            self._fail(email=email, reason="registry_unconfigured")

        app_code = resolve_request_app_code(self._member_web_app_registry, required=False)
        if not app_code:
            self._fail(email=email, reason="unknown_origin")

        user: Optional[UserSensitive] = await self._repository.get_sensitive_by_email(email)
        if not user or not user.verified or not user.is_active:
            self._fail(email=email, reason="user_not_allowed", app_code=app_code)

        result = await self._login_service.complete_member_login(user, app_code=app_code)
        self._audit(outcome="success", email=email, reason="ok", app_code=app_code)
        return result
