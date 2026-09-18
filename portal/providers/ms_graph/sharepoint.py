"""
MSGraphSharePoint — drive item reads/uploads via Microsoft Graph (application permission).
"""

from msgraph_beta.generated.models.o_data_errors.o_data_error import ODataError

from portal.config import settings
from portal.providers.ms_graph.base import MSGraphClientBase

HTTP_NOT_FOUND = 404


class MSGraphSharePoint(MSGraphClientBase):
    """Upload files to a configured document-library drive using the shared Graph app."""

    def is_configured(self) -> bool:
        return super().is_configured() and bool(settings.SHAREPOINT_DRIVE_ID)

    async def item_exists(self, *, drive_id: str, item_path: str) -> bool:
        """Return True when a drive item already exists at `root:/{item_path}:`."""
        try:
            await self.client.drives.by_drive_id(drive_id).items.by_drive_item_id(f"root:/{item_path}:").get()
            return True
        except ODataError as exc:
            if exc.response_status_code == HTTP_NOT_FOUND:
                return False
            raise

    async def upload_bytes(self, *, drive_id: str, item_path: str, content: bytes) -> None:
        """Upload `content` to `root:/{item_path}:`. Caller must have already checked for collisions."""
        await self.client.drives.by_drive_id(drive_id).items.by_drive_item_id(f"root:/{item_path}:").content.put(content)
