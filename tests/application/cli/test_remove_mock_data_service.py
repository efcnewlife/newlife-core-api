"""
Tests for the remove-mock-data orchestration service (fake session seam).
"""

from collections import defaultdict
from uuid import UUID, uuid4

import pytest

from portal.application.cli.remove_mock_data_service import LEGACY_DEMO_ACCOUNT_EMAILS, MockDataDependencyError, RemoveMockDataService

MOCK_SUFFIX = "@test.local"

PERSONAL_ID = uuid4()
STEWARD_ID = uuid4()
OWNER_ID = uuid4()
REAL_USER_ID = uuid4()

MINISTRY_ID = uuid4()
OTHER_REAL_MINISTRY_ID = uuid4()

_TABLE_ATTR = {
    "AuthUser": "users",
    "OrgMinistryMember": "ministry_members",
    "FacilityBooking": "bookings",
    "FacilityBookingSeries": "series",
    "FacilityBookingDraft": "drafts",
    "OrgMinistry": "ministries",
    "OrgMinistryTranslation": "translations",
    "OrgMinistryApproval": "approvals",
    "FacilityRoomSlotTemplate": "slot_templates",
    "FacilityRoomBlackout": "blackouts",
}


def _matches(row: dict, key: str, op: str, value) -> bool:
    row_value = row.get(key)
    if op == "in_op":
        return row_value in value
    if op == "not_in_op":
        return row_value not in value
    if op == "is_not":
        return row_value is not None
    if op == "like_op":
        if value.startswith("%") and value.endswith("%") and len(value) > 1:
            return value[1:-1] in row_value
        if value.startswith("%"):
            return row_value.endswith(value[1:])
        if value.endswith("%"):
            return row_value.startswith(value[:-1])
        return row_value == value
    if op == "eq":
        return row_value == value
    raise NotImplementedError(op)


class FakeSession:
    """Minimal fake standing in for portal.libs.database.Session, backed by in-memory tables."""

    def __init__(
        self,
        *,
        users: list[dict] | None = None,
        ministry_members: list[dict] | None = None,
        bookings: list[dict] | None = None,
        series: list[dict] | None = None,
        drafts: list[dict] | None = None,
        ministries: list[dict] | None = None,
        translations: list[dict] | None = None,
        approvals: list[dict] | None = None,
        slot_templates: list[dict] | None = None,
        blackouts: list[dict] | None = None,
    ):
        self.users = list(users or [])
        self.ministry_members = list(ministry_members or [])
        self.bookings = list(bookings or [])
        self.series = list(series or [])
        self.drafts = list(drafts or [])
        self.ministries = list(ministries or [])
        self.translations = list(translations or [])
        self.approvals = list(approvals or [])
        self.slot_templates = list(slot_templates or [])
        self.blackouts = list(blackouts or [])

        self.deleted: dict[str, list[set]] = defaultdict(list)
        self.committed = False
        self.rolled_back = False

        self._pending_model_name = None
        self._pending_cols = None
        self._pending_wheres: list[tuple] = []
        self._pending_delete_model = None

    def select(self, *cols):
        self._pending_cols = cols
        self._pending_model_name = cols[0].class_.__name__
        self._pending_wheres = []
        return self

    def where(self, *args, **kwargs):
        if args:
            cond = args[0]
            key = cond.left.key
            op = cond.operator.__name__
            value = getattr(cond.right, "value", None)  # NULL literal (`isnot(None)`) has no .value
            self._pending_wheres.append((key, op, value))
        return self

    def _rows(self, model_name: str) -> list[dict]:
        return getattr(self, _TABLE_ATTR[model_name])

    def _filtered(self) -> list[dict]:
        rows = self._rows(self._pending_model_name)
        return [row for row in rows if all(_matches(row, k, o, v) for k, o, v in self._pending_wheres)]

    async def fetchvals(self):
        col_key = self._pending_cols[0].key
        return [row[col_key] for row in self._filtered()]

    async def fetch(self):
        keys = [c.key for c in self._pending_cols]
        return [{k: row.get(k) for k in keys} for row in self._filtered()]

    def delete(self, model):
        self._pending_delete_model = model.__name__
        self._pending_wheres = []
        return self

    async def execute(self):
        model_name = self._pending_delete_model
        matched = self._rows(model_name)
        to_delete = [row for row in matched if all(_matches(row, k, o, v) for k, o, v in self._pending_wheres)]
        deleted_ids = {row["id"] for row in to_delete}
        self.deleted[model_name].append(deleted_ids)
        setattr(self, _TABLE_ATTR[model_name], [row for row in matched if row["id"] not in deleted_ids])
        self._pending_delete_model = None
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _mock_users() -> list[dict]:
    return [
        {"id": PERSONAL_ID, "email": "personal.aaaa@test.local"},
        {"id": STEWARD_ID, "email": "steward.aaaa@test.local"},
        {"id": OWNER_ID, "email": "owner.aaaa@test.local"},
        {"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"},
    ]


