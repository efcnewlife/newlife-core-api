"""
Mock testing-account CLI commands.
"""

import asyncio

import click

from portal.application.cli.mock_user_seed_service import MockUserSeedService, email_has_testing_suffix, resolve_testing_account_email_suffix
from portal.container import Container
from portal.libs.shared import validator


async def create_mock_user(email: str, first_name: str, last_name: str):
    """Create a mock-login testing account via application seed service."""
    container = Container()
    session = container.db_session()
    try:
        service = MockUserSeedService(session)
        return await service.run(email=email, first_name=first_name, last_name=last_name)
    except Exception as exc:
        click.echo(f"Error creating mock testing account: {exc}")
        await session.rollback()
        return None
    finally:
        await session.close()


def create_mock_user_process() -> None:
    """Create a mock-login testing account via interactive prompts."""
    suffix = resolve_testing_account_email_suffix()
    click.echo(
        f"\nThis process will guide you through creating a {click.style('mock-login testing account', fg='blue')} "
        f"(email suffix {click.style(suffix, fg='cyan')})."
    )
    click.echo("Please enter the following information.\n")

    while True:
        email = click.prompt(click.style(f"Enter testing account email (must end with {suffix})", fg="green"), type=str)
        normalized = email.strip().lower()
        if not validator.is_email(normalized):
            click.echo(click.style("Invalid email format. Please enter a valid email address.", fg="red"))
            continue
        if not email_has_testing_suffix(normalized):
            click.echo(click.style(f"Email must end with {suffix!r}. Please try again.", fg="red"))
            continue
        email = normalized
        break

    while True:
        first_name = click.prompt(click.style("Enter first name", fg="green"), type=str).strip()
        if not first_name:
            click.echo(click.style("first_name cannot be empty.", fg="red"))
            continue
        first_name = first_name[:64]
        break

    while True:
        last_name = click.prompt(click.style("Enter last name", fg="green"), type=str).strip()
        if not last_name:
            click.echo(click.style("last_name cannot be empty.", fg="red"))
            continue
        last_name = last_name[:64]
        break

    result = asyncio.run(create_mock_user(email=email, first_name=first_name, last_name=last_name))

    if result is not None:
        click.echo(click.style(f"\nMock testing account process finished: {email}", fg="bright_green"))
    else:
        click.echo(click.style("\nMock testing account process failed.", fg="red"))
