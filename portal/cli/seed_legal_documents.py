"""
Legal Document seed CLI.
"""

import asyncio

import click

from portal.application.cli.legal_document_seed_service import LegalDocumentSeedService
from portal.cli.datas.legal_document_seed_data import seed_legal_documents
from portal.container import Container
from portal.libs.logger import logger


async def seed_legal_documents_async() -> None:
    """Seed content.legal_document rows (insert-if-missing)."""
    container = Container()
    session = container.db_session()
    try:
        service = LegalDocumentSeedService(session)
        await service.run(seed_legal_documents)
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"Legal Document seed failed: {e}", fg="red"))
        logger.exception(e)
        raise
    finally:
        await session.close()


def seed_legal_documents_process() -> None:
    """Synchronous entry for Legal Document seed."""
    asyncio.run(seed_legal_documents_async())
