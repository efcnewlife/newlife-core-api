"""
Tests for Microsoft user directory sync service.
"""
import json
from uuid import UUID, uuid4

import pytest

from portal.application.auth.results import UserSensitive
from portal.application.cli.microsoft_user_sync_service import (
    DEFAULT_SYNC_FILTER,
    MicrosoftUserSyncService,
    is_real_person,
    is_sync_email_domain,
    resolve_sync_email,
)
from portal.domain.member.constants import AccountKind
from portal.libs.consts.enums import ThirdPartyProvider
from portal.providers.microsoft_graph_provider import GraphUserRecord

TENANT_ID = UUID("1611ced1-d776-4134-acca-a77746e45623")


def _load_example_graph_user() -> GraphUserRecord:
    """Example real-person Graph user for sync tests."""
    return GraphUserRecord(
        object_id=str(uuid4()),
        email="jay.hsia@efcnewlife.org",
        given_name="Jay",
        surname="Hsia",
        display_name="Jay Hsia",
        account_enabled=True,
        user_principal_name="jay.hsia@efcnewlife.org",
        user_type="Member",
    )


class StubGraphProvider:
    def __init__(self, records: list[GraphUserRecord]):
        self._records = records

    def is_configured(self) -> bool:
        return True

    async def list_users(self, *, filter_expr: str, select_fields=None, page_size: int = 999):
        for record in self._records:
            yield record


class StubSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class StubUserRepository:
    def __init__(
        self,
        *,
        by_third_party: dict[str, UUID] | None = None,
        by_email: dict[str, UserSensitive] | None = None,
        profiles: set[UUID] | None = None,
    ):
        self.by_third_party = by_third_party or {}
        self.by_email = by_email or {}
        self.profiles = profiles or set()
        self.created_users: list[dict] = []
        self.updated_profiles: list[dict] = []
        self.active_updates: list[tuple[UUID, bool]] = []
        self.third_party_upserts: list[dict] = []
        self.profile_creates: list[dict] = []

    async def get_user_id_by_third_party(self, provider, provider_uid: str):
        if provider != ThirdPartyProvider.MICROSOFT:
            return None
        return self.by_third_party.get(provider_uid)

    async def get_sensitive_by_email_without_profile(self, email: str):
        return self.by_email.get(email.strip().lower())

    async def user_profile_exists(self, user_id: UUID) -> bool:
        return user_id in self.profiles

    async def create_directory_user(self, user_id, email, **kwargs):
        self.created_users.append({"user_id": user_id, "email": email, **kwargs})

    async def update_directory_user_profile(self, user_id, first_name, last_name, preferred_name=None):
        self.updated_profiles.append(
            {
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": preferred_name,
            }
        )

    async def update_user_active_flag(self, user_id, is_active: bool):
        self.active_updates.append((user_id, is_active))

    async def create_user_profile(self, user_id, first_name, last_name, preferred_name=None):
        self.profile_creates.append(
            {
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": preferred_name,
            }
        )

    async def upsert_auth_user_third_party(self, **kwargs):
        self.third_party_upserts.append(kwargs)


def test_default_sync_filter_includes_efcnewlife_domain():
    assert "efcnewlife.org" in DEFAULT_SYNC_FILTER
    assert "userType eq 'Member'" in DEFAULT_SYNC_FILTER
    assert "givenName ne null" in DEFAULT_SYNC_FILTER
    assert "surname ne null" in DEFAULT_SYNC_FILTER


def test_is_real_person_requires_given_name_and_surname():
    assert is_real_person(
        GraphUserRecord(object_id=str(uuid4()), given_name="Jay", surname="Hsia")
    ) is True
    assert is_real_person(
        GraphUserRecord(object_id=str(uuid4()), given_name="Jay", surname=None)
    ) is False
    assert is_real_person(
        GraphUserRecord(
            object_id=str(uuid4()),
            given_name=" ",
            surname="Room",
            display_name="Conference Room A",
            email="room@efcnewlife.org",
        )
    ) is False


def test_resolve_sync_email_prefers_mail():
    record = GraphUserRecord(
        object_id=str(uuid4()),
        email="dev@efcnewlife.org",
        user_principal_name="other@example.com",
    )
    assert resolve_sync_email(record) == "dev@efcnewlife.org"


