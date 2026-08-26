"""
Top-level package for models.
"""

from .audit import AuditLog
from .auth import (
    AuthDevice,
    AuthPermission,
    AuthPermissionTranslation,
    AuthRefreshToken,
    AuthResource,
    AuthResourceTranslation,
    AuthRole,
    AuthRolePermission,
    AuthRoleTranslation,
    AuthUser,
    AuthUserProfile,
    AuthUserRole,
    AuthUserThirdParty,
    AuthVerb,
    AuthVerbTranslation,
)
from .content import ContentFile, ContentFileAssociation, ContentLegalDocument, ContentLegalDocumentTranslation
from .facility import (
    FacilityBooking,
    FacilityBookingOverrideLog,
    FacilityBookingRoom,
    FacilityBookingSlot,
    FacilityBookingSurcharge,
    FacilityRentalDiscountRule,
    FacilityRentalPolicySetting,
    FacilityRentalRate,
    FacilityRentalRateTemplate,
    FacilityRentalSurcharge,
    FacilityRoom,
    FacilityRoomBlackout,
    FacilityRoomSlotTemplate,
    FacilityRoomTranslation,
)
from .member import MemberPerson
from .org import (
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistrySchedule,
    OrgMinistryTargetAudience,
    OrgMinistryTranslation,
    OrgMinistryType,
    OrgMinistryTypeTranslation,
    OrgPosition,
    OrgPositionAssignment,
    OrgPositionTranslation,
    OrgTargetAudience,
    OrgTargetAudienceTranslation,
)
from .system_locale import SystemLocale
from .system_setting import SystemSetting

__all__ = [
    # audit
    "AuditLog",
    # user
    "AuthUser",
    "AuthUserProfile",
    "AuthUserThirdParty",
    # rbac
    "AuthRole",
    "AuthRoleTranslation",
    "AuthResource",
    "AuthResourceTranslation",
    "AuthVerb",
    "AuthVerbTranslation",
    "AuthPermission",
    "AuthPermissionTranslation",
    "AuthUserRole",
    "AuthRolePermission",
    # locale
    "SystemLocale",
    # system setting
    "SystemSetting",
    # auth
    "AuthDevice",
    "AuthRefreshToken",
    # facility
    "FacilityRoom",
    "FacilityRoomTranslation",
    "FacilityRoomSlotTemplate",
    "FacilityRoomBlackout",
    "FacilityRentalRateTemplate",
    "FacilityRentalRate",
    "FacilityRentalDiscountRule",
    "FacilityRentalSurcharge",
    "FacilityRentalPolicySetting",
    "FacilityBooking",
    "FacilityBookingRoom",
    "FacilityBookingSlot",
    "FacilityBookingSurcharge",
    "FacilityBookingOverrideLog",
    # member
    "MemberPerson",
    # content
    "ContentFile",
    "ContentFileAssociation",
    "ContentLegalDocument",
    "ContentLegalDocumentTranslation",
    # org
    "OrgPosition",
    "OrgPositionTranslation",
    "OrgPositionAssignment",
    "OrgMinistryType",
    "OrgMinistryTypeTranslation",
    "OrgTargetAudience",
    "OrgTargetAudienceTranslation",
    "OrgMinistryTargetAudience",
    "OrgMinistry",
    "OrgMinistryTranslation",
    "OrgMinistryMember",
    "OrgMinistrySchedule",
    "OrgMinistryApproval",
]
