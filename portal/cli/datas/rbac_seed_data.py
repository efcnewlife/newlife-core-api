"""
Seed data for RBAC CLI: verbs, parent resources, child resources, and exclusions.
"""
from uuid import UUID

from portal.libs.consts.enums import ResourceType

SUPPORTED_LOCALES = ("zh-TW", "zh-CN", "en")


def _with_locale_values(values: dict[str, str]) -> dict[str, str]:
    """Keep only locales required in current phase."""
    return {locale_code: values[locale_code] for locale_code in SUPPORTED_LOCALES}


def _with_locale_descriptions(values: dict[str, str]) -> dict[str, str]:
    """Localized descriptions for current phase locales."""
    return {locale_code: values[locale_code] for locale_code in SUPPORTED_LOCALES}

# Parent resource IDs (constants)
SYSTEM_PARENT_ID = UUID("b46586f5-7e43-4eed-9f44-fecff64c9b1d")
CONFERENCE_PARENT_ID = UUID("902bc7d2-8c42-40e6-9a8e-8bf12fc0efc5")
WORKSHOP_PARENT_ID = UUID("d92c0e66-0ac4-475c-981e-8989c7e5f472")
COMMS_PARENT_ID = UUID("342a72a7-544a-4967-8841-c11c9cf7ccd9")
CONTENT_PARENT_ID = UUID("bbc09c99-28b9-4d37-a1c7-c44a427cbfbf")
FACILITY_PARENT_ID = UUID("a1f2c3d4-e5f6-4789-a012-3456789abcde")
MINISTRY_PARENT_ID = UUID("b2e3d4f5-a6b7-4890-c123-456789abcdef")
ORG_PARENT_ID = UUID("c3f4e5a6-b7c8-4901-d234-567890abcdef")
SUPPORT_PARENT_ID = UUID("0450da45-9482-4321-81a3-1fddcf6264e5")

# Verbs
seed_verbs = [
    {
        "action": "create",
        "display_name": "Create",
        "translations": _with_locale_values({"zh-TW": "建立", "zh-CN": "创建", "en": "Create"}),
    },
    {
        "action": "read",
        "display_name": "Read",
        "translations": _with_locale_values({"zh-TW": "查看", "zh-CN": "查看", "en": "Read"}),
    },
    {
        "action": "update",
        "display_name": "Update",
        "translations": _with_locale_values({"zh-TW": "更新", "zh-CN": "更新", "en": "Update"}),
    },
    {
        "action": "delete",
        "display_name": "Delete",
        "translations": _with_locale_values({"zh-TW": "刪除", "zh-CN": "删除", "en": "Delete"}),
    },
]

# Parent resources (grouping only)
parent_resources = [
    {
        "id": SYSTEM_PARENT_ID,
        "code": "system",
        "name": "System Management",
        "key": "SYSTEM",
        "icon": "settings",
        "path": "/system",
        "sequence": 1,
        "translations": _with_locale_values(
            {"zh-TW": "系統管理", "zh-CN": "系统管理", "en": "System Management"}
        ),
        "description": "System related management",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "系統相關管理",
                "zh-CN": "系统相关管理",
                "en": "System related management",
            }
        ),
        "type": ResourceType.SYSTEM.value,
    },
    {
        "id": CONTENT_PARENT_ID,
        "code": "content",
        "name": "Content Management",
        "key": "CONTENT",
        "icon": "folder",
        "path": "/content",
        "sequence": 2,
        "translations": _with_locale_values(
            {"zh-TW": "內容管理", "zh-CN": "内容管理", "en": "Content Management"}
        ),
        "description": "Content related management",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "內容相關管理",
                "zh-CN": "内容相关管理",
                "en": "Content related management",
            }
        ),
        "type": ResourceType.GENERAL.value,
    },
    {
        "id": FACILITY_PARENT_ID,
        "code": "facility",
        "name": "Facility Booking",
        "key": "FACILITY",
        "icon": "MdMeetingRoom",
        "path": "/facility",
        "sequence": 2.5,
        "translations": _with_locale_values(
            {"zh-TW": "場地預約", "zh-CN": "场地预约", "en": "Facility Booking"}
        ),
        "description": "Facility rooms, rates, and bookings",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "場地、費率與預約管理",
                "zh-CN": "场地、费率与预约管理",
                "en": "Facility rooms, rates, and bookings",
            }
        ),
        "type": ResourceType.GENERAL.value,
    },
    {
        "id": MINISTRY_PARENT_ID,
        "code": "ministry",
        "name": "Ministry",
        "key": "MINISTRY",
        "icon": "MdGroups",
        "path": "/ministry",
        "sequence": 2.6,
        "translations": _with_locale_values(
            {"zh-TW": "事工", "zh-CN": "事工", "en": "Ministry"}
        ),
        "description": "Ministry units and member assignment",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "事工單位與成員指派",
                "zh-CN": "事工单位与成员指派",
                "en": "Ministry units and member assignment",
            }
        ),
        "type": ResourceType.GENERAL.value,
    },
    {
        "id": ORG_PARENT_ID,
        "code": "org",
        "name": "Organization",
        "key": "ORG",
        "icon": "MdAccountTree",
        "path": "/org",
        "sequence": 2.55,
        "translations": _with_locale_values(
            {"zh-TW": "教會組織", "zh-CN": "教会组织", "en": "Organization"}
        ),
        "description": "Church positions and members",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "教會職位與會友管理",
                "zh-CN": "教会职位与会友管理",
                "en": "Church positions and members",
            }
        ),
        "type": ResourceType.GENERAL.value,
    },
    {
        "id": SUPPORT_PARENT_ID,
        "code": "support",
        "name": "Support Management",
        "key": "SUPPORT",
        "icon": "MdSupportAgent",
        "path": "/support",
        "sequence": 3,
        "translations": _with_locale_values(
            {"zh-TW": "支援管理", "zh-CN": "支持管理", "en": "Support Management"}
        ),
        "description": "Support and feedback",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "支援與意見回饋",
                "zh-CN": "支持与意见反馈",
                "en": "Support and feedback",
            }
        ),
        "type": ResourceType.GENERAL.value,
    },
]

