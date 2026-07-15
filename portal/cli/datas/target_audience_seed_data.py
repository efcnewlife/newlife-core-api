"""
Target audience seed data.
"""
from typing import Any

from portal.domain.org.catalog_codes import (
    TARGET_AUDIENCE_ADULTS,
    TARGET_AUDIENCE_ALL_AGES,
    TARGET_AUDIENCE_CHILDREN,
    TARGET_AUDIENCE_FAMILY,
    TARGET_AUDIENCE_YOUTHS,
)

target_audience_seed_rows: list[dict[str, Any]] = [
    {
        "code": TARGET_AUDIENCE_CHILDREN,
        "sequence": 10,
        "translations": {
            "en": {"name": "Children"},
            "zh-TW": {"name": "兒童"},
            "zh-CN": {"name": "儿童"},
        },
    },
    {
        "code": TARGET_AUDIENCE_YOUTHS,
        "sequence": 20,
        "translations": {
            "en": {"name": "Youths"},
            "zh-TW": {"name": "青少年"},
            "zh-CN": {"name": "青少年"},
        },
    },
    {
        "code": TARGET_AUDIENCE_ADULTS,
        "sequence": 30,
        "translations": {
            "en": {"name": "Adults"},
            "zh-TW": {"name": "成人"},
            "zh-CN": {"name": "成人"},
        },
    },
    {
        "code": TARGET_AUDIENCE_FAMILY,
        "sequence": 40,
        "translations": {
            "en": {"name": "Family"},
            "zh-TW": {"name": "家庭"},
            "zh-CN": {"name": "家庭"},
        },
    },
    {
        "code": TARGET_AUDIENCE_ALL_AGES,
        "sequence": 50,
        "translations": {
            "en": {"name": "All Ages"},
            "zh-TW": {"name": "全年齡"},
            "zh-CN": {"name": "全年龄"},
        },
    },
]
