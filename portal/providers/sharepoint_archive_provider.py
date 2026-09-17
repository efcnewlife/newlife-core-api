"""
SharePoint archive-writer facade for seed-mock-users (ADR 0025).
"""

from collections.abc import Callable
from pathlib import Path

from portal.config import settings
from portal.providers.ms_graph.sharepoint import MSGraphSharePoint

__all__ = ["SharePointArchiveProvider"]

_ENV_FOLDERS = {"dev": lambda: settings.SHAREPOINT_TEST_ACCOUNT_FOLDER_DEV, "stg": lambda: settings.SHAREPOINT_TEST_ACCOUNT_FOLDER_STG}


def _folder_for_env(env: str) -> str:
    resolver = _ENV_FOLDERS.get(env)
    if not resolver:
        raise ValueError(f"No SharePoint archive folder configured for ENV={env!r}")
    return resolver()


class SharePointArchiveProvider:
    """Upload the account/Ministry CSV pair to the environment's `Test Account` archive folder."""

    def __init__(self, sharepoint_factory: Callable[[], MSGraphSharePoint] = MSGraphSharePoint) -> None:
        self._sharepoint_factory = sharepoint_factory

    def is_configured(self) -> bool:
        return self._sharepoint_factory().is_configured()

    async def upload_csv_pair(self, *, env: str, account_csv: Path, ministry_csv: Path) -> None:
        if not self.is_configured():
            raise RuntimeError("SharePoint archive writer is not configured")

        sharepoint = self._sharepoint_factory()
        drive_id = str(settings.SHAREPOINT_DRIVE_ID)
        folder = _folder_for_env(env)

        for local_path in (account_csv, ministry_csv):
            item_path = f"{folder}/{local_path.name}"
            if await sharepoint.item_exists(drive_id=drive_id, item_path=item_path):
                raise RuntimeError(f"SharePoint archive already has a file at {item_path!r}; refusing to overwrite it.")

        for local_path in (account_csv, ministry_csv):
            item_path = f"{folder}/{local_path.name}"
            await sharepoint.upload_bytes(drive_id=drive_id, item_path=item_path, content=local_path.read_bytes())
