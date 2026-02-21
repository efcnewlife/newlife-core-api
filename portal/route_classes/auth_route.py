"""
Authentication and Authorization Route
"""
from typing import Optional, Callable

from fastapi import Request, Response
from portal.libs.authorization.auth_config import AuthConfig
from portal.route_classes.log_route import LogRoute


class AuthRoute(LogRoute):
    """
    Route with Authentication and Authorization metadata

    This route class only stores auth_config metadata.
    Actual authentication and authorization are handled by AuthMiddleware.
    No dependency injection is used.
    """

    def __init__(self, *args, auth_config: Optional[AuthConfig] = None, **kwargs):
        """
        Initialize route with authentication and authorization configuration
        :param auth_config: Authentication and authorization configuration (stored as metadata only)
        """
        super().__init__(*args, **kwargs)
        self.auth_config = auth_config  # NOTE: After the request came in, auth_config was None for unknown reasons
