"""
MSGraphSharePoint — dedicated app-only SharePoint archive-writer client.

Deliberately separate from MSGraphClientBase: the Mock QA data lifecycle
archive writer must use its own least-privilege Entra registration
(Sites.Selected + an explicit write grant on one site), never the
general-purpose Graph app used for mail/user sync (ADR 0025).
"""

from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.request_adapter import RequestAdapter
from msgraph_beta import GraphServiceClient
from msgraph_beta.generated.models.o_data_errors.o_data_error import ODataError
from msgraph_beta.graph_request_adapter import GraphRequestAdapter

from portal.config import settings
from portal.providers.ms_graph.authentication_provider import CustomAzureIdentityAuthenticationProvider

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_BASE_URL = "https://graph.microsoft.com/beta/"
HTTP_NOT_FOUND = 404


class MSGraphSharePoint:
    """App-only GraphServiceClient scoped to the SharePoint archive-writer app registration."""

    def is_configured(self) -> bool:
        return bool(
            settings.SHAREPOINT_TENANT_ID and settings.SHAREPOINT_APP_CLIENT_ID and settings.SHAREPOINT_APP_CLIENT_SECRET and settings.SHAREPOINT_DRIVE_ID
        )

    @property
    def _credential(self) -> ClientSecretCredential:
        if not self.is_configured():
            raise RuntimeError("SharePoint archive writer is not configured")
        return ClientSecretCredential(
            tenant_id=str(settings.SHAREPOINT_TENANT_ID),
            client_id=str(settings.SHAREPOINT_APP_CLIENT_ID),
            client_secret=str(settings.SHAREPOINT_APP_CLIENT_SECRET),
        )

    @property
    def _request_adapter(self) -> RequestAdapter:
        auth_provider = CustomAzureIdentityAuthenticationProvider(credentials=self._credential, scopes=GRAPH_SCOPE)
        adapter = GraphRequestAdapter(auth_provider=auth_provider)
        adapter.base_url = GRAPH_BASE_URL
        return adapter

    @property
    def client(self) -> GraphServiceClient:
        return GraphServiceClient(request_adapter=self._request_adapter)

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
