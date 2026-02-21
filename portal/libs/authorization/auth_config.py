"""
Authentication and Authorization Configuration
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AuthConfig(BaseModel):
    """
    Authentication and Authorization configuration for route

    This configuration integrates:
    - Authentication (Token verification)
    - Authorization (Permission checking)
    """
    # Permission configuration
    permission_codes: Optional[List[str]] = Field(
        default=None,
        description="List of permission codes required for access. If None, no permission check is performed."
    )
    require_all: bool = Field(
        default=False,
        description="Whether to require all permissions (True) or any permission (False)"
    )
    allow_superuser: bool = Field(
        default=False,
        description="Whether to allow superuser to bypass permission check"
    )

    # Authentication configuration
    require_auth: bool = Field(
        default=True,
        description="Whether to require authentication (token verification)"
    )
    is_admin: bool = Field(
        default=False,
        description="Whether to use admin authentication (True) or user authentication (False)"
    )

    @field_validator("permission_codes")
    @classmethod
    def validate_permission_codes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """
        Validate and normalize permission codes
        Removes duplicates while preserving order
        """
        if v is None:
            return None

        if len(v) == 0:
            return None

        # Remove duplicates while preserving order
        seen = set()
        unique_codes = []
        for code in v:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)
        return unique_codes

    def has_permission_check(self) -> bool:
        """Check if permission checking is enabled"""
        return self.permission_codes is not None and len(self.permission_codes) > 0