@pytest.mark.asyncio
async def test_remove_mock_data_deletes_every_mock_user_and_derived_data():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}, {"ministry_id": MINISTRY_ID, "user_id": OWNER_ID}],
        bookings=[{"id": uuid4(), "user_id": PERSONAL_ID, "ministry_id": None}, {"id": uuid4(), "user_id": STEWARD_ID, "ministry_id": MINISTRY_ID}],
        series=[{"id": uuid4(), "user_id": STEWARD_ID, "ministry_id": MINISTRY_ID}],
        drafts=[{"id": uuid4(), "user_id": PERSONAL_ID, "ministry_id": None}],
        ministries=[{"id": MINISTRY_ID}],
        approvals=[{"ministry_id": MINISTRY_ID, "requested_by_id": STEWARD_ID, "resolved_by_id": None}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_user_count == 3
    assert result.removed_ministry_count == 1
    assert result.removed_booking_count == 2
    assert result.removed_series_count == 1
    assert result.removed_draft_count == 1

    assert session.deleted["AuthUser"] == [{PERSONAL_ID, STEWARD_ID, OWNER_ID}]
    assert session.deleted["OrgMinistry"] == [{MINISTRY_ID}]
    assert session.committed is True
    assert session.rolled_back is False

    # The real user and their account row are untouched.
    assert any(row["id"] == REAL_USER_ID for row in session.users)


@pytest.mark.asyncio
async def test_remove_mock_data_never_deletes_models_outside_mock_scope():
    session = FakeSession(users=_mock_users(), ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}], ministries=[{"id": MINISTRY_ID}])
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    await service.run()

    assert set(session.deleted.keys()) <= {
        "FacilityBooking",
        "FacilityBookingSeries",
        "FacilityBookingDraft",
        "OrgMinistry",
        "AuthUser",
        "FacilityRoomSlotTemplate",
        "FacilityRoomBlackout",
    }


@pytest.mark.asyncio
async def test_remove_mock_data_is_a_no_op_when_no_mock_users_exist():
    session = FakeSession(users=[{"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"}])
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_user_count == 0
    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_leaves_ministries_with_only_non_mock_members_alone():
    session = FakeSession(
        users=_mock_users(), ministry_members=[{"ministry_id": OTHER_REAL_MINISTRY_ID, "user_id": REAL_USER_ID}], ministries=[{"id": OTHER_REAL_MINISTRY_ID}]
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_ministry_count == 0
    assert session.deleted.get("OrgMinistry", []) == []
    assert any(row["id"] == OTHER_REAL_MINISTRY_ID for row in session.ministries)


@pytest.mark.asyncio
async def test_remove_mock_data_fails_when_candidate_ministry_has_a_non_mock_member():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}, {"ministry_id": MINISTRY_ID, "user_id": REAL_USER_ID}],
        ministries=[{"id": MINISTRY_ID}],
        translations=[{"ministry_id": MINISTRY_ID, "name": "Mock Ministry ABCD"}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError, match="Mock Ministry ABCD"):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_leaves_marked_fixtures_when_a_non_mock_dependency_blocks_cleanup():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}, {"ministry_id": MINISTRY_ID, "user_id": REAL_USER_ID}],
        ministries=[{"id": MINISTRY_ID}],
        translations=[{"ministry_id": MINISTRY_ID, "name": "Mock Ministry ABCD"}],
        slot_templates=slot_templates,
        blackouts=blackouts,
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError, match="Mock Ministry ABCD"):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False
    assert any(row["id"] == MOCK_SLOT_TEMPLATE_ID for row in session.slot_templates)
    assert any(row["id"] == MOCK_BLACKOUT_ID for row in session.blackouts)


