"""
Tests for MicrosoftAuthService profile bootstrap on login.
"""
from uuid import uuid4

import pytest

from portal.application.auth.commands import MicrosoftLoginCommand
from portal.application.auth.microsoft_auth_service import (
    MicrosoftAuthService,
    _profile_fields_from_microsoft_claims,
)
from portal.application.auth.results import AdminProfileResult, LoginResult, TokenResult, UserSensitive
from portal.exceptions.responses import UnauthorizedException


SAMPLE_CLAIMS = {
    "email": "jay.hsia@efcnewlife.org",
    "family_name": "Hsia",
    "given_name": "Jay",
    "name": "Jay Hsia",
    "oid": "61a98ff3-760a-4756-b88c-f981c87eb54c",
    "tid": "1611ced1-d776-4134-acca-a77746e45623",
    "upn": "jay.hsia@efcnewlife.org",
    "exp": 1780606257,
}


def test_profile_fields_from_microsoft_claims_uses_given_and_family_name():
    first_name, last_name, preferred_name = _profile_fields_from_microsoft_claims(SAMPLE_CLAIMS)
    assert first_name == "Jay"
    assert last_name == "Hsia"
    assert preferred_name == "Jay Hsia"


def test_profile_fields_from_microsoft_claims_splits_display_name():
    claims = {"name": "Jay Hsia", "upn": "jay.hsia@efcnewlife.org"}
    first_name, last_name, preferred_name = _profile_fields_from_microsoft_claims(claims)
    assert first_name == "Jay"
    assert last_name == "Hsia"
    assert preferred_name == "Jay Hsia"


class StubMicrosoftOidcProvider:
    def __init__(self, claims=None, configured=True):
        self._claims = claims or SAMPLE_CLAIMS
        self._configured = configured

    def is_configured(self):
        return self._configured

    def verify_id_token(self, _id_token):
        return self._claims


class StubLoginService:
    async def complete_admin_login(self, user):
        return LoginResult(
            admin=AdminProfileResult(
                id=user.id,
                email=user.email or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                preferred_name=user.preferred_name,
                roles=[],
                preferred_locale_id=user.preferred_locale_id,
                last_login_at=user.last_login_at,
            ),
            token=TokenResult(
                access_token="access",
                refresh_token="refresh",
                expires_in=3600,
            ),
        )


class StubUserRepository:
    def __init__(self, account: UserSensitive, with_profile: bool = False):
        self._account = account
        self._with_profile = with_profile
        self.profile_created: list[tuple] = []
        self.third_party_upserts: list = []

    async def get_sensitive_by_email(self, email):
        if self._with_profile:
            return self._account
        return None

    async def get_sensitive_by_email_without_profile(self, email):
        return self._account

    async def user_profile_exists(self, user_id):
        return self._with_profile

    async def create_user_profile(self, user_id, first_name, last_name, preferred_name=None):
        self.profile_created.append((user_id, first_name, last_name, preferred_name))
        self._with_profile = True
        self._account = self._account.model_copy(
            update={
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": preferred_name,
            }
        )

    async def upsert_auth_user_third_party(self, **kwargs):
        self.third_party_upserts.append(kwargs)

    async def update_last_login_at(self, user_id, last_login_at):
        pass


@pytest.mark.asyncio
async def test_microsoft_login_creates_profile_when_missing():
    user_id = uuid4()
    account = UserSensitive(
        id=user_id,
        email="jay.hsia@efcnewlife.org",
        verified=True,
        is_active=True,
        is_admin=True,
        is_superuser=False,
    )
    repo = StubUserRepository(account=account, with_profile=False)
    service = MicrosoftAuthService(
        user_repository=repo,
        microsoft_oidc_provider=StubMicrosoftOidcProvider(),
        login_service=StubLoginService(),
    )

    result = await service.microsoft_login(MicrosoftLoginCommand(id_token="token"))

    assert isinstance(result, LoginResult)
    assert len(repo.profile_created) == 1
    created = repo.profile_created[0]
    assert created[0] == user_id
    assert created[1] == "Jay"
    assert created[2] == "Hsia"
    assert created[3] == "Jay Hsia"


@pytest.mark.asyncio
async def test_microsoft_login_rejects_unknown_user():
    class EmptyRepo(StubUserRepository):
        async def get_sensitive_by_email_without_profile(self, email):
            return None

    service = MicrosoftAuthService(
        user_repository=EmptyRepo(
            account=UserSensitive(
                id=uuid4(),
                email="missing@example.com",
                verified=True,
                is_active=True,
                is_admin=True,
            ),
        ),
        microsoft_oidc_provider=StubMicrosoftOidcProvider(),
        login_service=StubLoginService(),
    )

    with pytest.raises(UnauthorizedException, match="User not found"):
        await service.microsoft_login(MicrosoftLoginCommand(id_token="token"))
