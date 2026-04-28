"""
Superuser related CLI commands.
"""

import asyncio
from typing import Optional
from uuid import uuid4

import click

from portal.container import Container
from portal.libs.consts.enums import Gender
from portal.libs.shared import validator
from portal.models import AuthUser, AuthUserProfile
from portal.providers.password_provider import PasswordProvider


async def create_superuser(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> Optional[AuthUser]:
    """
    Create a superuser.

    Notes:
    - This CLI writes directly into `AuthUser` and `AuthUserProfile`.
    - RBAC roles are not required for authorization because middleware/permission
      checks include a superuser bypass (`AuthUser.is_superuser`).
    """
    container = Container()
    session = container.db_session()
    password_provider = PasswordProvider()

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

    # DB column length constraints
    first_name = first_name[:64]
    last_name = last_name[:64]

    try:
        existing_user_id = await (
            session
            .select(AuthUser.id)
            .where(AuthUser.email == normalized_email)
            .fetchval()
        )

        if existing_user_id:
            return await (
                session
                .select(AuthUser)
                .where(AuthUser.id == existing_user_id)
                .fetchrow()
            )

        password_hash = password_provider.hash_password(password)
        user_id = uuid4()

        await (
            session
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
            session
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

        await session.commit()

        click.echo(f"Superuser created: {normalized_email}")
        return await (
            session
            .select(AuthUser)
            .where(AuthUser.id == user_id)
            .fetchrow()
        )
    except Exception as exc:
        click.echo(f"Error creating superuser: {exc}")
        await session.rollback()
        return None
    finally:
        await session.close()


def create_superuser_process() -> None:
    """Create a superuser via interactive prompts."""
    click.echo(
        "\nThis process will guide you through creating a "
        f"{click.style('superuser', fg='blue')} account in the portal."
    )
    click.echo("Please enter the following information to create a superuser account.\n")

    while True:
        email = click.prompt(
            click.style("Enter superuser email (e.g., admin@example.com)", fg="green"),
            type=str,
        )
        if not validator.is_email(email.strip().lower()):
            click.echo(
                click.style(
                    "Invalid email format. Please enter a valid email address.",
                    fg="red",
                )
            )
            continue
        email = email.strip().lower()
        break

    while True:
        password = click.prompt(
            click.style("Enter superuser password", fg="green"),
            hide_input=True,
            confirmation_prompt=click.style("Confirm password", fg="yellow"),
            type=str,
        )
        if len(password) < 8:
            click.echo(click.style("Password must be at least 8 characters long. Please try again.", fg="red"))
            continue
        break

    while True:
        first_name = click.prompt(
            click.style("Enter first name", fg="green"),
            type=str,
        ).strip()
        if not first_name:
            click.echo(click.style("first_name cannot be empty.", fg="red"))
            continue
        first_name = first_name[:64]
        break

    while True:
        last_name = click.prompt(
            click.style("Enter last name", fg="green"),
            type=str,
        ).strip()
        if not last_name:
            click.echo(click.style("last_name cannot be empty.", fg="red"))
            continue
        last_name = last_name[:64]
        break

    asyncio.run(
        create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
    )

    click.echo(
        click.style(
            f"\nSuperuser process finished: {email}",
            fg="bright_green",
        )
    )

