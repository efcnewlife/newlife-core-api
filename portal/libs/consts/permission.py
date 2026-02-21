"""
Permission constants - Template: System resources only
"""
from enum import Enum


class Verb(Enum):
    """Verb enum"""
    READ = "read"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class Resource(Enum):
    """Resource enum - System resources only"""
    SYSTEM_PERMISSION = "system:permission"
    SYSTEM_RESOURCE = "system:resource"
    SYSTEM_ROLE = "system:role"
    SYSTEM_USER = "system:user"
    SYSTEM_LOG = "system:log"


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
            return f"{self._resource_value}:{Verb.MODIFY.value}"

        @property
        def delete(self):
            return f"{self._resource_value}:{Verb.DELETE.value}"

    SYSTEM_PERMISSION = PermissionCode(Resource.SYSTEM_PERMISSION)
    SYSTEM_RESOURCE = PermissionCode(Resource.SYSTEM_RESOURCE)
    SYSTEM_ROLE = PermissionCode(Resource.SYSTEM_ROLE)
    SYSTEM_USER = PermissionCode(Resource.SYSTEM_USER)
    SYSTEM_LOG = PermissionCode(Resource.SYSTEM_LOG)
