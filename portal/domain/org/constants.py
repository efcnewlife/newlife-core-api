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


class OrgErrorCode(str, Enum):
    """Machine-readable org admin error codes for clients."""

    MINISTRY_NOT_FOUND = "ORG_MINISTRY_NOT_FOUND"
    MINISTRY_PRIMARY_REQUIRED = "ORG_MINISTRY_PRIMARY_REQUIRED"
    MINISTRY_SECONDARY_REQUIRED = "ORG_MINISTRY_SECONDARY_REQUIRED"
    MINISTRY_NOT_PENDING_APPROVAL = "ORG_MINISTRY_NOT_PENDING_APPROVAL"
    MINISTRY_INVALID_STATUS_FOR_SUBMIT = "ORG_MINISTRY_INVALID_STATUS_FOR_SUBMIT"
    MINISTRY_OWNER_POSITION_REQUIRED = "ORG_MINISTRY_OWNER_POSITION_REQUIRED"
    MINISTRY_INVALID_TARGET_AUDIENCES = "ORG_MINISTRY_INVALID_TARGET_AUDIENCES"
    POSITION_NO_INCUMBENT = "ORG_POSITION_NO_INCUMBENT"
    POSITION_NOT_FOUND = "ORG_POSITION_NOT_FOUND"
    POSITION_CODE_EXISTS = "ORG_POSITION_CODE_EXISTS"


def position_office_can_own_ministry(office: PositionOffice | str) -> bool:
    """Whether the office may own a ministry."""
    value = office.value if isinstance(office, PositionOffice) else office
    return value in {PositionOffice.ELDER.value, PositionOffice.DEACON.value, PositionOffice.PASTOR.value}