@pytest.mark.asyncio
async def test_remove_mock_data_fails_when_candidate_ministry_has_a_non_mock_booking():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}],
        bookings=[{"id": uuid4(), "user_id": REAL_USER_ID, "ministry_id": MINISTRY_ID}],
        ministries=[{"id": MINISTRY_ID}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError, match=str(MINISTRY_ID)):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_fails_when_candidate_ministry_has_a_non_mock_recurring_series():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}],
        series=[{"id": uuid4(), "user_id": REAL_USER_ID, "ministry_id": MINISTRY_ID}],
        ministries=[{"id": MINISTRY_ID}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_fails_when_candidate_ministry_has_a_non_mock_draft():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}],
        drafts=[{"id": uuid4(), "user_id": REAL_USER_ID, "ministry_id": MINISTRY_ID}],
        ministries=[{"id": MINISTRY_ID}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_fails_when_candidate_ministry_has_a_non_mock_approval_decision():
    session = FakeSession(
        users=_mock_users(),
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}],
        approvals=[{"ministry_id": MINISTRY_ID, "requested_by_id": STEWARD_ID, "resolved_by_id": REAL_USER_ID}],
        ministries=[{"id": MINISTRY_ID}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError):
        await service.run()

    assert session.deleted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_remove_mock_data_honors_configured_email_suffix():
    users = [{"id": PERSONAL_ID, "email": "qa.owner@qa.test"}, {"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"}]
    session = FakeSession(users=users)
    service = RemoveMockDataService(session, email_suffix="@qa.test")

    result = await service.run()

    assert result.removed_user_count == 1
    assert session.deleted["AuthUser"] == [{PERSONAL_ID}]


MOCK_SLOT_TEMPLATE_ID = uuid4()
MANUAL_SLOT_TEMPLATE_ID = uuid4()
MOCK_BLACKOUT_ID = uuid4()
MANUAL_BLACKOUT_ID = uuid4()
SEED_SLOT_TEMPLATE_ID = uuid4()
SEED_BLACKOUT_ID = uuid4()
LEGACY_BOOKER_ID = uuid4()
ARBITRARY_LOCAL_ID = uuid4()
SEED_MINISTRY_ID = uuid4()


def _marked_fixture_rows() -> tuple[list[dict], list[dict]]:
    slot_templates = [
        {"id": MOCK_SLOT_TEMPLATE_ID, "name": "Mock all-week daytime (mock:dev-2026-09-18_1430)"},
        {"id": MANUAL_SLOT_TEMPLATE_ID, "name": "Sunday morning operator template"},
        {"id": SEED_SLOT_TEMPLATE_ID, "name": "seed:All-week daytime"},
    ]
    blackouts = [
        {"id": MOCK_BLACKOUT_ID, "name": "Mock campus holiday (mock:dev-2026-09-18_1430)"},
        {"id": MANUAL_BLACKOUT_ID, "name": "Choir rehearsal closure"},
        {"id": SEED_BLACKOUT_ID, "name": "seed:Campus holiday demo"},
    ]
    return slot_templates, blackouts


@pytest.mark.asyncio
async def test_remove_mock_data_deletes_mock_marked_slot_templates_and_blackouts():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(users=_mock_users(), slot_templates=slot_templates, blackouts=blackouts)
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_slot_template_count == 1
    assert result.removed_blackout_count == 1
    assert session.deleted["FacilityRoomSlotTemplate"] == [{MOCK_SLOT_TEMPLATE_ID}]
    assert session.deleted["FacilityRoomBlackout"] == [{MOCK_BLACKOUT_ID}]
    assert any(row["id"] == MANUAL_SLOT_TEMPLATE_ID for row in session.slot_templates)
    assert any(row["id"] == SEED_SLOT_TEMPLATE_ID for row in session.slot_templates)
    assert any(row["id"] == MANUAL_BLACKOUT_ID for row in session.blackouts)
    assert any(row["id"] == SEED_BLACKOUT_ID for row in session.blackouts)
    assert session.committed is True


