"""
Orchestrate catalog bootstrap for a new environment, then hand off to superuser creation.
"""

import asyncio
from collections.abc import Awaitable, Callable

CatalogStep = Callable[[], Awaitable[None]]
SuperuserStep = Callable[[], None]


class InitAllService:
    """Run catalog upserts in a fixed fail-fast order, then create a superuser."""

    def __init__(
        self,
        *,
        init_locales: CatalogStep,
        init_rbac: CatalogStep,
        seed_system_settings: CatalogStep,
        seed_positions: CatalogStep,
        seed_target_audiences: CatalogStep,
        seed_facility_rental: CatalogStep,
        seed_legal_documents: CatalogStep,
        create_superuser: SuperuserStep,
    ):
        self._catalog_steps: tuple[CatalogStep, ...] = (
            init_locales,
            init_rbac,
            seed_system_settings,
            seed_positions,
            seed_target_audiences,
            seed_facility_rental,
            seed_legal_documents,
        )
        self._create_superuser = create_superuser

    async def _run_catalog_steps(self) -> None:
        for step in self._catalog_steps:
            await step()

    def run(self) -> None:
        asyncio.run(self._run_catalog_steps())
        self._create_superuser()
