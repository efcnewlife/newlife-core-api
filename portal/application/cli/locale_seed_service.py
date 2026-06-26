"""
Locale seed use case for CLI.
"""
import click

from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import SystemLocale


class LocaleSeedService:
    """Upsert system locales from seed data."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, seed_locales: list[dict]) -> int:
        """
        Seed locales into SystemLocale table.
        :param seed_locales:
        :return: number of seed rows processed
        """
        for locale in seed_locales:
            await (
                self._session
                .insert(SystemLocale)
                .values(**locale)
                .on_conflict_do_update(
                    index_elements=["language_code", "script_code", "region_code"],
                    set_=dict(
                        name=locale.get("name"),
                        native_name=locale.get("native_name"),
                        is_active=locale.get("is_active", True),
                        is_default=locale.get("is_default", False),
                    ),
                )
                .execute()
            )
        await self._session.commit()
        click.echo(click.style("Locales initialized successfully.", fg="bright_green"))
        logger.info(f"Locale init completed. locales upserted: {len(seed_locales)}")
        return len(seed_locales)
