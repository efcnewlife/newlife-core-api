"""
Organization domain constants.
"""
from enum import Enum


class MinistryStatus(str, Enum):
    """Ministry lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    REJECTED = "rejected"
    INACTIVE = "inactive"


class MinistryMemberRole(str, Enum):
    """Ministry member steward role (booking eligibility)."""
    PRIMARY = "primary"
    SECONDARY = "secondary"


class MinistryApprovalStatus(str, Enum):
    """Ministry approval request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PositionTeam(str, Enum):
    """Church leadership team grouping."""
    ELDER_AND_DEACON = "elder_and_deacon"
    PASTORAL_TEAM = "pastoral_team"


class PositionOffice(str, Enum):
    """Church leadership office / role."""
    ELDER = "elder"
    DEACON = "deacon"
    PASTOR = "pastor"
    STAFF = "staff"


def position_office_can_own_ministry(office: PositionOffice | str) -> bool:
    """Whether the office may own a ministry."""
    value = office.value if isinstance(office, PositionOffice) else office
    return value in {
        PositionOffice.ELDER.value,
        PositionOffice.DEACON.value,
        PositionOffice.PASTOR.value,
    }
