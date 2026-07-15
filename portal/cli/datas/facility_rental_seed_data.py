"""
Facility room, rate, and rental catalog seed data from New Life Gospel Church Rental Policy.
Facility Rate effective 2021; policy rules from April/11/2022 usage policy.
"""
from decimal import Decimal
from typing import Any, Optional

from portal.domain.facility.constants import (
    BookingType,
    RentalDiscountCode,
    RentalPolicySettingKey,
    RentalSurchargeChargeType,
    RentalSurchargeCode,
)


def _translations(en_name: str, zh_name: str) -> dict[str, dict[str, str]]:
    return {
        "en": {"name": en_name},
        "zh-TW": {"name": zh_name},
        "zh-CN": {"name": zh_name},
    }


def _room(
    *,
    code: str,
    en_name: str,
    zh_name: str,
    sequence: int,
    hourly: int,
    daily_flat: int,
    room_number: Optional[str] = None,
    capacity: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "room_number": room_number,
        "capacity": capacity,
        "sequence": sequence,
        "is_active": True,
        "hourly": Decimal(str(hourly)),
        "daily_flat": Decimal(str(daily_flat)),
        "translations": _translations(en_name, zh_name),
    }


# Room codes and rates from Facility Rate table (pages 3-4).
facility_room_seed_rows: list[dict[str, Any]] = [
    _room(
        code="sanctuary-hall",
        room_number="124",
        capacity=390,
        sequence=10,
        hourly=80,
        daily_flat=400,
        en_name="Sanctuary Hall",
        zh_name="禮拜堂",
    ),
    _room(
        code="gym",
        room_number="G19",
        capacity=390,
        sequence=20,
        hourly=50,
        daily_flat=250,
        en_name="Gym",
        zh_name="體育館",
    ),
    _room(
        code="lobby",
        room_number="102",
        capacity=None,
        sequence=30,
        hourly=20,
        daily_flat=100,
        en_name="Lobby",
        zh_name="外廳",
    ),
    _room(
        code="gym-lobby",
        room_number=None,
        capacity=None,
        sequence=40,
        hourly=40,
        daily_flat=200,
        en_name="Gym Lobby",
        zh_name="體育館外廳",
    ),
    _room(
        code="half-gym-lobby",
        room_number=None,
        capacity=None,
        sequence=50,
        hourly=20,
        daily_flat=100,
        en_name="Half Gym Lobby",
        zh_name="半體育館外廳",
    ),
    _room(
        code="nursery-cribs",
        room_number="111",
        capacity=20,
        sequence=60,
        hourly=25,
        daily_flat=125,
        en_name="Nursery/cribs",
        zh_name="嬰兒室",
    ),
    _room(
        code="nursery",
        room_number="116",
        capacity=20,
        sequence=70,
        hourly=25,
        daily_flat=125,
        en_name="Nursery",
        zh_name="幼兒室",
    ),
    _room(
        code="kitchen",
        room_number="128",
        capacity=None,
        sequence=80,
        hourly=25,
        daily_flat=125,
        en_name="Kitchen",
        zh_name="廚房",
    ),
    _room(
        code="lounge",
        room_number="123",
        capacity=30,
        sequence=90,
        hourly=30,
        daily_flat=150,
        en_name="Lounge",
        zh_name="交誼廳",
    ),
    _room(
        code="meeting-room",
        room_number="124",
        capacity=10,
        sequence=100,
        hourly=20,
        daily_flat=100,
        en_name="Meeting Room",
        zh_name="會議室",
    ),
    _room(
        code="classroom-103-104",
        room_number="103/104",
        capacity=30,
        sequence=110,
        hourly=30,
        daily_flat=150,
        en_name="Classroom 103/104",
        zh_name="教室 103/104",
    ),
    _room(
        code="classroom-105",
        room_number="105",
        capacity=10,
        sequence=120,
        hourly=20,
        daily_flat=100,
        en_name="Classroom 105",
        zh_name="教室 105",
    ),
    _room(
        code="classroom-106",
        room_number="106",
        capacity=15,
        sequence=130,
        hourly=25,
        daily_flat=125,
        en_name="Classroom 106",
        zh_name="教室 106",
    ),
    _room(
        code="classroom-107",
        room_number="107",
        capacity=10,
        sequence=140,
        hourly=20,
        daily_flat=100,
        en_name="Classroom 107",
        zh_name="教室 107",
    ),
    _room(
        code="classroom-112-113",
        room_number="112/113",
        capacity=30,
        sequence=150,
        hourly=30,
        daily_flat=150,
        en_name="Classroom 112/113",
        zh_name="教室 112/113",
    ),
    _room(
        code="classroom-125",
        room_number="125",
        capacity=15,
        sequence=160,
        hourly=25,
        daily_flat=125,
        en_name="Classroom 125",
        zh_name="教室 125",
    ),
    _room(
        code="classroom-126",
        room_number="126",
        capacity=15,
        sequence=170,
        hourly=25,
        daily_flat=125,
        en_name="Classroom 126",
        zh_name="教室 126",
    ),
    _room(
        code="classroom-127",
        room_number="127",
        capacity=30,
        sequence=180,
        hourly=30,
        daily_flat=150,
        en_name="Classroom 127",
        zh_name="教室 127",
    ),
]

