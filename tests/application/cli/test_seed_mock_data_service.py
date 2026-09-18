"""
Tests for the seed-mock-data orchestration service (fake session seam).
"""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import ACCOUNT_CSV_COLUMNS, MINISTRY_CSV_COLUMNS, write_csv
from portal.application.cli.seed_mock_data_service import MockDataPrerequisiteError, SeedMockDataService
from portal.domain.org.constants import MinistryApprovalStatus, MinistryStatus
from portal.models import (
    AuthUser,
    FacilityBooking,
    FacilityRoom,
    OrgMinistry,
    OrgMinistryMember,
    OrgMinistryTranslation,
    OrgPosition,
    OrgPositionAssignment,
    SystemLocale,
)

MINISTRY_NAME = "Mock Ministry ABCD"

PERSONAL_ID = uuid4()
STEWARD_ID = uuid4()
OWNER_ID = uuid4()
MINISTRY_ID = uuid4()
ROOM_ID = uuid4()
POSITION_ID = uuid4()


def _where_value(cond):
    left = getattr(cond, "left", None)
    key = getattr(left, "key", None) if left is not None else None
    right = getattr(cond, "right", None)
    try:
        value = right.value if right is not None else None
    except AttributeError:
        value = None
    return key, value


class FakeSession:
    """Minimal fake standing in for portal.libs.database.Session."""

    def __init__(
        self,
        *,
        users: dict[str, UUID] | None = None,
        ministry_id: UUID | None = MINISTRY_ID,
        ministry_status: str = MinistryStatus.DRAFT.value,
        ministry_member_ids: set[UUID] | None = None,
        room_id: UUID | None = ROOM_ID,
        position: tuple[UUID, str] | None = (POSITION_ID, "DEACON_FACILITY"),
        locale_rows: list[dict] | None = None,
        raise_on_insert: dict[str, Exception] | None = None,
    ):
        self._users = users if users is not None else {"personal@test.local": PERSONAL_ID, "steward@test.local": STEWARD_ID, "owner@test.local": OWNER_ID}
        self._ministry_id = ministry_id
        self._ministry_status = ministry_status
        self._ministry_member_ids = ministry_member_ids if ministry_member_ids is not None else {STEWARD_ID}
        self._room_id = room_id
        self._position = position
        self._locale_rows = [{"id": uuid4(), "language_code": "en"}] if locale_rows is None else locale_rows
        self._raise_on_insert = raise_on_insert or {}

        self.inserted: dict[str, list[dict]] = defaultdict(list)
        self.updated: dict[str, list[dict]] = defaultdict(list)
        self.committed = False
        self.rolled_back = False

        self._pending_select = None
        self._pending_wheres: list = []
        self._pending_model = None
        self._pending_mode = None
        self._pending_values = None
        self._pending_exc = None

    # -- select chain --
    def select(self, *cols):
        self._pending_select = cols
        self._pending_wheres = []
        return self

    def where(self, *args, **kwargs):
        if args:
            self._pending_wheres.append(args[0])
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def _select_key(self) -> tuple[str, tuple[str, ...]]:
        first = self._pending_select[0]
        return first.class_.__name__, tuple(col.key for col in self._pending_select)

    def _where_map(self) -> dict[str, object]:
        result = {}
        for cond in self._pending_wheres:
            key, value = _where_value(cond)
            if key is not None:
                result[key] = value
        return result

    async def fetch(self):
        model_name, _keys = self._select_key()
        if model_name == "SystemLocale":
            return self._locale_rows
        return []

    async def fetchval(self):
        model_name, keys = self._select_key()
        wheres = self._where_map()
        if model_name == "AuthUser" and keys == ("id",):
            return self._users.get(wheres.get("email"))
        if model_name == "OrgMinistryTranslation" and keys == ("ministry_id",):
            return self._ministry_id if wheres.get("name") == MINISTRY_NAME else None
        if model_name == "OrgMinistry" and keys == ("status",):
            return self._ministry_status
        if model_name == "OrgMinistryMember" and keys == ("user_id",):
            return wheres.get("user_id") if wheres.get("user_id") in self._ministry_member_ids else None
        if model_name == "FacilityRoom" and keys == ("id",):
            return self._room_id
        return None

    async def fetchrow(self):
        model_name, keys = self._select_key()
        if model_name == "OrgPosition" and keys == ("id", "code"):
            if not self._position:
                return None
            return {"id": self._position[0], "code": self._position[1]}
        return None

    # -- write chain --
    def insert(self, model):
        self._pending_model = model
        self._pending_mode = "insert"
        return self

    def update(self, model):
        self._pending_model = model
        self._pending_mode = "update"
        self._pending_wheres = []
        return self

    def values(self, **kwargs):
        name = self._pending_model.__name__
        if self._pending_mode == "insert":
            self._pending_exc = self._raise_on_insert.get(name)
            self._pending_values = ("insert", name, kwargs)
        else:
            self._pending_values = ("update", name, kwargs)
        return self

    async def execute(self):
        mode, name, kwargs = self._pending_values
        if mode == "insert":
            if self._pending_exc is not None:
                exc = self._pending_exc
                self._pending_exc = None
                raise exc
            self.inserted[name].append(kwargs)
        else:
            self.updated[name].append(kwargs)
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _write_inventory(tmp_path: Path) -> Path:
    account_path = tmp_path / "2026-09-17_1405_dev_test_account.csv"
    ministry_path = tmp_path / "2026-09-17_1405_dev_ministry.csv"
    write_csv(
        account_path,
        ACCOUNT_CSV_COLUMNS,
        [
            {
                "email": "personal@test.local",
                "first_name": "Personal",
                "last_name": "Mock",
                "persona": "personal",
                "purpose": "x",
                "is_active": True,
                "created_in_run": True,
            },
            {
                "email": "steward@test.local",
                "first_name": "Steward",
                "last_name": "Mock",
                "persona": "steward",
                "purpose": "x",
                "is_active": True,
                "created_in_run": True,
            },
            {
                "email": "owner@test.local",
                "first_name": "Owner",
                "last_name": "Mock",
                "persona": "owner",
                "purpose": "x",
                "is_active": True,
                "created_in_run": True,
            },
            {
                "email": "inactive@test.local",
                "first_name": "Inactive",
                "last_name": "Mock",
                "persona": "inactive",
                "purpose": "x",
                "is_active": False,
                "created_in_run": True,
            },
        ],
    )
    write_csv(
        ministry_path,
        MINISTRY_CSV_COLUMNS,
        [
            {
                "ministry_code": "ABCD",
                "ministry_name": MINISTRY_NAME,
                "status": "draft",
                "primary_steward_email": "steward@test.local",
                "secondary_steward_emails": "",
                "purpose": "x",
                "created_in_run": True,
            }
        ],
    )
    return account_path


