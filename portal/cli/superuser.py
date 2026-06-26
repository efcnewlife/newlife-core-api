"""
Superuser related CLI commands.
"""

import asyncio

import click

from portal.application.cli.superuser_seed_service import SuperuserSeedService
from portal.container import Container
from portal.libs.shared import validator
from portal.providers.password_provider import PasswordProvider


async def create_superuser(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
):
    """
    Create a superuser via application seed service.
    """
    container = Container()
    session = container.db_session()
    try:
        service = SuperuserSeedService(session, PasswordProvider())
        return await service.run(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
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
