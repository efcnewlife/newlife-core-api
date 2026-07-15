"""
Unit tests for MSGraphUsers mapping and pagination.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from msgraph_beta.generated.models.user import User
from msgraph_beta.generated.models.user_collection_response import UserCollectionResponse

from portal.providers.ms_graph.models import GraphUserRecord
from portal.providers.ms_graph.users import MSGraphUsers


def test_parse_user_maps_sdk_user() -> None:
    user = User(
        id="oid-1",
        mail="jay@efcnewlife.org",
        given_name="Jay",
        surname="Hsia",
        display_name="Jay Hsia",
        account_enabled=True,
        user_principal_name="jay@efcnewlife.org",
        user_type="Member",
    )
    record = MSGraphUsers._parse_user(user)
    assert record is not None
    assert record == GraphUserRecord(
        object_id="oid-1",
        email="jay@efcnewlife.org",
        given_name="Jay",
        surname="Hsia",
        display_name="Jay Hsia",
        account_enabled=True,
        user_principal_name="jay@efcnewlife.org",
        user_type="Member",
    )


def test_parse_user_skips_missing_id() -> None:
    assert MSGraphUsers._parse_user(User(id=None, mail="a@b.c")) is None
    assert MSGraphUsers._parse_user(User(id="  ", mail="a@b.c")) is None


def test_parse_user_defaults_account_enabled() -> None:
    record = MSGraphUsers._parse_user(User(id="oid-2", account_enabled=None))
    assert record is not None
    assert record.account_enabled is True


@pytest.mark.asyncio
async def test_list_users_paginates_across_pages(mocker) -> None:
    page_one = UserCollectionResponse(
        value=[
            User(id="u1", given_name="A", surname="One", mail="a@efcnewlife.org"),
        ],
        odata_next_link="https://graph.microsoft.com/beta/users?$skiptoken=abc",
    )
    page_two = UserCollectionResponse(
        value=[
            User(id="u2", given_name="B", surname="Two", mail="b@efcnewlife.org"),
        ],
        odata_next_link=None,
    )

    users = MSGraphUsers()
    mocker.patch.object(users, "is_configured", return_value=True)
    mocker.patch.object(users, "get_users", new=AsyncMock(return_value=page_one))
    mocker.patch.object(users, "get_next_link", new=AsyncMock(return_value=page_two))

    records = [
        record
        async for record in users.list_users(filter_expr="userType eq 'Member'")
    ]

    assert [r.object_id for r in records] == ["u1", "u2"]
    users.get_users.assert_awaited_once()
    users.get_next_link.assert_awaited_once_with(
        "https://graph.microsoft.com/beta/users?$skiptoken=abc"
    )


@pytest.mark.asyncio
async def test_list_users_requires_configuration() -> None:
    users = MSGraphUsers()
    users._tenant_id = None
    users._client_id = None
    users._client_secret = None

    with pytest.raises(RuntimeError, match="not configured"):
        async for _ in users.list_users(filter_expr="userType eq 'Member'"):
            pass


def test_microsoft_graph_provider_is_configured(mocker) -> None:
    from portal.providers.microsoft_graph_provider import MicrosoftGraphProvider

    stub_users = SimpleNamespace(is_configured=lambda: True)
    provider = MicrosoftGraphProvider(users_factory=lambda: stub_users)
    assert provider.is_configured() is True
