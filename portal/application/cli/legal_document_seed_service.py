"""
Legal Document seed use case for CLI (insert-if-missing).
"""

from uuid import uuid4

import click

from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import ContentLegalDocument


class LegalDocumentSeedService:
    """Insert Legal Document parents when Product+Kind is absent; never overwrite."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, seed_rows: list[dict]) -> int:
        inserted = 0
        for row in seed_rows:
            existing_id = await (
                self._session.select(ContentLegalDocument.id)
                .where(ContentLegalDocument.product == row["product"])
                .where(ContentLegalDocument.kind == row["kind"])
                .fetchval()
            )
            if existing_id:
                continue
            await self._session.insert(ContentLegalDocument).values(id=uuid4(), product=row["product"], kind=row["kind"]).execute()
            inserted += 1
        await self._session.commit()
        click.echo(click.style(f"Legal Documents seeded. inserted={inserted} skipped={len(seed_rows) - inserted}", fg="bright_green"))
        logger.info("Legal Document seed completed. inserted=%s skipped=%s", inserted, len(seed_rows) - inserted)
        return inserted