@pytest.mark.asyncio
async def test_remove_mock_data_removes_marked_fixtures_when_no_mock_users_exist():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(users=[{"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"}], slot_templates=slot_templates, blackouts=blackouts)
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_user_count == 0
    assert result.removed_slot_template_count == 1
    assert result.removed_blackout_count == 1
    assert session.deleted["FacilityRoomSlotTemplate"] == [{MOCK_SLOT_TEMPLATE_ID}]
    assert session.deleted["FacilityRoomBlackout"] == [{MOCK_BLACKOUT_ID}]
    assert any(row["id"] == REAL_USER_ID for row in session.users)
    assert session.committed is True


def _legacy_and_local_users() -> list[dict]:
    return [
        {"id": LEGACY_BOOKER_ID, "email": "seed.booker.1@local.test"},
        {"id": ARBITRARY_LOCAL_ID, "email": "other.person@local.test"},
        {"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"},
    ]


@pytest.mark.asyncio
async def test_remove_mock_data_leaves_legacy_demo_identities_and_seed_markers_alone():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(
        users=_legacy_and_local_users(),
        ministry_members=[{"ministry_id": SEED_MINISTRY_ID, "user_id": LEGACY_BOOKER_ID}],
        ministries=[{"id": SEED_MINISTRY_ID}],
        translations=[{"ministry_id": SEED_MINISTRY_ID, "name": "seed: Demo Badminton"}],
        slot_templates=slot_templates,
        blackouts=blackouts,
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run()

    assert result.removed_user_count == 0
    assert result.removed_ministry_count == 0
    assert any(row["id"] == LEGACY_BOOKER_ID for row in session.users)
    assert any(row["id"] == SEED_MINISTRY_ID for row in session.ministries)
    assert any(row["id"] == SEED_SLOT_TEMPLATE_ID for row in session.slot_templates)
    assert any(row["id"] == SEED_BLACKOUT_ID for row in session.blackouts)


@pytest.mark.asyncio
async def test_include_legacy_demo_removes_exact_demo_identities_and_seed_markers_only():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(
        users=_legacy_and_local_users(),
        ministry_members=[{"ministry_id": SEED_MINISTRY_ID, "user_id": LEGACY_BOOKER_ID}],
        ministries=[{"id": SEED_MINISTRY_ID}],
        translations=[{"ministry_id": SEED_MINISTRY_ID, "name": "seed: Demo Badminton"}],
        slot_templates=slot_templates,
        blackouts=blackouts,
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run(include_legacy_demo=True)

    assert result.removed_user_count == 1
    assert result.removed_ministry_count == 1
    assert result.removed_slot_template_count == 2
    assert result.removed_blackout_count == 2
    assert session.deleted["AuthUser"] == [{LEGACY_BOOKER_ID}]
    assert session.deleted["OrgMinistry"] == [{SEED_MINISTRY_ID}]
    assert session.deleted["FacilityRoomSlotTemplate"] == [{MOCK_SLOT_TEMPLATE_ID, SEED_SLOT_TEMPLATE_ID}]
    assert session.deleted["FacilityRoomBlackout"] == [{MOCK_BLACKOUT_ID, SEED_BLACKOUT_ID}]
    assert any(row["id"] == ARBITRARY_LOCAL_ID for row in session.users)
    assert any(row["id"] == REAL_USER_ID for row in session.users)
    assert any(row["id"] == MANUAL_SLOT_TEMPLATE_ID for row in session.slot_templates)
    assert any(row["id"] == MANUAL_BLACKOUT_ID for row in session.blackouts)
    assert session.committed is True


@pytest.mark.asyncio
async def test_include_legacy_demo_fails_atomically_on_a_non_legacy_ministry_dependency():
    session = FakeSession(
        users=_legacy_and_local_users(),
        ministry_members=[{"ministry_id": SEED_MINISTRY_ID, "user_id": LEGACY_BOOKER_ID}, {"ministry_id": SEED_MINISTRY_ID, "user_id": REAL_USER_ID}],
        ministries=[{"id": SEED_MINISTRY_ID}],
        translations=[{"ministry_id": SEED_MINISTRY_ID, "name": "seed: Demo Badminton"}],
        slot_templates=[{"id": SEED_SLOT_TEMPLATE_ID, "name": "seed:All-week daytime"}],
        blackouts=[{"id": SEED_BLACKOUT_ID, "name": "seed:Campus holiday demo"}],
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError, match="seed: Demo Badminton"):
        await service.run(include_legacy_demo=True)

    assert session.deleted == {}
    assert session.committed is False
    assert any(row["id"] == LEGACY_BOOKER_ID for row in session.users)
    assert any(row["id"] == SEED_SLOT_TEMPLATE_ID for row in session.slot_templates)


@pytest.mark.asyncio
async def test_include_legacy_demo_fails_atomically_on_a_seed_marked_booking_owned_by_a_non_legacy_user():
    session = FakeSession(
        users=_legacy_and_local_users(), bookings=[{"id": uuid4(), "user_id": REAL_USER_ID, "ministry_id": None, "remark": "seed:personal-1 classroom-105"}]
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    with pytest.raises(MockDataDependencyError, match="seed-marked Booking"):
        await service.run(include_legacy_demo=True)

    assert session.deleted == {}
    assert session.committed is False
    assert any(row["id"] == REAL_USER_ID for row in session.users)
    assert len(session.bookings) == 1


@pytest.mark.asyncio
async def test_include_legacy_demo_still_removes_the_current_mock_snapshot():
    slot_templates, blackouts = _marked_fixture_rows()
    session = FakeSession(
        users=[
            {"id": PERSONAL_ID, "email": "personal.aaaa@test.local"},
            {"id": STEWARD_ID, "email": "steward.aaaa@test.local"},
            {"id": LEGACY_BOOKER_ID, "email": "seed.booker.1@local.test"},
            {"id": ARBITRARY_LOCAL_ID, "email": "other.person@local.test"},
            {"id": REAL_USER_ID, "email": "real.person@efcnewlife.org"},
        ],
        ministry_members=[{"ministry_id": MINISTRY_ID, "user_id": STEWARD_ID}, {"ministry_id": SEED_MINISTRY_ID, "user_id": LEGACY_BOOKER_ID}],
        ministries=[{"id": MINISTRY_ID}, {"id": SEED_MINISTRY_ID}],
        translations=[{"ministry_id": MINISTRY_ID, "name": "Mock Ministry ABCD"}, {"ministry_id": SEED_MINISTRY_ID, "name": "seed: Demo Badminton"}],
        slot_templates=slot_templates,
        blackouts=blackouts,
    )
    service = RemoveMockDataService(session, email_suffix=MOCK_SUFFIX)

    result = await service.run(include_legacy_demo=True)

    assert result.removed_user_count == 3
    assert result.removed_ministry_count == 2
    assert session.deleted["AuthUser"] == [{PERSONAL_ID, STEWARD_ID, LEGACY_BOOKER_ID}]
    assert session.deleted["OrgMinistry"] == [{MINISTRY_ID, SEED_MINISTRY_ID}]
    assert any(row["id"] == ARBITRARY_LOCAL_ID for row in session.users)
    assert any(row["id"] == REAL_USER_ID for row in session.users)


def test_legacy_demo_account_emails_match_known_seed_identities():
    assert LEGACY_DEMO_ACCOUNT_EMAILS == frozenset(
        {
            "seed.booker.1@local.test",
            "seed.booker.2@local.test",
            "seed.booker.3@local.test",
            "seed.booker.4@local.test",
            "seed.booker.5@local.test",
            "seed.ministry.primary@local.test",
            "seed.ministry.secondary@local.test",
            "seed.ministry.secondary2@local.test",
        }
    )
