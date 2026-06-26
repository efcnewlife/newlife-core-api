"""
Church position seed data from docs/position.md.
"""
from typing import Any

from portal.domain.org.constants import PositionOffice, PositionTeam, position_office_can_own_ministry


def _slug(office: PositionOffice, name: str) -> str:
    office_part = office.value.upper()
    name_part = name.upper().replace(" ", "_").replace("-", "_")
    return f"{office_part}_{name_part}"


_POSITION_ROWS: list[tuple[PositionTeam, PositionOffice, str]] = [
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Chairperson"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Worship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Chinese Worship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "English Worship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Vice Chair"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Property"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Treasurer"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Facility"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "General Operation"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Cashier"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Secretary"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Chinese Fellowship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Administration"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Chinese Fellowship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Education"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Children"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Children"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Chinese Education"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "Mission"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.ELDER, "English Fellowship"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "English Mission"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Chinese Mission"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "Chinese Caring"),
    (PositionTeam.ELDER_AND_DEACON, PositionOffice.DEACON, "English Caring"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.PASTOR, "Senior Pastor"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.PASTOR, "Caring Pastor"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.PASTOR, "English Pastor"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.PASTOR, "Chinese Pastor"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.PASTOR, "Part time Caring Pastor"),
    (PositionTeam.PASTORAL_TEAM, PositionOffice.STAFF, "Secretary"),
]

_NAME_ZH_TW = {
    "Chairperson": "主席",
    "Worship": "敬拜",
    "Chinese Worship": "中文敬拜",
    "English Worship": "英文敬拜",
    "Vice Chair": "副主席",
    "Property": "財產",
    "Treasurer": "司庫",
    "Facility": "場地",
    "General Operation": "總務",
    "Cashier": "出纳",
    "Secretary": "書記",
    "Chinese Fellowship": "中文團契",
    "Administration": "行政",
    "Education": "教育",
    "Children": "兒童",
    "Chinese Education": "中文教育",
    "Mission": "宣教",
    "English Fellowship": "英文團契",
    "English Mission": "英文宣教",
    "Chinese Mission": "中文宣教",
    "Chinese Caring": "中文關懷",
    "English Caring": "英文關懷",
    "Senior Pastor": "主任牧師",
    "Caring Pastor": "關懷牧師",
    "English Pastor": "英文牧師",
    "Chinese Pastor": "中文牧師",
    "Part time Caring Pastor": "兼職關懷牧師",
}
_NAME_ZH_CN = {
    "Chairperson": "主席",
    "Worship": "敬拜",
    "Chinese Worship": "中文敬拜",
    "English Worship": "英文敬拜",
    "Vice Chair": "副主席",
    "Property": "财产",
    "Treasurer": "司库",
    "Facility": "场地",
    "General Operation": "总务",
    "Cashier": "出纳",
    "Secretary": "书记",
    "Chinese Fellowship": "中文团契",
    "Administration": "行政",
    "Education": "教育",
    "Children": "儿童",
    "Chinese Education": "中文教育",
    "Mission": "宣教",
    "English Fellowship": "英文团契",
    "English Mission": "英文宣教",
    "Chinese Mission": "中文宣教",
    "Chinese Caring": "中文关怀",
    "English Caring": "英文关怀",
    "Senior Pastor": "主任牧师",
    "Caring Pastor": "关怀牧师",
    "English Pastor": "英文牧师",
    "Chinese Pastor": "中文牧师",
    "Part time Caring Pastor": "兼职关怀牧师",
}


def build_position_seed_rows() -> list[dict[str, Any]]:
    """Build position rows with en/zh-TW/zh-CN name translations."""
    rows: list[dict[str, Any]] = []
    for sequence, (team, office, name) in enumerate(_POSITION_ROWS, start=1):
        rows.append(
            {
                "code": _slug(office, name),
                "team": team.value,
                "office": office.value,
                "can_own_ministry": position_office_can_own_ministry(office),
                "is_active": True,
                "sequence": float(sequence),
                "translations": {
                    "en": {"name": name},
                    "zh-TW": {"name": _NAME_ZH_TW.get(name, name)},
                    "zh-CN": {"name": _NAME_ZH_CN.get(name, name)},
                },
            }
        )
    return rows


position_seed_rows = build_position_seed_rows()
