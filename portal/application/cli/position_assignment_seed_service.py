"""
Position assignment seed use case for CLI.

Binds existing users (by email) to org positions (by code) as incumbents.
"""
from typing import Any

import click

from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import AuthUser, OrgPosition


async def run_position_assignment_seed(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Assign incumbents from email -> position code rows.

    Missing users are skipped with a warning. Missing position codes raise.
    """
    repository = PositionRepository(session)
    assigned = 0
    skipped_missing_user = 0

    for row in rows:
        email = (row.get("email") or "").strip().lower()
        codes: list[str] = list(row.get("codes") or [])
        if not email or not codes:
            continue

        user_id = await (
            session.select(AuthUser.id)
            .where(AuthUser.email == email)
            .fetchval()
        )
        if not user_id:
            skipped_missing_user += 1
            click.echo(
                click.style(
                    f"Skip: user not found for email {email}",
                    fg="yellow",
                )
            )
            continue

        for code in codes:
            position_id = await (
                session.select(OrgPosition.id)
                .where(OrgPosition.code == code)
                .where(OrgPosition.is_deleted == False)
                .fetchval()
            )
            if not position_id:
                raise ValueError(
                    f"Position code {code!r} not found. Run seed-positions first."
                )
            await repository.assign_incumbent(position_id=position_id, user_id=user_id)
            assigned += 1
            click.echo(f"Assigned {email} -> {code}")

    await session.commit()
    click.echo(
        click.style(
            f"Done: assigned={assigned}, skipped_missing_user={skipped_missing_user}",
            fg="green",
        )
    )
    logger.info(
        "Position assignment seed completed: assigned=%s skipped_missing_user=%s",
        assigned,
        skipped_missing_user,
    )