# Leaf resources (permissions will be created for these)
resources = [
    {
        "code": "system:user",
        "name": "User Management",
        "key": "SYSTEM_USER",
        "icon": "MdPerson",
        "path": "/system/users",
        "type": ResourceType.SYSTEM.value,
        "sequence": 4,
        "translations": _with_locale_values(
            {"zh-TW": "使用者管理", "zh-CN": "用户管理", "en": "User Management"}
        ),
        "description": "Manage system users",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理系統使用者",
                "zh-CN": "管理系统用户",
                "en": "Manage system users",
            }
        ),
        "pid": SYSTEM_PARENT_ID,
    },
    {
        "code": "system:resource",
        "name": "Resource Management",
        "key": "SYSTEM_RESOURCE",
        "icon": "MdAccountTree",
        "path": "/system/resources",
        "type": ResourceType.SYSTEM.value,
        "sequence": 5,
        "translations": _with_locale_values(
            {"zh-TW": "資源管理", "zh-CN": "资源管理", "en": "Resource Management"}
        ),
        "description": "Manage system resources",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理系統資源",
                "zh-CN": "管理系统资源",
                "en": "Manage system resources",
            }
        ),
        "pid": SYSTEM_PARENT_ID,
    },
    {
        "code": "system:permission",
        "name": "Permission Management",
        "key": "SYSTEM_PERMISSION",
        "icon": "MdSecurity",
        "path": "/system/permissions",
        "type": ResourceType.SYSTEM.value,
        "sequence": 6,
        "translations": _with_locale_values(
            {"zh-TW": "權限管理", "zh-CN": "权限管理", "en": "Permission Management"}
        ),
        "description": "Manage system permissions",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理系統權限",
                "zh-CN": "管理系统权限",
                "en": "Manage system permissions",
            }
        ),
        "pid": SYSTEM_PARENT_ID,
    },
    {
        "code": "system:role",
        "name": "Role Management",
        "key": "SYSTEM_ROLE",
        "icon": "MdAdminPanelSettings",
        "path": "/system/roles",
        "type": ResourceType.SYSTEM.value,
        "sequence": 7,
        "translations": _with_locale_values(
            {"zh-TW": "角色管理", "zh-CN": "角色管理", "en": "Role Management"}
        ),
        "description": "Manage system roles",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理系統角色",
                "zh-CN": "管理系统角色",
                "en": "Manage system roles",
            }
        ),
        "pid": SYSTEM_PARENT_ID,
    },
    {
        "code": "system:log",
        "name": "System Log",
        "key": "SYSTEM_LOG",
        "icon": "MdArticle",
        "path": "/system/logs",
        "type": ResourceType.SYSTEM.value,
        "sequence": 8,
        "translations": _with_locale_values(
            {"zh-TW": "系統日誌", "zh-CN": "系统日志", "en": "System Log"}
        ),
        "description": "Manage system logs",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理系統日誌",
                "zh-CN": "管理系统日志",
                "en": "Manage system logs",
            }
        ),
        "pid": SYSTEM_PARENT_ID,
    },
    {
        "code": "content:file",
        "name": "File",
        "key": "CONTENT_FILE",
        "icon": "MdPermMedia",
        "path": "/content/files",
        "type": ResourceType.GENERAL.value,
        "sequence": 9,
        "translations": _with_locale_values(
            {"zh-TW": "檔案管理", "zh-CN": "文件管理", "en": "File"}
        ),
        "description": "Manage files",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理檔案",
                "zh-CN": "管理文件",
                "en": "Manage files",
            }
        ),
        "pid": CONTENT_PARENT_ID,
    },
    {
        "code": "facility:room",
        "name": "Rooms",
        "key": "FACILITY_ROOM",
        "icon": "MdMeetingRoom",
        "path": "/facility/rooms",
        "type": ResourceType.GENERAL.value,
        "sequence": 10,
        "translations": _with_locale_values(
            {"zh-TW": "場地管理", "zh-CN": "场地管理", "en": "Rooms"}
        ),
        "description": "Manage facility rooms",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理場地",
                "zh-CN": "管理场地",
                "en": "Manage facility rooms",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "facility:room_slot_template",
        "name": "Room Slot Templates",
        "key": "FACILITY_ROOM_SLOT_TEMPLATE",
        "icon": "MdSchedule",
        "path": "/facility/room-slot-templates",
        "type": ResourceType.GENERAL.value,
        "sequence": 11,
        "translations": _with_locale_values(
            {"zh-TW": "時段範本", "zh-CN": "时段范本", "en": "Slot Templates"}
        ),
        "description": "Manage weekly slot templates per room",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理場地時段範本",
                "zh-CN": "管理场地时段范本",
                "en": "Manage weekly slot templates per room",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "facility:rental_rate",
        "name": "Rental Rates",
        "key": "FACILITY_RENTAL_RATE",
        "icon": "MdAttachMoney",
        "path": "/facility/rental-rates",
        "type": ResourceType.GENERAL.value,
        "sequence": 12,
        "translations": _with_locale_values(
            {"zh-TW": "租金費率", "zh-CN": "租金费率", "en": "Rental Rates"}
        ),
        "description": "Manage rental rate schedules",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理場地租金費率",
                "zh-CN": "管理场地租金费率",
                "en": "Manage rental rate schedules",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "facility:booking",
        "name": "Bookings",
        "key": "FACILITY_BOOKING",
        "icon": "MdEvent",
        "path": "/facility/bookings",
        "type": ResourceType.GENERAL.value,
        "sequence": 13,
        "translations": _with_locale_values(
            {"zh-TW": "預約管理", "zh-CN": "预约管理", "en": "Bookings"}
        ),
        "description": "Manage facility bookings",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理場地預約",
                "zh-CN": "管理场地预约",
                "en": "Manage facility bookings",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "facility:booking_override_log",
        "name": "Override Logs",
        "key": "FACILITY_BOOKING_OVERRIDE_LOG",
        "icon": "MdHistory",
        "path": "/facility/override-logs",
        "type": ResourceType.GENERAL.value,
        "sequence": 14,
        "translations": _with_locale_values(
            {"zh-TW": "覆寫稽核", "zh-CN": "覆写稽核", "en": "Override Logs"}
        ),
        "description": "Read-only booking override audit log",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "預約覆寫稽核紀錄",
                "zh-CN": "预约覆写稽核记录",
                "en": "Read-only booking override audit log",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "facility:member",
        "name": "Members",
        "key": "FACILITY_MEMBER",
        "icon": "MdPeople",
        "path": "/facility/members",
        "type": ResourceType.GENERAL.value,
        "sequence": 15,
        "translations": _with_locale_values(
            {"zh-TW": "會員查詢", "zh-CN": "会员查询", "en": "Members"}
        ),
        "description": "Search SSO members for facility booking",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "查詢場地預約會員",
                "zh-CN": "查询场地预约会员",
                "en": "Search SSO members for facility booking",
            }
        ),
        "pid": FACILITY_PARENT_ID,
    },
    {
        "code": "ministry:ministry",
        "name": "Ministries",
        "key": "MINISTRY_MINISTRY",
        "icon": "MdGroups",
        "path": "/ministry/ministries",
        "type": ResourceType.GENERAL.value,
        "sequence": 16,
        "translations": _with_locale_values(
            {"zh-TW": "事工單位", "zh-CN": "事工单位", "en": "Ministries"}
        ),
        "description": "Manage ministry units and lifecycle",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理事工單位與生命週期",
                "zh-CN": "管理事工单位与生命周期",
                "en": "Manage ministry units and lifecycle",
            }
        ),
        "pid": MINISTRY_PARENT_ID,
    },
    {
        "code": "ministry:member",
        "name": "Ministry Members",
        "key": "MINISTRY_MEMBER",
        "icon": "MdGroupAdd",
        "path": "/ministry/members",
        "type": ResourceType.GENERAL.value,
        "sequence": 17,
        "translations": _with_locale_values(
            {"zh-TW": "事工成員", "zh-CN": "事工成员", "en": "Ministry Members"}
        ),
        "description": "Assign ministry stewards (primary / secondary)",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "指派事工主負責人與次負責人",
                "zh-CN": "指派事工主负责人与次负责人",
                "en": "Assign ministry stewards (primary / secondary)",
            }
        ),
        "pid": MINISTRY_PARENT_ID,
    },
    {
        "code": "ministry:approval",
        "name": "Ministry Approvals",
        "key": "MINISTRY_APPROVAL",
        "icon": "MdFactCheck",
        "path": "/ministry/approvals",
        "type": ResourceType.GENERAL.value,
        "sequence": 18,
        "translations": _with_locale_values(
            {"zh-TW": "事工審核", "zh-CN": "事工审核", "en": "Ministry Approvals"}
        ),
        "description": "Review pending ministry applications",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "審核待核准事工申請",
                "zh-CN": "审核待核准事工申请",
                "en": "Review pending ministry applications",
            }
        ),
        "pid": MINISTRY_PARENT_ID,
    },
    {
        "code": "org:position",
        "name": "Positions",
        "key": "ORG_POSITION",
        "icon": "MdBadge",
        "path": "/org/positions",
        "type": ResourceType.GENERAL.value,
        "sequence": 19,
        "translations": _with_locale_values(
            {"zh-TW": "教會職位", "zh-CN": "教会职位", "en": "Positions"}
        ),
        "description": "Manage church leadership positions",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理教會領導職位",
                "zh-CN": "管理教会领导职位",
                "en": "Manage church leadership positions",
            }
        ),
        "pid": ORG_PARENT_ID,
    },
    {
        "code": "member:person",
        "name": "Member",
        "key": "MEMBER_PERSON",
        "icon": "MdPersonOutline",
        "path": "/org/members",
        "type": ResourceType.GENERAL.value,
        "sequence": 20,
        "translations": _with_locale_values(
            {"zh-TW": "會友", "zh-CN": "会友", "en": "Member"}
        ),
        "description": "Manage church members",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理教會會友",
                "zh-CN": "管理教会会友",
                "en": "Manage church members",
            }
        ),
        "pid": ORG_PARENT_ID,
    },
    {
        "code": "support:feedback",
        "name": "Feedback",
        "key": "SUPPORT_FEEDBACK",
        "icon": "MdFeedback",
        "path": "/support/feedback",
        "type": ResourceType.GENERAL.value,
        "sequence": 12,
        "translations": _with_locale_values(
            {"zh-TW": "意見回饋", "zh-CN": "意见反馈", "en": "Feedback"}
        ),
        "description": "Manage feedback",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理意見回饋",
                "zh-CN": "管理意见反馈",
                "en": "Manage feedback",
            }
        ),
        "pid": SUPPORT_PARENT_ID,
    },
    {
        "code": "support:faq",
        "name": "FAQ",
        "key": "SUPPORT_FAQ",
        "icon": "MdHelp",
        "path": "/content/faq",
        "type": ResourceType.GENERAL.value,
        "sequence": 11,
        "translations": _with_locale_values(
            {"zh-TW": "常見問題", "zh-CN": "常见问题", "en": "FAQ"}
        ),
        "description": "Manage FAQ",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理常見問題",
                "zh-CN": "管理常见问题",
                "en": "Manage FAQ",
            }
        ),
        "pid": SUPPORT_PARENT_ID,
    },
]
