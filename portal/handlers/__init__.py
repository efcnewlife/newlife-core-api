"""
Top level handlers package - Template: minimal handlers for auth
"""
from .admin.auth import AdminAuthHandler
from .admin.locale import AdminLocaleHandler
from .admin.log import AdminLogHandler
from .admin.permission import AdminPermissionHandler
from .admin.resource import AdminResourceHandler
from .admin.role import AdminRoleHandler
from .admin.user import AdminUserHandler
from .admin.verb import AdminVerbHandler
from .user import UserHandler

__all__ = [
    # admin
    "AdminAuthHandler",
    "AdminLocaleHandler",
    "AdminLogHandler",
    "AdminPermissionHandler",
    "AdminResourceHandler",
    "AdminRoleHandler",
    "AdminUserHandler",
    "AdminVerbHandler",
    # general
    "UserHandler",
]