def _service(tmp_path: Path, *, session: FakeSession | None = None) -> tuple[SeedMockDataService, FakeSession]:
    fake = session or FakeSession()
    service = SeedMockDataService(
        fake, env="dev", default_locale_code="en", output_dir=tmp_path, clock=lambda: datetime(2026, 9, 17, 14, 5, tzinfo=timezone.utc)
    )
    return service, fake


@pytest.mark.asyncio
async def test_seed_mock_data_completes_all_four_scenarios(tmp_path: Path):
    _write_inventory(tmp_path)
    service, session = _service(tmp_path)

    result = await service.run()

    # Personal Rental Booking: owned by the personal Mock user, no ministry.
    bookings = session.inserted["FacilityBooking"]
    assert len(bookings) == 2
    personal_booking = next(b for b in bookings if b["user_id"] == PERSONAL_ID)
    assert personal_booking["ministry_id"] is None
    assert personal_booking["id"] == result.personal_rental_booking_id

    # Steward Church Activity Booking: owned by the steward, linked to the Ministry.
    church_booking = next(b for b in bookings if b["user_id"] == STEWARD_ID)
    assert church_booking["ministry_id"] == MINISTRY_ID
    assert church_booking["id"] == result.church_activity_booking_id

    # The steward's Ministry is activated in place (same id, not a new row). No incumbent exists
    # for this Ministry (owner_position_id stays unset), so approved_by_id stays unset too rather
    # than recording the submitting steward as their own approver.
    assert len(session.updated["OrgMinistry"]) == 1
    activation = session.updated["OrgMinistry"][0]
    assert activation["status"] == MinistryStatus.ACTIVE.value
    assert activation["is_active"] is True
    assert activation["submitted_by_id"] == STEWARD_ID
    assert activation["approved_by_id"] is None
    assert result.ministry_id == MINISTRY_ID

    # Owner assigned as the Owner-position incumbent: closes any prior open assignment, then inserts the new one.
    assert len(session.updated["OrgPositionAssignment"]) == 1
    assert len(session.inserted["OrgPositionAssignment"]) == 1
    assignment = session.inserted["OrgPositionAssignment"][0]
    assert assignment["position_id"] == POSITION_ID
    assert assignment["user_id"] == OWNER_ID
    assert result.owner_position_id == POSITION_ID
    assert result.owner_position_code == "DEACON_FACILITY"

    # Pending Ministry Application: a new Ministry, PENDING_APPROVAL, owned by that position.
    applications = session.inserted["OrgMinistry"]
    assert len(applications) == 1
    application = applications[0]
    assert application["status"] == MinistryStatus.PENDING_APPROVAL.value
    assert application["owner_position_id"] == POSITION_ID
    assert application["ministry_type_id"] is None
    assert application["submitted_by_id"] == STEWARD_ID
    assert application["id"] == result.ministry_application_id

    approvals = session.inserted["OrgMinistryApproval"]
    assert len(approvals) == 2
    activation_approval = next(a for a in approvals if a["ministry_id"] == MINISTRY_ID)
    assert activation_approval["status"] == MinistryApprovalStatus.APPROVED.value
    assert activation_approval["owner_position_id"] is None

    application_approval = next(a for a in approvals if a["ministry_id"] == application["id"])
    assert application_approval["status"] == MinistryApprovalStatus.PENDING.value
    assert application_approval["owner_position_id"] == POSITION_ID
    assert application_approval["requested_by_id"] == STEWARD_ID

    members = session.inserted["OrgMinistryMember"]
    assert any(m["ministry_id"] == application["id"] and m["user_id"] == STEWARD_ID for m in members)

    assert session.committed is True


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_local_inventory(tmp_path: Path):
    service, _session = _service(tmp_path)

    with pytest.raises(MockDataPrerequisiteError, match="seed-mock-users"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_persona_missing_from_inventory(tmp_path: Path):
    account_path = tmp_path / "2026-09-17_1405_dev_test_account.csv"
    ministry_path = tmp_path / "2026-09-17_1405_dev_ministry.csv"
    write_csv(
        account_path,
        ACCOUNT_CSV_COLUMNS,
        [
            {
                "email": "steward@test.local",
                "first_name": "Steward",
                "last_name": "Mock",
                "persona": "steward",
                "purpose": "x",
                "is_active": True,
                "created_in_run": True,
            }
        ],
    )
    write_csv(
        ministry_path,
        MINISTRY_CSV_COLUMNS,
        [
            {
                "ministry_code": "ABCD",
                "ministry_name": MINISTRY_NAME,
                "status": "draft",
                "primary_steward_email": "steward@test.local",
                "secondary_steward_emails": "",
                "purpose": "x",
                "created_in_run": True,
            }
        ],
    )
    service, _session = _service(tmp_path)

    with pytest.raises(MockDataPrerequisiteError, match="personal, owner"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_a_mock_user_is_not_in_the_database(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(users={"steward@test.local": STEWARD_ID, "owner@test.local": OWNER_ID})
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(MockDataPrerequisiteError, match="Personal Mock user"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_steward_ministry_already_active(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(ministry_status=MinistryStatus.ACTIVE.value)
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(MockDataPrerequisiteError, match="already run"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_active_room(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(room_id=None)
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(MockDataPrerequisiteError, match="seed-facility-rental"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_owning_position(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(position=None)
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(MockDataPrerequisiteError, match="seed-positions"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_default_locale_missing(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(locale_rows=[])
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(MockDataPrerequisiteError, match="init-all"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_reports_clear_error_when_ministry_type_is_not_nullable(tmp_path: Path):
    _write_inventory(tmp_path)
    session = FakeSession(raise_on_insert={"OrgMinistry": NotNullViolationError("ministry_type_id")})
    service, _ = _service(tmp_path, session=session)

    with pytest.raises(RuntimeError, match="66fd53b703c7"):
        await service.run()

    assert session.committed is False
