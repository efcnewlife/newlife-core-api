"""
Map Microsoft OIDC claims or Graph user fields to AuthUserProfile columns.
"""
from typing import Any, Optional

from portal.providers.microsoft_graph_provider import GraphUserRecord


def profile_fields_from_microsoft_claims(claims: dict[str, Any]) -> tuple[str, str, Optional[str]]:
    given_name = str(claims.get("given_name") or "").strip()
    family_name = str(claims.get("family_name") or "").strip()
    display_name = str(claims.get("name") or "").strip()

    if not given_name and display_name:
        name_parts = display_name.split(None, 1)
        given_name = name_parts[0] if name_parts else ""
        if not family_name and len(name_parts) > 1:
            family_name = name_parts[1]

    if not given_name:
        fallback = (
            display_name
            or str(claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "")
            .strip()
        )
        if "@" in fallback:
            fallback = fallback.split("@", 1)[0]
        given_name = fallback or "User"

    preferred_name = display_name or None
    return given_name, family_name, preferred_name


def profile_fields_from_graph_user(record: GraphUserRecord) -> tuple[str, str, Optional[str]]:
    claims = {
        "given_name": record.given_name,
        "family_name": record.surname,
        "name": record.display_name,
        "email": record.email,
        "upn": record.user_principal_name,
    }
    return profile_fields_from_microsoft_claims(claims)
