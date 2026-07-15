"""Custom authentication provider for Microsoft Graph."""
from typing import Any

from azure.core.exceptions import ClientAuthenticationError
from kiota_abstractions.request_information import RequestInformation
from kiota_authentication_azure.azure_identity_authentication_provider import (
    AzureIdentityAuthenticationProvider,
)


class CustomAzureIdentityAuthenticationProvider(AzureIdentityAuthenticationProvider):
    """Azure identity auth provider that raises RuntimeError on failure."""

    async def authenticate_request(
        self,
        request: RequestInformation,
        additional_authentication_context: dict[str, Any] | None = None,
    ) -> None:
        if additional_authentication_context is None:
            additional_authentication_context = {}
        try:
            await super().authenticate_request(request, additional_authentication_context)
        except ClientAuthenticationError as exc:
            raise RuntimeError(f"Failed to acquire Graph access token: {exc.message}") from exc
