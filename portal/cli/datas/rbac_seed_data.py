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
        "code": "content:location",
        "name": "Location",
        "key": "CONTENT_LOCATION",
        "icon": "MdLocationOn",
        "path": "/content/locations",
        "type": ResourceType.GENERAL.value,
        "sequence": 10,
        "translations": _with_locale_values(
            {"zh-TW": "場地位置", "zh-CN": "场地位置", "en": "Location"}
        ),
        "description": "Manage locations",
        "description_translations": _with_locale_descriptions(
            {
                "zh-TW": "管理場地位置",
                "zh-CN": "管理场地位置",
                "en": "Manage locations",
            }
        ),
        "pid": CONTENT_PARENT_ID,
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
