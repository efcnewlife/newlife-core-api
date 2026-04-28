"""
Seed data for Locale CLI: supported locales and their translations.
"""
from uuid import UUID

ENGLISH = {
    "id": UUID("019dd0c8-69fa-7657-87bb-3b7255f5c5ae"),
    "language_code": "en",
    "script_code": None,
    "region_code": None,
    "name": "English",
    "native_name": "English",
    "is_active": True,
    "is_default": True,
}

CHINESE_TRADITIONAL = {
    "id": UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a"),
    "language_code": "zh",
    "script_code": "Hant",
    "region_code": "TW",
    "name": "Traditional Chinese",
    "native_name": "繁體中文",
    "is_active": True,
    "is_default": False,
}

CHINESE_SIMPLIFIED = {
    "id": UUID("019dd0c8-7c12-727f-878f-16807adf39e8"),
    "language_code": "zh",
    "script_code": "Hans",
    "region_code": "CN",
    "name": "Simplified Chinese",
    "native_name": "简体中文",
    "is_active": True,
    "is_default": False,
}

seed_locales = [
    ENGLISH,
    CHINESE_TRADITIONAL,
    CHINESE_SIMPLIFIED,
]