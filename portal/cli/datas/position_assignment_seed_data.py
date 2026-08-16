"""
One-time position incumbent seed data from Elder / Deacon / Pastor roster.

Maps user email -> position codes (from position_seed_data / docs/position.md).
Slash-separated responsibilities are split into multiple position codes.
"""

from typing import Any

# (email, list of OrgPosition.code)
_ASSIGNMENT_ROWS: list[tuple[str, list[str]]] = [
    # Elder (multi-position when responsibilities were slash-separated)
    ("johnson.chang@efcnewlife.org", ["ELDER_CHAIRPERSON", "ELDER_WORSHIP"]),
    ("eugene.chen@efcnewlife.org", ["ELDER_VICE_CHAIR", "ELDER_PROPERTY", "ELDER_TREASURER"]),
    ("peter.hou@efcnewlife.org", ["ELDER_SECRETARY", "ELDER_CHINESE_FELLOWSHIP"]),
    ("pofong.yang@efcnewlife.org", ["ELDER_EDUCATION", "ELDER_CHILDREN"]),
    ("ken.tung@efcnewlife.org", ["ELDER_MISSION", "ELDER_ENGLISH_FELLOWSHIP"]),
    # Deacon
    ("john.cheng@efcnewlife.org", ["DEACON_CHINESE_WORSHIP"]),
    ("synge.chen@efcnewlife.org", ["DEACON_ENGLISH_WORSHIP"]),
    ("jacky.chang@efcnewlife.org", ["DEACON_FACILITY"]),
    ("felix.lam@efcnewlife.org", ["DEACON_GENERAL_OPERATION"]),
    ("annie.wang@efcnewlife.org", ["DEACON_CASHIER"]),
    ("louis.huang@efcnewlife.org", ["DEACON_ADMINISTRATION"]),
    ("helen.li@efcnewlife.org", ["DEACON_CHINESE_FELLOWSHIP"]),
    ("virgilia.chen@efcnewlife.org", ["DEACON_CHILDREN"]),
    ("lei.yang@efcnewlife.org", ["DEACON_CHINESE_EDUCATION"]),
    ("danny.yang@efcnewlife.org", ["DEACON_ENGLISH_MISSION"]),
    ("mary.tan@efcnewlife.org", ["DEACON_CHINESE_MISSION"]),
    ("hong.wu@efcnewlife.org", ["DEACON_CHINESE_CARING"]),
    ("jackson.chung@efcnewlife.org", ["DEACON_ENGLISH_CARING"]),
    # Pastoral team
    ("joe.tung@efcnewlife.org", ["PASTOR_SENIOR_PASTOR"]),
    ("enoch.cho@efcnewlife.org", ["PASTOR_CARING_PASTOR"]),
    ("daniel.hsu@efcnewlife.org", ["PASTOR_ENGLISH_PASTOR"]),
    ("daniel.tu@efcnewlife.org", ["PASTOR_CHINESE_PASTOR"]),
    ("david.pan@efcnewlife.org", ["PASTOR_PART_TIME_CARING_PASTOR"]),
    ("may.chou@efcnewlife.org", ["STAFF_SECRETARY"]),
]


def build_position_assignment_seed_rows() -> list[dict[str, Any]]:
    """Build assignment rows with normalized email and position codes."""
    rows: list[dict[str, Any]] = []
    for email, codes in _ASSIGNMENT_ROWS:
        rows.append({"email": email.strip().lower(), "codes": list(codes)})
    return rows


position_assignment_seed_rows = build_position_assignment_seed_rows()