facility_discount_seed_rows: list[dict[str, Any]] = [
    {
        "code": RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value,
        "percent_off": Decimal("20.00"),
        "is_active": True,
        "description": "20% discount for activities recurring weekly or monthly (policy 4b)",
    },
    {
        "code": RentalDiscountCode.MISSION_ALIGNED.value,
        "percent_off": Decimal("30.00"),
        "is_active": True,
        "description": "30% discount for activities aligned with church mission and vision (policy 4c)",
    },
]

facility_surcharge_seed_rows: list[dict[str, Any]] = [
    {
        "code": RentalSurchargeCode.DEPOSIT_ONE_TIME.value,
        "charge_type": RentalSurchargeChargeType.FLAT.value,
        "unit_amount": Decimal("20.00"),
        "currency": "CAD",
        "is_active": True,
        "applies_to_booking_type": BookingType.ONE_TIME.value,
        "remark": "Deposit may be required for one-time rentals (policy 8)",
    },
    {
        "code": RentalSurchargeCode.DOOR_AUDIO_OPERATOR.value,
        "charge_type": RentalSurchargeChargeType.PER_HOUR.value,
        "unit_amount": Decimal("30.00"),
        "currency": "CAD",
        "is_active": True,
        "applies_to_booking_type": None,
        "remark": "Open/close door and operate audio system (policy 11)",
    },
]

# facility_code None = global default; "gym" resolves to gym room id at seed time.
facility_policy_seed_rows: list[dict[str, Any]] = [
    {
        "setting_key": RentalPolicySettingKey.MINIMUM_FEE_DEFAULT.value,
        "facility_code": None,
        "amount": Decimal("60.00"),
        "currency": "CAD",
        "is_active": True,
    },
    {
        "setting_key": RentalPolicySettingKey.MINIMUM_FEE_GYM.value,
        "facility_code": "gym",
        "amount": Decimal("35.00"),
        "currency": "CAD",
        "is_active": True,
    },
]

# Hours-only applicability (PDF: daily flat at 5+ hours).
APPLICABILITY_HOURS_LT_5: dict[str, Any] = {"all": [{"op": "hours_lt", "value": 5}]}
APPLICABILITY_HOURS_GTE_5: dict[str, Any] = {"all": [{"op": "hours_gte", "value": 5}]}

rate_applicability_by_billing_unit: dict[str, dict[str, Any]] = {
    "hourly": APPLICABILITY_HOURS_LT_5,
    "daily_flat": APPLICABILITY_HOURS_GTE_5,
}

rate_name_translations: dict[str, dict[str, dict[str, str]]] = {
    "hourly": _translations("Hourly", "每小時"),
    "daily_flat": _translations("Daily flat (5+ hours)", "全日定價（5小時以上）"),
}
