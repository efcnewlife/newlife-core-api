"""
Tests for the remove-mock-data orchestration service (fake session seam).
"""

from collections import defaultdict
from uuid import UUID, uuid4

import pytest

from portal.application.cli.remove_mock_data_service import MockDataDependencyError, RemoveMockDataService

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
    ):
        self.users = list(users or [])
        self.ministry_members = list(ministry_members or [])
        self.bookings = list(bookings or [])
        self.series = list(series or [])
        self.drafts = list(drafts or [])
        self.ministries = list(ministries or [])
        self.translations = list(translations or [])
        self.approvals = list(approvals or [])

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
        return [{k: row[k] for k in keys} for row in self._filtered()]

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

    assert set(session.deleted.keys()) <= {"FacilityBooking", "FacilityBookingSeries", "FacilityBookingDraft", "OrgMinistry", "AuthUser"}


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
