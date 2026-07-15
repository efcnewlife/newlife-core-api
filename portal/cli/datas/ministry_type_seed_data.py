"""
Ministry type seed data.
"""
from typing import Any

from portal.domain.org.catalog_codes import (
    MINISTRY_TYPE_INTERNAL,
    MINISTRY_TYPE_OUTREACH,
    MINISTRY_TYPE_WORSHIP,
)

ministry_type_seed_rows: list[dict[str, Any]] = [
    {
        "code": MINISTRY_TYPE_OUTREACH,
        "sequence": 10,
        "translations": {
            "en": {"name": "Outreach"},
            "zh-TW": {"name": "對外事工"},
            "zh-CN": {"name": "对外事工"},
        },
    },
    {
        "code": MINISTRY_TYPE_INTERNAL,
        "sequence": 20,
        "translations": {
            "en": {"name": "Internal"},
            "zh-TW": {"name": "內部事工"},
            "zh-CN": {"name": "内部事工"},
        },
    },
    {
        "code": MINISTRY_TYPE_WORSHIP,
        "sequence": 30,
        "translations": {
            "en": {"name": "Worship"},
            "zh-TW": {"name": "敬拜"},
            "zh-CN": {"name": "敬拜"},
        },
    },
]
