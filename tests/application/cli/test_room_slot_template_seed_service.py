"""
Tests for the default Room Slot Template seed (gap-fill only, idempotent).
"""

from datetime import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import False_, True_

from portal.application.cli.room_slot_template_seed_service import RoomSlotTemplateSeedService
from portal.cli.datas.room_slot_template_seed_data import default_room_slot_template_seed_rows

MONDAY_TO_SATURDAY_MASK = 0b0111111
SUNDAY_MASK = 0b1000000


def _where_value(cond):
    left = getattr(cond, "left", None)
    key = getattr(left, "key", None) if left is not None else None
    right = getattr(cond, "right", None)
    if isinstance(right, (True_, False_)):
        return key, isinstance(right, True_)
    try:
        value = right.value if right is not None else None
    except AttributeError:
        value = None
    return key, value


class FakeSession:
    """Minimal fake for the room and slot-template reads/inserts this seed performs."""

    def __init__(self, *, rooms: dict[str, UUID], templates: list[dict] | None = None, deleted_room_codes: set[str] | None = None):
        self._rooms = [{"id": room_id, "code": code, "is_deleted": code in (deleted_room_codes or set())} for code, room_id in rooms.items()]
        self.templates: list[dict] = [dict(row) for row in templates or []]
        self.commits = 0
        self._pending_model = None
        self._pending_wheres: dict[str, object] = {}
        self._pending_insert_model = None
        self._pending_values: dict | None = None

    def select(self, *cols):
        self._pending_model = cols[0].class_.__name__
        self._pending_wheres = {}
        return self

    def where(self, cond):
        key, value = _where_value(cond)
        if key is not None:
            self._pending_wheres[key] = value
        return self

    def distinct(self, *args):
        return self

    async def fetch(self, as_model=None):
        assert self._pending_model == "FacilityRoom"
        codes = self._pending_wheres.get("code")
        return [{"id": room["id"], "code": room["code"]} for room in self._rooms if not room["is_deleted"] and (codes is None or room["code"] in codes)]

    async def fetchvals(self):
        assert self._pending_model == "FacilityRoomSlotTemplate"
        rows = self.templates
        if "is_deleted" in self._pending_wheres:
            rows = [row for row in rows if row.get("is_deleted", False) == self._pending_wheres["is_deleted"]]
        return [row["facility_id"] for row in rows]

    def insert(self, model):
        self._pending_insert_model = model.__name__
        return self

    def values(self, **values):
        self._pending_values = values
        return self

    async def execute(self):
        assert self._pending_insert_model == "FacilityRoomSlotTemplate"
        self.templates.append({"is_deleted": False, **self._pending_values})

    async def commit(self):
        self.commits += 1


def _templates_for(session: FakeSession, room_id: UUID) -> list[dict]:
    return [row for row in session.templates if row["facility_id"] == room_id]


def _windows(rows: list[dict]) -> set[tuple[int, time, time, int, bool]]:
    return {(row["days_of_week_mask"], row["start_time"], row["end_time"], row["slot_duration_minutes"], row["is_active"]) for row in rows}


DEFAULT_WINDOWS = {(MONDAY_TO_SATURDAY_MASK, time(8, 0), time(22, 0), 60, True), (SUNDAY_MASK, time(14, 0), time(22, 0), 60, True)}


async def _run(session: FakeSession, room_codes: list[str]) -> int:
    return await RoomSlotTemplateSeedService(session).run(room_codes=room_codes, template_rows=default_room_slot_template_seed_rows)


@pytest.mark.asyncio
async def test_rooms_without_templates_get_default_opening_hours():
    rooms = {"gym": uuid4(), "lounge": uuid4()}
    session = FakeSession(rooms=rooms)

    inserted = await _run(session, ["gym", "lounge"])

    assert inserted == 4
    for room_id in rooms.values():
        rows = _templates_for(session, room_id)
        assert _windows(rows) == DEFAULT_WINDOWS
        assert all(row["effective_from"] is None and row["effective_to"] is None for row in rows)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_room_with_any_existing_template_keeps_exactly_its_templates():
    rooms = {"gym": uuid4(), "lounge": uuid4(), "kitchen": uuid4()}
    admin_active = {"id": uuid4(), "facility_id": rooms["gym"], "days_of_week_mask": 1, "start_time": time(9), "end_time": time(12), "is_active": True}
    admin_inactive = {"id": uuid4(), "facility_id": rooms["lounge"], "days_of_week_mask": 1, "start_time": time(9), "end_time": time(12), "is_active": False}
    session = FakeSession(rooms=rooms, templates=[admin_active, admin_inactive])

    inserted = await _run(session, ["gym", "lounge", "kitchen"])

    assert inserted == 2
    assert _templates_for(session, rooms["gym"]) == [admin_active]
    assert _templates_for(session, rooms["lounge"]) == [admin_inactive]
    assert _windows(_templates_for(session, rooms["kitchen"])) == DEFAULT_WINDOWS


@pytest.mark.asyncio
async def test_room_with_only_soft_deleted_templates_gets_defaults():
    rooms = {"gym": uuid4()}
    deleted = {
        "id": uuid4(),
        "facility_id": rooms["gym"],
        "days_of_week_mask": 1,
        "start_time": time(9),
        "end_time": time(12),
        "is_active": True,
        "is_deleted": True,
    }
    session = FakeSession(rooms=rooms, templates=[deleted])

    inserted = await _run(session, ["gym"])

    assert inserted == 2
    live = [row for row in _templates_for(session, rooms["gym"]) if not row["is_deleted"]]
    assert _windows(live) == DEFAULT_WINDOWS


@pytest.mark.asyncio
async def test_re_running_creates_no_duplicates():
    rooms = {"gym": uuid4(), "lounge": uuid4()}
    session = FakeSession(rooms=rooms)

    await _run(session, ["gym", "lounge"])
    second = await _run(session, ["gym", "lounge"])

    assert second == 0
    assert len(session.templates) == 4


@pytest.mark.asyncio
async def test_only_seeded_rooms_that_exist_and_are_not_deleted_are_filled():
    rooms = {"gym": uuid4(), "admin-created": uuid4(), "retired": uuid4()}
    session = FakeSession(rooms=rooms, deleted_room_codes={"retired"})

    inserted = await _run(session, ["gym", "retired", "missing-room"])

    assert inserted == 2
    assert _templates_for(session, rooms["admin-created"]) == []
    assert _templates_for(session, rooms["retired"]) == []
