"""
Mock testing-account seed use case for CLI (Facility Booking QA).
"""

from typing import Any, Optional
from uuid import uuid4

import click

from portal.config import settings
from portal.domain.member.constants import AccountKind
from portal.libs.consts.enums import Gender
from portal.libs.database import Session
from portal.libs.shared import validator
from portal.models import AuthUser, AuthUserProfile

CLI_ACTOR = "create_mock_user_cli"
DEFAULT_TESTING_ACCOUNT_EMAIL_SUFFIX = "@test.local"


def resolve_testing_account_email_suffix() -> str:
    """Return configured testing suffix or the project default."""
    configured = settings.TESTING_ACCOUNT_EMAIL_SUFFIX.strip()
    return configured or DEFAULT_TESTING_ACCOUNT_EMAIL_SUFFIX


def email_has_testing_suffix(email: str, suffix: Optional[str] = None) -> bool:
    """Return True when email ends with the configured testing-account suffix."""
    configured_suffix = (suffix if suffix is not None else resolve_testing_account_email_suffix()).strip().lower()
    if not configured_suffix:
        return False
    return email.endswith(configured_suffix)


class MockUserSeedService:
    """Create or return an existing mock-login testing account."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, email: str, first_name: str, last_name: str) -> Optional[Any]:
        """
        Create a member testing account when one does not already exist for the email.
        """
        normalized_email = (email or "").strip().lower()

        if not normalized_email or not validator.is_email(normalized_email):
            raise ValueError("Invalid email format")
        if not email_has_testing_suffix(normalized_email):
            suffix = resolve_testing_account_email_suffix()
            raise ValueError(f"Email must end with testing suffix {suffix!r}")
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        if not first_name:
            raise ValueError("first_name is required")
        if not last_name:
            raise ValueError("last_name is required")

        first_name = first_name[:64]
        last_name = last_name[:64]

        existing_user_id = await self._session.select(AuthUser.id).where(AuthUser.email == normalized_email).fetchval()

        if existing_user_id:
            click.echo(f"Testing account already exists: {normalized_email}")
            return await self._session.select(AuthUser).where(AuthUser.id == existing_user_id).fetchrow()

        user_id = uuid4()

        await (
            self._session.insert(AuthUser)
            .values(
                id=user_id,
                email=normalized_email,
                verified=True,
                is_active=True,
                is_superuser=False,
                is_admin=False,
                account_kind=AccountKind.MEMBER.value,
                created_by=CLI_ACTOR,
                updated_by=CLI_ACTOR,
            )
            .execute()
        )

        await (
            self._session.insert(AuthUserProfile)
            .values(
                id=uuid4(), user_id=user_id, first_name=first_name, last_name=last_name, gender=Gender.UNKNOWN.value, created_by=CLI_ACTOR, updated_by=CLI_ACTOR
            )
            .execute()
        )

        await self._session.commit()

        click.echo(f"Mock testing account created: {normalized_email}")
        return await self._session.select(AuthUser).where(AuthUser.id == user_id).fetchrow()
