"""
System setting seed use case for CLI (insert-if-missing).
"""
import json

import click

from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import SystemSetting


class SystemSettingSeedService:
    """Insert system settings when namespace+key is absent; never overwrite value."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, seed_rows: list[dict]) -> int:
        inserted = 0
        for row in seed_rows:
            existing_id = await (
                self._session.select(SystemSetting.id)
                .where(SystemSetting.namespace == row["namespace"])
                .where(SystemSetting.setting_key == row["setting_key"])
                .where(SystemSetting.is_deleted == False)
                .fetchval()
            )
            if existing_id:
                continue
            # asyncpg JSONB bind expects a JSON text string (e.g. '"America/Toronto"').
            insert_row = {**row, "value": json.dumps(row["value"])}
            await self._session.insert(SystemSetting).values(**insert_row).execute()
            inserted += 1
        await self._session.commit()
        click.echo(
            click.style(
                f"System settings seeded. inserted={inserted} skipped={len(seed_rows) - inserted}",
                fg="bright_green",
            )
        )
        logger.info(
            "System setting seed completed. inserted=%s skipped=%s",
            inserted,
            len(seed_rows) - inserted,
        )
        return inserted
