"""
MSGraphClientBase — app-only Microsoft Graph beta client.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.request_option import RequestOption
from msgraph_beta import GraphServiceClient
from msgraph_beta.generated.models.o_data_errors.o_data_error import ODataError
from msgraph_beta.graph_request_adapter import GraphRequestAdapter

from portal.config import settings
from portal.providers.ms_graph.authentication_provider import (
    CustomAzureIdentityAuthenticationProvider,
)

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_BASE_URL = "https://graph.microsoft.com/beta"


@dataclass
class MSGraphConfiguration:
    """Per-request Graph configuration (fluent builder state)."""

    as_application: bool = True
    headers: Optional[Dict[str, str]] = None
    options: Optional[List[RequestOption]] = None
    query_parameters: Optional[Any] = None


class MSGraphClientBase:
    """App-only GraphServiceClient wrapper."""

    def __init__(self) -> None:
        self.configuration = MSGraphConfiguration()
        self._tenant_id = settings.AZURE_TENANT_ID
        self._client_id = settings.AZURE_APP_CLIENT_ID
        self._client_secret = settings.AZURE_APP_CLIENT_SECRET

    def is_configured(self) -> bool:
        return bool(self._tenant_id and self._client_id and self._client_secret)

    @property
    def base_url(self) -> str:
        return f"{GRAPH_BASE_URL}/"

    @property
    def _credential(self) -> ClientSecretCredential:
        if not self.is_configured():
            raise RuntimeError("Microsoft Graph is not configured")
        return ClientSecretCredential(
            tenant_id=str(self._tenant_id),
            client_id=str(self._client_id),
            client_secret=str(self._client_secret),
        )

    @property
    def _auth_provider(self) -> CustomAzureIdentityAuthenticationProvider:
        return CustomAzureIdentityAuthenticationProvider(
            credentials=self._credential,
            scopes=GRAPH_SCOPE,
        )

    @property
    def _request_adapter(self) -> GraphRequestAdapter:
        adapter = GraphRequestAdapter(auth_provider=self._auth_provider)
        adapter.base_url = self.base_url
        return adapter

    @property
    def client(self) -> GraphServiceClient:
        return GraphServiceClient(request_adapter=self._request_adapter)

    @property
    def default_error(self) -> Dict[str, Type[ODataError]]:
        return {
            "4XX": ODataError,
            "5XX": ODataError,
        }

    def as_application(self, as_application: bool = True) -> "MSGraphClientBase":
        self.configuration.as_application = as_application
        return self

    def add_header(self, key: Optional[str] = None, value: Any = None) -> "MSGraphClientBase":
        if not key or value is None:
            return self
        if not self.configuration.headers:
            self.configuration.headers = {}
        self.configuration.headers[key] = value
        return self

    def add_headers(self, headers: Optional[Dict[str, str]] = None) -> "MSGraphClientBase":
        if not headers:
            return self
        if not self.configuration.headers:
            self.configuration.headers = {}
        self.configuration.headers.update(headers)
        return self

    def add_option(self, option: Optional[RequestOption] = None) -> "MSGraphClientBase":
        if not option:
            return self
        if not self.configuration.options:
            self.configuration.options = []
        self.configuration.options.append(option)
        return self

    def add_options(self, options: Optional[List[RequestOption]] = None) -> "MSGraphClientBase":
        if not options:
            return self
        if not self.configuration.options:
            self.configuration.options = []
        self.configuration.options.extend(options)
        return self

    def add_query_parameter(self, query_parameter: Any = None) -> "MSGraphClientBase":
        if not query_parameter:
            return self
        assert hasattr(query_parameter, "get_query_parameter"), (
            "object must have get_query_parameter method"
        )
        self.configuration.query_parameters = query_parameter
        return self

    def _apply_headers(self, request_configuration: Any) -> None:
        if not self.configuration.headers:
            return
        for key, value in self.configuration.headers.items():
            request_configuration.headers.add(key, value)
