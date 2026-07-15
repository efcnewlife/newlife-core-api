"""Normalized Graph models for directory sync."""
from typing import Optional

from pydantic import BaseModel, Field


class GraphUserRecord(BaseModel):
    """Normalized Graph user fields for directory sync."""

    object_id: str = Field(..., description="Entra object id")
    email: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    display_name: Optional[str] = None
    account_enabled: bool = True
    user_principal_name: Optional[str] = None
    user_type: Optional[str] = None
