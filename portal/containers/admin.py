"""
Admin bounded context application services.
"""

from dependency_injector import containers, providers

from portal.application.audit.rbac_audit_service import RbacAuditService
from portal.application.auth.admin_user_service import AdminUserService
from portal.application.auth.login_service import LoginService
from portal.application.auth.microsoft_auth_service import MicrosoftAuthService
from portal.application.auth.mock_login_auth_service import MockLoginAuthService
from portal.application.auth.refresh_token_service import RefreshTokenService
from portal.application.auth.user_read_service import UserReadService
from portal.application.locale.locale_service import LocaleService
from portal.application.rbac.permission_service import PermissionService
from portal.application.rbac.resource_service import ResourceService
from portal.application.rbac.role_service import RoleService
from portal.application.rbac.verb_service import VerbService
from portal.application.system.setting_service import SettingService
from portal.config import settings as app_settings
from portal.containers.content import ContentContainer
from portal.containers.facility import FacilityContainer
from portal.containers.org import OrgContainer
from portal.domain.auth.member_web_app import MemberWebAppRegistry, parse_member_web_apps
from portal.infrastructure.cache.locale_cache import LocaleCache
from portal.infrastructure.cache.permission_cache import PermissionCache
from portal.infrastructure.cache.role_cache import RoleCache
from portal.infrastructure.cache.setting_cache import SettingCache
from portal.infrastructure.cache.verb_list_cache import VerbListCache
from portal.infrastructure.persistence.repositories.locale_repository import LocaleRepository
from portal.infrastructure.persistence.repositories.permission_repository import PermissionRepository
from portal.infrastructure.persistence.repositories.resource_repository import ResourceRepository
from portal.infrastructure.persistence.repositories.role_repository import RoleRepository
from portal.infrastructure.persistence.repositories.system.setting_repository import SettingRepository
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.infrastructure.persistence.repositories.verb_repository import VerbRepository
from portal.libs.authorization.permission_checker import PermissionChecker


class AdminContainer(containers.DeclarativeContainer):
    """Admin portal application services."""

    core = providers.DependenciesContainer()

    member_web_app_registry = providers.Singleton(lambda: MemberWebAppRegistry(parse_member_web_apps(app_settings.MEMBER_WEB_APPS)))

    rbac_audit_service = providers.Factory(RbacAuditService)

    user_repository = providers.Factory(UserRepository, session=core.request_session)
    user_read_service = providers.Factory(UserReadService, user_repository=user_repository)

    locale_repository = providers.Factory(LocaleRepository, session=core.request_session)
    locale_cache = providers.Factory(LocaleCache, redis_client=core.redis_client)
    locale_service = providers.Factory(LocaleService, locale_repository=locale_repository, locale_cache=locale_cache)

    setting_repository = providers.Factory(SettingRepository, session=core.request_session)
    setting_cache = providers.Factory(SettingCache, redis_client=core.redis_client)
    setting_service = providers.Factory(SettingService, setting_repository=setting_repository, setting_cache=setting_cache)

    permission_repository = providers.Factory(PermissionRepository, session=core.request_session)
    permission_cache = providers.Factory(PermissionCache, redis_client=core.redis_client)
    permission_service = providers.Factory(
        PermissionService, permission_repository=permission_repository, permission_cache=permission_cache, rbac_audit_service=rbac_audit_service
    )

    resource_repository = providers.Factory(ResourceRepository, session=core.request_session)
    resource_service = providers.Factory(ResourceService, resource_repository=resource_repository, rbac_audit_service=rbac_audit_service)

    role_repository = providers.Factory(RoleRepository, session=core.request_session)
    role_cache = providers.Factory(RoleCache, redis_client=core.redis_client)
    role_service = providers.Factory(RoleService, role_repository=role_repository, role_cache=role_cache, rbac_audit_service=rbac_audit_service)

    admin_user_service = providers.Factory(
        AdminUserService,
        user_repository=user_repository,
        password_provider=core.password_provider,
        role_service=role_service,
        permission_service=permission_service,
    )

    login_service = providers.Factory(
        LoginService,
        user_repository=user_repository,
        jwt_provider=core.jwt_provider,
        refresh_token_provider=core.refresh_token_provider,
        password_provider=core.password_provider,
        role_service=role_service,
        permission_service=permission_service,
        member_refresh_app_binding_provider=core.member_refresh_app_binding_provider,
    )
    refresh_token_service = providers.Factory(
        RefreshTokenService,
        user_repository=user_repository,
        jwt_provider=core.jwt_provider,
        refresh_token_provider=core.refresh_token_provider,
        token_blacklist_provider=core.token_blacklist_provider,
        role_service=role_service,
        permission_service=permission_service,
        member_web_app_registry=member_web_app_registry,
        member_refresh_app_binding_provider=core.member_refresh_app_binding_provider,
    )
    microsoft_auth_service = providers.Factory(
        MicrosoftAuthService,
        user_repository=user_repository,
        microsoft_oidc_provider=core.microsoft_oidc_provider,
        login_service=login_service,
        member_web_app_registry=member_web_app_registry,
    )
    mock_login_auth_service = providers.Factory(
        MockLoginAuthService, user_repository=user_repository, login_service=login_service, member_web_app_registry=member_web_app_registry
    )

    verb_repository = providers.Factory(VerbRepository, session=core.request_session)
    verb_list_cache = providers.Factory(VerbListCache, redis_client=core.redis_client)
    verb_service = providers.Factory(VerbService, verb_repository=verb_repository, verb_list_cache=verb_list_cache)

    permission_checker = providers.Factory(PermissionChecker, redis_client=core.redis_client)

    org = providers.Container(OrgContainer, core=core)
    content = providers.Container(ContentContainer, core=core, rbac_audit_service=rbac_audit_service)
    facility = providers.Container(FacilityContainer, core=core, setting_service=setting_service, file_service=content.file_service)
