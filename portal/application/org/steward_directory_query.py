"""
Steward directory q matching (Ministry name or Steward identity).
"""

from typing import Optional


def matches_steward_directory_q(
    q: Optional[str],
    *,
    translation_names: list[str],
    steward_login_emails: list[Optional[str]],
    steward_display_names: list[Optional[str]],
    steward_contact_emails: list[Optional[str]],
) -> bool:
    needle = (q or "").strip().lower()
    if not needle:
        return True
    values = [*translation_names, *steward_login_emails, *steward_display_names, *steward_contact_emails]
    return any(needle in value.lower() for value in values if value)
