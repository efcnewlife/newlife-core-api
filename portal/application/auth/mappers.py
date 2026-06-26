"""
Map auth application results to API serializers.
"""
from portal.application.auth.results import AdminProfileResult, LoginResult, TokenResult, UserSensitive
from portal.serializers.admin.v1.auth import AdminInfo, AdminLoginResponse
from portal.serializers.mixins import TokenResponse


def normalize_user_for_token(user: UserSensitive) -> UserSensitive:
    """
    Ensure token-related name fields are non-null strings.
    :param user:
    :return:
    """
    data = user.model_dump()
    data["first_name"] = data.get("first_name") or ""
    data["last_name"] = data.get("last_name") or ""
    return UserSensitive.model_validate(data)


def token_result_to_api(result: TokenResult) -> TokenResponse:
    """
    Map token result to API response model.
    :param result:
    :return:
    """
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


def admin_profile_result_to_api(result: AdminProfileResult) -> AdminInfo:
    """
    Map admin profile result to API response model.
    :param result:
    :return:
    """
    return AdminInfo(
        id=result.id,
        email=result.email,
        first_name=result.first_name,
        last_name=result.last_name,
        preferred_name=result.preferred_name,
        roles=result.roles,
        preferred_locale_id=result.preferred_locale_id,
        last_login_at=result.last_login_at,
    )


def login_result_to_api(result: LoginResult) -> AdminLoginResponse:
    """
    Map login result to API response model.
    :param result:
    :return:
    """
    return AdminLoginResponse(
        admin=admin_profile_result_to_api(result.admin),
        token=token_result_to_api(result.token),
    )
