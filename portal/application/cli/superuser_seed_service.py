"""
Superuser seed use case for CLI.
"""
from typing import Any, Optional
from uuid import uuid4

import click

from portal.libs.consts.enums import Gender
from portal.libs.database import Session
from portal.libs.shared import validator
from portal.models import AuthUser, AuthUserProfile
from portal.providers.password_provider import PasswordProvider


class SuperuserSeedService:
    """Create or return an existing superuser account."""

    def __init__(self, session: Session, password_provider: PasswordProvider):
        self._session = session
        self._password_provider = password_provider

    async def run(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> Optional[Any]:
        """
        Create a superuser when one does not already exist for the email.
        :param email:
        :param password:
        :param first_name:
        :param last_name:
        :return:
        """
        normalized_email = (email or "").strip().lower()

        if not normalized_email or not validator.is_email(normalized_email):
            raise ValueError("Invalid email format")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        if not first_name:
            raise ValueError("first_name is required")
        if not last_name:
            raise ValueError("last_name is required")

        first_name = first_name[:64]
        last_name = last_name[:64]

        existing_user_id = await (
            self._session
            .select(AuthUser.id)
            .where(AuthUser.email == normalized_email)
            .fetchval()
        )

        if existing_user_id:
            return await (
                self._session
                .select(AuthUser)
                .where(AuthUser.id == existing_user_id)
                .fetchrow()
            )

        password_hash = self._password_provider.hash_password(password)
        user_id = uuid4()

        await (
            self._session
            .insert(AuthUser)
            .values(
                id=user_id,
                email=normalized_email,
                password_hash=password_hash,
                verified=True,
                is_active=True,
                is_superuser=True,
                is_admin=True,
            )
            .execute()
        )

        await (
            self._session
            .insert(AuthUserProfile)
            .values(
                id=uuid4(),
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                gender=Gender.UNKNOWN.value,
            )
            .execute()
        )

        await self._session.commit()

        click.echo(f"Superuser created: {normalized_email}")
        return await (
            self._session
            .select(AuthUser)
            .where(AuthUser.id == user_id)
            .fetchrow()
        )
