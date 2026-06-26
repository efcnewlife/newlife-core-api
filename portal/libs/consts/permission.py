"""
Permission constants - Template: System resources only
"""
from enum import Enum


class Verb(Enum):
    """Verb enum"""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class Resource(Enum):
    """Resource enum"""
    SYSTEM_PERMISSION = "system:permission"
    SYSTEM_RESOURCE = "system:resource"
    SYSTEM_ROLE = "system:role"
    SYSTEM_USER = "system:user"
    SYSTEM_LOG = "system:log"
    FACILITY_ROOM = "facility:room"
    FACILITY_ROOM_SLOT_TEMPLATE = "facility:room_slot_template"
    FACILITY_RENTAL_RATE = "facility:rental_rate"
    FACILITY_BOOKING = "facility:booking"
    FACILITY_BOOKING_OVERRIDE_LOG = "facility:booking_override_log"
    FACILITY_MEMBER = "facility:member"
    MINISTRY_MINISTRY = "ministry:ministry"
    MINISTRY_MEMBER = "ministry:member"
    MINISTRY_APPROVAL = "ministry:approval"
    ORG_POSITION = "org:position"
    MEMBER_PERSON = "member:person"


class Permission:
    """
    Permission - usage: Permission.{resource}.{verb}
    E.g., Permission.SYSTEM_USER.READ = "system:user:read"
    """

    class PermissionCode:
        def __init__(self, resource: Resource):
            self._resource_value = resource.value

        @property
        def all(self):
            return f"{self._resource_value}:*"

        @property
        def read(self):
            return f"{self._resource_value}:{Verb.READ.value}"

        @property
        def create(self):
            return f"{self._resource_value}:{Verb.CREATE.value}"

        @property
        def modify(self):
            return f"{self._resource_value}:{Verb.UPDATE.value}"

        @property
        def delete(self):
            return f"{self._resource_value}:{Verb.DELETE.value}"

    SYSTEM_PERMISSION = PermissionCode(Resource.SYSTEM_PERMISSION)
    SYSTEM_RESOURCE = PermissionCode(Resource.SYSTEM_RESOURCE)
    SYSTEM_ROLE = PermissionCode(Resource.SYSTEM_ROLE)
    SYSTEM_USER = PermissionCode(Resource.SYSTEM_USER)
    SYSTEM_LOG = PermissionCode(Resource.SYSTEM_LOG)
    FACILITY_ROOM = PermissionCode(Resource.FACILITY_ROOM)
    FACILITY_ROOM_SLOT_TEMPLATE = PermissionCode(Resource.FACILITY_ROOM_SLOT_TEMPLATE)
    FACILITY_RENTAL_RATE = PermissionCode(Resource.FACILITY_RENTAL_RATE)
    FACILITY_BOOKING = PermissionCode(Resource.FACILITY_BOOKING)
    FACILITY_BOOKING_OVERRIDE_LOG = PermissionCode(Resource.FACILITY_BOOKING_OVERRIDE_LOG)
    FACILITY_MEMBER = PermissionCode(Resource.FACILITY_MEMBER)
    MINISTRY_MINISTRY = PermissionCode(Resource.MINISTRY_MINISTRY)
    MINISTRY_MEMBER = PermissionCode(Resource.MINISTRY_MEMBER)
    MINISTRY_APPROVAL = PermissionCode(Resource.MINISTRY_APPROVAL)
    ORG_POSITION = PermissionCode(Resource.ORG_POSITION)
    MEMBER_PERSON = PermissionCode(Resource.MEMBER_PERSON)