def test_is_sync_email_domain():
    assert is_sync_email_domain("dev@efcnewlife.org") is True
    assert is_sync_email_domain("guest@gmail.com") is False


@pytest.mark.asyncio
async def test_sync_creates_new_user(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = _load_example_graph_user()
    session = StubSession()
    repo = StubUserRepository()
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.created == 1
    assert stats.total_fetched == 1
    assert len(repo.created_users) == 1
    created = repo.created_users[0]
    assert created["email"] == "jay.hsia@efcnewlife.org"
    assert created["account_kind"] == AccountKind.MEMBER.value
    assert created["verified"] is True
    assert created["is_admin"] is False
    assert len(repo.third_party_upserts) == 1
    assert repo.third_party_upserts[0]["provider_uid"] == record.object_id
    assert session.committed is True


@pytest.mark.asyncio
async def test_sync_skips_non_efcnewlife_domain(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = GraphUserRecord(
        object_id=str(uuid4()),
        email="guest@gmail.com",
        user_principal_name="guest@gmail.com",
        account_enabled=True,
        user_type="Member",
    )
    session = StubSession()
    repo = StubUserRepository()
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.skipped_domain_mismatch == 1
    assert stats.created == 0
    assert len(repo.created_users) == 0


@pytest.mark.asyncio
async def test_sync_skips_resource_without_given_name_and_surname(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = GraphUserRecord(
        object_id=str(uuid4()),
        email="conf-room-a@efcnewlife.org",
        user_principal_name="conf-room-a@efcnewlife.org",
        display_name="Conference Room A",
        account_enabled=True,
        user_type="Member",
    )
    session = StubSession()
    repo = StubUserRepository()
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.skipped_not_real_person == 1
    assert stats.created == 0
    assert len(repo.created_users) == 0


@pytest.mark.asyncio
async def test_sync_skips_service_account(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = GraphUserRecord(
        object_id=str(uuid4()),
        email="dev@efcnewlife.org",
        user_principal_name="dev@efcnewlife.org",
        given_name="DEV",
        surname="EFCNL",
        display_name="DEV EFCNL",
        account_enabled=True,
        user_type="Member",
    )
    session = StubSession()
    repo = StubUserRepository()
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.skipped_service_account == 1
    assert stats.created == 0


@pytest.mark.asyncio
async def test_sync_links_existing_email(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = _load_example_graph_user()
    existing_id = uuid4()
    session = StubSession()
    repo = StubUserRepository(
        by_email={
            "jay.hsia@efcnewlife.org": UserSensitive(
                id=existing_id,
                email="jay.hsia@efcnewlife.org",
                verified=True,
                is_active=True,
                is_admin=False,
            ),
        },
        profiles={existing_id},
    )
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.linked == 1
    assert len(repo.third_party_upserts) == 1
    assert repo.third_party_upserts[0]["user_id"] == existing_id


@pytest.mark.asyncio
async def test_sync_updates_existing_third_party_user(monkeypatch):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = _load_example_graph_user()
    existing_id = uuid4()
    session = StubSession()
    repo = StubUserRepository(by_third_party={record.object_id: existing_id})
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=False)

    assert stats.updated == 1
    assert len(repo.updated_profiles) == 1
    assert repo.active_updates == [(existing_id, True)]


@pytest.mark.asyncio
async def test_sync_dry_run_does_not_write(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "portal.application.cli.microsoft_user_sync_service.settings.AZURE_TENANT_ID",
        str(TENANT_ID),
    )
    record = _load_example_graph_user()
    session = StubSession()
    repo = StubUserRepository()
    service = MicrosoftUserSyncService(
        session=session,
        user_repository=repo,
        graph_provider=StubGraphProvider([record]),
    )

    stats = await service.run(dry_run=True, dry_run_output_dir=tmp_path)

    assert stats.created == 1
    assert len(repo.created_users) == 0
    assert session.rolled_back is True
    assert session.committed is False
    assert stats.dry_run_output_dir == str(tmp_path.resolve())
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    actions = json.loads((tmp_path / "actions.json").read_text(encoding="utf-8"))
    assert summary["created"] == 1
    assert summary["dry_run"] is True
    assert len(actions) == 1
    assert actions[0]["action"] == "create"
    assert actions[0]["email"] == "jay.hsia@efcnewlife.org"
