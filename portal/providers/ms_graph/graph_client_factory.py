"""
Shared app-only Microsoft Graph client construction.

Extracted so Graph providers (users, mail, SharePoint) can build a
GraphServiceClient the same way without duplicating the
credential -> auth-provider -> adapter -> client wiring.
"""

from azure.identity.aio import ClientSecretCredential
from msgraph_beta import GraphServiceClient
from msgraph_beta.graph_request_adapter import GraphRequestAdapter

from portal.providers.ms_graph.authentication_provider import CustomAzureIdentityAuthenticationProvider

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


def build_app_only_graph_client(*, tenant_id: str, client_id: str, client_secret: str, base_url: str) -> GraphServiceClient:
    """Build an app-only GraphServiceClient for one Entra registration."""
    credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
    auth_provider = CustomAzureIdentityAuthenticationProvider(credentials=credential, scopes=GRAPH_SCOPE)
    adapter = GraphRequestAdapter(auth_provider=auth_provider)
    adapter.base_url = base_url
    return GraphServiceClient(request_adapter=adapter)
