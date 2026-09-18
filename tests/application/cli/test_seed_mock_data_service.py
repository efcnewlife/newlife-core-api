"""
Tests for the seed-mock-data orchestration service (fake session seam).
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import ACCOUNT_CSV_COLUMNS, MINISTRY_CSV_COLUMNS, write_csv
from portal.application.cli.mock_fixture_plans import BOOKING_PLACEMENT_WINDOW_DAYS, local_range_to_utc
from portal.application.cli.mock_ministry_inventory import build_mock_ministry_plans, ministry_display_name
from portal.application.cli.seed_mock_data_service import MockDataPrerequisiteError, MockFixturePlacementError, SeedMockDataService
from portal.cli.datas.facility_rental_seed_data import facility_room_seed_rows
from portal.domain.facility.constants import BookingStatus, BookingType, RoomBlackoutKind
from portal.domain.org.constants import MinistryApprovalStatus, MinistryStatus

RUN_IDENTITY = "dev-2026-09-17_1405"
MINISTRY_TZ = ZoneInfo("America/Toronto")
CLOCK = datetime(2026, 9, 17, 14, 5, tzinfo=timezone.utc)

PERSONAL_IDS = [uuid4() for _ in range(5)]
STEWARD_IDS = [uuid4() for _ in range(3)]
OWNER_ID = uuid4()
POSITION_ID = uuid4()
MINISTRY_LABELS = [plan.label for plan in build_mock_ministry_plans(year=2026)]
MINISTRY_NAMES = {label: ministry_display_name(label=label, run_identity=RUN_IDENTITY) for label in MINISTRY_LABELS}
MINISTRY_IDS = {label: uuid4() for label in MINISTRY_LABELS}
MINISTRY_IDS_BY_NAME = {MINISTRY_NAMES[label]: MINISTRY_IDS[label] for label in MINISTRY_LABELS}
ROOM_IDS = {row["code"]: uuid4() for row in facility_room_seed_rows}

PERSONAL_EMAILS = [f"personal.{index:04x}@test.local" for index in range(5)]
STEWARD_EMAILS = [f"steward.{index:04x}@test.local" for index in range(3)]
OWNER_EMAIL = "owner.0009@test.local"
INACTIVE_EMAIL = "inactive.000a@test.local"


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
        ministry_ids: dict[str, UUID] | None = None,
        rooms: dict[str, UUID] | None = None,
        position: tuple[UUID, str] | None = (POSITION_ID, "DEACON_FACILITY"),
        locale_rows: list[dict] | None = None,
        occupying_slots: list[dict] | None = None,
        existing_blackouts: list[dict] | None = None,
        raise_on_insert: dict[str, Exception] | None = None,
    ):
        self._users = users if users is not None else _default_users()
        self._ministry_ids = ministry_ids if ministry_ids is not None else dict(MINISTRY_IDS_BY_NAME)
        self._rooms = rooms if rooms is not None else dict(ROOM_IDS)
        self._position = position
        self._locale_rows = [{"id": uuid4(), "language_code": "en"}] if locale_rows is None else locale_rows
        self._occupying_slots = occupying_slots or []
        self._existing_blackouts = existing_blackouts or []
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
        model_name, keys = self._select_key()
        if model_name == "SystemLocale":
            return self._locale_rows
        if model_name == "FacilityRoom" and keys == ("id", "code"):
            return [{"id": room_id, "code": code} for code, room_id in self._rooms.items()]
        if model_name == "FacilityBookingSlot":
            return list(self._occupying_slots)
        if model_name == "FacilityRoomBlackout":
            return list(self._existing_blackouts)
        return []

    async def fetchval(self):
        model_name, keys = self._select_key()
        wheres = self._where_map()
        if model_name == "AuthUser" and keys == ("id",):
            return self._users.get(wheres.get("email"))
        if model_name == "OrgMinistryTranslation" and keys == ("ministry_id",):
            return self._ministry_ids.get(wheres.get("name"))
        return None

    async def fetchrow(self):
        model_name, keys = self._select_key()
        if model_name == "OrgPosition" and keys == ("id", "code"):
            if not self._position:
                return None
            return {"id": self._position[0], "code": self._position[1]}
        return None

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


def _default_users() -> dict[str, UUID]:
    users = {email: user_id for email, user_id in zip(PERSONAL_EMAILS, PERSONAL_IDS, strict=True)}
    users.update({email: user_id for email, user_id in zip(STEWARD_EMAILS, STEWARD_IDS, strict=True)})
    users[OWNER_EMAIL] = OWNER_ID
    users[INACTIVE_EMAIL] = uuid4()
    return users


def _write_inventory(tmp_path: Path, *, ministry_count: int | None = None) -> None:
    account_path = tmp_path / "2026-09-17_1405_dev_test_account.csv"
    ministry_path = tmp_path / "2026-09-17_1405_dev_ministry.csv"
    write_csv(
        account_path,
        ACCOUNT_CSV_COLUMNS,
        [
            *[
                {
                    "email": email,
                    "first_name": "Personal",
                    "last_name": "Mock",
                    "persona": "personal",
                    "purpose": f"personal-{index}",
                    "is_active": True,
                    "created_in_run": True,
                }
                for index, email in enumerate(PERSONAL_EMAILS, start=1)
            ],
            *[
                {
                    "email": email,
                    "first_name": "Steward",
                    "last_name": "Mock",
                    "persona": "steward",
                    "purpose": f"steward-{index}",
                    "is_active": True,
                    "created_in_run": True,
                }
                for index, email in enumerate(STEWARD_EMAILS, start=1)
            ],
            {
                "email": OWNER_EMAIL,
                "first_name": "Owner",
                "last_name": "Mock",
                "persona": "owner",
                "purpose": "owner",
                "is_active": True,
                "created_in_run": True,
            },
            {
                "email": INACTIVE_EMAIL,
                "first_name": "Inactive",
                "last_name": "Mock",
                "persona": "inactive",
                "purpose": "inactive",
                "is_active": False,
                "created_in_run": True,
            },
        ],
    )
    labels = MINISTRY_LABELS if ministry_count is None else MINISTRY_LABELS[:ministry_count]
    write_csv(
        ministry_path,
        MINISTRY_CSV_COLUMNS,
        [
            {
                "ministry_code": f"MOCK-{index:04X}",
                "ministry_name": MINISTRY_NAMES[label],
                "status": "active",
                "primary_steward_email": STEWARD_EMAILS[0],
                "secondary_steward_emails": ",".join(STEWARD_EMAILS[1:]),
                "purpose": f"Ministry list display: {label}",
                "created_in_run": True,
            }
            for index, label in enumerate(labels, start=1)
        ],
    )


def _service(tmp_path: Path, *, session: FakeSession | None = None) -> tuple[SeedMockDataService, FakeSession]:
    fake = session or FakeSession()
    service = SeedMockDataService(fake, env="dev", default_locale_code="en", output_dir=tmp_path, clock=lambda: CLOCK)
    return service, fake


def _local_day(value: datetime) -> object:
    return value.astimezone(MINISTRY_TZ).date()


@pytest.mark.asyncio
async def test_seed_mock_data_creates_complete_near_term_fixture_suite(tmp_path: Path):
    _write_inventory(tmp_path)
    service, session = _service(tmp_path)

    result = await service.run()

    assert result.run_identity == RUN_IDENTITY
    assert "AuthUser" not in session.inserted
    assert len(session.inserted["OrgMinistry"]) == 1
    assert session.updated.get("OrgMinistry", []) == []

    slots = session.inserted["FacilityRoomSlotTemplate"]
    assert len(slots) == len(ROOM_IDS)
    assert {row["facility_id"] for row in slots} == set(ROOM_IDS.values())
    for row in slots:
        assert row["name"].startswith("Mock ")
        assert f"mock:{RUN_IDENTITY}" in row["name"]
        assert row["start_time"] == time(8, 0)
        assert row["end_time"] == time(22, 0)

    blackouts = session.inserted["FacilityRoomBlackout"]
    assert len(blackouts) == 2
    campus = next(row for row in blackouts if row["facility_id"] is None)
    room_specific = next(row for row in blackouts if row["facility_id"] == ROOM_IDS["sanctuary-hall"])
    assert campus["kind"] == RoomBlackoutKind.ONE_OFF.value
    assert campus["blackout_date"] == datetime(2026, 9, 18).date()
    assert f"mock:{RUN_IDENTITY}" in campus["name"]
    assert campus["name"].startswith("Mock ")
    assert room_specific["kind"] == RoomBlackoutKind.ONE_OFF.value
    assert room_specific["blackout_date"] == datetime(2026, 9, 19).date()
    assert f"mock:{RUN_IDENTITY}" in room_specific["name"]

    bookings = session.inserted["FacilityBooking"]
    assert len(bookings) == 10
    assert all(row["status"] == BookingStatus.CONFIRMED.value for row in bookings)
    assert all(row["booking_type"] == BookingType.ONE_TIME.value for row in bookings)
    personal_bookings = [row for row in bookings if row["ministry_id"] is None]
    ministry_bookings = [row for row in bookings if row["ministry_id"] is not None]
    assert len(personal_bookings) == 6
    assert len(ministry_bookings) == 4
    assert {row["user_id"] for row in personal_bookings} == set(PERSONAL_IDS)
    assert {row["user_id"] for row in ministry_bookings} == set(STEWARD_IDS)
    assert {row["ministry_id"] for row in ministry_bookings} == {
        MINISTRY_IDS["Alpha"],
        MINISTRY_IDS["Badminton"],
        MINISTRY_IDS["Basketball"],
        MINISTRY_IDS["Pickleball"],
    }
    assert all(_local_day(row["start_at"]) == datetime(2026, 9, 19).date() for row in bookings)

    rooms_by_booking = defaultdict(list)
    for line in session.inserted["FacilityBookingRoom"]:
        rooms_by_booking[line["facility_booking_id"]].append(line["facility_id"])
    multi_room = [booking_id for booking_id, facility_ids in rooms_by_booking.items() if len(facility_ids) >= 2]
    assert len(multi_room) == 1
    assert set(rooms_by_booking[multi_room[0]]) == {ROOM_IDS["gym"], ROOM_IDS["lobby"]}

    assignment = session.inserted["OrgPositionAssignment"][0]
    assert assignment["position_id"] == POSITION_ID
    assert assignment["user_id"] == OWNER_ID
    assert result.owner_position_code == "DEACON_FACILITY"

    application = session.inserted["OrgMinistry"][0]
    assert application["status"] == MinistryStatus.PENDING_APPROVAL.value
    assert application["owner_position_id"] == POSITION_ID
    assert application["ministry_type_id"] is None
    assert application["submitted_by_id"] == STEWARD_IDS[0]
    assert application["id"] == result.ministry_application_id
    application_approval = next(row for row in session.inserted["OrgMinistryApproval"] if row["ministry_id"] == application["id"])
    assert application_approval["status"] == MinistryApprovalStatus.PENDING.value

    assert session.committed is True


def _occupying_slot(room_code: str, local_day: date, start_hour: int, end_hour: int) -> dict:
    start_at, end_at = local_range_to_utc(local_day=local_day, start_hour=start_hour, end_hour=end_hour)
    return {"facility_id": ROOM_IDS[room_code], "start_at": start_at, "end_at": end_at}


@pytest.mark.asyncio
async def test_seed_mock_data_skips_occupied_days_within_the_30_day_window(tmp_path: Path):
    _write_inventory(tmp_path)
    occupied = _occupying_slot("classroom-105", date(2026, 9, 19), 10, 11)
    service, session = _service(tmp_path, session=FakeSession(occupying_slots=[occupied]))

    await service.run()

    personal_105 = next(
        row for row in session.inserted["FacilityBooking"] if row["user_id"] == PERSONAL_IDS[0] and row["facility_id"] == ROOM_IDS["classroom-105"]
    )
    assert _local_day(personal_105["start_at"]) == date(2026, 9, 20)


@pytest.mark.asyncio
async def test_seed_mock_data_skips_existing_blackouts_within_the_30_day_window(tmp_path: Path):
    _write_inventory(tmp_path)
    existing = {
        "facility_id": None,
        "kind": RoomBlackoutKind.ONE_OFF.value,
        "blackout_date": date(2026, 9, 19),
        "days_of_week_mask": None,
        "start_time": time(0, 0),
        "end_time": time(23, 59),
        "effective_from": None,
        "effective_to": None,
    }
    service, session = _service(tmp_path, session=FakeSession(existing_blackouts=[existing]))

    await service.run()

    campus = next(row for row in session.inserted["FacilityRoomBlackout"] if row["facility_id"] is None)
    assert campus["blackout_date"] == date(2026, 9, 18)
    assert all(_local_day(row["start_at"]) == date(2026, 9, 20) for row in session.inserted["FacilityBooking"])


@pytest.mark.asyncio
async def test_seed_mock_data_fails_atomically_when_no_slot_exists(tmp_path: Path):
    _write_inventory(tmp_path)
    occupying_slots = [
        _occupying_slot("classroom-105", date(2026, 9, 19) + timedelta(days=offset), 10, 11) for offset in range(BOOKING_PLACEMENT_WINDOW_DAYS - 1)
    ]
    service, session = _service(tmp_path, session=FakeSession(occupying_slots=occupying_slots))

    with pytest.raises(MockFixturePlacementError, match="complete fixture suite was not created"):
        await service.run()

    assert session.committed is False
    assert session.inserted == {}


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_local_inventory(tmp_path: Path):
    service, _session = _service(tmp_path)

    with pytest.raises(MockDataPrerequisiteError, match="seed-mock-users"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_persona_missing_from_inventory(tmp_path: Path):
    _write_inventory(tmp_path)
    account_path = tmp_path / "2026-09-17_1405_dev_test_account.csv"
    account_path.unlink()
    write_csv(
        account_path,
        ACCOUNT_CSV_COLUMNS,
        [
            {
                "email": STEWARD_EMAILS[0],
                "first_name": "Steward",
                "last_name": "Mock",
                "persona": "steward",
                "purpose": "x",
                "is_active": True,
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
    users = _default_users()
    del users[PERSONAL_EMAILS[0]]
    service, _ = _service(tmp_path, session=FakeSession(users=users))

    with pytest.raises(MockDataPrerequisiteError, match="Personal\\[0\\] Mock user"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_active_room(tmp_path: Path):
    _write_inventory(tmp_path)
    service, _ = _service(tmp_path, session=FakeSession(rooms={}))

    with pytest.raises(MockDataPrerequisiteError, match="seed-facility-rental"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_no_owning_position(tmp_path: Path):
    _write_inventory(tmp_path)
    service, _ = _service(tmp_path, session=FakeSession(position=None))

    with pytest.raises(MockDataPrerequisiteError, match="seed-positions"):
        await service.run()


@pytest.mark.asyncio
async def test_seed_mock_data_fails_when_default_locale_missing(tmp_path: Path):
    _write_inventory(tmp_path)
    service, _ = _service(tmp_path, session=FakeSession(locale_rows=[]))

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
